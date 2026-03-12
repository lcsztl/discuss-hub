# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    llm_state = fields.Selection(
        selection=[("active", "Active"), ("paused", "Paused")],
        default="active",
        copy=False,
        string="LLM State",
        help="Pause automatic replies without losing conversation memory.",
    )
    llm_thread_id = fields.Many2one(
        "llm.thread",
        string="LLM Thread",
        copy=False,
        readonly=True,
        ondelete="set null",
    )
    llm_assistant_id = fields.Many2one(
        related="gateway_id.llm_assistant_id",
        string="LLM Assistant",
        readonly=True,
    )
    llm_run_count = fields.Integer(compute="_compute_llm_run_count")

    def _compute_llm_run_count(self):
        grouped = self.env["mail.gateway.llm.run"].read_group(
            [("channel_id", "in", self.ids)],
            ["channel_id"],
            ["channel_id"],
        )
        counts = {item["channel_id"][0]: item["channel_id_count"] for item in grouped}
        for channel in self:
            channel.llm_run_count = counts.get(channel.id, 0)

    def _channel_basic_info(self):
        info = super()._channel_basic_info()
        info.update(
            {
                "llm_state": self.llm_state,
                "llm_assistant_id": self.llm_assistant_id.id if self.llm_assistant_id else False,
                "llm_mode": self.gateway_id.llm_mode if self.gateway_id else False,
            }
        )
        return info

    def _check_can_manage_llm_state(self):
        self.ensure_one()
        if not self.env.user._is_internal():
            raise AccessError(_("Only internal users can manage the AI auto-service."))

        channel = self.with_user(self.env.user)
        channel.check_access("read")

        if channel.channel_type != "gateway" or not channel.gateway_id:
            raise AccessError(_("AI auto-service can only be managed on gateway channels."))
        if not channel.llm_assistant_id or channel.gateway_id.llm_mode == "off":
            raise UserError(_("Configure an active AI assistant on the gateway first."))

    def _set_llm_state(self, target_state):
        self.ensure_one()
        if target_state not in {"active", "paused"}:
            raise UserError(_("Unsupported AI state '%s'.") % target_state)

        self._check_can_manage_llm_state()
        if self.llm_state != target_state:
            self.sudo().write({"llm_state": target_state})
        return {"llm_state": self.llm_state}

    def action_pause_llm(self):
        self.ensure_one()
        return self._set_llm_state("paused")

    def action_resume_llm(self):
        self.ensure_one()
        return self._set_llm_state("active")

    def _get_gateway_llm_assistant(self):
        self.ensure_one()
        return self.llm_assistant_id.exists()

    def _sync_gateway_llm_thread_assistant(self, thread, assistant):
        self.ensure_one()
        if not thread or not assistant:
            return thread

        assistant_tools = assistant.tool_ids
        thread_tools = thread.tool_ids
        needs_assistant_sync = (
            thread.assistant_id != assistant
            or thread.provider_id != assistant.provider_id
            or thread.model_id != assistant.model_id
            or thread.prompt_id != assistant.prompt_id
            or set(thread_tools.ids) != set(assistant_tools.ids)
        )
        if not needs_assistant_sync:
            return thread

        thread.sudo().set_assistant(assistant.id)
        if not assistant.prompt_id and thread.prompt_id:
            thread.sudo().write({"prompt_id": False})
        return thread

    def _ensure_gateway_llm_thread(self, assistant=None):
        self.ensure_one()

        assistant = assistant or self._get_gateway_llm_assistant()
        if not assistant:
            raise UserError(_("Configure an active LLM assistant on the gateway first."))
        if not assistant.provider_id or not assistant.model_id:
            raise UserError(
                _(
                    "Assistant '%s' must define both provider and model before it can be used.",
                )
                % assistant.display_name
            )

        thread = self.llm_thread_id.exists()
        if not thread:
            thread = self.env["llm.thread"].sudo().create(
                {
                    "name": _("Gateway AI - %s") % self.display_name,
                    "model": self._name,
                    "res_id": self.id,
                    "provider_id": assistant.provider_id.id,
                    "model_id": assistant.model_id.id,
                }
            )
            thread = self._sync_gateway_llm_thread_assistant(thread, assistant)
            self.sudo().write({"llm_thread_id": thread.id})
            return thread

        update_vals = {}
        if thread.model != self._name or thread.res_id != self.id:
            update_vals.update({"model": self._name, "res_id": self.id})
        if not thread.provider_id and assistant.provider_id:
            update_vals["provider_id"] = assistant.provider_id.id
        if not thread.model_id and assistant.model_id:
            update_vals["model_id"] = assistant.model_id.id
        if update_vals:
            thread.sudo().write(update_vals)
        thread = self._sync_gateway_llm_thread_assistant(thread, assistant)
        if self.llm_thread_id != thread:
            self.sudo().write({"llm_thread_id": thread.id})
        return thread

    def action_open_llm_thread(self):
        self.ensure_one()
        return self._ensure_gateway_llm_thread().action_open_thread()

    def action_view_llm_runs(self):
        self.ensure_one()
        action = self.env.ref(
            "mail_gateway_llm.mail_gateway_llm_run_action"
        ).read()[0]
        action["domain"] = [("channel_id", "=", self.id)]
        action["context"] = {
            "default_channel_id": self.id,
            "default_gateway_id": self.gateway_id.id,
        }
        action["name"] = _("Channel AI Runs")
        return action
