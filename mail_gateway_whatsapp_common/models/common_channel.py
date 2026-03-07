import base64
import re
import requests
from odoo import Command
from psycopg2 import IntegrityError

class MailGatewayWhatsappCommonChannel:
    def _channel_token_rank(self, token):
        token = str(token or "")
        if token.endswith("@g.us"):
            return 4
        if token.endswith("@s.whatsapp.net") or token.endswith("@c.us"):
            return 3
        if token.endswith("@lid"):
            return 2
        if "@" in token:
            return 1
        return 0

    def _expand_channel_token_aliases(self, token):
        token = (token or "").strip()
        if not token:
            return []
        result = [token]
        local = token.split("@", 1)[0] if "@" in token else token
        digits = re.sub(r"\D", "", local)
        if not digits:
            return result
        if token.endswith("@s.whatsapp.net"):
            result.extend([f"{digits}@c.us", digits])
        elif token.endswith("@c.us"):
            result.extend([f"{digits}@s.whatsapp.net", digits])
        elif "@" not in token:
            result.extend([f"{digits}@s.whatsapp.net", f"{digits}@c.us"])
        return result

    def _channel_token_candidates(self, dto):
        raw_candidates = [
            (dto.chat_id or "").strip(),
            (dto.contact_jid or "").strip(),
            (dto.sender_jid or "").strip(),
            (dto.sender_jid_alt or "").strip(),
            (dto.sender_participant_jid or "").strip(),
        ]
        raw_candidates = [token for token in raw_candidates if token]
        if not raw_candidates:
            return []

        if dto.is_group:
            group_candidates = [
                token for token in raw_candidates if token.endswith("@g.us")
            ]
            if group_candidates:
                raw_candidates = group_candidates
        else:
            raw_candidates = [
                token for token in raw_candidates if not token.endswith("@g.us")
            ]
            has_phone_jid = any(
                token.endswith("@s.whatsapp.net") or token.endswith("@c.us")
                for token in raw_candidates
            )
            if has_phone_jid:
                raw_candidates = [
                    token for token in raw_candidates if not token.endswith("@lid")
                ]

        ranked = sorted(
            raw_candidates,
            key=lambda token: self._channel_token_rank(token),
            reverse=True,
        )
        expanded = []
        for token in ranked:
            expanded.extend(self._expand_channel_token_aliases(token))

        seen = set()
        result = []
        for token in expanded:
            token = (token or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            result.append(token)
        return result

    def _find_channel_by_tokens(self, gateway, tokens):
        if not gateway:
            return False
        channel_model = self.env["discuss.channel"]
        for token in tokens or []:
            channel_id = gateway._get_channel_id(token)
            if channel_id:
                return channel_model.browse(channel_id)
        return False

    def _get_channel_by_chat_id(self, gateway, chat_id):
        if not gateway or not chat_id:
            return False
        channel_id = gateway._get_channel_id(chat_id)
        if not channel_id:
            return False
        return self.env["discuss.channel"].browse(channel_id)


    def _handle_chat_update(self, gateway, dto, channel, author=None):
        """Update channel metadata such as name and unread count."""
        chat_tokens = self._channel_token_candidates(dto)
        if not chat_tokens:
            return {"status": "ignored", "reason": "missing_chat_id"}
        channel = self._find_channel_by_tokens(gateway, chat_tokens)
        if not channel:
            return {"status": "ignored", "reason": "channel_not_found"}
        chat_id = chat_tokens[0]
        update_vals = {}
        if dto.chat_name and self._should_update_channel_name(channel, dto, chat_id):
            update_vals["name"] = dto.chat_name.strip()
        if (
            dto.chat_unread_count is not None
            and "gateway_unread_count" in channel._fields
            and channel.gateway_unread_count != dto.chat_unread_count
        ):
            update_vals["gateway_unread_count"] = dto.chat_unread_count
        if update_vals:
            channel.sudo().write(update_vals)
        return {"status": "ok", "channel_id": channel.id}


    def _get_or_create_channel(self, gateway, dto, author):
        """Find or create the gateway channel for a chat_id."""
        chat_tokens = self._channel_token_candidates(dto)
        if not chat_tokens:
            return False
        channel = self._find_channel_by_tokens(gateway, chat_tokens)
        if channel:
            self._ensure_channel_members(channel, author=author)
            if gateway and hasattr(gateway, "_reopen_channel_if_needed"):
                reopened_by = (
                    gateway.webhook_user_id.partner_id
                    if gateway.webhook_user_id
                    else self.env.user.partner_id
                )
                channel = gateway._reopen_channel_if_needed(
                    channel, reopened_by=reopened_by
                )
            return channel
        chat_id = chat_tokens[0]
        channel_name = self._get_channel_name(dto, chat_id=chat_id)
        members = self._build_channel_members(gateway, author)
        channel_env = self.env["discuss.channel"].sudo()
        channel_env = channel_env.with_user(gateway.webhook_user_id or self.env.user)
        channel_env = channel_env.with_context(install_mode=True)
        try:
            channel = channel_env.create(
                {
                    "name": channel_name,
                    "channel_type": "gateway",
                    "gateway_id": gateway.id,
                    "gateway_channel_token": chat_id,
                    "channel_member_ids": members,
                    "company_id": gateway.company_id.id,
                    "description": (dto.chat_description or "").strip() or False,
                }
            )
        except IntegrityError:
            # Another transaction created the same gateway channel concurrently.
            self.env.cr.rollback()
            channel_id = gateway._get_channel_id(chat_id)
            if not channel_id:
                raise
            channel = self.env["discuss.channel"].browse(channel_id)
        self._ensure_channel_members(channel, author=author)
        channel._broadcast(channel.channel_member_ids.mapped("partner_id").ids)
        if gateway and hasattr(gateway, "_reopen_channel_if_needed"):
            reopened_by = (
                gateway.webhook_user_id.partner_id
                if gateway.webhook_user_id
                else self.env.user.partner_id
            )
            channel = gateway._reopen_channel_if_needed(
                channel, reopened_by=reopened_by
            )
        return channel


    def _channel_member_targets(self, author):
        partner_ids = set()
        guest_ids = set()
        if author and author._name == "res.partner":
            internal_users = author.user_ids.filtered(lambda user: user._is_internal())
            if not internal_users:
                partner_ids.add(author.id)
        elif author and author._name == "mail.guest":
            member_model = self.env["discuss.channel.member"]
            if "guest_id" in member_model._fields:
                guest_ids.add(author.id)
        return sorted(partner_ids), sorted(guest_ids)


    def _build_channel_members(self, gateway, author):
        """Add gateway members and the author to the channel."""
        partner_ids, guest_ids = self._channel_member_targets(author)
        members = [
            Command.create({"partner_id": partner_id, "unpin_dt": False})
            for partner_id in partner_ids
        ]
        members.extend(
            [
                Command.create({"guest_id": guest_id, "unpin_dt": False})
                for guest_id in guest_ids
            ]
        )
        return members


    def _ensure_channel_members(self, channel, gateway=None, author=None):
        if not channel:
            return
        partner_ids, guest_ids = self._channel_member_targets(author)
        if not partner_ids and not guest_ids:
            return
        existing_partner_ids = set(channel.channel_member_ids.mapped("partner_id").ids)
        existing_guest_ids = set(channel.channel_member_ids.mapped("guest_id").ids)
        missing_partners = [pid for pid in partner_ids if pid not in existing_partner_ids]
        missing_guests = [gid for gid in guest_ids if gid not in existing_guest_ids]
        if not missing_partners and not missing_guests:
            return
        channel.sudo().add_members(
            partner_ids=missing_partners,
            guest_ids=missing_guests,
            post_joined_message=False,
        )


    def _apply_channel_metadata(self, channel, dto):
        """Update group channel metadata when missing or clearly outdated."""
        chat_id = (dto.chat_id or "").strip()
        if not chat_id or not self._is_group_chat(chat_id):
            return
        update_vals = {}
        if dto.chat_name:
            if self._should_update_channel_name(channel, dto, chat_id):
                update_vals["name"] = dto.chat_name.strip()
        if dto.chat_description and not channel.description:
            update_vals["description"] = dto.chat_description.strip()
        if dto.chat_picture_url and not channel.image_128:
            image_base64 = self._fetch_image_base64(dto.chat_picture_url)
            if image_base64:
                update_vals["image_128"] = image_base64
        if update_vals:
            channel.sudo().write(update_vals)


    def _should_update_channel_name(self, channel, dto, chat_id):
        """Heuristic to replace fallback names with a better one."""
        current_name = (channel.name or "").strip()
        if not current_name:
            return True
        new_name = (dto.chat_name or "").strip()
        if not new_name or current_name == new_name:
            return False
        fallback_group = self._format_group_name(chat_id)
        fallback_chat = self._format_chat_id(chat_id)
        sender_name = (dto.sender_name or "").strip()
        if current_name in {fallback_group, fallback_chat}:
            return True
        if sender_name and current_name == sender_name:
            return True
        return False


    def _get_channel_name(self, dto, chat_id=None):
        """Compute a human-friendly channel name."""
        chat_id = (chat_id or dto.chat_id or "").strip()
        if not chat_id:
            return (dto.sender_name or "").strip()
        if self._is_group_chat(chat_id):
            return (dto.chat_name or "").strip() or self._format_group_name(chat_id)
        if dto.from_me:
            if dto.contact_name:
                return dto.contact_name.strip()
            return self._format_chat_id(chat_id)
        return (dto.sender_name or "").strip() or self._format_chat_id(chat_id)


    def _fetch_image_base64(self, url):
        """Download and convert images to base64 for channel avatars."""
        if not url:
            return False
        max_bytes = 2 * 1024 * 1024  # 2 MB hard limit for avatars
        allowed_mime = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        try:
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code != 200:
                return False
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type and content_type not in allowed_mime:
                return False
            length = response.headers.get("Content-Length")
            if length:
                try:
                    if int(length) > max_bytes:
                        return False
                except ValueError:
                    pass
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    return False
                chunks.append(chunk)
            if not chunks:
                return False
            return base64.b64encode(b"".join(chunks)).decode("ascii")
        except Exception as exc:
            self._logger.warning("Failed to fetch group image: %s", exc)
            return False
