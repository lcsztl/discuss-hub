# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import uuid
from urllib.parse import urlsplit, urlunsplit

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MailGateway(models.Model):
    _name = "mail.gateway"
    _inherit = [
        "mail.gateway",
        "mail.gateway.whatsapp_evolution_api.mixin",
        "mail.gateway.whatsapp_evolution_api.settings.mixin",
    ]

    gateway_type = fields.Selection(
        selection_add=[
            ("whatsapp_evolution_api", "WhatsApp (Evolution API)"),
        ],
        ondelete={"whatsapp_evolution_api": "cascade"},
    )
    evolution_api_url = fields.Char(
        string="Evolution API URL",
        help="Base URL of the Evolution API server (ex: https://evolution.example.com)",
    )
    evolution_instance = fields.Char(
        string="Evolution Instance",
        help="Technical instance name in Evolution API. Defaults to the gateway name.",
    )
    evolution_base64_webhook = fields.Boolean(
        string="Webhook Base64",
        default=True,
        help="When enabled, Evolution will send media as base64 in webhooks.",
    )
    evolution_webhook_by_events = fields.Boolean(
        string="Webhook by Events",
        help="Create a route for each event by adding the event name to the end of the URL.",
    )
    evolution_webhook_event_ids = fields.Many2many(
        "mail.gateway.whatsapp_evolution_api.webhook_event",
        "mail_gateway_whatsapp_evolution_api_event_rel",
        "gateway_id",
        "event_id",
        string="Webhook Events",
        help="Events to subscribe in Evolution API.",
        default=lambda self: self._default_webhook_event_ids(),
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("evolution_api_url"):
                vals["evolution_api_url"] = vals["evolution_api_url"].rstrip("/")
            if (
                vals.get("gateway_type") == "whatsapp_evolution_api"
                and not vals.get("webhook_key")
            ):
                vals["webhook_key"] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("evolution_api_url"):
            vals["evolution_api_url"] = vals["evolution_api_url"].rstrip("/")
        res = super().write(vals)
        settings_fields = self._get_settings_fields()
        if settings_fields.intersection(vals):
            for record in self.filtered(
                lambda r: r.gateway_type == "whatsapp_evolution_api"
            ):
                try:
                    record._apply_settings()
                except UserError as exc:
                    raise UserError(_("Failed to update Evolution settings: %s") % exc) from exc
        webhook_fields = {
            "evolution_webhook_by_events",
            "evolution_base64_webhook",
            "evolution_webhook_event_ids",
        }
        if webhook_fields.intersection(vals):
            for record in self.filtered(
                lambda r: r.gateway_type == "whatsapp_evolution_api"
            ):
                try:
                    record._apply_webhook_settings()
                except UserError as exc:
                    raise UserError(_("Failed to update Evolution webhook: %s") % exc) from exc
        if not self.env.context.get("skip_evolution_defaults"):
            for record in self.filtered(
                lambda r: r.gateway_type == "whatsapp_evolution_api" and not r.webhook_key
            ):
                record.with_context(skip_evolution_defaults=True).write(
                    {"webhook_key": str(uuid.uuid4())}
                )
        return res

    def _apply_settings(self):
        self.ensure_one()
        if self.gateway_type != "whatsapp_evolution_api":
            return
        if not self.evolution_api_url or not self.token:
            raise UserError(_("Evolution API URL and token are required."))
        instance_name = self.evolution_instance or self.name
        if not instance_name:
            raise UserError(_("Evolution API instance name is required."))
        self._evolution_api_set_settings(
            self.evolution_api_url,
            self.token,
            instance_name,
            self._settings_payload(),
        )

    def _apply_webhook_settings(self):
        self.ensure_one()
        if self.gateway_type != "whatsapp_evolution_api":
            return
        if not self.can_set_webhook or self.integrated_webhook_state != "integrated":
            return
        self.update_webhook()

    def _default_webhook_event_ids(self):
        return self.env[
            "mail.gateway.whatsapp_evolution_api.webhook_event"
        ].search([]).ids

    def action_select_all_webhook_events(self):
        events = self.env["mail.gateway.whatsapp_evolution_api.webhook_event"].search([])
        for record in self.filtered(
            lambda r: r.gateway_type == "whatsapp_evolution_api"
        ):
            record.evolution_webhook_event_ids = [(6, 0, events.ids)]

    def action_clear_webhook_events(self):
        for record in self.filtered(
            lambda r: r.gateway_type == "whatsapp_evolution_api"
        ):
            record.evolution_webhook_event_ids = [(5, 0, 0)]

    def _get_webhook_events(self):
        """Retorna a lista de eventos selecionados para envio ao Evolution API."""
        self.ensure_one()
        if self.gateway_type != "whatsapp_evolution_api":
            return []
        return [ev.code for ev in self.evolution_webhook_event_ids]

    def _get_webhook_url(self):
        if self.gateway_type != "whatsapp_evolution_api":
            return super()._get_webhook_url()
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).strip()
        if not base_url and self.webhook_url:
            base_url = self.webhook_url.split("/gateway/")[0]
        base_url = base_url.rstrip("/")
        if base_url:
            parts = urlsplit(base_url)
            if parts.scheme and parts.netloc:
                base_url = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        return "{}/gateway/{}/{}/update".format(
            base_url,
            self.gateway_type,
            self.webhook_key,
        )
