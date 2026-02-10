# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


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

    def _discuss_hub_check_can_tag(self):
        """Centralizes security for tagging conversations from the Discuss UI.

        We intentionally *don't* rely on the user having generic write access to
        the channel. Tagging is a specific action: internal users who can access
        a channel via Discuss Hub rules should be able to classify it.
        """

        self.ensure_one()
        user = self.env.user
        if not user._is_internal():
            raise AccessError(_("Only internal users can tag conversations."))

        # Ensure the user can at least read this record through normal rules.
        channel = self.with_user(user)
        channel.check_access_rights("read")
        channel.check_access_rule("read")

        if channel.channel_type in ("channel", "gateway"):
            group = (
                channel.parent_channel_id.group_public_id
                if channel.parent_channel_id
                else channel.group_public_id
            )
            if group and group not in user.groups_id:
                raise AccessError(_("You don't have access to tag this conversation."))
            return

        if not channel.is_member:
            raise AccessError(_("You must be a member to tag this conversation."))

    @api.model
    def _discuss_hub_sanitize_tag_ids(self, tag_ids):
        tag_ids = tag_ids or []
        sanitized = []
        seen = set()
        for value in tag_ids:
            try:
                tag_id = int(value)
            except (TypeError, ValueError):
                continue
            if tag_id <= 0 or tag_id in seen:
                continue
            seen.add(tag_id)
            sanitized.append(tag_id)
        return sanitized

    def action_discuss_hub_set_tags(self, tag_ids):
        """Set Discuss Hub tags on a channel and return the resulting ids.

        Designed for the Discuss frontend to keep the store in sync.
        """

        self.ensure_one()
        self._discuss_hub_check_can_tag()

        sanitized = self._discuss_hub_sanitize_tag_ids(tag_ids)
        tags = self.env["mail.discuss.hub.tag"].browse(sanitized).exists()

        # Apply with sudo to avoid surprises from channel write restrictions,
        # after explicit access checks above.
        self.sudo().write({"discuss_hub_tag_ids": [(6, 0, tags.ids)]})
        return {"discuss_hub_tag_ids": tags.ids}
