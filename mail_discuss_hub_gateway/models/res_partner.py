# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _discuss_hub_partner_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.display_name,
            "phone": self.phone,
            "mobile": self.mobile,
            "email": self.email,
            "gateway_phone": self.gateway_phone,
            "categories": [
                {"id": category.id, "name": category.name}
                for category in self.category_id
            ],
        }

    def _get_discuss_hub_related_guest(self):
        self.ensure_one()
        guest_model = self.env["mail.guest"]
        token = self.gateway_phone
        if not token and self.gateway_channel_ids:
            token = next(
                (
                    channel.gateway_token
                    for channel in self.gateway_channel_ids
                    if channel.gateway_token
                ),
                False,
            )
        if token:
            return guest_model.search([("gateway_phone", "=", token)], limit=1)
        return False

    def action_get_discuss_hub_contact_panel_data(self):
        self.ensure_one()
        guest = self._get_discuss_hub_related_guest()
        return {
            "partner": self._discuss_hub_partner_payload(),
            "guest": guest._discuss_hub_guest_payload() if guest else False,
        }
