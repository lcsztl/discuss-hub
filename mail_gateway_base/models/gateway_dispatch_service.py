# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import html as std_html
import re

from markupsafe import Markup
from psycopg2 import IntegrityError

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape, html2plaintext


class MailGatewayDispatchService(models.AbstractModel):
    _name = "mail.gateway.dispatch.service"
    _description = "Gateway Dispatch Service"

    _html_tag_re = re.compile(r"(?is)<\s*/?\s*[a-zA-Z][^>]*>")
    _escaped_tag_re = re.compile(r"(?is)&lt;\s*/?\s*[a-zA-Z][^&]*&gt;")
    _single_break_re = re.compile(r"(?<!\n)\n(?!\n)")
    _spaces_re = re.compile(r"[ \t]{2,}")
    _line_spaces_re = re.compile(r"[ \t]*\n[ \t]*")
    _multi_breaks_re = re.compile(r"\n{3,}")

    @staticmethod
    def _digits(value):
        return re.sub(r"\D", "", value or "")

    def _resolve_destination(self, partner, order=("gateway_phone", "mobile", "phone")):
        if not partner:
            return False
        for field_name in order or ():
            if field_name not in partner._fields:
                continue
            value = getattr(partner, field_name, False)
            if value:
                return str(value).strip()
        return False

    def _chat_candidates(self, gateway, destination):
        value = (destination or "").strip()
        if not value:
            return []
        if "@" in value:
            return [value]
        digits = self._digits(value)
        if not digits:
            return [value]

        if gateway.gateway_type == "whatsapp_waha":
            candidates = [f"{digits}@c.us", digits]
        elif gateway.gateway_type == "whatsapp_evolution_api":
            candidates = [f"{digits}@s.whatsapp.net", f"{digits}@c.us", digits]
        else:
            candidates = [digits]

        seen = set()
        ordered = []
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            ordered.append(candidate)
        return ordered

    def _include_inactive_channels(self, gateway):
        return False

    def _find_channel(self, gateway, chat_tokens, include_inactive=False):
        if not gateway:
            return False
        channel_model = self.env["discuss.channel"].sudo()
        if include_inactive:
            channel_model = channel_model.with_context(active_test=False)
        gateway = gateway.sudo()
        for token in chat_tokens or []:
            channel_id = gateway._get_channel_id(token)
            if channel_id:
                channel = channel_model.browse(channel_id)
                if channel.exists():
                    return channel
        return False

    def _reopen_channel_if_needed(self, gateway, channel, reopened_by):
        if gateway and hasattr(gateway, "_reopen_channel_if_needed"):
            return gateway._reopen_channel_if_needed(channel, reopened_by=reopened_by)
        return channel

    def _default_reopened_by(self, gateway, author_partner=None):
        if author_partner:
            return author_partner
        if gateway and gateway.webhook_user_id and gateway.webhook_user_id.partner_id:
            return gateway.webhook_user_id.partner_id
        return self.env.user.partner_id

    @staticmethod
    def _normalize_newlines(text):
        return (text or "").replace("\r\n", "\n").replace("\r", "\n")

    def _normalize_plain_text(self, text, collapse_single_breaks=False):
        text = std_html.unescape(text or "").replace("\xa0", " ")
        text = self._normalize_newlines(text)
        text = self._line_spaces_re.sub("\n", text)
        if collapse_single_breaks:
            text = self._single_break_re.sub(" ", text)
        text = self._spaces_re.sub(" ", text)
        text = self._multi_breaks_re.sub("\n\n", text)
        return text.strip()

    def _to_plain_text(self, body, collapse_single_breaks=None):
        source = str(body or "")
        has_html_markup = bool(
            self._html_tag_re.search(source) or self._escaped_tag_re.search(source)
        )
        text = html2plaintext(source) if has_html_markup else source
        text = std_html.unescape(text or "")
        if text and self._html_tag_re.search(text):
            text = self._html_tag_re.sub("", text)
        if collapse_single_breaks is None:
            collapse_single_breaks = has_html_markup
        return self._normalize_plain_text(
            text,
            collapse_single_breaks=collapse_single_breaks,
        )

    def _get_or_create_channel(
        self,
        gateway,
        chat_tokens,
        company_id=None,
        author_partner=None,
    ):
        if not gateway:
            raise ValidationError(_("Gateway is required."))
        dispatcher = False
        model_name = f"mail.gateway.{gateway.gateway_type}"
        if model_name in self.env:
            dispatcher = self.env[model_name].sudo()
            if company_id:
                dispatcher = dispatcher.with_company(company_id)
        member_dispatcher = dispatcher
        if (
            dispatcher
            and getattr(dispatcher, "_uses_gateway_common", False)
            and "mail.gateway.whatsapp.common" in self.env
        ):
            member_dispatcher = self.env["mail.gateway.whatsapp.common"].sudo()
            if company_id:
                member_dispatcher = member_dispatcher.with_company(company_id)

        include_inactive = self._include_inactive_channels(gateway)
        channel = self._find_channel(
            gateway, chat_tokens, include_inactive=include_inactive
        )
        if channel:
            ensure_member = getattr(member_dispatcher, "_ensure_channel_destination_member", None)
            if callable(ensure_member):
                ensure_member(channel, gateway.sudo(), chat_tokens)
            reopened_by = self._default_reopened_by(
                gateway, author_partner=author_partner
            )
            return self._reopen_channel_if_needed(gateway, channel, reopened_by)

        if not chat_tokens:
            raise ValidationError(_("Recipient destination is invalid."))

        token = chat_tokens[0]
        if not dispatcher:
            raise ValidationError(
                _("Gateway type '%s' is not supported.") % (gateway.gateway_type or "")
            )

        with self.env.cr.savepoint():
            try:
                channel = dispatcher._get_channel(
                    gateway.sudo(), token, {}, force_create=True
                )
            except IntegrityError:
                channel = self._find_channel(
                    gateway, [token], include_inactive=True
                )

        if not channel:
            channel = self._find_channel(gateway, [token], include_inactive=True)
        if not channel:
            raise ValidationError(
                _("Unable to create/find gateway channel for '%s'.") % token
            )
        ensure_member = getattr(member_dispatcher, "_ensure_channel_destination_member", None)
        if callable(ensure_member):
            ensure_member(channel, gateway.sudo(), chat_tokens)

        reopened_by = self._default_reopened_by(gateway, author_partner=author_partner)
        return self._reopen_channel_if_needed(gateway, channel, reopened_by)

    @staticmethod
    def _render_text_body_to_html(text):
        text = (text or "").strip()
        if not text:
            return Markup("")
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        parts = [html_escape(line) for line in normalized.split("\n")]
        return Markup("<br/>").join(parts)

    @staticmethod
    def _prepare_ir_attachments_payload(attachment_ids):
        payload = []
        for attachment in attachment_ids:
            raw = attachment.raw
            if not raw:
                continue
            info = {}
            if attachment.mimetype:
                info["mimetype"] = attachment.mimetype
            payload.append((attachment.name or "attachment", raw, info))
        return payload

    def _force_plain_message_body(self, message, body_text):
        if not message:
            return
        self.env.cr.execute(
            "UPDATE mail_message SET body=%s WHERE id=%s",
            (body_text or "", message.id),
        )
        message.invalidate_recordset(["body"])

    def _send_message(
        self,
        gateway,
        destination,
        body_text=None,
        body_html=None,
        attachments=None,
        company_id=None,
        author_user=None,
        author_partner=None,
    ):
        if not gateway:
            raise ValidationError(_("Gateway is required."))

        candidates = self._chat_candidates(gateway, destination)
        if not candidates:
            raise ValidationError(_("Invalid recipient destination."))

        channel = self._get_or_create_channel(
            gateway,
            candidates,
            company_id=company_id,
            author_partner=author_partner,
        )
        send_user = author_user or gateway.webhook_user_id or self.env.user
        author_partner = author_partner or send_user.partner_id or self.env.user.partner_id

        source_body = body_text if body_text is not None else body_html
        normalized_body = self._to_plain_text(source_body)
        if not normalized_body and not attachments:
            raise ValidationError(
                _("Message body or at least one attachment is required.")
            )

        message = channel.with_user(send_user).with_context(
            mail_gateway_background_post=True
        ).message_post(
            author_id=author_partner.id if author_partner else False,
            body=normalized_body or False,
            attachments=attachments or [],
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self._force_plain_message_body(message, normalized_body)
        return {
            "channel_id": channel.id,
            "message_id": message.id,
            "chat_token": candidates[0],
            "channel": channel,
            "message": message,
        }

    def _send_text_message(
        self,
        gateway,
        destination,
        body_text,
        attachments=None,
        company_id=None,
        author_user=None,
        author_partner=None,
    ):
        return self._send_message(
            gateway=gateway,
            destination=destination,
            body_text=body_text,
            attachments=attachments,
            company_id=company_id,
            author_user=author_user,
            author_partner=author_partner,
        )
