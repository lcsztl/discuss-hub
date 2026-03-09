# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailNotification(models.Model):
    _inherit = "mail.notification"

    def _to_store(self, store: Store, /):
        result = super()._to_store(store)
        for record in self:
            store.add(record, {"is_read": record.is_read})
        return result

    def send_gateway(self, auto_commit=False, raise_exception=False, parse_mode="HTML"):
        common = self.env["mail.gateway.whatsapp.common"]

        def _use_common(record):
            channel = record.gateway_channel_id
            gateway = channel.gateway_id if channel else False
            return common._get_outbound_provider(gateway) is not False

        common_records = self.filtered(_use_common)
        if common_records:
            for record in common_records:
                gateway = record.gateway_channel_id.gateway_id
                result = common._send_outbound(
                    gateway,
                    record,
                    auto_commit=auto_commit,
                    raise_exception=raise_exception,
                    parse_mode=parse_mode,
                )
                record._dispatch_gateway_outbound_success(result=result)
        remaining = self - common_records
        if remaining:
            return super(MailNotification, remaining).send_gateway(
                auto_commit=auto_commit,
                raise_exception=raise_exception,
                parse_mode=parse_mode,
            )
        return True
