# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import hashlib
import hmac
import logging
import re
from datetime import datetime

import requests

from odoo import _, models
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.mail_gateway_whatsapp_common.models.normalized_payload import (
    NormalizedPayload,
)

_logger = logging.getLogger(__name__)


class MailGatewayWhatsappWaha(models.AbstractModel):
    _name = "mail.gateway.whatsapp_waha"
    _inherit = "mail.gateway.abstract"
    _description = "WhatsApp WAHA Gateway"
    _uses_gateway_common = True

    def _receive_get_update(self, bot_data, req, **kwargs):
        response = request.make_response(
            "{}",
            [
                ("Content-Type", "application/json"),
            ],
        )
        response.status_code = 200
        return response

    def _receive_update(self, gateway, update):
        payload = update.get("payload") or {}
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        canonical_event = self._normalize_event(update, payload)
        if not canonical_event:
            return {"status": "ignored", "reason": "event_not_supported"}
        if update.get("event") == "engine.event" and isinstance(payload, dict):
            payload = payload.get("data") or {}
            if isinstance(payload, list):
                payload = payload[0] if payload else {}
        if not payload:
            return {"status": "ignored", "reason": "missing_payload"}
        dto = self._build_message_dto(update, gateway, payload, canonical_event)
        if not dto:
            return {"status": "ignored", "reason": "normalization_failed"}
        common = self.env["mail.gateway.whatsapp.common"]
        return common._process_normalized(gateway, dto, None, author=None)

    def _verify_update(self, bot_data, kwargs):
        gateway = self.env["mail.gateway"].browse(bot_data.get("id"))
        secret = gateway.webhook_secret if gateway else None
        if not secret:
            return True
        signature = request.httprequest.headers.get("X-Webhook-Hmac")
        if not signature:
            return False
        algorithm = request.httprequest.headers.get("X-Webhook-Hmac-Algorithm", "sha256")
        if algorithm.lower() != "sha256":
            return False
        digest = hmac.new(
            secret.encode("utf-8"),
            request.httprequest.data,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, digest)

    def _set_webhook(self, gateway):
        self._ensure_gateway_ready(gateway)
        session = gateway.waha_session or "default"
        payload = {"config": {"webhooks": [self._build_webhook_config(gateway)]}}
        self._send_api_request(gateway, "PUT", f"/api/sessions/{session}", payload)
        gateway.integrated_webhook_state = "integrated"

    def _remove_webhook(self, gateway):
        if not gateway.waha_api_url or not gateway.token:
            gateway.integrated_webhook_state = False
            return
        session = gateway.waha_session or "default"
        payload = {"config": {"webhooks": []}}
        try:
            self._send_api_request(gateway, "PUT", f"/api/sessions/{session}", payload)
        except Exception as exc:
            _logger.warning("Failed to disable WAHA webhook: %s", exc)
        gateway.integrated_webhook_state = False

    def _send(
        self,
        gateway,
        record,
        auto_commit=False,
        raise_exception=False,
        parse_mode=False,
    ):
        common = self.env["mail.gateway.whatsapp.common"]
        return common._send_outbound(
            gateway,
            record,
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            parse_mode=parse_mode,
            provider=self,
        )

    def _send_outbound_text(self, gateway, dto, body):
        self._ensure_gateway_ready(gateway)
        session = gateway.waha_session or "default"
        chat_id = self._normalize_chat_id(dto.chat_id)
        payload = {
            "session": session,
            "chatId": chat_id,
            "text": (body or "").strip(),
        }
        response = requests.post(
            self._join_url(gateway.waha_api_url, "/api/sendText"),
            json=payload,
            headers=self._get_headers(gateway),
            timeout=20,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def _send_outbound_attachment(self, gateway, dto, attachment):
        raise UserError(_("WAHA media sending is not supported yet."))

    def _send_outbound(self, gateway, dto):
        # Kept for direct calls, though common orchestration is the canonical path.
        self._ensure_gateway_ready(gateway)
        session = gateway.waha_session or "default"
        chat_id = self._normalize_chat_id(dto.chat_id)
        if dto.attachments:
            raise UserError(_("WAHA media sending is not supported yet."))
        body = (dto.text or "").strip()
        if not body:
            raise UserError(_("Message body is empty."))
        message = self._send_outbound_text(gateway, dto, body)
        return {
            "message_id": self._extract_message_id_from_response(message),
            "instance": session,
            "chat_id": chat_id,
            "responses": [message] if message else [],
        }

    def _send_reaction_outbound(
        self,
        gateway,
        message,
        reaction,
        action,
        chat_id=None,
        message_external_id=None,
        instance=None,
    ):
        return {"status": "ignored", "reason": "reaction_not_supported"}

    def _ensure_gateway_ready(self, gateway):
        if not gateway.waha_api_url or not gateway.token:
            raise UserError(_("WAHA API URL and API key are required."))

    def _get_headers(self, gateway):
        return {
            "Content-Type": "application/json",
            "X-Api-Key": gateway.token,
        }

    def _join_url(self, base_url, endpoint):
        return f"{(base_url or '').rstrip('/')}/{endpoint.lstrip('/')}"

    def _normalize_chat_id(self, chat_id):
        if not chat_id:
            return ""
        chat_id = chat_id.strip()
        if "@" in chat_id:
            return chat_id
        digits = re.sub(r"\D", "", chat_id)
        if digits:
            return f"{digits}@c.us"
        return chat_id

    def _normalize_event(self, update, payload=None):
        event = (update.get("event") or "").strip().lower()
        if event in ("message", "message.any"):
            return "message.upsert"
        if event == "engine.event":
            engine_event = (payload or {}).get("event") or ""
            engine_event = engine_event.strip().lower()
            if engine_event in ("message_create", "message"):
                return "message.upsert"
        return None

    def _build_message_dto(self, update, gateway, payload, canonical_event):
        message_id = self._extract_message_id(payload)
        from_me = bool(payload.get("fromMe"))
        chat_id = self._get_chat_id(payload, from_me)
        if not message_id or not chat_id:
            return False
        is_group = chat_id.endswith("@g.us")
        reply_to = payload.get("replyTo") or {}
        sender_jid = self._get_sender_jid(payload, chat_id, is_group)
        sender_participant = payload.get("author") or payload.get("participant")
        return NormalizedPayload(
            provider="waha",
            instance=update.get("session"),
            event=canonical_event,
            message_id=message_id,
            chat_id=chat_id,
            is_group=is_group,
            from_me=from_me,
            sender_jid=sender_jid,
            sender_participant_jid=sender_participant,
            sender_name=self._get_sender_name(payload),
            timestamp=self._coerce_timestamp(
                payload.get("timestamp") or update.get("timestamp")
            ),
            message_type=self._get_message_type(payload),
            text=payload.get("body"),
            quote_id=reply_to.get("id"),
            quote_text=reply_to.get("body"),
            raw=update,
        )

    def _coerce_timestamp(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if value > 1e11:
                value = value / 1000.0
            return datetime.utcfromtimestamp(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if value.isdigit():
                numeric = int(value)
                if numeric > 1e11:
                    numeric = numeric / 1000.0
                return datetime.utcfromtimestamp(numeric)
        return value

    def _extract_message_id(self, payload):
        if not isinstance(payload, dict):
            return False
        candidates = [
            payload.get("id"),
            (payload.get("_data") or {}).get("id"),
        ]
        for candidate in candidates:
            if isinstance(candidate, dict):
                for key in ("_serialized", "id"):
                    value = candidate.get(key)
                    if value:
                        return value
            elif isinstance(candidate, str):
                value = candidate.strip()
                if value:
                    return value
        return False

    def _get_chat_id(self, payload, from_me):
        if from_me:
            return payload.get("to") or payload.get("from")
        return payload.get("from") or payload.get("to")

    def _get_sender_jid(self, payload, chat_id, is_group):
        if is_group:
            return payload.get("author") or payload.get("participant") or chat_id
        return payload.get("from") or chat_id

    def _get_sender_name(self, payload):
        data = payload.get("_data") or {}
        for key in ("notifyName", "pushname", "senderName", "name"):
            value = data.get(key)
            if value:
                return value
        return None

    def _get_message_type(self, payload):
        data = payload.get("_data") or {}
        return data.get("type") or payload.get("type")

    def _extract_message_id_from_response(self, payload):
        if not payload:
            return False
        if isinstance(payload, dict):
            candidates = [
                payload.get("_data", {}).get("id", {}).get("_serialized"),
                payload.get("id", {}).get("_serialized"),
                payload.get("_data", {}).get("id", {}).get("id"),
                payload.get("id", {}).get("id"),
                payload.get("id"),
                payload.get("messageId"),
            ]
            for candidate in candidates:
                if candidate:
                    return candidate
        return False

    def _get_webhook_events(self, gateway):
        return gateway._get_waha_webhook_events()

    def _build_webhook_config(self, gateway):
        webhook = {
            "url": gateway._get_webhook_url(),
            "events": self._get_webhook_events(gateway),
        }
        if gateway.webhook_secret:
            webhook["hmac"] = {"key": gateway.webhook_secret}
        return webhook

    def _send_api_request(self, gateway, method, endpoint, payload=None):
        url = self._join_url(gateway.waha_api_url, endpoint)
        response = requests.request(
            method,
            url,
            json=payload,
            headers=self._get_headers(gateway),
            timeout=20,
        )
        response.raise_for_status()
        return response.json() if response.content else {}
