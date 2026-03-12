# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import re

from odoo import models

_logger = logging.getLogger(__name__)
_NON_DIGIT_RE = re.compile(r"\D+")


class MailGatewayLLMIdentityResolver(models.AbstractModel):
    _name = "mail.gateway.llm.identity.resolver"
    _description = "Mail Gateway LLM Identity Resolver"

    def resolve_from_context(self):
        run_id = self.env.context.get("mail_gateway_llm_run_id")
        if not run_id:
            return self._empty_identity("missing_run_context")

        run = self.env["mail.gateway.llm.run"].sudo().browse(run_id).exists()
        if not run:
            return self._empty_identity("run_not_found")

        return self.resolve(run)

    def resolve(self, run):
        run = run.sudo().exists()
        if not run:
            return self._empty_identity("run_not_found")

        source = run.source_message_id.sudo()
        gateway = run.gateway_id.sudo()
        guest = source.author_guest_id.sudo().exists()
        metadata = self._collect_metadata(source, guest, run.payload_json)

        partner = self._trusted_author_partner(source, gateway)
        if partner:
            return self._identity_payload(
                run=run,
                partner=partner,
                guest=guest,
                guest_token=metadata["guest_token"],
                guest_phone=metadata["guest_phone"],
                confidence="high",
                resolution_method="author_id",
                needs_verification=False,
            )

        partner_candidate, resolution_method = self._resolve_partner_candidate(
            gateway,
            guest=guest,
            metadata=metadata,
        )
        if partner_candidate:
            return self._identity_payload(
                run=run,
                partner=partner_candidate,
                guest=guest,
                guest_token=metadata["guest_token"],
                guest_phone=metadata["guest_phone"],
                confidence="medium",
                resolution_method=resolution_method,
                needs_verification=True,
            )

        if guest:
            return self._identity_payload(
                run=run,
                guest=guest,
                guest_token=metadata["guest_token"],
                guest_phone=metadata["guest_phone"],
                confidence="low",
                resolution_method="guest_only",
                needs_verification=True,
            )

        return self._empty_identity(
            "unresolved",
            run=run,
            guest=guest,
            guest_token=metadata["guest_token"],
            guest_phone=metadata["guest_phone"],
        )

    def _resolve_partner_candidate(self, gateway, *, guest=False, metadata=None):
        metadata = metadata or {"token_candidates": [], "phone_candidates": []}
        partner = self._match_gateway_channel(
            gateway,
            metadata.get("token_candidates", []),
        )
        if partner:
            return partner, "guest_gateway_match" if guest else "message_gateway_match"

        partner = self._match_partner_from_phone(metadata.get("phone_candidates", []))
        if partner:
            return partner, "guest_metadata_match" if guest else "message_metadata_match"

        partner = self._match_gateway_channel_normalized(
            gateway,
            metadata.get("token_candidates", []),
            metadata.get("phone_candidates", []),
        )
        if partner:
            return partner, "guest_metadata_match" if guest else "message_metadata_match"

        return self.env["res.partner"], False

    def _trusted_author_partner(self, source, gateway):
        partner = source.author_id.sudo().exists()
        if not partner:
            return self.env["res.partner"]

        webhook_partner = gateway.webhook_user_id.partner_id.sudo().exists()
        if webhook_partner and partner == webhook_partner:
            return self.env["res.partner"]

        if "gateway_from_me" in source._fields and source.gateway_from_me:
            return self.env["res.partner"]

        return partner

    def _collect_metadata(self, source, guest=False, payload=None):
        token_candidates = []
        phone_candidates = []

        guest_token = self._record_value(guest, "gateway_token")
        guest_phone = self._extract_phone(self._record_value(guest, "gateway_phone"))
        self._append_token(token_candidates, guest_token)
        self._append_phone(phone_candidates, guest_phone)

        for field_name in ("gateway_sender_jid", "gateway_chat_id", "gateway_message_key"):
            candidate = self._record_value(source, field_name)
            self._append_token(token_candidates, candidate)
            self._append_phone(phone_candidates, self._extract_phone(candidate))

        payload_candidates = []
        self._collect_payload_candidates(payload or {}, payload_candidates)
        for candidate in payload_candidates:
            self._append_token(token_candidates, candidate)
            self._append_phone(phone_candidates, self._extract_phone(candidate))

        if not guest_token and token_candidates:
            guest_token = token_candidates[0]
        if not guest_phone and phone_candidates:
            guest_phone = phone_candidates[0]

        return {
            "guest_token": guest_token or False,
            "guest_phone": guest_phone or False,
            "token_candidates": token_candidates,
            "phone_candidates": phone_candidates,
        }

    def _collect_payload_candidates(self, value, bucket):
        if isinstance(value, dict):
            interesting_keys = {
                "sender",
                "sender_id",
                "sender_jid",
                "sender_jid_alt",
                "senderJid",
                "senderJidAlt",
                "remoteJid",
                "remoteJidAlt",
                "chat_id",
                "chatId",
                "from",
                "fromNumber",
                "participant",
                "participantAlt",
                "phone",
                "number",
                "gateway_token",
            }
            for key, candidate in value.items():
                if key in interesting_keys:
                    self._append_token(bucket, candidate)
                self._collect_payload_candidates(candidate, bucket)
            return
        if isinstance(value, list):
            for item in value:
                self._collect_payload_candidates(item, bucket)

    def _match_gateway_channel(self, gateway, token_candidates):
        if not gateway or not token_candidates:
            return self.env["res.partner"]

        gateway_channels = self.env["res.partner.gateway.channel"].sudo().search(
            [
                ("gateway_id", "=", gateway.id),
                ("gateway_token", "in", token_candidates),
            ]
        )
        return self._unique_partner(
            gateway_channels.mapped("partner_id"),
            "Exact gateway token match",
            gateway.id,
        )

    def _match_partner_from_phone(self, phone_candidates):
        partner_model = self.env["res.partner"]
        if "gateway_phone" not in partner_model._fields or not phone_candidates:
            return partner_model

        partners = partner_model.sudo().search(
            [("gateway_phone", "in", phone_candidates)]
        )
        return self._unique_partner(partners, "Partner gateway phone match")

    def _match_gateway_channel_normalized(
        self,
        gateway,
        token_candidates,
        phone_candidates,
    ):
        if not gateway:
            return self.env["res.partner"]

        normalized_candidates = {
            self._normalize_token(value)
            for value in [*(token_candidates or []), *(phone_candidates or [])]
            if self._normalize_token(value)
        }
        if not normalized_candidates:
            return self.env["res.partner"]

        channels = self.env["res.partner.gateway.channel"].sudo().search(
            [("gateway_id", "=", gateway.id), ("gateway_token", "!=", False)]
        )
        partners = channels.filtered(
            lambda channel: self._normalize_token(channel.gateway_token)
            in normalized_candidates
        ).mapped("partner_id")
        return self._unique_partner(
            partners,
            "Normalized gateway token match",
            gateway.id,
        )

    def _unique_partner(self, partners, label, gateway_id=False):
        partners = partners.sudo().exists()
        if len(partners) == 1:
            return partners
        if len(partners) > 1:
            _logger.warning(
                "%s produced multiple partners for gateway %s: %s",
                label,
                gateway_id or "-",
                partners.ids,
            )
        return self.env["res.partner"]

    def _identity_payload(
        self,
        *,
        run,
        partner=False,
        guest=False,
        guest_token=False,
        guest_phone=False,
        confidence,
        resolution_method,
        needs_verification,
    ):
        partner = partner.sudo().exists() if partner else self.env["res.partner"]
        guest = guest.sudo().exists() if guest else self.env["mail.guest"]
        gateway = run.gateway_id.sudo()
        company = gateway.company_id.sudo()
        channel = run.channel_id.sudo()
        source = run.source_message_id.sudo()
        return {
            "run_id": run.id,
            "run": run,
            "channel_id": channel.id,
            "channel": channel,
            "gateway_id": gateway.id,
            "gateway": gateway,
            "company_id": company.id if company else False,
            "company": company,
            "source_message_id": source.id,
            "source_message": source,
            "resolved_partner_id": partner.id if partner else False,
            "resolved_partner": partner,
            "partner_id": partner.id if partner else False,
            "partner": partner,
            "guest_id": guest.id if guest else False,
            "guest": guest,
            "guest_token": guest_token or False,
            "guest_phone": guest_phone or False,
            "confidence": confidence,
            "resolution_method": resolution_method,
            "needs_verification": needs_verification,
            "identified": bool(partner),
        }

    def _empty_identity(
        self,
        resolution_method,
        *,
        run=False,
        guest=False,
        guest_token=False,
        guest_phone=False,
    ):
        if run:
            return self._identity_payload(
                run=run,
                guest=guest,
                guest_token=guest_token,
                guest_phone=guest_phone,
                confidence="none",
                resolution_method=resolution_method,
                needs_verification=True,
            )
        return {
            "run_id": False,
            "run": self.env["mail.gateway.llm.run"],
            "channel_id": False,
            "channel": self.env["discuss.channel"],
            "gateway_id": False,
            "gateway": self.env["mail.gateway"],
            "company_id": False,
            "company": self.env["res.company"],
            "source_message_id": False,
            "source_message": self.env["mail.message"],
            "resolved_partner_id": False,
            "resolved_partner": self.env["res.partner"],
            "partner_id": False,
            "partner": self.env["res.partner"],
            "guest_id": guest.id if guest else False,
            "guest": guest or self.env["mail.guest"],
            "guest_token": guest_token or False,
            "guest_phone": guest_phone or False,
            "confidence": "none",
            "resolution_method": resolution_method,
            "needs_verification": True,
            "identified": False,
        }

    def _record_value(self, record, field_name):
        if not record or field_name not in record._fields:
            return False
        return getattr(record, field_name) or False

    def _append_token(self, bucket, value):
        normalized = self._normalize_token(value)
        if normalized and normalized not in bucket:
            bucket.append(normalized)

    def _append_phone(self, bucket, value):
        normalized = self._extract_phone(value)
        if normalized and normalized not in bucket:
            bucket.append(normalized)

    def _normalize_token(self, value):
        if value in (False, None):
            return False
        if isinstance(value, dict):
            for key in ("id", "jid", "value", "phone", "number"):
                if value.get(key):
                    return self._normalize_token(value[key])
            return False
        value = str(value).strip()
        if not value:
            return False
        return value.lower()

    def _extract_phone(self, value):
        if value in (False, None):
            return False
        if isinstance(value, dict):
            for key in ("phone", "number", "id", "jid", "value"):
                if value.get(key):
                    return self._extract_phone(value[key])
            return False
        value = str(value).strip()
        if not value:
            return False
        if "@" in value:
            value = value.split("@", 1)[0]
        digits = _NON_DIGIT_RE.sub("", value)
        return digits if len(digits) >= 6 else False
