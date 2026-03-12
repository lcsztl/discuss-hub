# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MailGatewayLLMAccessBinding(models.Model):
    _name = "mail.gateway.llm.access.binding"
    _description = "Mail Gateway LLM Access Binding"
    _order = "name, id"

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    gateway_id = fields.Many2one("mail.gateway", ondelete="restrict")
    company_id = fields.Many2one("res.company", ondelete="restrict")
    principal_partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="cascade",
    )
    verification_mode = fields.Selection(
        [
            ("phone_only", "Phone Only"),
            ("phone_plus_question", "Phone Plus Verification Question"),
            ("human_approval", "Human Approval"),
        ],
        default="phone_only",
        required=True,
    )
    allow_sensitive_data = fields.Boolean(default=True)
    notes = fields.Text()

    @api.constrains("company_id", "gateway_id")
    def _check_company_consistency(self):
        for binding in self:
            if (
                binding.company_id
                and binding.gateway_id
                and binding.gateway_id.company_id != binding.company_id
            ):
                raise ValidationError(
                    "Binding company must match the selected gateway company."
                )
