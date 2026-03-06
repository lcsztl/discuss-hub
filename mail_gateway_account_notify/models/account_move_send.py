# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import threading

from odoo import SUPERUSER_ID, _, api, models
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


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
        attachment_ids = self._collect_gateway_attachment_ids(move, move_data)
        attachments = self.env["ir.attachment"].browse(attachment_ids).exists()
        return self._prepare_gateway_attachments_payload(attachments)

    @api.model
    def _collect_gateway_attachment_ids(self, move, move_data):
        attachment_ids = set()
        mail_attachments_widget = (move_data or {}).get("mail_attachments_widget") or []
        to_exclude = {entry["name"] for entry in mail_attachments_widget if entry.get("skip")}

        for entry in self._get_invoice_extra_attachments_data(move) + mail_attachments_widget:
            if entry["name"] in to_exclude and not entry.get("manual"):
                continue
            try:
                attachment_ids.add(int(entry["id"]))
            except (TypeError, ValueError):
                continue
        return sorted(attachment_ids)

    @api.model
    def _resolve_gateway_author(self, gateway, author_user_id=False, author_partner_id=False):
        author_user = self.env["res.users"].browse(author_user_id).exists()
        if not author_user:
            author_user = gateway.webhook_user_id or self.env.user

        author_partner = self.env["res.partner"].browse(author_partner_id).exists()
        if not author_partner:
            author_partner = author_user.partner_id or self.env.user.partner_id
        return author_user, author_partner

    @api.model
    def _build_gateway_send_job(self, move, move_data):
        gateway = self._get_move_gateway(move, move_data)
        destination = self._get_move_gateway_destination(move, move_data)
        if not gateway or not destination:
            return False
        return {
            "move_id": move.id,
            "gateway_id": gateway.id,
            "destination": destination,
            "body_text": self._get_gateway_body(move, move_data),
            "attachment_ids": self._collect_gateway_attachment_ids(move, move_data),
            "author_user_id": move_data.get("author_user_id"),
            "author_partner_id": move_data.get("author_partner_id"),
            "company_id": move.company_id.id,
        }

    @api.model
    def _run_gateway_send_jobs(self, jobs):
        for job in jobs or []:
            try:
                with self.env.cr.savepoint(flush=False):
                    self._run_single_gateway_send_job(job)
                    # Flush inside the savepoint so serialization conflicts are
                    # handled as a per-job failure instead of escaping at commit.
                    self.env.cr.flush()
            except Exception as err:
                _logger.exception(
                    "Gateway send job failed for invoice ID %s.",
                    job.get("move_id"),
                )
                try:
                    with self.env.cr.savepoint(flush=False):
                        self._log_gateway_send_job_error(job.get("move_id"), str(err))
                        self.env.cr.flush()
                except Exception:
                    _logger.exception(
                        "Unable to persist gateway job failure log for invoice ID %s.",
                        job.get("move_id"),
                    )

    @api.model
    def _run_single_gateway_send_job(self, job):
        move_id = int(job.get("move_id") or 0)
        gateway_id = int(job.get("gateway_id") or 0)
        destination = (job.get("destination") or "").strip()
        if not move_id or not gateway_id or not destination:
            raise ValueError(_("Invalid gateway send job payload."))

        move = self.env["account.move"].browse(move_id).exists()
        gateway = self.env["mail.gateway"].browse(gateway_id).exists()
        if not move or not gateway:
            raise ValueError(_("Invoice or gateway not found for send job."))

        attachment_ids = []
        for attachment_id in job.get("attachment_ids") or []:
            try:
                attachment_ids.append(int(attachment_id))
            except (TypeError, ValueError):
                continue
        attachments = self.env["ir.attachment"].browse(attachment_ids).exists()
        attachment_payload = self._prepare_gateway_attachments_payload(attachments)

        author_user, author_partner = self._resolve_gateway_author(
            gateway,
            author_user_id=job.get("author_user_id"),
            author_partner_id=job.get("author_partner_id"),
        )
        company = self.env["res.company"].browse(int(job.get("company_id") or 0)).exists()
        company = company or move.company_id

        self._send_gateway_text_message(
            gateway=gateway,
            destination=destination,
            body_text=job.get("body_text") or "",
            attachments=attachment_payload,
            company_id=company,
            author_user=author_user,
            author_partner=author_partner,
        )

        move._message_log(
            body=_("Invoice sent by gateway '%(gateway)s' to %(destination)s.")
            % {
                "gateway": gateway.display_name,
                "destination": destination,
            }
        )

    @api.model
    def _log_gateway_send_job_error(self, move_id, error_text):
        move = self.env["account.move"].browse(int(move_id or 0)).exists()
        if not move:
            return
        error_text = (error_text or _("Unknown gateway error")).strip()
        if len(error_text) > 400:
            error_text = f"{error_text[:397]}..."
        move._message_log(
            body=_(
                "Gateway sending failed after invoice confirmation. "
                "Error: %(error)s. Please retry the gateway sending manually."
            )
            % {"error": error_text}
        )

    def _send_gateway_messages(self, moves_data):
        for move, move_data in moves_data.items():
            gateway = self._get_move_gateway(move, move_data)
            destination = self._get_move_gateway_destination(move, move_data)
            body = self._get_gateway_body(move, move_data)
            attachments = self._get_gateway_attachments(move, move_data)

            author_user, author_partner = self._resolve_gateway_author(
                gateway,
                author_user_id=move_data.get("author_user_id"),
                author_partner_id=move_data.get("author_partner_id"),
            )

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
        if not to_send:
            return

        jobs = []
        for move, move_data in to_send.items():
            job = self._build_gateway_send_job(move, move_data)
            if job:
                jobs.append(job)
        if not jobs:
            return

        if getattr(threading.current_thread(), "testing", False):
            self._run_gateway_send_jobs(jobs)
            return

        dbname = self.env.cr.dbname
        context = dict(self.env.context or {})

        @self.env.cr.postcommit.add
        def _send_gateway_after_commit():
            registry = Registry(dbname)
            for job in jobs:
                try:
                    with registry.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, context)
                        env["account.move.send"]._run_gateway_send_jobs([job])
                except Exception:
                    _logger.exception(
                        "Post-commit gateway send failed for invoice ID %s.",
                        job.get("move_id"),
                    )
