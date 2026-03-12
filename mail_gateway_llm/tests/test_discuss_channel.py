from .common import MailGatewayLLMTestCommon


class TestMailGatewayLLMDiscussChannel(MailGatewayLLMTestCommon):
    def test_channel_basic_info_exposes_llm_state(self):
        self.gateway.write(
            {
                "llm_assistant_id": self.assistant.id,
                "llm_mode": "auto",
            }
        )

        info = self.channel._channel_basic_info()

        self.assertEqual(info["llm_state"], "active")
        self.assertEqual(info["llm_assistant_id"], self.assistant.id)
        self.assertEqual(info["llm_mode"], "auto")

    def test_pause_and_resume_llm_updates_channel_state(self):
        self.gateway.write(
            {
                "llm_assistant_id": self.assistant.id,
                "llm_mode": "auto",
            }
        )

        pause_result = self.channel.action_pause_llm()
        self.assertEqual(pause_result, {"llm_state": "paused"})
        self.assertEqual(self.channel.llm_state, "paused")

        resume_result = self.channel.action_resume_llm()
        self.assertEqual(resume_result, {"llm_state": "active"})
        self.assertEqual(self.channel.llm_state, "active")
