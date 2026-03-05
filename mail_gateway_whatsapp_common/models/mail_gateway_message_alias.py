from odoo import fields, models


class MailGatewayMessageAlias(models.Model):
    _name = "mail.gateway.message.alias"
    _description = "Gateway Message Alias"

    gateway_id = fields.Many2one(
        "mail.gateway",
        required=True,
        index=True,
        ondelete="cascade",
    )
    gateway_instance = fields.Char(index=True)
    gateway_chat_id = fields.Char(index=True)
    gateway_message_external_id = fields.Char(required=True, index=True)
    gateway_message_key = fields.Char(required=True, index=True)
    mail_message_id = fields.Many2one(
        "mail.message",
        required=True,
        index=True,
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "msg_alias_key_uniq",
            "unique(gateway_message_key)",
            "Gateway message alias already exists.",
        )
    ]
