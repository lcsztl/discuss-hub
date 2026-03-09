# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class MailGateway(models.Model):
    _inherit = "mail.gateway"

    llm_mode = fields.Selection(
        selection=[
            ("off", "Off"),
            ("suggest", "Suggest"),
            ("auto", "Auto Reply"),
        ],
        default="off",
        required=True,
        string="LLM Mode",
        help="How the assistant should react to inbound gateway messages.",
    )
    llm_assistant_id = fields.Many2one(
        "llm.assistant",
        string="LLM Assistant",
        domain="[('active', '=', True)]",
        ondelete="restrict",
        help="Assistant used for conversations routed through this gateway.",
    )
    llm_run_count = fields.Integer(compute="_compute_llm_run_count")

    def _compute_llm_run_count(self):
        grouped = self.env["mail.gateway.llm.run"].read_group(
            [("gateway_id", "in", self.ids)],
            ["gateway_id"],
            ["gateway_id"],
        )
        counts = {item["gateway_id"][0]: item["gateway_id_count"] for item in grouped}
        for gateway in self:
            gateway.llm_run_count = counts.get(gateway.id, 0)

    def _gateway_llm_ready(self):
        self.ensure_one()
        return bool(self.llm_assistant_id and self.llm_mode != "off")

    def _after_gateway_message_received(
        self,
        channel,
        message,
        *,
        author=None,
        payload=None,
    ):
        self.ensure_one()
        if not self._gateway_llm_ready():
            return False
        return self.env["mail.gateway.llm.run"]._enqueue_inbound_run(
            self,
            channel,
            message,
            payload=payload,
        )

    def _after_gateway_outbound_sent(
        self,
        notification,
        *,
        message=None,
        channel=None,
        result=None,
    ):
        self.ensure_one()
        if not self._gateway_llm_ready():
            return False
        return self.env["mail.gateway.llm.run"]._enqueue_outbound_run(
            self,
            channel or notification.gateway_channel_id,
            notification,
            message=message,
        )

    def action_view_llm_runs(self):
        self.ensure_one()
        action = self.env.ref(
            "mail_gateway_llm.mail_gateway_llm_run_action"
        ).read()[0]
        action["domain"] = [("gateway_id", "=", self.id)]
        action["context"] = {"default_gateway_id": self.id}
        action["name"] = _("Gateway AI Runs")
        return action
