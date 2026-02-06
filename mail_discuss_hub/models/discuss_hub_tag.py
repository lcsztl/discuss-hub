# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiscussHubTag(models.Model):
    _name = "mail.discuss.hub.tag"
    _description = "Discuss Hub Tag"
    _order = "name"

    name = fields.Char(required=True, index=True)
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "Tag name must be unique."),
    ]

    @api.constrains("name")
    def _check_name_not_empty(self):
        for tag in self:
            if not (tag.name or "").strip():
                raise ValidationError("Tag name cannot be empty.")
