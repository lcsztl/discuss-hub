from odoo import fields
from odoo.tests.common import TransactionCase


class MailGatewayLLMTestCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.prompt = cls.env["llm.prompt"].create(
            {
                "name": "Gateway AI Prompt",
                "template": "You are a gateway AI assistant.",
                "format": "text",
            }
        )
        cls.assistant = cls.env["llm.assistant"].create(
            {
                "name": "Gateway AI Assistant",
                "prompt_id": cls.prompt.id,
            }
        )
        cls.gateway = cls._create_gateway()
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Gateway AI Channel",
                "channel_type": "gateway",
                "gateway_id": cls.gateway.id,
                "gateway_channel_token": "gateway-ai-channel-1",
                "company_id": cls.company.id,
            }
        )

        cls.partner_a = cls._create_partner("Partner A", gateway_phone="5511999999999")
        cls.partner_b = cls._create_partner("Partner B", gateway_phone="5521999999999")
        cls.company_partner = cls._create_partner("Partner Company")
        cls.contact_partner = cls._create_partner(
            "Partner Contact",
            parent_id=cls.company_partner.id,
            gateway_phone="5531999999999",
        )

    @classmethod
    def _create_partner(cls, name, **extra_vals):
        vals = {"name": name}
        if "gateway_phone" in cls.env["res.partner"]._fields and extra_vals.get("gateway_phone"):
            vals["gateway_phone"] = extra_vals["gateway_phone"]
        if extra_vals.get("parent_id"):
            vals["parent_id"] = extra_vals["parent_id"]
        return cls.env["res.partner"].create(vals)

    @classmethod
    def _create_gateway(cls):
        gateway_model = cls.env["mail.gateway"]
        selection = gateway_model.fields_get(["gateway_type"])["gateway_type"]["selection"]
        if selection:
            return gateway_model.create(
                {
                    "name": "Gateway AI",
                    "token": "gateway-ai-token",
                    "gateway_type": selection[0][0],
                    "webhook_user_id": cls.env.ref("base.user_root").id,
                    "company_id": cls.company.id,
                    "llm_mode": "off",
                }
            )

        now = fields.Datetime.now()
        cls.env.cr.execute(
            """
            INSERT INTO mail_gateway
                (name, token, gateway_type, webhook_user_id, company_id, llm_mode,
                 create_uid, create_date, write_uid, write_date)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "Gateway AI",
                "gateway-ai-token",
                "test",
                cls.env.ref("base.user_root").id,
                cls.company.id,
                "off",
                cls.env.user.id,
                now,
                cls.env.user.id,
                now,
            ),
        )
        gateway_id = cls.env.cr.fetchone()[0]
        return gateway_model.browse(gateway_id)

    def _create_run_from_message(self, message, payload_json=None):
        return self.env["mail.gateway.llm.run"].sudo().create(
            {
                "gateway_id": self.gateway.id,
                "channel_id": self.channel.id,
                "assistant_id": self.assistant.id,
                "source_message_id": message.id,
                "run_type": "inbound",
                "mode": "suggest",
                "payload_json": payload_json or {},
            }
        )

    def _apply_message_updates(self, message, updates=None):
        if not updates:
            return message
        valid_updates = {
            key: value for key, value in updates.items() if key in message._fields
        }
        if valid_updates:
            message.sudo().write(valid_updates)
        return message

    def _create_partner_run(self, partner, *, body="Partner question", message_updates=None, payload_json=None):
        source_message = self.channel.with_context(
            no_gateway_notification=True,
            mail_gateway_skip_inbound_hooks=True,
        ).message_post(
            body=body,
            author_id=partner.id,
            message_type="comment",
        )
        self._apply_message_updates(source_message, message_updates)
        return self._create_run_from_message(source_message, payload_json=payload_json)

    def _create_guest_run(
        self,
        token,
        *,
        body="Guest question",
        partner=False,
        message_updates=None,
        payload_json=None,
    ):
        guest_vals = {
            "name": f"Guest {token}",
            "gateway_id": self.gateway.id,
            "gateway_token": token,
        }
        if "gateway_phone" in self.env["mail.guest"]._fields:
            guest_vals["gateway_phone"] = token
        guest = self.env["mail.guest"].create(guest_vals)
        if partner:
            gateway_channel = self.env["res.partner.gateway.channel"].search(
                [
                    ("partner_id", "=", partner.id),
                    ("gateway_id", "=", self.gateway.id),
                ],
                limit=1,
            )
            if gateway_channel:
                gateway_channel.write({"gateway_token": token})
            else:
                self.env["res.partner.gateway.channel"].create(
                    {
                        "partner_id": partner.id,
                        "gateway_id": self.gateway.id,
                        "gateway_token": token,
                    }
                )
        self.channel.sudo().add_members(guest_ids=[guest.id])
        public_user = self.env.ref("base.public_user")
        source_message = (
            self.channel.with_user(public_user)
            .with_context(
                guest=guest,
                no_gateway_notification=True,
                mail_gateway_skip_inbound_hooks=True,
            )
            .message_post(body=body, message_type="comment")
        )
        self._apply_message_updates(source_message, message_updates)
        return self._create_run_from_message(source_message, payload_json=payload_json)

    def _create_webhook_run(self, *, body="Webhook question", message_updates=None, payload_json=None):
        source_message = self.channel.with_context(
            no_gateway_notification=True,
            mail_gateway_skip_inbound_hooks=True,
        ).message_post(
            body=body,
            author_id=self.gateway.webhook_user_id.partner_id.id,
            message_type="comment",
        )
        self._apply_message_updates(source_message, message_updates)
        return self._create_run_from_message(source_message, payload_json=payload_json)
