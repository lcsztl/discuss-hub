from .common import MailGatewayLLMTestCommon


class TestMailGatewayLLMScopeResolver(MailGatewayLLMTestCommon):
    def test_contact_defaults_to_commercial_partner_scope(self):
        run = self._create_partner_run(self.contact_partner)
        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        scope = self.env["mail.gateway.llm.scope.resolver"].compute(identity)

        self.assertEqual(scope["resolved_partner_id"], self.contact_partner.id)
        self.assertEqual(scope["principal_partner_id"], self.company_partner.id)
        self.assertEqual(scope["commercial_partner_id"], self.company_partner.id)
        self.assertEqual(
            set(scope["related_partner_ids"]),
            {self.contact_partner.id, self.company_partner.id},
        )
        self.assertTrue(scope["allow_sensitive_data"])
        self.assertEqual(scope["scope_mode"], "automatic")

    def test_exact_partner_binding_has_priority_over_commercial_partner_binding(self):
        company_binding = self.env["mail.gateway.llm.access.binding"].create(
            {
                "name": "Company Scope",
                "principal_partner_id": self.company_partner.id,
                "gateway_id": self.gateway.id,
                "company_id": self.company.id,
                "allow_sensitive_data": True,
            }
        )
        exact_binding = self.env["mail.gateway.llm.access.binding"].create(
            {
                "name": "Contact Scope",
                "principal_partner_id": self.contact_partner.id,
                "allow_sensitive_data": False,
            }
        )
        run = self._create_partner_run(self.contact_partner)
        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        scope = self.env["mail.gateway.llm.scope.resolver"].compute(identity)

        self.assertEqual(scope["binding_id"], exact_binding.id)
        self.assertNotEqual(scope["binding_id"], company_binding.id)
        self.assertEqual(scope["principal_partner_id"], self.contact_partner.id)
        self.assertFalse(scope["allow_sensitive_data"])

    def test_gateway_specific_binding_has_priority_over_company_binding(self):
        company_binding = self.env["mail.gateway.llm.access.binding"].create(
            {
                "name": "Company Partner B",
                "principal_partner_id": self.partner_b.id,
                "company_id": self.company.id,
                "allow_sensitive_data": False,
            }
        )
        gateway_binding = self.env["mail.gateway.llm.access.binding"].create(
            {
                "name": "Gateway Partner B",
                "principal_partner_id": self.partner_b.id,
                "gateway_id": self.gateway.id,
                "allow_sensitive_data": True,
            }
        )
        run = self._create_partner_run(self.partner_b)
        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        scope = self.env["mail.gateway.llm.scope.resolver"].compute(identity)

        self.assertEqual(scope["binding_id"], gateway_binding.id)
        self.assertNotEqual(scope["binding_id"], company_binding.id)
        self.assertTrue(scope["allow_sensitive_data"])

    def test_medium_confidence_requires_binding_for_sensitive_data(self):
        run = self._create_guest_run("guest-medium", partner=self.partner_a)
        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        scope_without_binding = self.env["mail.gateway.llm.scope.resolver"].compute(identity)
        self.assertFalse(scope_without_binding["allow_sensitive_data"])

        self.env["mail.gateway.llm.access.binding"].create(
            {
                "name": "Guest Partner A",
                "principal_partner_id": self.partner_a.id,
                "gateway_id": self.gateway.id,
                "allow_sensitive_data": True,
            }
        )

        scope_with_binding = self.env["mail.gateway.llm.scope.resolver"].compute(identity)
        self.assertTrue(scope_with_binding["allow_sensitive_data"])

    def test_low_confidence_never_allows_sensitive_data(self):
        run = self._create_guest_run("guest-low")
        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        scope = self.env["mail.gateway.llm.scope.resolver"].compute(identity)

        self.assertEqual(identity["confidence"], "low")
        self.assertFalse(scope["allow_sensitive_data"])

    def test_unresolved_identity_never_allows_sensitive_data(self):
        run = self._create_webhook_run()
        identity = self.env["mail.gateway.llm.identity.resolver"].resolve(run)

        scope = self.env["mail.gateway.llm.scope.resolver"].compute(identity)

        self.assertEqual(identity["confidence"], "none")
        self.assertFalse(scope["allow_sensitive_data"])
        self.assertEqual(scope["scope_mode"], "empty")

    def test_scope_resolve_from_context_uses_run_id(self):
        run = self._create_partner_run(self.partner_a)

        scope = self.env["mail.gateway.llm.scope.resolver"].with_context(
            mail_gateway_llm_run_id=run.id
        ).resolve_from_context()

        self.assertEqual(scope["resolved_partner_id"], self.partner_a.id)
