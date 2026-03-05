# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, tools


class MailGateway(models.Model):
    _inherit = "mail.gateway"

    @api.model
    @tools.ormcache("state", "gateway_type")
    def _get_gateway_map(self, state="integrated", gateway_type=False):
        result = {}
        for record in self.sudo().search(
            [
                ("integrated_webhook_state", "=", state),
                ("gateway_type", "=", gateway_type),
            ]
        ):
            result[record.webhook_key] = record._get_gateway_data()
        return result
