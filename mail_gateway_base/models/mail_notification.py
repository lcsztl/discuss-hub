# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class MailNotification(models.Model):
    _inherit = "mail.notification"

    def _dispatch_gateway_outbound_success(self, result=None):
        if self.env.context.get("mail_gateway_skip_outbound_hooks"):
            return False

        for record in self.filtered(
            lambda rec: rec.notification_type == "gateway"
            and rec.notification_status == "sent"
            and rec.gateway_channel_id
            and rec.gateway_channel_id.gateway_id
        ):
            record.gateway_channel_id.gateway_id._dispatch_after_gateway_outbound_sent(
                record,
                message=record.mail_message_id,
                channel=record.gateway_channel_id,
                result=result,
            )
        return True

    def send_gateway(self, auto_commit=False, raise_exception=False, parse_mode="HTML"):
        status_before = {record.id: record.notification_status for record in self}
        result = super().send_gateway(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            parse_mode=parse_mode,
        )
        success_records = self.filtered(
            lambda rec: rec.notification_type == "gateway"
            and rec.notification_status == "sent"
            and status_before.get(rec.id) != "sent"
        )
        success_records._dispatch_gateway_outbound_success()
        return result
