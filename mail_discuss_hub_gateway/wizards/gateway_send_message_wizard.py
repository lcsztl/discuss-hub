# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from markupsafe import Markup
from psycopg2 import IntegrityError

from odoo import _, Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape


class MailGatewaySendMessageWizard(models.TransientModel):
    _name = "mail.gateway.send.message.wizard"
    _description = "Send Message through Gateway"

    gateway_id = fields.Many2one(
        "mail.gateway",
        string="From",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="To (Contact)",
        help="Optional contact used to prefill the destination.",
    )
    to = fields.Char(
        string="To",
        required=True,
        help="Phone number or provider chat id (e.g. 5511999999999, 5511999999999@c.us).",
    )
    body = fields.Text(string="Message")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mail_gateway_send_message_wizard_ir_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Attachments",
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for wizard in self:
            partner = wizard.partner_id
            if not partner:
                continue
            phone = (
                getattr(partner, "gateway_phone", False)
                or partner.mobile
                or partner.phone
                or False
            )
            if phone:
                wizard.to = phone

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _digits(value):
        return re.sub(r"\D", "", value or "")

    def _chat_id_candidates(self, gateway, value):
        value = (value or "").strip()
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

        # De-duplicate while keeping order.
        seen = set()
        result = []
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            result.append(candidate)
        return result

    def _build_channel_members(self, gateway, author_partner):
        members = []
        seen_partner_ids = set()
        auto_users = (
            gateway._get_auto_assign_users()
            if hasattr(gateway, "_get_auto_assign_users")
            else gateway.member_ids
        )
        for user in auto_users:
            partner = user.partner_id
            if not partner:
                continue
            if partner.id in seen_partner_ids:
                continue
            seen_partner_ids.add(partner.id)
            if user.partner_id:
                members.append(
                    Command.create(
                        {
                            "partner_id": user.partner_id.id,
                            "unpin_dt": False,
                        }
                    )
                )
        webhook_partner = (
            gateway.webhook_user_id.partner_id
            if gateway.webhook_user_id and gateway.webhook_user_id.partner_id
            else False
        )
        if (
            author_partner
            and (not webhook_partner or author_partner.id != webhook_partner.id)
            and author_partner.id not in seen_partner_ids
        ):
            seen_partner_ids.add(author_partner.id)
            members.append(
                Command.create(
                    {
                        "partner_id": author_partner.id,
                        "unpin_dt": False,
                    }
                )
            )
        return members

    def _find_channel(self, gateway, chat_ids):
        gateway_sudo = gateway.sudo()
        channel_model = self.env["discuss.channel"].sudo()
        for chat_id in chat_ids or []:
            channel_id = gateway_sudo._get_channel_id(chat_id)
            if channel_id:
                return channel_model.browse(channel_id)
        return False

    def _get_or_create_channel(self, gateway, chat_id, author_partner):
        existing = self._find_channel(gateway, [chat_id])
        if existing:
            return existing

        name = (
            (self.partner_id.display_name or "").strip()
            if self.partner_id
            else ""
        ) or chat_id
        members = self._build_channel_members(gateway, author_partner)
        channel_env = self.env["discuss.channel"].sudo().with_user(
            gateway.webhook_user_id or self.env.user
        )
        channel_env = channel_env.with_context(install_mode=True)
        try:
            channel = channel_env.create(
                {
                    "name": name,
                    "channel_type": "gateway",
                    "gateway_id": gateway.id,
                    "gateway_channel_token": chat_id,
                    "channel_member_ids": members,
                    "company_id": gateway.company_id.id,
                }
            )
        except IntegrityError:
            # Another transaction created the same gateway channel concurrently.
            self.env.cr.rollback()
            channel = self._find_channel(gateway, [chat_id])
            if not channel:
                raise
        channel._broadcast(channel.channel_member_ids.mapped("partner_id").ids)
        return channel

    @staticmethod
    def _render_body(text):
        text = (text or "").strip()
        if not text:
            return Markup("")
        escaped = html_escape(text).replace("\r\n", "\n").replace("\r", "\n")
        return Markup(escaped.replace("\n", Markup("<br/>")))

    def _prepare_attachments_payload(self):
        payload = []
        for attachment in self.attachment_ids:
            raw = attachment.raw
            if not raw:
                continue
            info = {}
            if attachment.mimetype:
                info["mimetype"] = attachment.mimetype
            payload.append((attachment.name or "attachment", raw, info))
        return payload

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_send(self):
        self.ensure_one()
        gateway = self.gateway_id
        if not gateway:
            raise ValidationError(_("Gateway is required."))

        to_value = (self.to or "").strip()
        if not to_value:
            raise ValidationError(_("Recipient is required."))

        if not (self.body or "").strip() and not self.attachment_ids:
            raise ValidationError(
                _("Message body or at least one attachment is required.")
            )

        author_partner = self.env.user.partner_id
        chat_candidates = self._chat_id_candidates(gateway, to_value)
        if not chat_candidates:
            raise ValidationError(_("Invalid recipient value."))

        channel = self._find_channel(gateway, chat_candidates)
        if not channel:
            channel = self._get_or_create_channel(
                gateway, chat_candidates[0], author_partner
            )

        if hasattr(gateway, "_reopen_channel_if_needed"):
            channel = gateway._reopen_channel_if_needed(
                channel, reopened_by=author_partner
            )

        attachments = self._prepare_attachments_payload()
        body = self._render_body(self.body)
        channel.with_user(self.env.user).message_post(
            author_id=author_partner.id,
            body=body,
            attachments=attachments,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Avoid leaving temporary wizard attachments around.
        if self.attachment_ids:
            self.attachment_ids.unlink()

        return {"type": "ir.actions.act_window_close"}
