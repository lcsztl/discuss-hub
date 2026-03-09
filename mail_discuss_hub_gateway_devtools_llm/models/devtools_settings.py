# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    llm_trace_enabled = fields.Boolean(
        string="LLM trace",
        config_parameter="mail_discuss_hub_gateway_devtools.llm_trace_enabled",
        default=False,
        help="Persist rendered prompt/context and provider-facing request snapshots for Gateway AI runs.",
    )
