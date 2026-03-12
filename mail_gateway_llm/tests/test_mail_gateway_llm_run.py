from .common import MailGatewayLLMTestCommon


class TestMailGatewayLLMRun(MailGatewayLLMTestCommon):
    def test_payload_pretty_formats_payload_json(self):
        run = self._create_partner_run(
            self.partner_a,
            payload_json={
                "provider": "evolution",
                "message_id": "abc123",
                "from_me": False,
            },
        )

        self.assertIn('"provider": "evolution"', run.payload_pretty)
        self.assertIn('"message_id": "abc123"', run.payload_pretty)
        self.assertIn('"from_me": false', run.payload_pretty)
