# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MailGatewaySendMessageWizard(models.TransientModel):
    _name = "mail.gateway.send.message.wizard"
    _description = "Send Message through Gateway"

    gateway_id = fields.Many2one(
        "mail.gateway",
        string="From",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="To (Contact)",
        help="Optional contact used to prefill the destination.",
    )
    to = fields.Char(
        string="To",
        required=True,
        help="Phone number or provider chat id (e.g. 5511999999999, 5511999999999@c.us).",
    )
    body = fields.Text(string="Message")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mail_gateway_send_message_wizard_ir_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Attachments",
    )

    @api.model
    def _get_gateway_dispatch_service(self):
        if "mail.gateway.dispatch.service" not in self.env:
            raise RuntimeError("mail.gateway.dispatch.service is not available.")
        return self.env["mail.gateway.dispatch.service"]

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for wizard in self:
            partner = wizard.partner_id
            if not partner:
                continue
            wizard.to = (
                wizard._get_gateway_dispatch_service()._resolve_destination(partner)
                or wizard.to
            )

    def _prepare_attachments_payload(self):
        return self._get_gateway_dispatch_service()._prepare_ir_attachments_payload(
            self.attachment_ids
        )

    def action_send(self):
        self.ensure_one()
        gateway = self.gateway_id
        if not gateway:
            raise ValidationError(_("Gateway is required."))

        to_value = (self.to or "").strip()
        if not to_value:
            raise ValidationError(_("Recipient is required."))

        if not (self.body or "").strip() and not self.attachment_ids:
            raise ValidationError(
                _("Message body or at least one attachment is required.")
            )

        author_partner = self.env.user.partner_id
        self._get_gateway_dispatch_service()._send_text_message(
            gateway=gateway,
            destination=to_value,
            body_text=self.body,
            attachments=self._prepare_attachments_payload(),
            company_id=gateway.company_id,
            author_user=gateway.webhook_user_id or self.env.user,
            author_partner=author_partner,
        )

        # Avoid leaving temporary wizard attachments around.
        if self.attachment_ids:
            self.attachment_ids.unlink()

        return {"type": "ir.actions.act_window_close"}
