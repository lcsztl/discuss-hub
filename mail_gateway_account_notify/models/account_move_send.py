# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _get_gateway_dispatch_service(self):
        if "mail.gateway.dispatch.service" not in self.env:
            raise RuntimeError("mail.gateway.dispatch.service is not available.")
        return self.env["mail.gateway.dispatch.service"]

    @api.model
    def _prepare_gateway_attachments_payload(self, attachments):
        return self._get_gateway_dispatch_service()._prepare_ir_attachments_payload(
            attachments
        )

    @api.model
    def _resolve_partner_gateway_destination(self, partner):
        return (
            self._get_gateway_dispatch_service()._resolve_destination(partner) or False
        )

    @api.model
    def _send_gateway_text_message(
        self,
        gateway,
        destination,
        body_text,
        attachments=None,
        company_id=None,
        author_user=None,
        author_partner=None,
    ):
        return self._get_gateway_dispatch_service()._send_text_message(
            gateway=gateway,
            destination=destination,
            body_text=body_text,
            attachments=attachments,
            company_id=company_id,
            author_user=author_user,
            author_partner=author_partner,
        )

    @api.model
    def _get_default_mail_gateway(self, move):
        if not move:
            return self.env["mail.gateway"]
        return self.env["mail.gateway"].sudo().search(
            [
                ("company_id", "=", move.company_id.id),
                ("integrated_webhook_state", "=", "integrated"),
            ],
            order="id",
            limit=1,
        )

    @api.model
    def _get_default_gateway_destination(self, move):
        if not move:
            return False
        partner = move.commercial_partner_id.with_company(move.company_id)
        return self._resolve_partner_gateway_destination(partner) or False

    @api.model
    def _normalize_gateway_value(self, gateway_value):
        gateway_model = self.env["mail.gateway"].sudo()
        if not gateway_value:
            return gateway_model.browse()
        if isinstance(gateway_value, models.BaseModel):
            return gateway_value.filtered(lambda gateway: gateway._name == "mail.gateway")[:1]
        if isinstance(gateway_value, int):
            return gateway_model.browse(gateway_value).exists()
        return gateway_model.browse()

    @api.model
    def _get_move_gateway(self, move, move_data):
        gateway = self._normalize_gateway_value((move_data or {}).get("mail_gateway"))
        if not gateway:
            gateway = self._get_default_mail_gateway(move)
        return gateway[:1]

    @api.model
    def _get_move_gateway_destination(self, move, move_data):
        destination = ((move_data or {}).get("mail_gateway_to") or "").strip()
        if destination:
            return destination
        return (self._get_default_gateway_destination(move) or "").strip()

    @api.model
    def _get_default_sending_settings(self, move, from_cron=False, **custom_settings):
        vals = super()._get_default_sending_settings(
            move,
            from_cron=from_cron,
            **custom_settings,
        )

        def get_setting(key, default_value=None):
            if key in custom_settings:
                return custom_settings.get(key)
            if from_cron:
                return move.sending_data.get(key, default_value)
            return default_value

        if "mail_gateway" in (vals.get("sending_methods") or set()):
            vals["mail_gateway"] = get_setting(
                "mail_gateway",
                default_value=self._get_default_mail_gateway(move),
            )
            vals["mail_gateway_to"] = get_setting(
                "mail_gateway_to",
                default_value=self._get_default_gateway_destination(move),
            )
            for key in ("mail_body", "mail_subject", "mail_lang", "mail_template"):
                if key in custom_settings:
                    vals[key] = custom_settings.get(key)

        return vals

    def _get_alerts(self, moves, moves_data):
        alerts = super()._get_alerts(moves, moves_data)

        gateway_moves = moves.filtered(
            lambda move: "mail_gateway" in moves_data[move]["sending_methods"]
        )
        if not gateway_moves:
            return alerts

        missing_gateway_moves = gateway_moves.filtered(
            lambda move: not self._get_move_gateway(move, moves_data[move])
        )
        if missing_gateway_moves:
            alerts["mail_gateway_account_missing_gateway"] = {
                "level": "danger" if len(missing_gateway_moves) == 1 else "warning",
                "message": _(
                    "No integrated gateway is configured for at least one selected invoice."
                ),
                "action_text": _("View Invoice(s)"),
                "action": missing_gateway_moves._get_records_action(
                    name=_("Check Invoice(s)")
                ),
            }

        missing_destination_moves = gateway_moves.filtered(
            lambda move: not self._get_move_gateway_destination(move, moves_data[move])
        )
        if missing_destination_moves:
            alerts["mail_gateway_account_missing_destination"] = {
                "level": "danger" if len(missing_destination_moves) == 1 else "warning",
                "message": _(
                    "At least one recipient has no gateway destination (gateway phone/mobile/phone)."
                ),
                "action_text": _("View Invoice(s)"),
                "action": missing_destination_moves._get_records_action(
                    name=_("Check Invoice(s)")
                ),
            }

        return alerts

    @api.model
    def _is_applicable_to_company(self, method, company):
        if method != "mail_gateway":
            return super()._is_applicable_to_company(method, company)
        return bool(
            self.env["mail.gateway"].sudo().search(
                [
                    ("company_id", "=", company.id),
                    ("integrated_webhook_state", "=", "integrated"),
                ],
                limit=1,
            )
        )

    @api.model
    def _is_applicable_to_move(self, method, move, **move_data):
        if method != "mail_gateway":
            return super()._is_applicable_to_move(method, move, **move_data)

        gateway = self._get_move_gateway(move, move_data)
        destination = self._get_move_gateway_destination(move, move_data)
        return bool(gateway and destination)

    @api.model
    def _display_attachments_widget(self, edi_format, sending_methods):
        return super()._display_attachments_widget(edi_format, sending_methods) or (
            "mail_gateway" in (sending_methods or ())
        )

    @api.model
    def _get_gateway_body(self, move, move_data):
        body = move_data.get("mail_body")
        if body:
            return body

        mail_template = move_data.get("mail_template") or self._get_default_mail_template_id(
            move
        )
        if not mail_template:
            return ""

        mail_lang = move_data.get("mail_lang") or self._get_default_mail_lang(
            move,
            mail_template,
        )
        return self._get_default_mail_body(move, mail_template, mail_lang) or ""

    @api.model
    def _get_gateway_attachments(self, move, move_data):
        attachment_ids = set()
        mail_attachments_widget = move_data.get("mail_attachments_widget") or []
        to_exclude = {
            entry["name"]
            for entry in mail_attachments_widget
            if entry.get("skip")
        }

        for entry in self._get_invoice_extra_attachments_data(move) + mail_attachments_widget:
            if entry["name"] in to_exclude and not entry.get("manual"):
                continue
            try:
                attachment_ids.add(int(entry["id"]))
            except (TypeError, ValueError):
                continue

        attachments = self.env["ir.attachment"].browse(list(attachment_ids)).exists()
        return self._prepare_gateway_attachments_payload(attachments)

    def _send_gateway_messages(self, moves_data):
        for move, move_data in moves_data.items():
            gateway = self._get_move_gateway(move, move_data)
            destination = self._get_move_gateway_destination(move, move_data)
            body = self._get_gateway_body(move, move_data)
            attachments = self._get_gateway_attachments(move, move_data)

            author_user = gateway.webhook_user_id or self.env["res.users"].browse(
                move_data.get("author_user_id")
            ).exists()
            author_partner = self.env["res.partner"].browse(
                move_data.get("author_partner_id")
            ).exists() or author_user.partner_id

            self._send_gateway_text_message(
                gateway=gateway,
                destination=destination,
                body_text=body,
                attachments=attachments,
                company_id=move.company_id,
                author_user=author_user,
                author_partner=author_partner,
            )

            move._message_log(
                body=_(
                    "Invoice sent by gateway '%(gateway)s' to %(destination)s."
                )
                % {
                    "gateway": gateway.display_name,
                    "destination": destination,
                }
            )

    def _hook_if_success(self, moves_data):
        super()._hook_if_success(moves_data)

        to_send = {
            move: move_data
            for move, move_data in moves_data.items()
            if "mail_gateway" in move_data["sending_methods"]
            and self._is_applicable_to_move("mail_gateway", move, **move_data)
        }
        if to_send:
            self._send_gateway_messages(to_send)
