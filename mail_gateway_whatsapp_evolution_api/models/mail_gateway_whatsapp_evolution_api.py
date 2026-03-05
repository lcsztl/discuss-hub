# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import logging
import mimetypes
from urllib.parse import quote

import requests

from odoo import _, models
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.mail_gateway_whatsapp_common.models.normalized_payload import (
    NormalizedPayload,
)

_logger = logging.getLogger(__name__)


class MailGatewayWhatsappEvolutionApi(models.AbstractModel):
    _name = "mail.gateway.whatsapp_evolution_api"
    _inherit = ["mail.gateway.abstract", "mail.gateway.whatsapp_evolution_api.mixin"]
    _description = "WhatsApp Evolution API Gateway"
    _uses_gateway_common = True

    # -------------------------------------------------------------------------
    # Webhook / verification
    # -------------------------------------------------------------------------
    def _verify_update(self, bot_data, kwargs):
        webhook_secret = bot_data.get("webhook_secret")
        if not webhook_secret:
            return True
        header_key = request.httprequest.headers.get("webhook_key") or request.httprequest.headers.get(
            "Webhook-Key"
        )
        return header_key == webhook_secret

    def _set_webhook(self, gateway):
        if not gateway.evolution_api_url or not gateway.token:
            raise UserError(_("Evolution API URL and token are required."))
        events = gateway._get_webhook_events()
        payload = {
            "webhook": {
                "enabled": True,
                "url": gateway._get_webhook_url(),
                "byEvents": bool(gateway.evolution_webhook_by_events),
                "events": events,
                "base64": bool(gateway.evolution_base64_webhook),
            }
        }
        if gateway.webhook_secret:
            payload["webhook"]["headers"] = {"webhook_key": gateway.webhook_secret}
        self._send_api_request(gateway, "POST", f"/webhook/set/{self._instance_name(gateway)}", payload)
        gateway.integrated_webhook_state = "integrated"

    def _remove_webhook(self, gateway):
        if not gateway.evolution_api_url or not gateway.token:
            gateway.integrated_webhook_state = False
            return
        payload = {
            "webhook": {
                "enabled": False,
                "url": gateway._get_webhook_url(),
                "byEvents": bool(gateway.evolution_webhook_by_events),
                "events": gateway._get_webhook_events(),
                "base64": bool(gateway.evolution_base64_webhook),
            }
        }
        if gateway.webhook_secret:
            payload["webhook"]["headers"] = {"webhook_key": gateway.webhook_secret}
        try:
            self._send_api_request(
                gateway,
                "POST",
                f"/webhook/set/{self._instance_name(gateway)}",
                payload,
            )
        except Exception as exc:
            _logger.warning("Failed to disable webhook: %s", exc)
        gateway.integrated_webhook_state = False

    # -------------------------------------------------------------------------
    # Incoming
    # -------------------------------------------------------------------------
    def _receive_update(self, gateway, update):
        canonical_event = self._normalize_event(update)
        if not canonical_event:
            return {"status": "ignored", "reason": "event_not_supported"}
        data = update.get("data", {}) or {}
        if isinstance(data, list):
            results = []
            for item in data:
                if not item:
                    continue
                item_update = dict(update)
                item_update["data"] = item
                results.append(
                    self._receive_update_item(gateway, item_update, canonical_event)
                )
            if not results:
                return {"status": "ignored", "reason": "missing_data"}
            status = "ok" if any(
                result.get("status") in ("ok", "duplicate") for result in results
            ) else "ignored"
            return {"status": status, "results": results}
        return self._receive_update_item(gateway, update, canonical_event)

    def _receive_update_item(self, gateway, update, canonical_event=None):
        canonical_event = canonical_event or self._normalize_event(update)
        if not canonical_event:
            return {"status": "ignored", "reason": "event_not_supported"}
        data = update.get("data", {}) or {}
        if not data:
            return {"status": "ignored", "reason": "missing_data"}
        if canonical_event == "message.upsert":
            message = data.get("message", {}) or {}
            if not message:
                return {"status": "ignored", "reason": "missing_message"}
        dto = self._build_dto_from_evolution(
            update, gateway, None, canonical_event=canonical_event
        )
        if not dto:
            return {"status": "ignored", "reason": "normalization_failed"}

        common = self.env["mail.gateway.whatsapp.common"]
        return common._process_normalized(gateway, dto, None, author=None)

    def _build_dto_from_evolution(self, update, gateway, channel, canonical_event=None):
        data = update.get("data", {}) or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        message = self._unwrap_message(data.get("message", {}) or {})
        key_data = data.get("key", {}) or {}
        body, attachments, text_is_html = self._prepare_message(message, data, gateway)
        dto_event = canonical_event or self._normalize_event(update)
        if not dto_event:
            return False
        if dto_event == "contact.update":
            return self._build_contact_dto(update, gateway, data)
        if dto_event == "chat.update":
            return self._build_chat_dto(update, gateway, data)
        reaction, reaction_target_id = self._extract_reaction_data(data, message)
        message_id = self._get_message_id(data, key_data)
        chat_id = self._get_chat_token(data)
        is_group = self._is_group_chat(chat_id)
        sender_name = data.get("pushName") or data.get("name")
        chat_name, chat_description, chat_picture_url = self._get_group_metadata(
            update, gateway, chat_id, sender_name, dto_event
        )
        sender_jid, sender_jid_alt, sender_participant_jid = self._extract_sender_jids(key_data)
        return NormalizedPayload(
            provider="evolution",
            instance=self._instance_name(gateway),
            event=dto_event,
            message_id=message_id,
            chat_id=chat_id,
            chat_name=chat_name,
            chat_description=chat_description,
            chat_picture_url=chat_picture_url,
            is_group=is_group,
            from_me=bool(key_data.get("fromMe")),
            sender_jid=sender_jid,
            sender_jid_alt=sender_jid_alt,
            sender_participant_jid=sender_participant_jid,
            sender_name=sender_name,
            timestamp=message.get("messageTimestamp") or data.get("timestamp"),
            message_type=message.get("messageType")
            or data.get("messageType")
            or message.get("type"),
            text=body,
            text_is_html=text_is_html,
            caption=message.get("caption"),
            attachments=attachments,
            quote_id=(data.get("quotedMessage") or {}).get("stanzaId") or data.get("quotedStanzaID"),
            quote_text=(data.get("quotedMessage") or {}).get("text"),
            reaction=reaction,
            reaction_target_id=reaction_target_id,
            status=data.get("status") or data.get("status_raw"),
            status_raw=data.get("status_raw") or data.get("status"),
            raw=update,
        )

    def _build_contact_dto(self, update, gateway, data):
        contact_jid = self._get_chat_token(data) or data.get("remoteJid")
        contact_name = data.get("pushName")
        contact_pic = data.get("profilePicUrl")
        return NormalizedPayload(
            provider="evolution",
            instance=self._instance_name(gateway),
            event="contact.update",
            chat_id=contact_jid,
            contact_jid=contact_jid,
            contact_name=contact_name,
            contact_profile_pic_url=contact_pic,
            sender_name=contact_name,
            is_group=self._is_group_chat(contact_jid),
            raw=update,
        )

    def _build_chat_dto(self, update, gateway, data):
        chat_id = self._get_chat_token(data) or data.get("remoteJid")
        return NormalizedPayload(
            provider="evolution",
            instance=self._instance_name(gateway),
            event="chat.update",
            chat_id=chat_id,
            chat_name=data.get("name"),
            chat_unread_count=data.get("unreadMessages"),
            is_group=self._is_group_chat(chat_id),
            raw=update,
        )

    def _prepare_message(self, message, data, gateway):
        body = ""
        attachments = []
        text_is_html = False
        if message.get("conversation"):
            body = message.get("conversation")
        elif message.get("extendedTextMessage"):
            body = message.get("extendedTextMessage", {}).get("text", "")
        for key in [
            "imageMessage",
            "videoMessage",
            "audioMessage",
            "documentMessage",
            "stickerMessage",
        ]:
            if not message.get(key):
                continue
            caption = message.get(key, {}).get("caption", "")
            if caption:
                body = caption
            payload_base64 = message.get(key, {}).get("base64") or message.get("base64")
            filename = None
            mimetype = message.get(key, {}).get("mimetype")
            if not payload_base64:
                payload_base64, mimetype, filename = self._fetch_media_base64_from_api(
                    gateway, data, message
                )
            decoded = self._decode_base64_payload(payload_base64)
            if decoded:
                filename = filename or self._get_attachment_name(message, key, data)
                filename = self._normalize_media_filename(filename, mimetype, key)
                attachments.append(
                    {
                        "name": filename,
                        "datas": decoded,
                        "mimetype": mimetype or "",
                    }
                )
            elif payload_base64 is False:
                _logger.warning(
                    "Missing media payload for %s (%s) on %s",
                    data.get("key", {}).get("id"),
                    key,
                    data.get("key", {}).get("remoteJid"),
                )
        if message.get("locationMessage"):
            location = message.get("locationMessage", {})
            latitude = location.get("degreesLatitude")
            longitude = location.get("degreesLongitude")
            if latitude and longitude:
                body = (
                    f'<a target="_blank" href="https://www.google.com/maps/'
                    f"search/?api=1&query={latitude},{longitude}\">Location</a>"
                )
                text_is_html = True
        return body, attachments, text_is_html

    def _fetch_media_base64_from_api(self, gateway, data, message):
        if not gateway or not data or not message:
            return False, None, None
        key_data = data.get("key") or {}
        if not key_data:
            return False, None, None
        endpoint = f"/chat/getBase64FromMediaMessage/{self._instance_name(gateway)}"
        payload = {"message": {"key": key_data, "message": message}}
        try:
            response = self._send_api_request(gateway, "POST", endpoint, payload=payload)
        except UserError as exc:
            _logger.warning("Failed to fetch media base64: %s", exc)
            return False, None, None
        if not response or not isinstance(response, dict):
            return False, None, None
        return (
            response.get("base64"),
            response.get("mimetype"),
            response.get("fileName") or response.get("filename"),
        )

    def _unwrap_message(self, message):
        current = message or {}
        for wrapper in (
            "ephemeralMessage",
            "viewOnceMessage",
            "viewOnceMessageV2",
            "viewOnceMessageV2Extension",
        ):
            nested = current.get(wrapper)
            if isinstance(nested, dict) and nested.get("message"):
                current = nested.get("message") or {}
        return current

    def _get_group_metadata(self, update, gateway, chat_id, sender_name, event):
        if not self._is_group_chat(chat_id):
            return None, None, None
        payload_name, payload_desc, payload_picture = (
            self._extract_group_metadata_from_payload(update)
        )
        if payload_name or payload_desc or payload_picture:
            return payload_name, payload_desc, payload_picture
        if event != "message.upsert":
            return None, None, None
        if not self._should_fetch_group_info(gateway, chat_id, sender_name):
            return None, None, None
        info = self._fetch_group_info(gateway, chat_id)
        if not info:
            return None, None, None
        return (
            info.get("subject") or info.get("name"),
            info.get("desc") or info.get("description"),
            info.get("pictureUrl") or info.get("picture_url"),
        )

    def _fetch_contact_metadata(self, gateway, dto):
        chat_id = (dto.contact_jid or dto.chat_id or "").strip()
        if not chat_id:
            return False
        instance = self._instance_name(gateway)
        endpoint = f"/chat/findContacts/{instance}"
        payload = {"where": {"remoteJid": chat_id}}
        try:
            response = self._send_api_request(gateway, "POST", endpoint, payload=payload)
        except Exception as exc:
            _logger.warning("Failed to fetch contact info: %s", exc)
            return False
        contact = self._select_contact_from_response(response, chat_id)
        if not contact:
            return False
        contact_name = (contact.get("pushName") or contact.get("name") or "").strip()
        contact_pic = contact.get("profilePicUrl") or contact.get("pictureUrl")
        return {
            "contact_name": contact_name,
            "contact_profile_pic_url": contact_pic,
        }

    @staticmethod
    def _select_contact_from_response(response, chat_id):
        contacts = []
        if isinstance(response, dict):
            for key in ("data", "contacts", "results"):
                data = response.get(key)
                if isinstance(data, list):
                    contacts = data
                    break
        elif isinstance(response, list):
            contacts = response
        if not contacts:
            return False
        for contact in contacts:
            if isinstance(contact, dict) and contact.get("remoteJid") == chat_id:
                return contact
        return contacts[0] if contacts else False

    def _extract_group_metadata_from_payload(self, update):
        data = update.get("data", {}) or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            return None, None, None
        return (
            data.get("subject") or data.get("name"),
            data.get("desc") or data.get("description"),
            data.get("pictureUrl") or data.get("profilePicUrl"),
        )

    def _should_fetch_group_info(self, gateway, chat_id, sender_name):
        if not gateway or not chat_id:
            return True
        channel_id = gateway._get_channel_id(chat_id)
        if not channel_id:
            return True
        channel = self.env["discuss.channel"].browse(channel_id)
        if not channel:
            return True
        fallback_group = self.env["mail.gateway.whatsapp.common"]._format_group_name(chat_id)
        fallback_chat = self.env["mail.gateway.whatsapp.common"]._format_chat_id(chat_id)
        current_name = (channel.name or "").strip()
        sender_name = (sender_name or "").strip()
        if not current_name or current_name in {fallback_group, fallback_chat}:
            return True
        if sender_name and current_name == sender_name:
            return True
        if not channel.description or not channel.image_128:
            return True
        return False

    def _fetch_group_info(self, gateway, chat_id):
        if not gateway or not chat_id:
            return False
        instance = self._instance_name(gateway)
        endpoint = f"/group/findGroupInfos/{instance}?groupJid={quote(chat_id)}"
        try:
            return self._send_api_request(gateway, "GET", endpoint)
        except Exception as exc:
            _logger.warning("Failed to fetch group info: %s", exc)
            return False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _normalize_event(self, update):
        event = (update.get("event") or "").lower()
        normalized_event = event.replace("_", ".")
        if normalized_event in {
            "message.upsert",
            "message.status",
            "message.delete",
            "reaction.upsert",
            "reaction.delete",
        }:
            return normalized_event
        if normalized_event in {"contacts.update", "contacts.upsert", "contact.update"}:
            return "contact.update"
        if normalized_event in {"chats.update", "chats.upsert", "chat.update"}:
            return "chat.update"

        data = update.get("data", {}) or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        message = data.get("message", {}) or {}
        reaction, reaction_target_id = self._extract_reaction_data(data, message)

        if normalized_event == "messages.upsert":
            if reaction_target_id:
                return "reaction.delete" if not reaction else "reaction.upsert"
            return "message.upsert"
        if normalized_event == "send.message":
            return "message.upsert"
        if normalized_event == "messages.update":
            return "message.status"
        if normalized_event == "messages.delete":
            return "message.delete"
        return None

    @staticmethod
    def _is_group_chat(chat_id):
        return str(chat_id or "").endswith("@g.us")

    def _extract_reaction_data(self, data, message):
        reaction = None
        reaction_target_id = None
        reaction_message = message.get("reactionMessage") if isinstance(message, dict) else None
        if isinstance(reaction_message, dict):
            reaction = reaction_message.get("text")
            if isinstance(reaction, str):
                reaction = reaction.strip()
            reaction_key = reaction_message.get("key") or {}
            reaction_target_id = reaction_key.get("id")
            return reaction, reaction_target_id

        if "reaction" in data:
            reaction = data.get("reaction")
            if isinstance(reaction, str):
                reaction = reaction.strip()
            reaction_target_id = data.get("reactionMessageId") or data.get("messageId")
        return reaction, reaction_target_id

    @staticmethod
    def _get_message_id(data, key_data):
        message_id = key_data.get("id")
        if message_id:
            return message_id
        message_id = data.get("keyId") or data.get("id") or data.get("messageId")
        if isinstance(message_id, list):
            message_id = message_id[0] if message_id else None
        return message_id

    def _decode_base64_payload(self, payload):
        if not payload:
            return False
        if isinstance(payload, bytes):
            return base64.b64encode(payload).decode()
        if isinstance(payload, str):
            return payload
        return False

    def _get_attachment_name(self, message, key, data):
        if message.get("fileName"):
            return message.get("fileName")
        if message.get(key, {}).get("fileName"):
            return message.get(key, {}).get("fileName")
        return f"{key}.bin"

    @staticmethod
    def _normalize_media_filename(filename, mimetype, key):
        name = (filename or "").strip()
        if not name:
            name = key
        extension = mimetypes.guess_extension(mimetype or "")
        if extension:
            if name.endswith(".bin"):
                name = f"{name[:-4]}{extension}"
            elif "." not in name:
                name = f"{name}{extension}"
        return name

    def _get_chat_token(self, data):
        candidates = self._extract_jids(data)
        best = None
        best_rank = -1
        for candidate in candidates:
            rank = self._chat_jid_rank(candidate)
            if rank > best_rank:
                best = candidate
                best_rank = rank
        return best

    def _extract_jids(self, data):
        data = data or {}
        key_data = data.get("key", {}) or {}
        candidates = [
            key_data.get("remoteJid"),
            data.get("remoteJid"),
            key_data.get("remoteJidAlt"),
            data.get("remoteJidAlt"),
            key_data.get("participant"),
            data.get("participant"),
        ]
        seen = set()
        result = []
        for candidate in candidates:
            candidate = (candidate or "").strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            result.append(candidate)
        return result

    @staticmethod
    def _chat_jid_rank(value):
        value = str(value or "")
        if value.endswith("@g.us"):
            return 4
        if value.endswith("@s.whatsapp.net") or value.endswith("@c.us"):
            return 3
        if value.endswith("@lid"):
            return 2
        if "@" in value:
            return 1
        return 0

    @staticmethod
    def _extract_sender_jids(key_data):
        participant = key_data.get("participant")
        participant_alt = key_data.get("participantAlt")
        remote_jid = key_data.get("remoteJid")
        remote_jid_alt = key_data.get("remoteJidAlt")

        def _jid_rank(value):
            value = str(value or "")
            if value.endswith("@s.whatsapp.net") or value.endswith("@c.us"):
                return 3
            if value.endswith("@lid"):
                return 2
            if value.endswith("@g.us"):
                return 1
            return 0

        def _pick_best(candidates):
            best = None
            best_rank = -1
            for candidate in candidates:
                if not candidate:
                    continue
                rank = _jid_rank(candidate)
                if rank > best_rank:
                    best = candidate
                    best_rank = rank
            return best

        sender_jid = _pick_best([participant_alt, participant]) or _pick_best(
            [remote_jid_alt, remote_jid]
        )
        alt_candidates = [
            candidate
            for candidate in [participant_alt, participant, remote_jid_alt, remote_jid]
            if candidate and candidate != sender_jid
        ]
        sender_jid_alt = _pick_best(alt_candidates)
        return sender_jid, sender_jid_alt, participant

    # -------------------------------------------------------------------------
    # Outgoing
    # -------------------------------------------------------------------------
    def _get_headers(self, gateway):
        return {"Content-Type": "application/json", "apikey": gateway.token}

    def _instance_name(self, gateway):
        return gateway.evolution_instance or gateway.name

    def _send(
        self,
        gateway,
        record,
        auto_commit=False,
        raise_exception=False,
        parse_mode=False,
    ):
        common = self.env["mail.gateway.whatsapp.common"]
        return common._send_outbound(
            gateway,
            record,
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            parse_mode=parse_mode,
            provider=self,
        )

    def _send_outbound_text(self, gateway, dto, body):
        self._ensure_gateway_ready(gateway)
        instance = self._instance_name(gateway)
        payload = {"number": dto.chat_id, "text": (body or "").strip()}
        response = requests.post(
            self._join_url(
                gateway.evolution_api_url,
                f"/message/sendText/{instance}",
            ),
            json=payload,
            headers=self._get_headers(gateway),
            timeout=20,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def _send_outbound_attachment(self, gateway, dto, attachment):
        self._ensure_gateway_ready(gateway)
        media = attachment.get("datas")
        if isinstance(media, bytes):
            media = media.decode("utf-8")
        if not media:
            return False

        instance = self._instance_name(gateway)
        payload = {
            "number": dto.chat_id,
            "mediatype": self._guess_media_type(attachment.get("mimetype")),
            "mimetype": attachment.get("mimetype"),
            "media": media,
            "fileName": attachment.get("name") or "attachment",
        }
        response = requests.post(
            self._join_url(
                gateway.evolution_api_url,
                f"/message/sendMedia/{instance}",
            ),
            json=payload,
            headers=self._get_headers(gateway),
            timeout=30,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def _send_outbound(self, gateway, dto):
        # Kept for direct calls, though common orchestration is the canonical path.
        self._ensure_gateway_ready(gateway)
        text_message = False
        responses = []
        instance = self._instance_name(gateway)
        body = (dto.text or "").strip()
        if body:
            text_message = self._send_outbound_text(gateway, dto, body)
            if text_message:
                responses.append(text_message)
        for attachment in dto.attachments or []:
            if not isinstance(attachment, dict):
                continue
            attachment_payload = self._send_outbound_attachment(
                gateway, dto, attachment
            )
            if attachment_payload:
                responses.append(attachment_payload)

        message_for_tracking = text_message or (responses[-1] if responses else False)
        return {
            "message_id": self._extract_message_id_from_response(message_for_tracking),
            "instance": instance,
            "chat_id": dto.chat_id,
            "responses": responses,
        }

    def _send_reaction_outbound(
        self,
        gateway,
        message,
        reaction,
        action,
        chat_id=None,
        message_external_id=None,
        instance=None,
    ):
        self._ensure_gateway_ready(gateway)
        instance = instance or self._instance_name(gateway)
        chat_id = chat_id or message.gateway_chat_id
        message_external_id = message_external_id or message.gateway_message_external_id
        if not chat_id or not message_external_id:
            return {"status": "ignored", "reason": "missing_target"}
        key_payload = {
            "remoteJid": chat_id,
            "fromMe": bool(message.gateway_from_me),
            "id": message_external_id,
        }
        if chat_id.endswith("@g.us") and message.gateway_sender_jid:
            key_payload["participant"] = message.gateway_sender_jid
        payload = {
            "key": key_payload,
            "reaction": reaction if action == "add" else "",
        }
        response = self._send_api_request(
            gateway,
            "POST",
            f"/message/sendReaction/{instance}",
            payload,
        )
        return {
            "status": "sent",
            "instance": instance,
            "chat_id": chat_id,
            "message_id": message_external_id,
            "response": response,
        }

    def _ensure_gateway_ready(self, gateway):
        if not gateway.evolution_api_url or not gateway.token:
            raise UserError(_("Evolution API URL and token are required."))

    def _join_url(self, base_url, endpoint):
        return f"{(base_url or '').rstrip('/')}/{endpoint.lstrip('/')}"

    def _get_message_body(self, record):
        return record.mail_message_id.body

    def _extract_message_id_from_response(self, payload):
        if not payload:
            return False
        if isinstance(payload, dict):
            key_data = payload.get("key") or {}
            message_id = key_data.get("id")
            if message_id:
                return message_id
            message_id = payload.get("messageId") or payload.get("id")
            if isinstance(message_id, list):
                message_id = message_id[0] if message_id else None
            if message_id:
                return message_id
            message_data = payload.get("message") or {}
            if isinstance(message_data, dict):
                key_data = message_data.get("key") or {}
                message_id = key_data.get("id")
                if message_id:
                    return message_id
                message_id = message_data.get("messageId") or message_data.get("id")
                if isinstance(message_id, list):
                    message_id = message_id[0] if message_id else None
                if message_id:
                    return message_id
        return False

    def _guess_media_type(self, mimetype):
        if not mimetype:
            return "document"
        if mimetype.startswith("image/"):
            return "image"
        if mimetype.startswith("video/"):
            return "video"
        if mimetype.startswith("audio/"):
            return "audio"
        return "document"

    # -------------------------------------------------------------------------
    # API request (wrapper)
    # -------------------------------------------------------------------------
    def _send_api_request(self, gateway, method, endpoint, payload=None):
        log_record = self._devtools_log_webhook(
            gateway,
            direction="out",
            status="sending",
            endpoint=endpoint,
            payload=payload,
        )
        return self._evolution_api_request(
            gateway.evolution_api_url,
            gateway.token,
            method,
            endpoint,
            payload=payload,
            log_record=log_record,
        )

    def _devtools_log_webhook(
        self,
        gateway,
        direction,
        status,
        payload=None,
        event=None,
        endpoint=None,
    ):
        return False
