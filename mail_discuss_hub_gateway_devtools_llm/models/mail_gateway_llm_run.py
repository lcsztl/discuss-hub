# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from datetime import date, datetime

from odoo import api, fields, models


class MailGatewayLLMRun(models.Model):
    _inherit = "mail.gateway.llm.run"

    llm_trace_enabled = fields.Boolean(
        compute="_compute_llm_trace_enabled",
        readonly=True,
    )
    llm_trace_payload = fields.Text(
        string="LLM Trace Payload",
        copy=False,
        readonly=True,
        help="Devtools-only audit trail of rendered prompt, context, request and response snapshots.",
    )
    llm_trace_turn_count = fields.Integer(
        compute="_compute_llm_trace_turn_count",
        readonly=True,
    )

    def _compute_llm_trace_enabled(self):
        enabled = self._devtools_is_llm_trace_enabled()
        for record in self:
            record.llm_trace_enabled = enabled

    @api.depends("llm_trace_payload")
    def _compute_llm_trace_turn_count(self):
        for record in self:
            trace = record._devtools_load_trace_payload()
            record.llm_trace_turn_count = len(trace.get("turns", []))

    @api.model
    def _devtools_is_llm_trace_enabled(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("mail_discuss_hub_gateway_devtools.llm_trace_enabled", default="0")
        )
        return str(value).lower() in ("1", "true", "yes")

    def _devtools_load_trace_payload(self):
        self.ensure_one()
        if not self.llm_trace_payload:
            return {"turns": []}
        try:
            payload = json.loads(self.llm_trace_payload)
        except Exception:
            payload = {
                "turns": [],
                "legacy_payload": self.llm_trace_payload,
            }
        payload.setdefault("turns", [])
        return payload

    def _devtools_store_trace_payload(self, payload):
        self.ensure_one()
        normalized_payload = self._devtools_normalize_value(payload)
        self.sudo().write(
            {
                "llm_trace_payload": json.dumps(
                    normalized_payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            }
        )

    def _devtools_normalize_value(self, value):
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, dict):
            return {
                str(key): self._devtools_normalize_value(val)
                for key, val in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self._devtools_normalize_value(item) for item in value]
        if hasattr(value, "_name") and hasattr(value, "ids"):
            names = []
            try:
                names = value.mapped("display_name")
            except Exception:
                names = []
            return {
                "model": value._name,
                "ids": list(value.ids),
                "display_names": names,
            }
        return str(value)

    def _devtools_serialize_tool_recordset(self, tools):
        result = []
        for tool in tools:
            result.append(
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                }
            )
        return result

    def _devtools_serialize_message(self, message):
        body_html = str(message.body or "")
        body_text = self.env["mail.gateway.dispatch.service"]._to_plain_text(body_html)
        return {
            "id": message.id,
            "model": message.model,
            "res_id": message.res_id,
            "llm_role": message.llm_role,
            "subtype_id": message.subtype_id.id if message.subtype_id else False,
            "author": {
                "id": message.author_id.id,
                "name": message.author_id.display_name,
            }
            if message.author_id
            else False,
            "body_html": body_html,
            "body_text": body_text,
            "body_json": self._devtools_normalize_value(message.body_json),
            "attachments": [
                {
                    "id": attachment.id,
                    "name": attachment.name,
                    "mimetype": attachment.mimetype,
                }
                for attachment in message.attachment_ids
            ],
        }

    def _devtools_serialize_messages(self, messages):
        return [self._devtools_serialize_message(message) for message in messages]

    def _devtools_build_provider_request(self, thread, chat_kwargs):
        provider = thread.model_id.provider_id.sudo()
        prepend_messages = self._devtools_normalize_value(
            chat_kwargs.get("prepend_messages") or []
        )
        provider_request = {
            "provider": provider.display_name,
            "model": thread.model_id.name,
            "stream": bool(chat_kwargs.get("stream")),
            "prepend_messages": prepend_messages,
        }

        try:
            formatted_messages = provider.format_messages(
                chat_kwargs.get("messages"),
                model=thread.model_id,
            )
            provider_request["formatted_messages"] = self._devtools_normalize_value(
                formatted_messages
            )
            provider_request["messages"] = prepend_messages + self._devtools_normalize_value(
                formatted_messages
            )
        except Exception as exc:
            provider_request["formatted_messages_error"] = str(exc)

        tools = chat_kwargs.get("tools") or self.env["llm.tool"]
        if tools:
            try:
                provider_request["formatted_tools"] = self._devtools_normalize_value(
                    provider.format_tools(tools)
                )
            except Exception as exc:
                provider_request["formatted_tools_error"] = str(exc)

        return provider_request

    def _devtools_capture_llm_request(self, thread, chat_kwargs):
        self.ensure_one()
        if not self._devtools_is_llm_trace_enabled():
            return False

        trace = self._devtools_load_trace_payload()
        trace.setdefault(
            "run",
            {
                "id": self.id,
                "name": self.name,
                "run_type": self.run_type,
                "mode": self.mode,
                "gateway_id": self.gateway_id.id if self.gateway_id else False,
                "channel_id": self.channel_id.id if self.channel_id else False,
                "assistant_id": self.assistant_id.id if self.assistant_id else False,
                "source_message_id": self.source_message_id.id
                if self.source_message_id
                else False,
            },
        )
        trace["thread"] = {
            "id": thread.id,
            "name": thread.name,
            "assistant_id": thread.assistant_id.id if thread.assistant_id else False,
            "prompt_id": thread.prompt_id.id if thread.prompt_id else False,
            "provider_id": thread.provider_id.id if thread.provider_id else False,
            "model_id": thread.model_id.id if thread.model_id else False,
        }
        trace["context"] = self._devtools_normalize_value(thread.get_context())

        turn = {
            "sequence": len(trace["turns"]) + 1,
            "captured_at": fields.Datetime.now(),
            "prompt": {
                "id": thread.prompt_id.id if thread.prompt_id else False,
                "name": thread.prompt_id.display_name if thread.prompt_id else False,
            },
            "tools": self._devtools_serialize_tool_recordset(chat_kwargs.get("tools") or self.env["llm.tool"]),
            "message_history": self._devtools_serialize_messages(
                chat_kwargs.get("messages") or self.env["mail.message"]
            ),
            "provider_request": self._devtools_build_provider_request(thread, chat_kwargs),
        }
        trace["turns"].append(self._devtools_normalize_value(turn))
        trace["updated_at"] = fields.Datetime.now()
        self._devtools_store_trace_payload(trace)
        return True

    def _devtools_capture_llm_response(
        self,
        response=None,
        assistant_message=None,
        stream_chunks=None,
    ):
        self.ensure_one()
        if not self._devtools_is_llm_trace_enabled():
            return False

        trace = self._devtools_load_trace_payload()
        if not trace.get("turns"):
            trace["turns"] = [{"sequence": 1}]

        turn = trace["turns"][-1]
        if response is not None:
            turn["provider_response"] = self._devtools_normalize_value(response)
        if stream_chunks is not None:
            turn["stream_chunks"] = self._devtools_normalize_value(stream_chunks)
        if assistant_message:
            turn["assistant_message"] = self._devtools_serialize_message(
                assistant_message.sudo()
            )
        turn["response_captured_at"] = fields.Datetime.now()
        trace["updated_at"] = fields.Datetime.now()
        self._devtools_store_trace_payload(trace)
        return True
