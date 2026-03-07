# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, models


class MailGatewayAbstract(models.AbstractModel):
    _inherit = "mail.gateway.abstract"

    @staticmethod
    def _extract_channel_name(update):
        if not isinstance(update, dict):
            return False

        for key in ("name", "subject", "pushName"):
            value = (update.get(key) or "").strip()
            if value:
                return value

        data = update.get("data")
        if isinstance(data, list):
            data = data[0] if data else {}
        if isinstance(data, dict):
            for key in ("name", "subject", "pushName"):
                value = (data.get(key) or "").strip()
                if value:
                    return value
        return False

    @staticmethod
    def _fallback_channel_name(token):
        chat_token = str(token or "").strip()
        if not chat_token:
            return "Gateway"
        base = chat_token.split("@", 1)[0] if "@" in chat_token else chat_token
        if chat_token.endswith("@g.us"):
            return f"Grupo {base}"
        return base or chat_token

    def _get_channel(self, gateway, token, update, force_create=False):
        channel = super()._get_channel(gateway, token, update, force_create=force_create)
        author = self._get_author(gateway, update)
        self._ensure_gateway_channel_members(channel, gateway, author=author)
        if (
            channel
            and gateway
            and hasattr(gateway, "_reopen_channel_if_needed")
            and hasattr(gateway, "webhook_user_id")
        ):
            reopened_by = (
                gateway.webhook_user_id.partner_id
                if gateway.webhook_user_id
                else self.env.user.partner_id
            )
            channel = gateway._reopen_channel_if_needed(
                channel, reopened_by=reopened_by
            )
        return channel

    def _gateway_channel_member_targets(self, gateway, author):
        partner_ids = set()
        guest_ids = set()
        auto_users = (
            gateway._get_auto_assign_users()
            if hasattr(gateway, "_get_auto_assign_users")
            else gateway.member_ids
        )
        for user in auto_users:
            if user.partner_id:
                partner_ids.add(user.partner_id.id)

        webhook_partner = (
            gateway.webhook_user_id.partner_id
            if gateway and gateway.webhook_user_id
            else False
        )
        if author and author._name == "res.partner":
            partner_ids.add(author.id)
        elif author and author._name == "mail.guest":
            member_model = self.env["discuss.channel.member"]
            if "guest_id" in member_model._fields:
                guest_ids.add(author.id)

        # Keep at least one internal member when no auto users are configured.
        if not partner_ids and webhook_partner:
            partner_ids.add(webhook_partner.id)

        return sorted(partner_ids), sorted(guest_ids)

    def _ensure_gateway_channel_members(self, channel, gateway, author=None):
        if not channel or not gateway:
            return
        partner_ids, guest_ids = self._gateway_channel_member_targets(gateway, author)
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

    def _get_channel_vals(self, gateway, token, update):
        author = self._get_author(gateway, update)
        partner_ids, guest_ids = self._gateway_channel_member_targets(gateway, author)
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
        vals = {
            "gateway_channel_token": token,
            "gateway_id": gateway.id,
            "channel_type": "gateway",
            "channel_member_ids": members,
            "company_id": gateway.company_id.id,
        }
        vals["name"] = self._extract_channel_name(update) or self._fallback_channel_name(
            token
        )
        if "group_public_id" in self.env["discuss.channel"]._fields:
            group = gateway._ensure_access_group()
            vals["group_public_id"] = group.id if group else False
        return vals
