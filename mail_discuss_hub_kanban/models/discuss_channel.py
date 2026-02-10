# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    discuss_hub_stage_id = fields.Many2one(
        "mail.discuss.hub.stage",
        string="Stage",
        index=True,
        ondelete="set null",
        group_expand="_read_group_discuss_hub_stage_ids",
        domain="['|', ('team_id', '=', False), ('team_id', '=', discuss_team_id)]",
        default=lambda self: self._default_discuss_hub_stage_id(),
    )

    @api.model
    def _default_discuss_hub_stage_id(self):
        team_id = self.env.context.get("default_discuss_team_id")
        domain = [
            ("company_id", "=", self.env.company.id),
            ("active", "=", True),
        ]
        if team_id:
            domain += ["|", ("team_id", "=", False), ("team_id", "=", team_id)]
        else:
            domain += [("team_id", "=", False)]
        stage = self.env["mail.discuss.hub.stage"].search(domain, order="sequence, id", limit=1)
        return stage

    @api.model
    def _read_group_discuss_hub_stage_ids(self, stages, domain):
        """Expand kanban columns.

        - Always show the stages that already exist in the current result (stages).
        - Also show global stages (team_id=False).
        - If a team is selected in context, include that team's stages too.

        This matches the standard pattern used by CRM/Project pipelines.
        """

        team_id = self._context.get("default_discuss_team_id")
        search_domain = [
            ("company_id", "=", self.env.company.id),
            ("active", "=", True),
            "|",
            ("id", "in", stages.ids),
        ]
        if team_id:
            search_domain += ["|", ("team_id", "=", False), ("team_id", "=", team_id)]
        else:
            search_domain += [("team_id", "=", False)]

        stage_ids = stages.sudo()._search(search_domain, order=stages._order)
        return stages.browse(stage_ids)

    def action_open_discuss(self):
        self.ensure_one()
        # Open the chat UI instead of the channel form.
        return self._get_access_action()
