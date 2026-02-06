# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    _sql_constraints = [
        (
            "group_public_id_check",
            "CHECK (group_public_id IS NULL OR channel_type IS NOT NULL)",
            "Group authorization restrictions are managed by add-ons.",
        ),
    ]

    discuss_team_id = fields.Many2one(
        "mail.discuss.team",
        string="Discuss Team",
        index=True,
    )

    discuss_hub_tag_ids = fields.Many2many(
        "mail.discuss.hub.tag",
        "mail_discuss_hub_channel_tag_rel",
        "channel_id",
        "tag_id",
        string="Tags",
    )

    @api.constrains("group_public_id", "group_ids")
    def _constraint_group_id_channel(self):
        auto_subscribe_blocked = self.sudo().filtered(
            lambda channel: channel.channel_type != "channel" and channel.group_ids
        )
        if auto_subscribe_blocked:
            raise ValidationError(
                _("Group auto-subscription is only supported on channels.")
            )

    def _channel_basic_info(self):
        info = super()._channel_basic_info()
        info["active"] = self.active
        info["discuss_hub_tag_ids"] = self.discuss_hub_tag_ids.ids
        return info
