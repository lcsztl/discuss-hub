# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

INTEGRATION_PROVIDER = "WHATSAPP-BAILEYS"

class EvolutionApiInstance(models.Model):
    _name = "evolution.api.instance"
    _description = "Evolution API Instance"
    _inherit = [
        "mail.gateway.whatsapp_evolution_api.mixin",
        "mail.gateway.whatsapp_evolution_api.settings.mixin",
    ]
    _order = "name"

    name = fields.Char(required=True)
    server_id = fields.Many2one(
        "evolution.api.server",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="server_id.company_id",
        store=True,
        readonly=True,
    )
    connection_status = fields.Char(
        readonly=True,
        help=(
            "Raw connection state returned by Evolution API (e.g. 'open', 'qrcode', "
            "'pair_device', 'connecting', 'closed', 'disconnected')."
        ),
    )
    status = fields.Selection(
        [
            ("connected", "Connected"),
            ("connecting", "Connecting"),
            ("disconnected", "Disconnected"),
            ("unknown", "Unknown"),
        ],
        compute="_compute_status",
        store=True,
        readonly=True,
        default="unknown",
        help=(
            "Normalized status computed from 'Connection Status' for easier reporting. "
            "Mapping: open→Connected; connecting/pair_device/qrcode→Connecting; "
            "close/closed/disconnected→Disconnected; others→Unknown."
        ),
    )
    profile_name = fields.Char(readonly=True)
    phone_number = fields.Char(readonly=True)
    api_key = fields.Char(readonly=True)
    qr_code = fields.Image(readonly=True)
    last_sync = fields.Datetime(readonly=True)
    gateway_id = fields.Many2one(
        "mail.gateway",
        string="Gateway",
        readonly=True,
        ondelete="set null",
    )
    gateway_state = fields.Selection(
        [
            ("with_gateway", "Com gateway"),
            ("no_gateway", "Sem gateway"),
        ],
        compute="_compute_gateway_state",
        readonly=True,
    )
    evolution_webhook_by_events = fields.Boolean(
        related="gateway_id.evolution_webhook_by_events",
        readonly=True,
    )
    evolution_base64_webhook = fields.Boolean(
        related="gateway_id.evolution_base64_webhook",
        readonly=False,
    )
    evolution_webhook_event_ids = fields.Many2many(
        related="gateway_id.evolution_webhook_event_ids",
        readonly=False,
    )
    gateway_type = fields.Selection(related="gateway_id.gateway_type", readonly=True)
    gateway_token = fields.Char(related="gateway_id.token", readonly=True)
    gateway_integrated_webhook_state = fields.Selection(
        related="gateway_id.integrated_webhook_state", readonly=True
    )
    gateway_webhook_url = fields.Char(related="gateway_id.webhook_url", readonly=True)
    gateway_webhook_key = fields.Char(related="gateway_id.webhook_key", readonly=True)
    gateway_webhook_secret = fields.Char(
        related="gateway_id.webhook_secret", readonly=True
    )
    gateway_webhook_user_id = fields.Many2one(
        related="gateway_id.webhook_user_id", readonly=True
    )
    gateway_member_ids = fields.Many2many(
        related="gateway_id.member_ids",
        readonly=True,
    )
    gateway_evolution_api_url = fields.Char(
        related="gateway_id.evolution_api_url", readonly=True
    )
    gateway_evolution_instance = fields.Char(
        related="gateway_id.evolution_instance", readonly=True
    )

    def _gateway_values(self):
        self.ensure_one()
        base_url = (self.server_id.base_url or "").rstrip("/")
        gateway_name = self.profile_name or self.name
        token = self.api_key or self.server_id.api_key
        return {
            "name": gateway_name,
            "gateway_type": "whatsapp_evolution_api",
            "token": token,
            "evolution_api_url": base_url,
            "evolution_instance": self.name,
            "company_id": self.company_id.id,
        }

    def _find_gateway(self):
        self.ensure_one()
        domain = [
            ("gateway_type", "=", "whatsapp_evolution_api"),
            ("evolution_instance", "=", self.name),
        ]
        if self.server_id and self.server_id.base_url:
            domain.append(("evolution_api_url", "=", self.server_id.base_url.rstrip("/")))
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        return self.env["mail.gateway"].search(domain, limit=1)

    def _action_open_gateway(self, gateway):
        action = self.env.ref("mail_gateway.mail_gateway_act_window").read()[0]
        action.update(
            {
                "res_id": gateway.id,
                "view_mode": "form",
                "views": [(False, "form")],
            }
        )
        return action

    def _action_open_gateway_inbox(self, gateway):
        if "discuss.hub.inbox" not in self.env:
            return self._action_open_gateway(gateway)
        inbox_model = self.env["discuss.hub.inbox"].sudo()
        if "gateway_id" not in inbox_model._fields:
            return self._action_open_gateway(gateway)
        inbox = inbox_model.search([("gateway_id", "=", gateway.id)], limit=1)
        if not inbox:
            inbox = inbox_model.create(
                {
                    "inbox_type": "gateway",
                    "gateway_id": gateway.id,
                    "name": gateway.name,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "discuss.hub.inbox",
            "res_id": inbox.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    def action_open_gateway(self):
        self.ensure_one()
        if not self.gateway_id:
            raise UserError(_("No gateway linked to this instance."))
        return self._action_open_gateway(self.gateway_id)

    def _get_api_context(self):
        self.ensure_one()
        if not self.server_id or not self.server_id.base_url:
            raise UserError(_("Evolution API server is required."))
        api_key = self.api_key or self.server_id.api_key
        if not api_key:
            raise UserError(_("Evolution API token is required."))
        return self.server_id.base_url, api_key

    def _api_request(self, method, endpoint, payload=None):
        base_url, api_key = self._get_api_context()
        return self._evolution_api_request(base_url, api_key, method, endpoint, payload)

    def _safe_json(self, payload):
        try:
            return json.dumps(payload, ensure_ascii=True)
        except Exception:
            return ""


    @staticmethod
    def _extract_qr_base64(payload):
        if not isinstance(payload, dict):
            return False
        candidates = [
            payload.get("base64"),
            payload.get("qr"),
        ]
        for key in ("qrcode", "qrCode", "qr_code"):
            value = payload.get(key)
            if isinstance(value, dict):
                candidates.extend([value.get("base64"), value.get("qr"), value.get("image")])
            elif isinstance(value, str):
                candidates.append(value)
        for nested_key in ("data", "instance"):
            nested = payload.get(nested_key)
            if isinstance(nested, dict):
                candidates.extend([nested.get("base64"), nested.get("qr")])
                nested_qr = nested.get("qrcode")
                if isinstance(nested_qr, dict):
                    candidates.extend(
                        [nested_qr.get("base64"), nested_qr.get("qr"), nested_qr.get("image")]
                    )
                elif isinstance(nested_qr, str):
                    candidates.append(nested_qr)
        for item in candidates:
            if isinstance(item, str) and item:
                if "," in item:
                    return item.split(",", 1)[1]
                return item
        return False

    def _apply_instance_payload(self, payload):
        self.ensure_one()
        vals = {"last_sync": fields.Datetime.now()}
        if "raw_payload" in self._fields:
            vals["raw_payload"] = self._safe_json(payload)
        instance_data = {}
        if isinstance(payload, dict):
            if isinstance(payload.get("instance"), dict):
                instance_data = payload["instance"]
            elif isinstance(payload.get("data"), dict):
                instance_data = payload["data"]
            else:
                instance_data = payload

        connection_status = (
            instance_data.get("connectionStatus")
            or instance_data.get("status")
            or instance_data.get("state")
        )
        if connection_status:
            vals["connection_status"] = connection_status

        profile_name = instance_data.get("profileName")
        if profile_name:
            vals["profile_name"] = profile_name

        owner_jid = instance_data.get("ownerJid")
        if owner_jid:
            vals["phone_number"] = self.server_id._parse_owner_jid(owner_jid)

        phone_number = instance_data.get("phoneNumber")
        if phone_number and not vals.get("phone_number"):
            vals["phone_number"] = phone_number

        token = instance_data.get("token")
        if token:
            vals["api_key"] = token

        qr_code = self._extract_qr_base64(payload)
        if qr_code:
            vals["qr_code"] = qr_code
        elif connection_status in ("open", "connected", "close", "closed", "disconnected"):
            vals["qr_code"] = False

        self.write(vals)

    def action_check_status(self):
        self.ensure_one()
        payload = self._api_request("GET", f"/instance/connectionState/{self.name}")
        self._apply_instance_payload(payload)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_create_instance(self):
        self.ensure_one()
        payload = {
            "instanceName": self.name,
            "integration": INTEGRATION_PROVIDER,
        }
        payload.update(self._settings_payload())
        response = self._api_request("POST", "/instance/create", payload)
        self._apply_instance_payload(response)
        if self.status == "unknown":
            self.write({"connection_status": "disconnected"})
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_connect(self):
        self.ensure_one()
        payload = self._api_request("GET", f"/instance/connect/{self.name}")
        qr_code = self._extract_qr_base64(payload) if isinstance(payload, dict) else False
        if qr_code:
            vals = {
                "connection_status": "qrcode",
                "last_sync": fields.Datetime.now(),
                "qr_code": qr_code,
            }
            if "raw_payload" in self._fields:
                vals["raw_payload"] = self._safe_json(payload)
            self.write(vals)
        else:
            self._apply_instance_payload(payload)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_refresh_qrcode(self):
        self.ensure_one()
        return self.action_connect()

    def action_restart(self):
        self.ensure_one()
        payload = self._api_request("POST", f"/instance/restart/{self.name}")
        self._apply_instance_payload(payload)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_disconnect(self):
        self.ensure_one()
        payload = self._api_request("DELETE", f"/instance/logout/{self.name}")
        self._apply_instance_payload(payload)
        if self.connection_status != "disconnected":
            self.write({"connection_status": "disconnected"})
        self.write({"qr_code": False})
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_delete_instance(self):
        self.ensure_one()
        payload = self._api_request("DELETE", f"/instance/delete/{self.name}")
        self._apply_instance_payload(payload)
        self.write({"connection_status": "disconnected", "qr_code": False})
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_create_gateway(self):
        self.ensure_one()
        existing = self.gateway_id or self._find_gateway()
        if existing:
            if not self.gateway_id:
                self.gateway_id = existing.id
            return self._action_open_gateway_inbox(existing)
        if not self.server_id:
            raise UserError(_("Evolution API server is required."))
        token = self.api_key or self.server_id.api_key
        if not token:
            raise UserError(_("Evolution API token is required to create a gateway."))
        duplicate = self.env["mail.gateway"].search([("token", "=", token)], limit=1)
        if duplicate:
            raise UserError(
                _("Token already in use by gateway '%s'. Please use a unique token.")
                % duplicate.display_name
            )
        gateway = self.env["mail.gateway"].create(self._gateway_values())
        gateway.set_webhook()
        self.gateway_id = gateway.id
        return self._action_open_gateway_inbox(gateway)

    def action_select_all_webhook_events(self):
        self.ensure_one()
        if not self.gateway_id:
            raise UserError(_("Gateway is required to manage webhook events."))
        return self.gateway_id.action_select_all_webhook_events()

    def action_clear_webhook_events(self):
        self.ensure_one()
        if not self.gateway_id:
            raise UserError(_("Gateway is required to manage webhook events."))
        return self.gateway_id.action_clear_webhook_events()

    def _apply_settings(self):
        self.ensure_one()
        if not self.server_id:
            raise UserError(_("Evolution API server is required."))
        if not self.name:
            raise UserError(_("Instance name is required."))
        self._evolution_api_set_settings(
            self.server_id.base_url,
            self.api_key or self.server_id.api_key,
            self.name,
            self._settings_payload(),
        )

    def write(self, vals):
        settings_fields = self._get_settings_fields()
        res = super().write(vals)
        if settings_fields.intersection(vals):
            for record in self:
                try:
                    record._apply_settings()
                except UserError as exc:
                    raise UserError(_("Failed to update Evolution settings: %s") % exc) from exc
        return res

    _sql_constraints = [
        (
            "evolution_api_instance_unique",
            "unique(server_id, name)",
            "Instance name must be unique per server.",
        ),
    ]

    @api.depends("connection_status")
    def _compute_status(self):
        for record in self:
            record.status = self._map_status(record.connection_status)

    @api.depends("gateway_id")
    def _compute_gateway_state(self):
        for record in self:
            record.gateway_state = "with_gateway" if record.gateway_id else "no_gateway"

    @staticmethod
    def _map_status(connection_status):
        if not connection_status:
            return "unknown"
        if connection_status == "open":
            return "connected"
        if connection_status in ("connecting", "pair_device", "qrcode"):
            return "connecting"
        if connection_status in ("close", "closed", "disconnected"):
            return "disconnected"
        return "unknown"
