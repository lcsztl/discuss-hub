# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    gateway_llm_source_message_id = fields.Many2one(
        "mail.message",
        string="Gateway LLM Source Message",
        index=True,
        copy=False,
        ondelete="set null",
    )
