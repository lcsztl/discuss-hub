from odoo import fields
from odoo.tests.common import TransactionCase

from odoo.addons.mail_gateway_whatsapp_common.models.normalized_payload import (
    NormalizedPayload,
)


class TestWhatsappCommonDedupe(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.common = cls.env["mail.gateway.whatsapp.common"]
        cls.gateway_a = cls._create_gateway("Gateway A")
        cls.gateway_b = cls._create_gateway("Gateway B")
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Gateway Common Test",
                "channel_type": "gateway",
                "gateway_id": cls.gateway_a.id,
                "gateway_channel_token": "gateway-common-test",
                "company_id": cls.company.id,
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Gateway Test Partner"})

    @classmethod
    def _create_gateway(cls, name):
        gateway_model = cls.env["mail.gateway"]
        selection = gateway_model.fields_get(["gateway_type"])["gateway_type"]["selection"]
        if selection:
            return gateway_model.create(
                {
                    "name": name,
                    "token": name.lower().replace(" ", "-"),
                    "gateway_type": selection[0][0],
                    "webhook_user_id": cls.env.ref("base.user_root").id,
                    "company_id": cls.company.id,
                }
            )

        now = fields.Datetime.now()
        cls.env.cr.execute(
            """
            INSERT INTO mail_gateway
                (name, token, gateway_type, webhook_user_id, company_id,
                 create_uid, create_date, write_uid, write_date)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                name,
                name.lower().replace(" ", "-"),
                "test",
                cls.env.ref("base.user_root").id,
                cls.company.id,
                cls.env.user.id,
                now,
                cls.env.user.id,
                now,
            ),
        )
        return gateway_model.browse(cls.env.cr.fetchone()[0])

    def _create_gateway_message(
        self,
        *,
        gateway,
        external_id,
        instance,
        chat_id,
        from_me,
    ):
        message = self.channel.with_context(
            no_gateway_notification=True,
            mail_gateway_skip_inbound_hooks=True,
        ).message_post(
            body="gateway test body",
            author_id=self.partner.id,
            message_type="comment",
        )
        message.sudo().write(
            {
                "gateway_message_external_id": external_id,
                "gateway_instance": instance,
                "gateway_chat_id": chat_id,
                "gateway_message_key": self.common._build_message_key_from_values(
                    gateway,
                    instance,
                    chat_id,
                    external_id,
                ),
                "gateway_type": gateway.gateway_type,
                "gateway_from_me": from_me,
            }
        )
        return message

    def test_find_existing_message_does_not_cross_gateway_instances(self):
        self._create_gateway_message(
            gateway=self.gateway_a,
            external_id="MSG-CROSS-1",
            instance="EnergyManager",
            chat_id="5511999999999@s.whatsapp.net",
            from_me=False,
        )
        dto = NormalizedPayload(
            provider="evolution",
            event="message.upsert",
            message_id="MSG-CROSS-1",
            instance="lucaszotelli",
            chat_id="551931990912@s.whatsapp.net",
            from_me=True,
            raw={},
        )

        existing = self.common._find_existing_message(self.gateway_b, dto)

        self.assertFalse(existing)

    def test_duplicate_backfill_does_not_flip_gateway_from_me(self):
        message = self._create_gateway_message(
            gateway=self.gateway_a,
            external_id="MSG-DUP-1",
            instance="EnergyManager",
            chat_id="5511999999999@s.whatsapp.net",
            from_me=False,
        )
        dto = NormalizedPayload(
            provider="evolution",
            event="message.upsert",
            message_id="MSG-DUP-1",
            instance="EnergyManager",
            chat_id="5511999999999@s.whatsapp.net",
            sender_jid="5511999999999@s.whatsapp.net",
            sender_name="Lucas",
            from_me=True,
            raw={},
        )

        result = self.common._handle_message_upsert(
            self.gateway_a,
            dto,
            self.channel,
            author=self.partner,
        )
        message.invalidate_recordset(["gateway_from_me"])

        self.assertEqual(result["status"], "duplicate")
        self.assertFalse(message.gateway_from_me)
