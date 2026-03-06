import base64
import hashlib
import re
from datetime import datetime, timedelta
from markupsafe import Markup
from odoo import SUPERUSER_ID, api, fields
from odoo.tools import html_escape
from psycopg2 import IntegrityError

class MailGatewayWhatsappCommonUtils:
    def _apply_message_timestamp(self, message, dto):
        """Apply gateway timestamps to preserve chronological ordering."""
        if not message or not dto or not dto.timestamp:
            return
        dt_value = self._normalize_timestamp(dto.timestamp)
        if not dt_value:
            return
        message.sudo().write({"date": dt_value, "write_date": dt_value})
        self._apply_message_create_date(message, dt_value)


    def _render_message_body(self, dto):
        text = (dto.text or "").strip()
        if not text:
            text = (dto.caption or "").strip()
        if not text:
            return ""
        if dto.text_is_html:
            return Markup(text)
        text = self._br_tag_re.sub("\n", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        escaped = html_escape(text)
        return Markup(escaped.replace("\n", Markup("<br/>")))


    def _normalize_timestamp(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return fields.Datetime.from_timestamp(self._normalize_epoch(value))
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return False
            if value.isdigit():
                return fields.Datetime.from_timestamp(self._normalize_epoch(int(value)))
            try:
                float_value = float(value)
            except ValueError:
                float_value = None
            if float_value is not None:
                return fields.Datetime.from_timestamp(self._normalize_epoch(float_value))
            try:
                return fields.Datetime.to_datetime(value)
            except Exception:
                return False
        return False


    def _normalize_epoch(self, value):
        if value is None:
            return value
        if value > 1e11:
            return value / 1000.0
        return value


    def _apply_message_create_date(self, message, dt_value):
        if not message or not dt_value:
            return
        if message.create_date and message.create_date == dt_value:
            return
        try:
            # Direct SQL is needed to update create_date without side effects.
            self.env.cr.execute(
                "UPDATE mail_message SET create_date=%s WHERE id=%s",
                (fields.Datetime.to_string(dt_value), message.id),
            )
            message.invalidate_recordset(["create_date"])
        except Exception:
            self._logger.debug("Failed to update mail.message create_date.", exc_info=True)


    def _find_message_by_external_id(
        self, gateway, message_id, chat_id=None, instance=None
    ):
        message_id = (message_id or "").strip()
        if not message_id:
            return False
        message_model = self.env["mail.message"].sudo()
        if "gateway_message_key" in message_model._fields and gateway:
            key = self._build_message_key_from_values(
                gateway, instance, chat_id, message_id
            )
            if key:
                existing = message_model.search(
                    [("gateway_message_key", "=", key)], limit=1
                )
                if existing:
                    return existing
        existing = self._find_message_alias(
            gateway, message_id, chat_id=chat_id, instance=instance
        )
        if existing:
            return existing
        existing = self._find_message_from_outbound_intent(
            gateway, message_id, chat_id=chat_id, instance=instance
        )
        if existing:
            return existing
        if "gateway_message_external_id" not in message_model._fields:
            return False
        base_domain = [("gateway_message_external_id", "=", message_id)]
        if "gateway_type" in message_model._fields and gateway:
            base_domain.append(("gateway_type", "=", gateway.gateway_type))

        strict_domain = list(base_domain)
        if instance and "gateway_instance" in message_model._fields:
            strict_domain.append(("gateway_instance", "=", instance))
        if chat_id and "gateway_chat_id" in message_model._fields:
            strict_domain.append(("gateway_chat_id", "=", chat_id))
        existing = message_model.search(strict_domain, limit=1)
        if existing:
            return existing

        # Evolution and similar providers may omit instance on outbound and
        # include it on inbound echo. Accept empty instance as a valid match.
        if instance and "gateway_instance" in message_model._fields:
            relaxed_instance_domain = list(base_domain)
            relaxed_instance_domain.append(("gateway_instance", "in", [instance, False]))
            if chat_id and "gateway_chat_id" in message_model._fields:
                relaxed_instance_domain.append(("gateway_chat_id", "=", chat_id))
            existing = message_model.search(relaxed_instance_domain, limit=1)
            if existing:
                return existing

        if chat_id and "gateway_chat_id" in message_model._fields:
            chat_only_domain = list(base_domain)
            chat_only_domain.append(("gateway_chat_id", "=", chat_id))
            existing = message_model.search(chat_only_domain, limit=1)
            if existing:
                return existing

        return message_model.search(base_domain, limit=1)


    def _find_existing_message(self, gateway, dto, message_key=None):
        # Prefer gateway_message_key for strict idempotency when available.
        message_model = self.env["mail.message"].sudo()
        if "gateway_message_key" in message_model._fields:
            message_key = message_key or self._build_message_key(gateway, dto)
            if message_key:
                existing = message_model.search(
                    [("gateway_message_key", "=", message_key)], limit=1
                )
                if existing:
                    return existing
        existing = self._find_message_alias(
            gateway,
            dto.message_id,
            chat_id=dto.chat_id,
            instance=dto.instance,
        )
        if existing:
            return existing
        existing = self._find_message_from_outbound_intent(
            gateway,
            dto.message_id,
            chat_id=dto.chat_id,
            instance=dto.instance,
        )
        if existing:
            return existing
        base_domain = [
            ("gateway_message_external_id", "=", dto.message_id),
            ("gateway_type", "=", gateway.gateway_type),
        ]

        strict_domain = list(base_domain)
        if dto.instance:
            strict_domain.append(("gateway_instance", "=", dto.instance))
        if dto.chat_id:
            strict_domain.append(("gateway_chat_id", "=", dto.chat_id))
        existing = message_model.search(strict_domain, limit=1)
        if existing:
            return existing

        if dto.instance:
            relaxed_instance_domain = list(base_domain)
            relaxed_instance_domain.append(
                ("gateway_instance", "in", [dto.instance, False])
            )
            if dto.chat_id:
                relaxed_instance_domain.append(("gateway_chat_id", "=", dto.chat_id))
            existing = message_model.search(relaxed_instance_domain, limit=1)
            if existing:
                return existing

        if dto.chat_id:
            chat_only_domain = list(base_domain)
            chat_only_domain.append(("gateway_chat_id", "=", dto.chat_id))
            existing = message_model.search(chat_only_domain, limit=1)
            if existing:
                return existing

        return message_model.search(base_domain, limit=1)


    def _find_message_alias(self, gateway, message_id, chat_id=None, instance=None):
        message_id = (message_id or "").strip()
        if not message_id or not gateway or "mail.gateway.message.alias" not in self.env:
            return False
        alias_model = self.env["mail.gateway.message.alias"].sudo()
        message_key = self._build_message_key_from_values(
            gateway, instance, chat_id, message_id
        )
        alias = False
        if message_key:
            alias = alias_model.search(
                [("gateway_message_key", "=", message_key)], limit=1
            )
        if not alias:
            base_domain = [
                ("gateway_id", "=", gateway.id),
                ("gateway_message_external_id", "=", message_id),
            ]
            strict_domain = list(base_domain)
            if instance:
                strict_domain.append(("gateway_instance", "=", instance))
            if chat_id:
                strict_domain.append(("gateway_chat_id", "=", chat_id))
            alias = alias_model.search(strict_domain, limit=1)
            if not alias and instance:
                relaxed_instance_domain = list(base_domain)
                relaxed_instance_domain.append(
                    ("gateway_instance", "in", [instance, False])
                )
                if chat_id:
                    relaxed_instance_domain.append(("gateway_chat_id", "=", chat_id))
                alias = alias_model.search(relaxed_instance_domain, limit=1)
            if not alias and chat_id:
                chat_only_domain = list(base_domain)
                chat_only_domain.append(("gateway_chat_id", "=", chat_id))
                alias = alias_model.search(chat_only_domain, limit=1)
            if not alias:
                alias = alias_model.search(base_domain, limit=1)
        if alias and alias.mail_message_id:
            return alias.mail_message_id.sudo()
        return False


    def _find_message_from_outbound_intent(
        self, gateway, message_id, chat_id=None, instance=None
    ):
        message_id = (message_id or "").strip()
        if (
            not message_id
            or not gateway
            or "mail.gateway.outbound.intent" not in self.env
        ):
            return False
        intent_model = self.env["mail.gateway.outbound.intent"].sudo()
        domain = [
            ("gateway_id", "=", gateway.id),
            ("state", "in", ["pending", "sent", "matched"]),
            "|",
            ("outbound_message_external_id", "=", message_id),
            ("inbound_message_external_id", "=", message_id),
        ]
        if instance:
            domain.extend(
                [
                    "|",
                    ("gateway_instance", "=", instance),
                    ("gateway_instance", "=", False),
                ]
            )
        if chat_id:
            domain.append(("gateway_chat_id", "=", chat_id))
        intent = intent_model.search(domain, order="id desc", limit=1)
        if not intent or not intent.mail_message_ref_id:
            return False
        message = self.env["mail.message"].sudo().browse(intent.mail_message_ref_id).exists()
        if not message:
            return False
        message_key = self._build_message_key_from_values(
            gateway,
            instance or intent.gateway_instance,
            chat_id or intent.gateway_chat_id,
            message_id,
        )
        if message_key and "mail.gateway.message.alias" in self.env:
            alias_model = self.env["mail.gateway.message.alias"].sudo()
            if not alias_model.search([("gateway_message_key", "=", message_key)], limit=1):
                values = {
                    "gateway_id": gateway.id,
                    "gateway_instance": instance or intent.gateway_instance,
                    "gateway_chat_id": chat_id or intent.gateway_chat_id,
                    "gateway_message_external_id": message_id,
                    "gateway_message_key": message_key,
                    "mail_message_id": message.id,
                }
                try:
                    with self.env.cr.savepoint():
                        alias_model.create(values)
                except IntegrityError:
                    pass
        return message


    def _register_message_alias_from_dto(self, message, gateway, dto):
        if (
            not message
            or not gateway
            or not dto
            or "mail.gateway.message.alias" not in self.env
        ):
            return
        message_id = (dto.message_id or "").strip()
        if not message_id:
            return
        message_key = self._build_message_key(gateway, dto)
        if not message_key:
            return
        alias_model = self.env["mail.gateway.message.alias"].sudo()
        existing = alias_model.search([("gateway_message_key", "=", message_key)], limit=1)
        if existing:
            return
        values = {
            "gateway_id": gateway.id,
            "gateway_instance": dto.instance,
            "gateway_chat_id": dto.chat_id,
            "gateway_message_external_id": message_id,
            "gateway_message_key": message_key,
            "mail_message_id": message.id,
        }
        try:
            with self.env.cr.savepoint():
                alias_model.create(values)
        except IntegrityError:
            return


    def _register_outbound_intents(self, gateway, record, dto):
        if (
            not gateway
            or not record
            or not dto
            or "mail.gateway.outbound.intent" not in self.env
        ):
            return []
        message = record.mail_message_id
        if not message or not message.id:
            return []
        chat_id = (dto.chat_id or "").strip()
        if not chat_id:
            return []

        values_list = []
        sequence = 1
        body_key = self._normalize_text_intent_key(dto.text)
        if body_key:
            values_list.append(
                {
                    "gateway_id": gateway.id,
                    "gateway_instance": dto.instance or False,
                    "gateway_chat_id": chat_id,
                    "mail_message_ref_id": message.id,
                    "mail_notification_ref_id": record.id,
                    "intent_type": "text",
                    "sequence": sequence,
                    "body_key": body_key,
                    "expire_at": fields.Datetime.now() + timedelta(minutes=10),
                }
            )
            sequence += 1

        for attachment in dto.attachments or []:
            if not isinstance(attachment, dict):
                continue
            fingerprint = self._attachment_fingerprint_from_outbound_payload(attachment)
            values_list.append(
                {
                    "gateway_id": gateway.id,
                    "gateway_instance": dto.instance or False,
                    "gateway_chat_id": chat_id,
                    "mail_message_ref_id": message.id,
                    "mail_notification_ref_id": record.id,
                    "intent_type": "attachment",
                    "sequence": sequence,
                    "attachment_name": fingerprint["name"],
                    "attachment_size": fingerprint["size"],
                    "attachment_sha1": fingerprint["sha1"],
                    "attachment_mimetype": attachment.get("mimetype") or False,
                    "expire_at": fields.Datetime.now() + timedelta(minutes=10),
                }
            )
            sequence += 1

        return self._create_outbound_intents_autonomous(record.id, values_list)


    def _create_outbound_intents_autonomous(self, notification_id, values_list):
        if not values_list or "mail.gateway.outbound.intent" not in self.env:
            return []
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            intent_model = env["mail.gateway.outbound.intent"].sudo()
            if notification_id:
                old_domain = [
                    ("mail_notification_ref_id", "=", notification_id),
                    ("state", "in", ["pending", "sent"]),
                ]
                intent_model.search(old_domain).unlink()
            intents = intent_model.create(values_list)
            cr.commit()
            return intents.ids


    def _mark_outbound_intents_failed(self, intent_ids):
        if not intent_ids or "mail.gateway.outbound.intent" not in self.env:
            return
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            intents = env["mail.gateway.outbound.intent"].sudo().browse(intent_ids).exists()
            if intents:
                intents.write({"state": "failed"})
            cr.commit()


    def _mark_outbound_intents_sent(self, intent_ids, response_message_ids):
        if not intent_ids or "mail.gateway.outbound.intent" not in self.env:
            return
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            intents = (
                env["mail.gateway.outbound.intent"]
                .sudo()
                .browse(intent_ids)
                .exists()
                .sorted(key=lambda intent: (intent.sequence, intent.id))
            )
            if intents:
                for intent in intents:
                    if intent.state != "matched":
                        intent.state = "sent"
                for index, message_id in enumerate(response_message_ids or []):
                    if index >= len(intents):
                        break
                    intent = intents[index]
                    if not message_id:
                        continue
                    intent.outbound_message_external_id = str(message_id).strip()
            cr.commit()


    def _find_pending_outbound_message_id(self, gateway, dto, body, attachments):
        if (
            not gateway
            or not dto
            or not dto.from_me
            or "mail.gateway.outbound.intent" not in self.env
        ):
            return False
        chat_id = (dto.chat_id or "").strip()
        if not chat_id:
            return False
        intent_model = self.env["mail.gateway.outbound.intent"].sudo()
        now = fields.Datetime.now()
        domain = [
            ("gateway_id", "=", gateway.id),
            ("gateway_chat_id", "=", chat_id),
            ("state", "in", ["pending", "sent", "matched"]),
            (
                "create_date",
                ">=",
                fields.Datetime.to_string(
                    now - timedelta(minutes=3)
                ),
            ),
        ]
        if dto.instance:
            domain.extend(
                [
                    "|",
                    ("gateway_instance", "=", dto.instance),
                    ("gateway_instance", "=", False),
                ]
            )
        intents = intent_model.search(domain, order="id desc", limit=80)
        if not intents:
            return False

        valid_intents = intents.filtered(
            lambda intent: not intent.expire_at or intent.expire_at >= now
        )
        if not valid_intents:
            return False

        if attachments:
            return self._match_pending_attachment_intents(valid_intents, dto, attachments)
        body_key = self._normalize_text_intent_key(body)
        if not body_key:
            return False
        text_intent = valid_intents.filtered(
            lambda intent: intent.intent_type == "text" and intent.body_key == body_key
        )[:1]
        if not text_intent:
            return False
        text_intent.write(
            {
                "state": "matched",
                "inbound_message_external_id": (dto.message_id or "").strip() or False,
                "matched_at": fields.Datetime.now(),
            }
        )
        return text_intent.mail_message_ref_id


    def _match_pending_attachment_intents(self, intents, dto, attachments):
        fingerprints = self._attachment_fingerprints_from_prepared(attachments)
        if not fingerprints:
            return False
        used_intent_ids = set()
        matched = intents.browse()

        for fingerprint in fingerprints:
            candidates = intents.filtered(
                lambda intent: (
                    intent.id not in used_intent_ids
                    and intent.intent_type == "attachment"
                    and self._intent_matches_fingerprint(intent, fingerprint)
                )
            )
            if not candidates:
                return False
            candidate = candidates.sorted(key=lambda intent: intent.id, reverse=True)[:1]
            matched |= candidate
            used_intent_ids.add(candidate.id)

        message_ids = set(matched.mapped("mail_message_ref_id"))
        if len(message_ids) != 1:
            return False
        message_id = list(message_ids)[0]
        matched.write(
            {
                "state": "matched",
                "inbound_message_external_id": (dto.message_id or "").strip() or False,
                "matched_at": fields.Datetime.now(),
            }
        )
        return message_id


    @staticmethod
    def _intent_matches_fingerprint(intent, fingerprint):
        if not intent or not fingerprint:
            return False
        if intent.attachment_sha1 and fingerprint.get("sha1"):
            return intent.attachment_sha1 == fingerprint["sha1"]
        return (
            (intent.attachment_name or "") == (fingerprint.get("name") or "")
            and int(intent.attachment_size or 0) == int(fingerprint.get("size") or 0)
        )


    def _attachment_fingerprint_from_outbound_payload(self, attachment):
        name = self._normalize_attachment_name_for_match(attachment.get("name"))
        payload = attachment.get("datas")
        decoded_size = int(attachment.get("size") or 0)
        digest = False
        if payload:
            try:
                raw = base64.b64decode(payload)
                decoded_size = decoded_size or len(raw)
                digest = hashlib.sha1(raw).hexdigest()
            except Exception:
                digest = False
        return {
            "name": name,
            "size": decoded_size,
            "sha1": digest,
        }


    def _attachment_fingerprints_from_prepared(self, attachments):
        fingerprints = []
        for attachment in attachments or []:
            if not attachment:
                continue
            name = self._normalize_attachment_name_for_match(attachment[0] if len(attachment) > 0 else "")
            data = attachment[1] if len(attachment) > 1 else b""
            data = data or b""
            if isinstance(data, bytearray):
                data = bytes(data)
            if isinstance(data, str):
                data = data.encode("utf-8")
            size = len(data)
            digest = hashlib.sha1(data).hexdigest() if data else False
            fingerprints.append(
                {
                    "name": name,
                    "size": size,
                    "sha1": digest,
                }
            )
        return fingerprints


    @staticmethod
    def _normalize_attachment_name_for_match(name):
        return (name or "").strip().lower()


    def _normalize_text_intent_key(self, body):
        return self._normalize_body_for_dedupe(body)


    def _find_recent_equivalent_message(
        self, gateway, dto, channel, body, attachments, window_seconds=45
    ):
        """Best-effort dedupe for bursty fromMe media echoes with different ids."""
        if not gateway or not dto or not channel or not dto.from_me:
            return False
        if not attachments:
            return False
        target_signature = self._attachment_signature_from_prepared(attachments)
        if not target_signature:
            return False
        target_body = self._normalize_body_for_dedupe(body)
        message_model = self.env["mail.message"].sudo()
        domain = [
            ("model", "=", "discuss.channel"),
            ("res_id", "=", channel.id),
            ("gateway_type", "=", gateway.gateway_type),
            ("gateway_from_me", "=", True),
            (
                "create_date",
                ">=",
                fields.Datetime.to_string(
                    fields.Datetime.now() - timedelta(seconds=window_seconds)
                ),
            ),
        ]
        candidates = message_model.search(domain, order="id desc", limit=25)
        for candidate in candidates:
            if (candidate.gateway_message_external_id or "").strip() == (dto.message_id or "").strip():
                return candidate
            if self._normalize_body_for_dedupe(candidate.body) != target_body:
                continue
            candidate_signature = self._attachment_signature_from_message(candidate)
            if (
                candidate_signature == target_signature
                or self._is_attachment_signature_subset(target_signature, candidate_signature)
            ):
                return candidate
        return False


    @staticmethod
    def _attachment_signature_from_prepared(attachments):
        signature = []
        for attachment in attachments or []:
            if not attachment:
                continue
            name = (attachment[0] or "").strip().lower() if len(attachment) > 0 else ""
            data = attachment[1] if len(attachment) > 1 else b""
            size = len(data or b"")
            signature.append((name, size))
        signature.sort()
        return signature


    @staticmethod
    def _attachment_signature_from_message(message):
        signature = []
        for attachment in message.attachment_ids:
            signature.append(
                (
                    (attachment.name or "").strip().lower(),
                    int(attachment.file_size or 0),
                )
            )
        signature.sort()
        return signature


    @staticmethod
    def _is_attachment_signature_subset(subset, superset):
        if not subset:
            return False
        remaining = list(superset or [])
        for item in subset:
            if item in remaining:
                remaining.remove(item)
                continue
            return False
        return True


    @staticmethod
    def _normalize_body_for_dedupe(body):
        body = str(body or "")
        body = body.replace("&nbsp;", " ")
        body = re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", body)
        body = re.sub(
            r"(?is)</?\s*(?:p|div|section|article|blockquote|li|ul|ol|tr|table|h[1-6])\b[^>]*>",
            "\n",
            body,
        )
        body = re.sub(r"<[^>]+>", "", body)
        body = body.replace("\r\n", "\n").replace("\r", "\n")
        body = re.sub(r"\s+", " ", body)
        return body.strip()


    def _build_message_key(self, gateway, dto):
        """Stable key to dedupe message upserts across retries."""
        if not gateway or not dto:
            return False
        return self._build_message_key_from_values(
            gateway, dto.instance, dto.chat_id, dto.message_id
        )


    def _build_message_key_from_values(self, gateway, instance, chat_id, message_id):
        if not gateway:
            return False
        parts = [
            gateway.gateway_type or "",
            str(gateway.id or ""),
            instance or "",
            chat_id or "",
            message_id or "",
        ]
        return "|".join(parts)


    def _normalize_status(self, status_raw):
        status = (status_raw or "").strip().lower()
        if not status:
            return False
        compact = status.replace("_", "").replace(" ", "").replace("-", "")
        if compact in {"read", "readself", "seen"}:
            return "read"
        if compact in {"readack"}:
            return "read"
        if compact in {"delivered"}:
            return "delivered"
        if compact in {"deliveryack"}:
            return "delivered"
        if compact in {"sent"}:
            return "sent"
        if compact in {"serverack"}:
            return "sent"
        if compact in {"failed", "error", "exception", "canceled", "cancelled"}:
            return "failed"
        if compact in {"pending", "processing", "process"}:
            return "pending"
        return False


    def _status_rank(self, status):
        rank = {
            "pending": 1,
            "sent": 2,
            "delivered": 3,
            "read": 4,
            "failed": 99,
        }
        return rank.get(status or "", 0)


    def _should_update_status(self, current, incoming):
        if not incoming:
            return False
        if not current:
            return True
        return self._status_rank(incoming) >= self._status_rank(current)


    def _notification_status_rank(self, status):
        rank = {
            "ready": 0,
            "process": 0,
            "pending": 1,
            "sent": 2,
            "bounce": 98,
            "exception": 99,
            "canceled": -1,
        }
        return rank.get(status or "", 0)


    def _map_notification_status(self, normalized):
        if normalized == "pending":
            return "pending"
        if normalized in {"sent", "delivered", "read"}:
            return "sent"
        if normalized == "failed":
            return "exception"
        return False


    def _update_gateway_notification_status(
        self, gateway, message_id, normalized, status_raw
    ):
        notification_model = self.env["mail.notification"].sudo()
        if "gateway_message_id" not in notification_model._fields:
            return 0
        domain = [("gateway_message_id", "=", message_id)]
        if "gateway_type" in notification_model._fields and gateway:
            domain.append(("gateway_type", "=", gateway.gateway_type))
        notifications = notification_model.search(domain)
        if not notifications:
            return 0
        mapped_status = self._map_notification_status(normalized)
        updated = 0
        for notification in notifications:
            update_vals = {}
            if mapped_status:
                if self._notification_status_rank(mapped_status) >= self._notification_status_rank(
                    notification.notification_status
                ):
                    update_vals["notification_status"] = mapped_status
            if (
                normalized == "failed"
                and status_raw
                and "gateway_failure_reason" in notification._fields
            ):
                update_vals["gateway_failure_reason"] = status_raw
            read_updated = False
            if normalized == "read" and hasattr(notification, "_set_read_gateway"):
                notification._set_read_gateway()
                read_updated = True
            if update_vals:
                notification.write(update_vals)
                updated += 1
            elif read_updated:
                updated += 1
        return updated


    def _build_deleted_body(self, body):
        body_text = str(body or "")
        if not body_text:
            return Markup("<p><s>This message was deleted</s> <em>(mensagem apagada)</em></p>")
        if "<s>" in body_text or "<del>" in body_text:
            return body_text
        updated = re.sub(
            r"(<p[^>]*>)(.*?)(</p>)",
            lambda m: f"{m.group(1)}<s>{m.group(2)}</s> <em>(mensagem apagada)</em>{m.group(3)}",
            body_text,
            flags=re.DOTALL,
        )
        if updated != body_text:
            return Markup(updated)
        return Markup(f"<p><s>{body_text}</s> <em>(mensagem apagada)</em></p>")


    @staticmethod
    def _is_group_chat(chat_id):
        return str(chat_id or "").endswith("@g.us")

    @classmethod
    def _format_group_name(cls, chat_id):
        return f"Grupo {cls._format_chat_id(chat_id)}"

    @staticmethod
    def _format_chat_id(chat_id):
        chat_id = str(chat_id or "").strip()
        if "@" in chat_id:
            return chat_id.split("@", 1)[0]
        return chat_id
