# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class LLMThread(models.Model):
    _inherit = "llm.thread"

    def _devtools_get_gateway_llm_run(self):
        self.ensure_one()
        run_id = self.env.context.get("mail_gateway_llm_run_id")
        if not run_id:
            return False
        return self.env["mail.gateway.llm.run"].sudo().browse(run_id).exists()

    def _prepare_chat_kwargs(self, message_history, use_streaming):
        self.ensure_one()
        chat_kwargs = super()._prepare_chat_kwargs(message_history, use_streaming)
        run = self._devtools_get_gateway_llm_run()
        if run:
            run._devtools_capture_llm_request(self, chat_kwargs)
        return chat_kwargs

    def _handle_non_streaming_response(self, response):
        self.ensure_one()
        assistant_message = yield from super()._handle_non_streaming_response(response)
        run = self._devtools_get_gateway_llm_run()
        if run:
            run._devtools_capture_llm_response(
                response=response,
                assistant_message=assistant_message,
            )
        return assistant_message

    def _handle_streaming_response(self, stream_response):
        self.ensure_one()
        run = self._devtools_get_gateway_llm_run()
        collected_chunks = []

        def _traced_stream():
            for chunk in stream_response:
                if run:
                    collected_chunks.append(run._devtools_normalize_value(chunk))
                yield chunk

        assistant_message = yield from super()._handle_streaming_response(_traced_stream())
        if run:
            run._devtools_capture_llm_response(
                assistant_message=assistant_message,
                stream_chunks=collected_chunks,
            )
        return assistant_message
