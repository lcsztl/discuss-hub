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

    def _get_channel_vals(self, gateway, token, update):
        author = self._get_author(gateway, update)
        members = []
        auto_users = (
            gateway._get_auto_assign_users()
            if hasattr(gateway, "_get_auto_assign_users")
            else gateway.member_ids
        )
        for user in auto_users:
            if user.partner_id:
                members.append(
                    Command.create(
                        {
                            "partner_id": user.partner_id.id,
                            "unpin_dt": False,
                        }
                    )
                )
        webhook_partner = gateway.webhook_user_id.partner_id if gateway.webhook_user_id else False
        if author and author._name == "res.partner":
            if not webhook_partner or author.id != webhook_partner.id:
                members.append(
                    Command.create(
                        {
                            "partner_id": author.id,
                            "unpin_dt": False,
                        }
                    )
                )
        elif author and author._name == "mail.guest":
            member_model = self.env["discuss.channel.member"]
            if "guest_id" in member_model._fields:
                members.append(Command.create({"guest_id": author.id, "unpin_dt": False}))
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
