from odoo import fields, models


class MailGatewayOutboundIntent(models.Model):
    _name = "mail.gateway.outbound.intent"
    _description = "Gateway Outbound Intent"
    _order = "id desc"

    gateway_id = fields.Many2one(
        "mail.gateway",
        required=True,
        index=True,
        ondelete="cascade",
    )
    gateway_instance = fields.Char(index=True)
    gateway_chat_id = fields.Char(required=True, index=True)

    # Keep as plain integer so intents can be committed before the parent tx.
    mail_message_ref_id = fields.Integer(required=True, index=True)
    mail_notification_ref_id = fields.Integer(index=True)

    intent_type = fields.Selection(
        [("attachment", "Attachment"), ("text", "Text")],
        required=True,
        index=True,
    )
    sequence = fields.Integer(required=True, default=1, index=True)

    attachment_name = fields.Char()
    attachment_size = fields.Integer()
    attachment_sha1 = fields.Char(index=True)
    attachment_mimetype = fields.Char()
    body_key = fields.Char(index=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("matched", "Matched"),
            ("failed", "Failed"),
        ],
        required=True,
        default="pending",
        index=True,
    )
    outbound_message_external_id = fields.Char(index=True)
    inbound_message_external_id = fields.Char(index=True)
    matched_at = fields.Datetime()
    expire_at = fields.Datetime(index=True)
