# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _mail_gateway_hook_author_from_post(self, kwargs):
        author_id = kwargs.get("author_id")
        if author_id:
            return self.env["res.partner"].browse(author_id)

        guest = self.env.context.get("guest")
        if hasattr(guest, "_name") and guest._name == "mail.guest":
            return guest
        if isinstance(guest, int):
            return self.env["mail.guest"].browse(guest)
        return False

    def _mail_gateway_hook_payload_from_post(self, kwargs):
        payload = self.env.context.get("mail_gateway_hook_payload")
        if payload:
            return payload
        return {
            "gateway_type": kwargs.get("gateway_type"),
            "message_type": kwargs.get("message_type"),
            "subtype_xmlid": kwargs.get("subtype_xmlid"),
        }

    @api.returns("mail.message", lambda value: value.id)
    def message_post(
        self, *, message_type="notification", gateway_type=False, **kwargs
    ):
        message = super().message_post(
            message_type=message_type,
            gateway_type=gateway_type,
            **kwargs,
        )
        if (
            not message
            or self.env.context.get("mail_gateway_skip_inbound_hooks")
            or not self.env.context.get("no_gateway_notification")
        ):
            return message

        for channel in self.filtered(lambda rec: rec.channel_type == "gateway" and rec.gateway_id):
            if message.model != channel._name or message.res_id != channel.id:
                continue
            if message.message_type == "notification":
                continue
            channel.gateway_id._dispatch_after_gateway_message_received(
                channel,
                message,
                author=channel._mail_gateway_hook_author_from_post(kwargs),
                payload=channel._mail_gateway_hook_payload_from_post(kwargs),
            )
        return message
