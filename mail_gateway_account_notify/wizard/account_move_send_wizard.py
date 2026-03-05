# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMoveSendWizard(models.TransientModel):
    _inherit = "account.move.send.wizard"

    mail_gateway_id = fields.Many2one(
        comodel_name="mail.gateway",
        string="Gateway",
        domain="[('company_id', '=', company_id), ('integrated_webhook_state', '=', 'integrated')]",
        compute="_compute_mail_gateway_id",
        store=True,
        readonly=False,
    )
    mail_gateway_to = fields.Char(
        string="Gateway Destination",
        compute="_compute_mail_gateway_to",
        store=True,
        readonly=False,
    )

    @api.depends("move_id")
    def _compute_mail_gateway_id(self):
        for wizard in self:
            wizard.mail_gateway_id = wizard._get_default_mail_gateway(wizard.move_id)

    @api.depends("move_id")
    def _compute_mail_gateway_to(self):
        for wizard in self:
            wizard.mail_gateway_to = wizard._get_default_gateway_destination(
                wizard.move_id
            )

    def _get_sending_settings(self):
        send_settings = super()._get_sending_settings()
        if self.sending_methods and "mail_gateway" in self.sending_methods:
            send_settings.update(
                {
                    "mail_gateway": self.mail_gateway_id,
                    "mail_gateway_to": self.mail_gateway_to,
                    "mail_body": self.mail_body,
                    "mail_subject": self.mail_subject,
                    "mail_lang": self.mail_lang,
                    "mail_template": self.mail_template_id,
                }
            )
        return send_settings
