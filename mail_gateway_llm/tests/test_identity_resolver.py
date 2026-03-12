from .common import MailGatewayLLMTestCommon


class TestMailGatewayLLMIdentityResolver(MailGatewayLLMTestCommon):
    def test_partner_author_resolves_high_confidence(self):
        run = self._create_partner_run(self.partner_a)

        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        self.assertTrue(identity["identified"])
        self.assertEqual(identity["resolved_partner_id"], self.partner_a.id)
        self.assertEqual(identity["confidence"], "high")
        self.assertEqual(identity["resolution_method"], "author_id")
        self.assertFalse(identity["needs_verification"])

    def test_guest_with_gateway_link_resolves_medium_confidence(self):
        run = self._create_guest_run("guest-a", partner=self.partner_a)

        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        self.assertTrue(identity["identified"])
        self.assertEqual(identity["resolved_partner_id"], self.partner_a.id)
        self.assertEqual(identity["confidence"], "medium")
        self.assertEqual(identity["resolution_method"], "guest_gateway_match")
        self.assertTrue(identity["needs_verification"])

    def test_webhook_author_is_treated_as_unresolved(self):
        run = self._create_webhook_run()

        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        self.assertFalse(identity["identified"])
        self.assertFalse(identity["resolved_partner_id"])
        self.assertEqual(identity["confidence"], "none")
        self.assertEqual(identity["resolution_method"], "unresolved")

    def test_payload_phone_can_resolve_system_attributed_message(self):
        run = self._create_webhook_run(
            payload_json={"sender_jid": "5511999999999@s.whatsapp.net"}
        )

        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        self.assertTrue(identity["identified"])
        self.assertEqual(identity["resolved_partner_id"], self.partner_a.id)
        self.assertEqual(identity["confidence"], "medium")
        self.assertEqual(identity["resolution_method"], "message_metadata_match")

    def test_message_metadata_phone_can_resolve_system_attributed_message(self):
        if "gateway_sender_jid" not in self.env["mail.message"]._fields:
            self.skipTest("gateway_sender_jid is not available in this test environment")

        run = self._create_webhook_run(
            message_updates={"gateway_sender_jid": "5511999999999@s.whatsapp.net"}
        )

        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        self.assertTrue(identity["identified"])
        self.assertEqual(identity["resolved_partner_id"], self.partner_a.id)
        self.assertEqual(identity["guest_phone"], "5511999999999")
        self.assertEqual(identity["confidence"], "medium")
        self.assertEqual(identity["resolution_method"], "message_metadata_match")

    def test_resolve_from_context_uses_run_id(self):
        run = self._create_partner_run(self.partner_b)

        identity = self.env["mail.gateway.llm.identity.resolver"].with_context(
            mail_gateway_llm_run_id=run.id
        ).resolve_from_context()

        self.assertEqual(identity["resolved_partner_id"], self.partner_b.id)
