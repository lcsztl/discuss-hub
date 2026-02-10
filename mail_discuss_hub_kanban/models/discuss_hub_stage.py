# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MailDiscussHubStage(models.Model):
    _name = "mail.discuss.hub.stage"
    _description = "Discuss Hub Stage"
    _order = "sequence, name"

    sequence = fields.Integer(default=10, index=True)
    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    fold = fields.Boolean(
        default=False,
        help="Folded stages are displayed as collapsed columns in kanban views.",
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    team_id = fields.Many2one(
        "mail.discuss.team",
        string="Discuss Team",
        check_company=True,
        help="Optional. When set, this stage is specific to a Discuss Team.",
    )

    _sql_constraints = [
        (
            "name_team_company_uniq",
            "unique(name, team_id, company_id)",
            "Stage name must be unique per team/company.",
        ),
    ]

    @api.constrains("name")
    def _check_name_not_empty(self):
        for stage in self:
            if not (stage.name or "").strip():
                raise ValidationError("Stage name cannot be empty.")
