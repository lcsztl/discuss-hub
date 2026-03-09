# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import threading
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class MailGatewayLLMRun(models.Model):
    _name = "mail.gateway.llm.run"
    _description = "Mail Gateway LLM Run"
    _order = "id desc"

    name = fields.Char(required=True, default=lambda self: _("New Gateway AI Run"))
    gateway_id = fields.Many2one(
        "mail.gateway",
        required=True,
        ondelete="cascade",
        index=True,
    )
    channel_id = fields.Many2one(
        "discuss.channel",
        required=True,
        ondelete="cascade",
        index=True,
    )
    thread_id = fields.Many2one("llm.thread", ondelete="set null", index=True)
    assistant_id = fields.Many2one(
        "llm.assistant",
        required=True,
        ondelete="restrict",
        index=True,
    )
    source_message_id = fields.Many2one(
        "mail.message",
        required=True,
        ondelete="cascade",
        index=True,
    )
    notification_id = fields.Many2one(
        "mail.notification",
        ondelete="set null",
        index=True,
    )
    thread_message_id = fields.Many2one(
        "mail.message",
        string="Thread Message",
        ondelete="set null",
    )
    assistant_message_id = fields.Many2one(
        "mail.message",
        string="Assistant Message",
        ondelete="set null",
    )
    published_message_id = fields.Many2one(
        "mail.message",
        string="Published Message",
        ondelete="set null",
    )
    run_type = fields.Selection(
        selection=[("inbound", "Inbound"), ("outbound", "Outbound")],
        required=True,
        index=True,
    )
    mode = fields.Selection(
        selection=[
            ("off", "Off"),
            ("suggest", "Suggest"),
            ("auto", "Auto Reply"),
        ],
        required=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("skipped", "Skipped"),
            ("error", "Error"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    payload_json = fields.Json(string="Payload")
    attempt_count = fields.Integer(default=0)
    max_attempts = fields.Integer(default=3)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, index=True)
    processed_at = fields.Datetime()
    error_text = fields.Text()
    assistant_body = fields.Html(related="assistant_message_id.body", readonly=True)

    _sql_constraints = [
        (
            "mail_gateway_llm_run_source_unique",
            "unique(source_message_id, run_type)",
            "A gateway message is already queued for this AI run type.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name"):
                continue
            run_type = vals.get("run_type") or "inbound"
            label = _("Inbound") if run_type == "inbound" else _("Outbound")
            source_message_id = vals.get("source_message_id") or "new"
            vals["name"] = _("%s #%s") % (label, source_message_id)
        return super().create(vals_list)

    @api.model
    def _default_payload(self, payload=None):
        return payload if isinstance(payload, dict) else {}

    @api.model
    def _enqueue_inbound_run(self, gateway, channel, message, payload=None):
        if not gateway or not channel or not message or not gateway.llm_assistant_id:
            return False
        payload = self._default_payload(payload)
        if payload.get("from_me"):
            return False
        vals = {
            "gateway_id": gateway.id,
            "channel_id": channel.id,
            "assistant_id": gateway.llm_assistant_id.id,
            "source_message_id": message.id,
            "run_type": "inbound",
            "mode": gateway.llm_mode,
            "payload_json": payload,
        }
        run = self._create_or_get_run(vals, message.id, "inbound")
        if run:
            self._schedule_processing([run.id])
        return run

    @api.model
    def _enqueue_outbound_run(self, gateway, channel, notification, message=None):
        message = message or notification.mail_message_id
        if not gateway or not channel or not notification or not message:
            return False
        if not gateway.llm_assistant_id:
            return False
        vals = {
            "gateway_id": gateway.id,
            "channel_id": channel.id,
            "assistant_id": gateway.llm_assistant_id.id,
            "source_message_id": message.id,
            "notification_id": notification.id,
            "run_type": "outbound",
            "mode": gateway.llm_mode,
        }
        run = self._create_or_get_run(vals, message.id, "outbound")
        if run:
            self._schedule_processing([run.id])
        return run

    @api.model
    def _create_or_get_run(self, vals, source_message_id, run_type):
        try:
            with self.env.cr.savepoint():
                return self.create(vals)
        except IntegrityError:
            return self.search(
                [
                    ("source_message_id", "=", source_message_id),
                    ("run_type", "=", run_type),
                ],
                limit=1,
            )

    @api.model
    def _schedule_processing(self, run_ids):
        run_ids = list({run_id for run_id in run_ids if run_id})
        if not run_ids:
            return False
        if getattr(threading.current_thread(), "testing", False):
            self._process_runs(run_ids=run_ids, limit=len(run_ids))
            return True

        dbname = self.env.cr.dbname
        context = dict(self.env.context or {})

        @self.env.cr.postcommit.add
        def _process_gateway_llm_runs_after_commit():
            registry = Registry(dbname)
            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, context)
                env["mail.gateway.llm.run"]._process_runs(
                    run_ids=run_ids,
                    limit=len(run_ids),
                )

        return True

    @api.model
    def _claim_pending_runs(self, run_ids=None, limit=20):
        if limit <= 0:
            return self.browse()

        ids_clause = ""
        params = [fields.Datetime.now()]
        if run_ids:
            ids_clause = " AND id = ANY(%s)"
            params.append(list(run_ids))
        params.extend([limit, self.env.uid])

        query = f"""
            WITH candidates AS (
                SELECT id
                  FROM {self._table}
                 WHERE state = 'pending'
                   AND next_attempt_at <= %s
                   {ids_clause}
                 ORDER BY id
                 FOR UPDATE SKIP LOCKED
                 LIMIT %s
            )
            UPDATE {self._table} AS run
               SET state = 'processing',
                   attempt_count = run.attempt_count + 1,
                   write_uid = %s,
                   write_date = NOW()
              FROM candidates
             WHERE run.id = candidates.id
         RETURNING run.id
        """
        self.env.cr.execute(query, params)
        run_ids = [row[0] for row in self.env.cr.fetchall()]
        return self.browse(run_ids).exists()

    @api.model
    def _cron_process_pending(self, limit=20):
        return self._process_runs(limit=limit)

    @api.model
    def _process_runs(self, run_ids=None, limit=20):
        runs = self._claim_pending_runs(run_ids=run_ids, limit=limit)
        for run in runs:
            with self.env.cr.savepoint():
                try:
                    run._process_one()
                except Exception as exc:
                    _logger.exception("Gateway LLM run %s failed", run.id)
                    run._mark_retry_or_error(str(exc))
            if not getattr(threading.current_thread(), "testing", False):
                self.env.cr.commit()
        return len(runs)

    def _process_one(self):
        self.ensure_one()

        source_message = self.source_message_id.sudo().exists()
        channel = self.channel_id.sudo().exists()
        if not source_message or not channel:
            self._mark_skipped(_("Source message or channel no longer exists."))
            return

        if self.run_type == "inbound" and self._is_inbound_echo(source_message):
            self._mark_skipped(_("Inbound echo from the gateway was ignored."))
            return

        thread = channel._ensure_gateway_llm_thread(assistant=self.assistant_id)
        if self.thread_id != thread:
            self.write({"thread_id": thread.id})

        if self.run_type == "inbound":
            self._process_inbound_run(thread, source_message)
        else:
            self._process_outbound_run(thread, source_message)

    def _is_inbound_echo(self, source_message):
        self.ensure_one()
        payload = self.payload_json or {}
        if payload.get("from_me"):
            return True
        if "gateway_from_me" in source_message._fields and source_message.gateway_from_me:
            return True
        return False

    def _process_inbound_run(self, thread, source_message):
        self.ensure_one()
        thread_message = self._sync_source_message_to_thread(thread, source_message, "user")
        update_vals = {"thread_message_id": thread_message.id if thread_message else False}

        if self.channel_id.llm_state != "active" or self.mode == "off":
            self._mark_done(update_vals)
            return

        previous_assistant = self._get_latest_assistant_message(thread)
        for _event in thread.generate():
            pass
        assistant_message = self._find_new_assistant_message(thread, previous_assistant)
        if not assistant_message:
            self._mark_skipped(_("No assistant response was generated."), update_vals)
            return

        update_vals["assistant_message_id"] = assistant_message.id
        if assistant_message.is_error:
            self._mark_error(_("Assistant generation failed."), update_vals)
            return

        if self.mode == "auto":
            published = self._publish_assistant_message(assistant_message)
            if published:
                update_vals["published_message_id"] = published.id
        self._mark_done(update_vals)

    def _process_outbound_run(self, thread, source_message):
        self.ensure_one()
        thread_message = self._sync_source_message_to_thread(
            thread,
            source_message,
            "assistant",
        )
        if not thread_message:
            self._mark_skipped(_("Outbound message has no content to mirror."))
            return
        self._mark_done({"thread_message_id": thread_message.id})

    def _sync_source_message_to_thread(self, thread, source_message, llm_role):
        self.ensure_one()
        existing = self._find_thread_message(thread, source_message)
        if existing:
            return existing

        body = self.env["mail.gateway.dispatch.service"]._to_plain_text(
            source_message.body or ""
        )
        attachment_ids = source_message.attachment_ids.ids
        if not body and not attachment_ids:
            return False

        author_id = source_message.author_id.id or (
            self.gateway_id.webhook_user_id.partner_id.id
            if self.gateway_id.webhook_user_id and self.gateway_id.webhook_user_id.partner_id
            else False
        )
        thread_message = thread.message_post(
            body=body or "",
            attachment_ids=attachment_ids,
            llm_role=llm_role,
            author_id=author_id,
        )
        thread_message.sudo().write(
            {"gateway_llm_source_message_id": source_message.id}
        )
        return thread_message

    def _find_thread_message(self, thread, source_message):
        self.ensure_one()
        return self.env["mail.message"].search(
            [
                ("model", "=", "llm.thread"),
                ("res_id", "=", thread.id),
                ("gateway_llm_source_message_id", "=", source_message.id),
            ],
            limit=1,
        )

    def _get_latest_assistant_message(self, thread):
        self.ensure_one()
        return self.env["mail.message"].search(
            [
                ("model", "=", "llm.thread"),
                ("res_id", "=", thread.id),
                ("llm_role", "=", "assistant"),
            ],
            order="id desc",
            limit=1,
        )

    def _find_new_assistant_message(self, thread, previous_assistant):
        self.ensure_one()
        domain = [
            ("model", "=", "llm.thread"),
            ("res_id", "=", thread.id),
            ("llm_role", "=", "assistant"),
        ]
        if previous_assistant:
            domain.append(("id", ">", previous_assistant.id))
        return self.env["mail.message"].search(domain, order="id desc", limit=1)

    def _publish_assistant_message(self, assistant_message):
        self.ensure_one()
        body = (assistant_message.body or "").strip()
        attachment_ids = assistant_message.attachment_ids.ids
        if not body and not attachment_ids:
            return False

        channel = self.channel_id.with_context(mail_gateway_skip_outbound_hooks=True)
        send_user = self.gateway_id.webhook_user_id or self.env.user
        send_partner = send_user.partner_id if send_user else False
        return channel.with_user(send_user).message_post(
            body=assistant_message.body or "",
            attachment_ids=attachment_ids,
            author_id=send_partner.id if send_partner else False,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _mark_done(self, extra_vals=None):
        self.ensure_one()
        vals = {
            "state": "done",
            "processed_at": fields.Datetime.now(),
            "next_attempt_at": False,
            "error_text": False,
        }
        if extra_vals:
            vals.update(extra_vals)
        self.write(vals)

    def _mark_skipped(self, reason, extra_vals=None):
        self.ensure_one()
        vals = {
            "state": "skipped",
            "processed_at": fields.Datetime.now(),
            "next_attempt_at": False,
            "error_text": reason,
        }
        if extra_vals:
            vals.update(extra_vals)
        self.write(vals)

    def _mark_error(self, reason, extra_vals=None):
        self.ensure_one()
        vals = {
            "state": "error",
            "processed_at": fields.Datetime.now(),
            "next_attempt_at": False,
            "error_text": reason,
        }
        if extra_vals:
            vals.update(extra_vals)
        self.write(vals)

    def _mark_retry_or_error(self, reason):
        self.ensure_one()
        if self.attempt_count >= self.max_attempts:
            self._mark_error(reason)
            return
        retry_at = fields.Datetime.now() + timedelta(minutes=max(1, self.attempt_count))
        self.write(
            {
                "state": "pending",
                "error_text": reason,
                "next_attempt_at": retry_at,
            }
        )
