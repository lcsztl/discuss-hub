import html as std_html
import re

from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.tools import html2plaintext
from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure
from .outbound_payload import OutboundPayload

class MailGatewayWhatsappCommonOutbound:
    _html_tag_re = re.compile(r"(?is)<\s*/?\s*[a-zA-Z][^>]*>")

    _span_bold_re = re.compile(
        r'(?is)<span\b[^>]*font-weight\s*:\s*(?:bold|[5-9]00)[^>]*>(.*?)</span>'
    )
    _span_italic_re = re.compile(
        r'(?is)<span\b[^>]*font-style\s*:\s*italic[^>]*>(.*?)</span>'
    )
    _span_strike_re = re.compile(
        r'(?is)<span\b[^>]*text-decoration[^>]*line-through[^>]*>(.*?)</span>'
    )
    _script_style_re = re.compile(
        r"(?is)<\s*(script|style)\b[^>]*>.*?<\s*/\s*(script|style)\s*>"
    )
    _comment_re = re.compile(r"(?is)<!--.*?-->")
    _li_open_re = re.compile(r"(?is)<\s*li\b[^>]*>")
    _li_close_re = re.compile(r"(?is)</\s*li\s*>")
    _br_re = re.compile(r"(?is)<\s*br\s*/?\s*>")
    _block_tags_re = re.compile(
        r"(?is)</?\s*(?:p|div|section|article|header|footer|blockquote|ul|ol|"
        r"table|thead|tbody|tfoot|tr|h[1-6]|pre)\b[^>]*>"
    )
    _bold_open_re = re.compile(r"(?is)<\s*(?:strong|b)\b[^>]*>")
    _bold_close_re = re.compile(r"(?is)</\s*(?:strong|b)\s*>")
    _italic_open_re = re.compile(r"(?is)<\s*(?:em|i)\b[^>]*>")
    _italic_close_re = re.compile(r"(?is)</\s*(?:em|i)\s*>")
    _strike_open_re = re.compile(r"(?is)<\s*(?:s|del)\b[^>]*>")
    _strike_close_re = re.compile(r"(?is)</\s*(?:s|del)\s*>")
    _remaining_tags_re = re.compile(r"(?is)<[^>]+>")
    _leading_space_line_re = re.compile(r"[ \t]+\n")
    _trailing_space_line_re = re.compile(r"\n[ \t]+")
    _multi_spaces_re = re.compile(r"[ \t]{2,}")
    _multi_breaks_re = re.compile(r"\n{3,}")

    def _get_outbound_provider(self, gateway):
        if not gateway or not gateway.gateway_type:
            return False
        model_name = f"mail.gateway.{gateway.gateway_type}"
        if model_name not in self.env:
            return False
        provider = self.env[model_name]
        if getattr(provider, "_uses_gateway_common", False):
            return provider
        return False


    def _send_outbound(
        self,
        gateway,
        record,
        auto_commit=False,
        raise_exception=False,
        parse_mode=False,
        provider=None,
    ):
        if not gateway or not record:
            return {"status": "ignored", "reason": "missing_gateway_or_record"}
        provider = provider or self._get_outbound_provider(gateway)
        if provider is False:
            return {"status": "ignored", "reason": "provider_not_supported"}
        if hasattr(gateway, "_reopen_channel_if_needed") and hasattr(
            record, "gateway_channel_id"
        ):
            channel = record.gateway_channel_id
            if channel:
                reopened_by = getattr(record, "author_id", False)
                if not reopened_by and hasattr(record, "mail_message_id"):
                    reopened_by = record.mail_message_id.author_id
                if not reopened_by:
                    reopened_by = self.env.user.partner_id
                gateway._reopen_channel_if_needed(channel, reopened_by=reopened_by)
        dto = self._build_outbound_dto(gateway, record)
        if not dto:
            return self._handle_outbound_failure(
                record, "payload_not_built", raise_exception
            )
        if not dto.has_text() and not dto.has_attachments():
            return self._handle_outbound_failure(
                record, "empty_body", raise_exception
            )
        intent_ids = self._register_outbound_intents(gateway, record, dto)
        try:
            result = self._send_outbound_parts(provider, gateway, dto)
        except Exception as exc:
            self._logger.exception("Unable to send gateway message")
            self._mark_outbound_intents_failed(intent_ids)
            if raise_exception:
                raise
            self._write_outbound_failure(record, str(exc))
            return {"status": "exception", "error": str(exc)}
        try:
            self._write_outbound_success(
                record,
                gateway,
                dto,
                result,
                intent_ids=intent_ids,
            )
        except Exception:
            self._mark_outbound_intents_failed(intent_ids)
            raise
        if auto_commit:
            record._cr.commit()
        return result or {"status": "sent"}

    def _send_outbound_parts(self, provider, gateway, dto):
        responses = []
        text_payload = False

        body = (dto.text or "").strip()
        if body:
            text_payload = self._send_outbound_text_part(
                provider,
                gateway,
                dto,
                body,
            )
            if text_payload:
                responses.append(text_payload)

        for attachment in dto.attachments or []:
            if not isinstance(attachment, dict):
                continue
            attachment_payload = self._send_outbound_attachment_part(
                provider,
                gateway,
                dto,
                attachment,
            )
            if attachment_payload:
                responses.append(attachment_payload)

        tracked_payload = text_payload or (responses[-1] if responses else False)
        return {
            "message_id": self._extract_message_id_from_payload(tracked_payload),
            "instance": dto.instance,
            "chat_id": dto.chat_id,
            "responses": responses,
        }

    def _send_outbound_text_part(self, provider, gateway, dto, body):
        sender = getattr(provider, "_send_outbound_text", None)
        if not callable(sender):
            raise MailDeliveryException(
                "Provider '%s' must implement _send_outbound_text."
                % (getattr(provider, "_name", "unknown"))
            )
        return sender(gateway, dto, body)

    def _send_outbound_attachment_part(self, provider, gateway, dto, attachment):
        sender = getattr(provider, "_send_outbound_attachment", None)
        if not callable(sender):
            raise MailDeliveryException(
                "Provider '%s' must implement _send_outbound_attachment."
                % (getattr(provider, "_name", "unknown"))
            )
        return sender(gateway, dto, attachment)


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
        if not gateway or not message or not reaction:
            return {"status": "ignored", "reason": "missing_payload"}
        provider = self._get_outbound_provider(gateway)
        if provider is False:
            return {"status": "ignored", "reason": "provider_not_supported"}
        message_external_id = message_external_id or message.gateway_message_external_id
        chat_id = chat_id or message.gateway_chat_id
        instance = instance or message.gateway_instance
        if not message_external_id or not chat_id:
            return {"status": "ignored", "reason": "missing_target"}
        if not hasattr(provider, "_send_reaction_outbound"):
            return {"status": "ignored", "reason": "provider_no_reaction"}
        try:
            return provider._send_reaction_outbound(
                gateway,
                message=message,
                reaction=reaction,
                action=action,
                chat_id=chat_id,
                message_external_id=message_external_id,
                instance=instance,
            )
        except Exception as exc:
            self._logger.exception("Unable to send gateway reaction")
            return {"status": "exception", "error": str(exc)}


    def _handle_outbound_failure(self, record, reason, raise_exception):
        message = self._format_outbound_failure(reason)
        if raise_exception:
            raise MailDeliveryException(message)
        self._write_outbound_failure(record, message)
        return {"status": "exception", "error": message, "reason": reason}

    @staticmethod
    def _format_outbound_failure(reason):
        if reason == "empty_body":
            return "Outbound message is empty."
        if reason == "payload_not_built":
            return "Outbound payload could not be built."
        return str(reason)


    def _build_outbound_dto(self, gateway, record):
        message = record.mail_message_id
        channel = record.gateway_channel_id
        if not message or not channel:
            return False
        body = self._to_whatsapp_text(message.body or "")
        author_name = message.author_id.name or message.author_guest_id.name or False
        dto = OutboundPayload(
            provider=gateway.gateway_type,
            gateway_type=gateway.gateway_type,
            notification_id=record.id,
            message_id=message.id,
            chat_id=channel.gateway_channel_token,
            text=(body or "").strip(),
            author_name=author_name,
            attachments=self._prepare_outbound_attachments(message),
        )
        if (
            dto
            and dto.text
            and gateway
            and hasattr(gateway, "_apply_outgoing_signature")
        ):
            dto.text = gateway._apply_outgoing_signature(dto.author_name, dto.text)
        return dto

    def _to_whatsapp_text(self, body):
        text = html2plaintext(body or "") or ""
        if text and self._html_tag_re.search(text):
            text = self._sanitize_html_like_text(text)
        return self._normalize_whatsapp_text(text)

    def _sanitize_html_like_text(self, text):
        text = std_html.unescape(text or "")
        if not text:
            return ""

        text = self._script_style_re.sub("", text)
        text = self._comment_re.sub("", text)

        text = self._span_bold_re.sub(r"*\1*", text)
        text = self._span_italic_re.sub(r"_\1_", text)
        text = self._span_strike_re.sub(r"~\1~", text)

        text = self._li_open_re.sub("\n- ", text)
        text = self._li_close_re.sub("", text)
        text = self._br_re.sub("\n", text)
        text = self._block_tags_re.sub("\n", text)

        text = self._bold_open_re.sub("*", text)
        text = self._bold_close_re.sub("*", text)
        text = self._italic_open_re.sub("_", text)
        text = self._italic_close_re.sub("_", text)
        text = self._strike_open_re.sub("~", text)
        text = self._strike_close_re.sub("~", text)

        text = self._remaining_tags_re.sub("", text)
        return std_html.unescape(text)

    def _normalize_whatsapp_text(self, text):
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        text = self._leading_space_line_re.sub("\n", text)
        text = self._trailing_space_line_re.sub("\n", text)
        text = self._multi_spaces_re.sub(" ", text)
        text = self._multi_breaks_re.sub("\n\n", text)
        return text.strip()


    def _prepare_outbound_attachments(self, message):
        attachments = []
        for attachment in message.attachment_ids:
            payload = self._attachment_datas_to_base64(attachment)
            if not payload:
                continue
            attachments.append(
                {
                    "id": attachment.id,
                    "name": attachment.name or "attachment",
                    "mimetype": attachment.mimetype,
                    "datas": payload,
                    "size": attachment.file_size,
                }
            )
        return attachments

    def _write_outbound_failure(self, record, error_message):
        if not record:
            return
        record.sudo().write(
            {
                "notification_status": "exception",
                "failure_reason": error_message,
            }
        )


    def _write_outbound_success(
        self, record, gateway, dto, result, intent_ids=None
    ):
        record.sudo().write(
            {
                "notification_status": "sent",
                "failure_reason": False,
            }
        )
        instance = dto.instance
        chat_id = dto.chat_id
        message_id = False
        message_ids = []
        intents_marked = False
        if isinstance(result, dict):
            message_id = result.get("message_id") or result.get("id")
            instance = result.get("instance") or instance
            chat_id = result.get("chat_id") or chat_id
            message_ids = self._collect_outbound_message_ids(result)
            ordered_response_ids = self._collect_ordered_response_message_ids(result)
            self._mark_outbound_intents_sent(intent_ids, ordered_response_ids)
            intents_marked = True
        if not message_id and message_ids:
            message_id = message_ids[0]
        elif isinstance(message_id, list):
            message_id = message_id[0] if message_id else False
        if message_id:
            self._update_outgoing_message(
                record,
                gateway,
                message_id,
                instance,
                chat_id,
                sender_name=dto.author_name,
                message_ids=message_ids,
            )
        elif intent_ids and not intents_marked:
            # Keep intents in sent state even when provider returns only response list.
            self._mark_outbound_intents_sent(intent_ids, message_ids)


    def _update_outgoing_message(
        self,
        record,
        gateway,
        message_id,
        instance,
        chat_id,
        sender_name=None,
        message_ids=None,
    ):
        mail_message = record.mail_message_id.sudo()
        if not mail_message or not message_id:
            return
        message_key = self._build_message_key_from_values(
            gateway, instance, chat_id, message_id
        )
        if message_key:
            existing = (
                self.env["mail.message"]
                .sudo()
                .search([("gateway_message_key", "=", message_key)], limit=1)
            )
            if existing and existing.id != mail_message.id:
                self._register_outgoing_message_aliases(
                    existing,
                    gateway,
                    instance,
                    chat_id,
                    message_ids or [message_id],
                )
                return
        if not sender_name:
            sender_name = (
                mail_message.author_id.name
                or mail_message.author_guest_id.name
                or False
            )
        update_vals = {
            "gateway_message_external_id": message_id,
            "gateway_message_key": message_key,
            "gateway_instance": instance,
            "gateway_chat_id": chat_id,
            "gateway_from_me": True,
            "gateway_type": gateway.gateway_type,
        }
        if sender_name:
            update_vals["gateway_sender_name"] = sender_name
        try:
            # Outbound and inbound can race to persist the same gateway_message_key.
            # Avoid flushing unrelated pending writes that may trigger concurrent
            # updates on discuss_channel during invoice send.
            with self.env.cr.savepoint(flush=False):
                mail_message.write(update_vals)
        except IntegrityError:
            if message_key:
                existing = (
                    self.env["mail.message"]
                    .sudo()
                    .search([("gateway_message_key", "=", message_key)], limit=1)
                )
                if existing and existing.id != mail_message.id:
                    self._register_outgoing_message_aliases(
                        existing,
                        gateway,
                        instance,
                        chat_id,
                        message_ids or [message_id],
                    )
                    record.sudo().write({"gateway_message_id": message_id})
                    return
            raise
        except SerializationFailure:
            self._logger.warning(
                "Serialization failure while updating gateway metadata for "
                "mail.message %s (gateway message id %s).",
                mail_message.id,
                message_id,
                exc_info=True,
            )
            try:
                record.sudo().write({"gateway_message_id": message_id})
            except Exception:
                self._logger.debug(
                    "Unable to persist gateway_message_id on notification %s.",
                    record.id if record else None,
                    exc_info=True,
                )
            return
        self._register_outgoing_message_aliases(
            mail_message,
            gateway,
            instance,
            chat_id,
            message_ids or [message_id],
        )
        record.sudo().write({"gateway_message_id": message_id})


    def _collect_outbound_message_ids(self, result):
        message_ids = []
        if not isinstance(result, dict):
            return message_ids
        self._append_message_ids(message_ids, result.get("message_id"))
        self._append_message_ids(message_ids, result.get("id"))
        responses = result.get("responses") or []
        if isinstance(responses, dict):
            responses = [responses]
        for payload in responses:
            extracted_id = self._extract_message_id_from_payload(payload)
            if extracted_id:
                self._append_message_ids(message_ids, extracted_id)
        return message_ids


    def _collect_ordered_response_message_ids(self, result):
        ordered = []
        if not isinstance(result, dict):
            return ordered
        responses = result.get("responses") or []
        if isinstance(responses, dict):
            responses = [responses]
        for payload in responses:
            extracted_id = self._extract_message_id_from_payload(payload)
            if extracted_id:
                ordered.append(str(extracted_id).strip())
        if not ordered:
            fallback_id = result.get("message_id") or result.get("id")
            if isinstance(fallback_id, list):
                fallback_id = fallback_id[0] if fallback_id else False
            if fallback_id:
                ordered.append(str(fallback_id).strip())
        return ordered


    def _append_message_ids(self, message_ids, values):
        if values in (None, False):
            return
        if isinstance(values, (list, tuple, set)):
            for value in values:
                self._append_message_ids(message_ids, value)
            return
        value = str(values).strip()
        if value and value not in message_ids:
            message_ids.append(value)


    def _extract_message_id_from_payload(self, payload):
        if not isinstance(payload, dict):
            return False
        key_data = payload.get("key") or {}
        if isinstance(key_data, dict):
            message_id = key_data.get("id")
            if message_id:
                return message_id
        message_id = payload.get("messageId") or payload.get("keyId")
        if message_id:
            return message_id
        message_data = payload.get("message") or {}
        if isinstance(message_data, dict):
            key_data = message_data.get("key") or {}
            if isinstance(key_data, dict):
                message_id = key_data.get("id")
                if message_id:
                    return message_id
            message_id = message_data.get("messageId")
            if message_id:
                return message_id
        return payload.get("id")


    def _register_outgoing_message_aliases(
        self, mail_message, gateway, instance, chat_id, message_ids
    ):
        if (
            not mail_message
            or not gateway
            or "mail.gateway.message.alias" not in self.env
        ):
            return
        alias_model = self.env["mail.gateway.message.alias"].sudo()
        for message_id in message_ids or []:
            message_id = (message_id or "").strip()
            if not message_id:
                continue
            message_key = self._build_message_key_from_values(
                gateway, instance, chat_id, message_id
            )
            if not message_key:
                continue
            existing = alias_model.search(
                [("gateway_message_key", "=", message_key)], limit=1
            )
            if existing:
                continue
            values = {
                "gateway_id": gateway.id,
                "gateway_instance": instance,
                "gateway_chat_id": chat_id,
                "gateway_message_external_id": message_id,
                "gateway_message_key": message_key,
                "mail_message_id": mail_message.id,
            }
            try:
                with self.env.cr.savepoint(flush=False):
                    alias_model.create(values)
            except IntegrityError:
                continue


    def _mark_outbound_message_status(self, record, status):
        mail_message = record.mail_message_id.sudo() if record else False
        if not mail_message or "gateway_message_status" not in mail_message._fields:
            return
        current = mail_message.gateway_message_status
        if current:
            return
        mail_message.write({"gateway_message_status": status})
