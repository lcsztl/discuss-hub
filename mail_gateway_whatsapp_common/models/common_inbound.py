import json
from odoo import fields
from psycopg2 import IntegrityError

class MailGatewayWhatsappCommonInbound:
    def _process_normalized(self, gateway, dto, channel, author=None):
        """Dispatch a normalized event to the matching handler."""
        if not gateway or not dto or not dto.event:
            return {
                "status": "ignored",
                "reason": "missing_gateway_or_event",
            }
        handler_name = f"_handle_{dto.event.replace('.', '_')}"
        handler = getattr(self, handler_name, None)
        if not handler:
            return {
                "status": "ignored",
                "reason": "unsupported_event",
                "event": dto.event,
            }
        return handler(gateway, dto, channel, author=author)


    def _handle_message_upsert(self, gateway, dto, channel, author=None):
        """Create or update a message coming from the gateway."""
        message_id = (dto.message_id or "").strip()
        chat_id = (dto.chat_id or "").strip()
        if not message_id:
            return {"status": "ignored", "reason": "missing_message_id"}
        if not chat_id:
            return {"status": "ignored", "reason": "missing_chat_id"}
        message_key = self._build_message_key(gateway, dto)
        existing = self._find_existing_message(gateway, dto, message_key=message_key)
        status_raw = (dto.status_raw or dto.status or "").strip()
        normalized = self._normalize_status(status_raw)
        if existing:
            self._register_message_alias_from_dto(existing, gateway, dto)
            update_vals = {}
            webhook_log_id = self.env.context.get("gateway_webhook_log_id")
            if (
                webhook_log_id
                and "gateway_webhook_log_id" in existing._fields
                and not existing.gateway_webhook_log_id
            ):
                update_vals["gateway_webhook_log_id"] = webhook_log_id
            if "gateway_payload_raw" in existing._fields and not existing.gateway_payload_raw:
                try:
                    update_vals["gateway_payload_raw"] = json.dumps(
                        dto.raw, ensure_ascii=True, sort_keys=True
                    )
                except Exception:
                    update_vals["gateway_payload_raw"] = str(dto.raw)
            backfill_values = {
                "gateway_message_external_id": message_id,
                "gateway_instance": dto.instance,
                "gateway_chat_id": chat_id,
                "gateway_sender_jid": dto.sender_jid,
                "gateway_sender_name": dto.sender_name,
                "gateway_from_me": bool(dto.from_me),
                "gateway_type": gateway.gateway_type,
                "gateway_message_key": message_key,
                "gateway_quote_external_id": (dto.quote_id or "").strip() or False,
                "gateway_quote_text": dto.quote_text,
            }
            if status_raw and "gateway_message_status_raw" in existing._fields:
                if existing.gateway_message_status_raw != status_raw:
                    update_vals["gateway_message_status_raw"] = status_raw
            if normalized and "gateway_message_status" in existing._fields:
                if self._should_update_status(existing.gateway_message_status, normalized):
                    update_vals["gateway_message_status"] = normalized
            # Backfill metadata only when missing to keep idempotent updates cheap.
            for field_name, value in backfill_values.items():
                if field_name not in existing._fields:
                    continue
                if not self._field_needs_backfill(existing, field_name):
                    continue
                if value in (None, "", False):
                    continue
                update_vals[field_name] = value
            if update_vals:
                existing.sudo().write(update_vals)
            return {
                "status": "duplicate",
                "message_id": existing.id,
            }

        attachments = self._prepare_attachments(dto)
        body = self._render_message_body(dto)
        if not body and not attachments:
            return {"status": "ignored", "reason": "empty_body"}

        pending_message_id = self._find_pending_outbound_message_id(
            gateway,
            dto,
            body,
            attachments,
        )
        if pending_message_id:
            pending_message = (
                self.env["mail.message"].sudo().browse(pending_message_id).exists()
            )
            if pending_message:
                self._register_message_alias_from_dto(pending_message, gateway, dto)
            return {
                "status": "duplicate",
                "message_id": pending_message_id,
            }

        author = author or self._resolve_author(gateway, dto)
        if not author:
            return {"status": "ignored", "reason": "author_not_found"}

        self._maybe_enrich_contact_metadata(gateway, dto, channel=channel)
        channel = channel or self._get_or_create_channel(gateway, dto, author)
        if not channel:
            return {"status": "ignored", "reason": "channel_not_found"}
        self._apply_channel_metadata(channel, dto)
        self._apply_contact_metadata(gateway, dto, channel=channel)
        self._ensure_guest_member(channel, author)

        equivalent = self._find_recent_equivalent_message(
            gateway,
            dto,
            channel,
            body,
            attachments,
        )
        if equivalent:
            self._register_message_alias_from_dto(equivalent, gateway, dto)
            return {
                "status": "duplicate",
                "message_id": equivalent.id,
            }
        parent_message = self._find_quoted_message(gateway, dto)

        ctx = dict(self.env.context or {})
        ctx["no_gateway_notification"] = True
        ctx["mail_gateway_hook_payload"] = {
            "provider": dto.provider,
            "gateway_type": gateway.gateway_type,
            "event": dto.event,
            "from_me": bool(dto.from_me),
            "message_id": message_id,
            "chat_id": chat_id,
            "instance": dto.instance,
        }
        post_channel = channel.with_context(**ctx)
        author_id = False
        if author._name == "mail.guest":
            # Post as public user with guest context so it renders as the guest.
            public_user = self.env.ref("base.public_user", raise_if_not_found=False)
            if public_user:
                post_channel = post_channel.with_user(public_user.id)
            post_channel = post_channel.with_context(guest=author)
        else:
            author_id = author.id

        msg_kwargs = {
            "gateway_message_external_id": message_id,
            "gateway_instance": dto.instance,
            "gateway_chat_id": chat_id,
            "gateway_sender_jid": dto.sender_jid,
            "gateway_sender_name": dto.sender_name,
            "gateway_from_me": bool(dto.from_me),
            "gateway_type": gateway.gateway_type,
            "gateway_message_key": message_key,
            "gateway_quote_external_id": (dto.quote_id or "").strip() or False,
            "gateway_quote_text": dto.quote_text,
        }
        if status_raw and "gateway_message_status_raw" in self.env["mail.message"]._fields:
            msg_kwargs["gateway_message_status_raw"] = status_raw
        if normalized and "gateway_message_status" in self.env["mail.message"]._fields:
            msg_kwargs["gateway_message_status"] = normalized
        webhook_log_id = self.env.context.get("gateway_webhook_log_id")
        if webhook_log_id and "gateway_webhook_log_id" in self.env["mail.message"]._fields:
            msg_kwargs["gateway_webhook_log_id"] = webhook_log_id
        if "gateway_payload_raw" in self.env["mail.message"]._fields:
            try:
                msg_kwargs["gateway_payload_raw"] = json.dumps(
                    dto.raw, ensure_ascii=True, sort_keys=True
                )
            except Exception:
                msg_kwargs["gateway_payload_raw"] = str(dto.raw)
        try:
            with self.env.cr.savepoint():
                message = post_channel.sudo().message_post(
                    body=body or "",
                    body_is_html=True,
                    author_id=author_id,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    parent_id=parent_message.id if parent_message else False,
                    attachments=attachments or None,
                )
        except IntegrityError:
            existing = self._find_existing_message(gateway, dto)
            if existing:
                return {"status": "duplicate", "message_id": existing.id}
            raise
        if not message:
            return {"status": "ignored", "reason": "message_not_created"}

        # Store gateway metadata after message creation to preserve mail.thread flow.
        # Wrap in a savepoint to handle concurrent upserts that hit the unique constraint.
        try:
            with self.env.cr.savepoint():
                message.sudo().write(msg_kwargs)
        except IntegrityError:
            existing = self._find_existing_message(gateway, dto, message_key=message_key)
            if existing:
                # Best effort cleanup of the duplicate message created in this txn.
                if message and message.id != existing.id:
                    try:
                        message.sudo().unlink()
                    except Exception:
                        pass
                return {"status": "duplicate", "message_id": existing.id}
            raise
        self._apply_message_timestamp(message, dto)

        return {
            "status": "ok",
            "message_id": message.id,
            "channel_id": channel.id,
        }


    def _handle_reaction_upsert(self, gateway, dto, channel, author=None):
        """Create or update reactions on an existing message."""
        target_id = (dto.reaction_target_id or dto.message_id or "").strip()
        reaction = (dto.reaction or "").strip()
        if not target_id:
            return {"status": "ignored", "reason": "missing_reaction_target"}
        if not reaction:
            return {"status": "ignored", "reason": "missing_reaction"}

        message = self._find_message_by_external_id(
            gateway,
            target_id,
            chat_id=dto.chat_id,
            instance=dto.instance,
        )
        if not message:
            return {"status": "ignored", "reason": "message_not_found"}

        author = author or self._resolve_author(gateway, dto)
        if not author:
            return {"status": "ignored", "reason": "author_not_found"}

        reaction_model = self.env["mail.message.reaction"].sudo().with_context(
            gateway_reaction_inbound=True
        )
        domain = [("message_id", "=", message.id), ("content", "=", reaction)]
        if author._name == "mail.guest":
            domain.append(("guest_id", "=", author.id))
        else:
            domain.append(("partner_id", "=", author.id))
        existing = reaction_model.search(domain, limit=1)
        if existing:
            self._notify_reaction_change(message, reaction)
            return {"status": "duplicate", "reaction_id": existing.id, "message_id": message.id}

        vals = {"message_id": message.id, "content": reaction}
        if author._name == "mail.guest":
            vals["guest_id"] = author.id
        else:
            vals["partner_id"] = author.id
        try:
            with self.env.cr.savepoint():
                new_reaction = reaction_model.create(vals)
        except IntegrityError:
            existing = reaction_model.search(domain, limit=1)
            if existing:
                return {"status": "duplicate", "reaction_id": existing.id, "message_id": message.id}
            raise

        self._notify_reaction_change(message, reaction)
        return {"status": "ok", "reaction_id": new_reaction.id, "message_id": message.id}


    def _handle_reaction_delete(self, gateway, dto, channel, author=None):
        """Remove reactions from an existing message."""
        target_id = (dto.reaction_target_id or dto.message_id or "").strip()
        if not target_id:
            return {"status": "ignored", "reason": "missing_reaction_target"}

        message = self._find_message_by_external_id(
            gateway,
            target_id,
            chat_id=dto.chat_id,
            instance=dto.instance,
        )
        if not message:
            return {"status": "ignored", "reason": "message_not_found"}

        author = author or self._resolve_author(gateway, dto)
        if not author:
            return {"status": "ignored", "reason": "author_not_found"}

        reaction_model = self.env["mail.message.reaction"].sudo().with_context(
            gateway_reaction_inbound=True
        )
        domain = [("message_id", "=", message.id)]
        if author._name == "mail.guest":
            domain.append(("guest_id", "=", author.id))
        else:
            domain.append(("partner_id", "=", author.id))
        reaction = (dto.reaction or "").strip()
        if reaction:
            domain.append(("content", "=", reaction))

        reactions = reaction_model.search(domain)
        if not reactions:
            return {"status": "ignored", "reason": "reaction_not_found"}
        contents = set(reactions.mapped("content"))
        if reaction:
            contents.add(reaction)
        count = len(reactions)
        reactions.with_context(gateway_reaction_inbound=True).unlink()
        for content in contents:
            self._notify_reaction_change(message, content)
        return {"status": "ok", "message_id": message.id, "deleted": count}


    def _notify_reaction_change(self, message, content):
        if not message or not content:
            return
        if hasattr(message, "_bus_send_reaction_group"):
            message._bus_send_reaction_group(content)


    def _handle_message_status(self, gateway, dto, channel, author=None):
        """Update delivery/read status for a gateway message."""
        message_id = (dto.message_id or "").strip()
        if not message_id:
            return {"status": "ignored", "reason": "missing_message_id"}
        status_raw = (dto.status_raw or dto.status or "").strip()
        normalized = self._normalize_status(status_raw)

        updated_message = False
        message = self._find_message_by_external_id(
            gateway,
            message_id,
            chat_id=dto.chat_id,
            instance=dto.instance,
        )
        if message:
            update_vals = {}
            if (
                status_raw
                and "gateway_message_status_raw" in message._fields
                and message.gateway_message_status_raw != status_raw
            ):
                update_vals["gateway_message_status_raw"] = status_raw
            if normalized and "gateway_message_status" in message._fields:
                if self._should_update_status(message.gateway_message_status, normalized):
                    update_vals["gateway_message_status"] = normalized
            if update_vals:
                message.sudo().write(update_vals)
                updated_message = True

        updated_notifications = self._update_gateway_notification_status(
            gateway, message_id, normalized, status_raw
        )
        if message and (updated_message or updated_notifications):
            if hasattr(message, "_notify_message_notification_update"):
                message._notify_message_notification_update()
        if updated_message or updated_notifications:
            return {
                "status": "ok",
                "message_id": message.id if message else False,
                "notification_count": updated_notifications,
            }
        return {"status": "ignored", "reason": "message_not_found"}


    def _handle_message_delete(self, gateway, dto, channel, author=None):
        """Mark a gateway message as deleted without removing it."""
        message_id = (dto.message_id or "").strip()
        if not message_id:
            return {"status": "ignored", "reason": "missing_message_id"}

        message = self._find_message_by_external_id(
            gateway,
            message_id,
            chat_id=dto.chat_id,
            instance=dto.instance,
        )
        if not message:
            return {"status": "ignored", "reason": "message_not_found"}
        if "gateway_is_deleted" in message._fields and message.gateway_is_deleted:
            return {"status": "duplicate", "message_id": message.id}

        updated_body = self._build_deleted_body(message.body)
        update_vals = {"body": updated_body}
        if "gateway_is_deleted" in message._fields:
            update_vals["gateway_is_deleted"] = True
        if "gateway_deleted_at" in message._fields:
            update_vals["gateway_deleted_at"] = fields.Datetime.now()
        message.sudo().write(update_vals)
        if hasattr(message, "_bus_send_store"):
            message._bus_send_store(
                message,
                {
                    "body": message.body,
                    "write_date": message.write_date,
                },
            )
        return {"status": "ok", "message_id": message.id}

    # -------------------------------------------------------------------------
    # Outgoing
    # -------------------------------------------------------------------------

    def _find_quoted_message(self, gateway, dto):
        quote_id = (dto.quote_id or "").strip()
        if not quote_id:
            return False
        message = self._find_message_by_external_id(
            gateway,
            quote_id,
            chat_id=dto.chat_id,
            instance=dto.instance,
        )
        if message:
            return message
        if dto.chat_id:
            return self._find_message_by_external_id(
                gateway,
                quote_id,
                chat_id=None,
                instance=dto.instance,
            )
        return False
