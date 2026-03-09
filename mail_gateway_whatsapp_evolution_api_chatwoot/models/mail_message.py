# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    chatwoot_message_id = fields.Char()
    chatwoot_conversation_id = fields.Char()
    chatwoot_inbox_id = fields.Char()
    chatwoot_source = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._chatwoot_try_fill_from_log()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._chatwoot_try_fill_from_log(updated_vals=vals)
        return res

    def _chatwoot_try_fill_from_log(self, updated_vals=None):
        if self.env.context.get("chatwoot_skip_parse"):
            return
        if "gateway_webhook_log_id" not in self._fields:
            return
        if updated_vals and "gateway_webhook_log_id" not in updated_vals:
            if not any(
                field in updated_vals
                for field in (
                    "chatwoot_message_id",
                    "chatwoot_conversation_id",
                    "chatwoot_inbox_id",
                    "chatwoot_source",
                )
            ):
                return
        for record in self:
            if not record.gateway_webhook_log_id:
                continue
            if (
                record.chatwoot_message_id
                and record.chatwoot_conversation_id
                and record.chatwoot_inbox_id
                and record.chatwoot_source
            ):
                continue
            payload = record.gateway_webhook_log_id.request_payload
            if not payload:
                continue
            values = self._chatwoot_extract_values(payload, record)
            if not values:
                continue
            record.with_context(chatwoot_skip_parse=True).write(values)

    def _chatwoot_extract_values(self, payload, record):
        try:
            update = json.loads(payload)
        except Exception:
            return {}
        if not isinstance(update, dict):
            return {}
        data = update.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        extracted = {
            "chatwoot_message_id": data.get("chatwootMessageId"),
            "chatwoot_conversation_id": data.get("chatwootConversationId"),
            "chatwoot_inbox_id": data.get("chatwootInboxId"),
            "chatwoot_source": data.get("source") or update.get("source"),
        }
        values = {}
        for field_name, raw_value in extracted.items():
            if raw_value is None or raw_value is False:
                continue
            if getattr(record, field_name):
                continue
            value = str(raw_value).strip()
            if not value:
                continue
            values[field_name] = value
        return values
