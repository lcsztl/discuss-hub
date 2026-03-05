# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    invoice_sending_method = fields.Selection(
        selection_add=[("mail_gateway", "by Gateway")],
    )
