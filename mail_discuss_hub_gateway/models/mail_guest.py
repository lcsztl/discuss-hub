# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MailGuest(models.Model):
    _inherit = "mail.guest"

    tag_ids = fields.Many2many(
        "res.partner.category",
        "mail_guest_res_partner_category_rel",
        "guest_id",
        "category_id",
        string="Tags",
    )

    def _discuss_hub_guest_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "gateway_phone": self.gateway_phone,
            "tags": [{"id": tag.id, "name": tag.name} for tag in self.tag_ids],
        }

    def _get_discuss_hub_related_partner(self):
        self.ensure_one()
        partner_model = self.env["res.partner"]
        if self.gateway_phone and "gateway_phone" in partner_model._fields:
            partner = partner_model.search(
                [("gateway_phone", "=", self.gateway_phone)], limit=1
            )
            if partner:
                return partner
        if self.gateway_id and self.gateway_token:
            partner = partner_model.search(
                [
                    ("gateway_channel_ids.gateway_id", "=", self.gateway_id.id),
                    ("gateway_channel_ids.gateway_token", "=", self.gateway_token),
                ],
                limit=1,
            )
            if partner:
                return partner
        return False

    def action_get_discuss_hub_contact_panel_data(self):
        self.ensure_one()
        partner = self._get_discuss_hub_related_partner()
        return {
            "guest": self._discuss_hub_guest_payload(),
            "partner": partner._discuss_hub_partner_payload() if partner else False,
        }

    def action_create_partner(self):
        self.ensure_one()
        wizard = self.env["mail.guest.manage"].create({"guest_id": self.id})
        return wizard.create_partner()
