from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.tools import html2plaintext
from psycopg2 import IntegrityError
from .outbound_payload import OutboundPayload

class MailGatewayWhatsappCommonOutbound:
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
        try:
            result = provider._send_outbound(gateway, dto)
        except Exception as exc:
            self._logger.exception("Unable to send gateway message")
            if raise_exception:
                raise
            self._write_outbound_failure(record, str(exc))
            return {"status": "exception", "error": str(exc)}
        self._write_outbound_success(record, gateway, dto, result)
        if auto_commit:
            record._cr.commit()
        return result or {"status": "sent"}


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
        body = html2plaintext(message.body or "")
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


    def _write_outbound_success(self, record, gateway, dto, result):
        record.sudo().write(
            {
                "notification_status": "sent",
                "failure_reason": False,
            }
        )
        message_id = False
        instance = dto.instance
        chat_id = dto.chat_id
        if isinstance(result, dict):
            message_id = result.get("message_id") or result.get("id")
            instance = result.get("instance") or instance
            chat_id = result.get("chat_id") or chat_id
        if isinstance(message_id, list):
            message_id = message_id[0] if message_id else False
        if message_id:
            self._update_outgoing_message(
                record,
                gateway,
                message_id,
                instance,
                chat_id,
                sender_name=dto.author_name,
            )


    def _update_outgoing_message(
        self, record, gateway, message_id, instance, chat_id, sender_name=None
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
            # Isolate this write so a duplicate key does not abort the caller transaction.
            with self.env.cr.savepoint():
                mail_message.write(update_vals)
        except IntegrityError:
            if message_key:
                existing = (
                    self.env["mail.message"]
                    .sudo()
                    .search([("gateway_message_key", "=", message_key)], limit=1)
                )
                if existing and existing.id != mail_message.id:
                    record.sudo().write({"gateway_message_id": message_id})
                    return
            raise
        record.sudo().write({"gateway_message_id": message_id})


    def _mark_outbound_message_status(self, record, status):
        mail_message = record.mail_message_id.sudo() if record else False
        if not mail_message or "gateway_message_status" not in mail_message._fields:
            return
        current = mail_message.gateway_message_status
        if current:
            return
        mail_message.write({"gateway_message_status": status})
