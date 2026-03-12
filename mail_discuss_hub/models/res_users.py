# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo import Command


class ResUsers(models.Model):
    _inherit = "res.users"

    discuss_role = fields.Selection(
        [
            ("agent", "Agent"),
            ("manager", "Manager"),
            ("admin", "Administrator"),
        ],
        string="Discuss Role",
        compute="_compute_discuss_role",
        inverse="_inverse_discuss_role",
        store=True,
    )
    discuss_message_signature = fields.Text(string="Message Signature")

    @api.depends("groups_id")
    def _compute_discuss_role(self):
        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_manager = self.env.ref(
            "mail_discuss_hub.group_discuss_hub_manager", raise_if_not_found=False
        )
        group_system = self.env.ref("base.group_system", raise_if_not_found=False)
        for user in self:
            if group_system and group_system in user.groups_id:
                user.discuss_role = "admin"
            elif group_manager and group_manager in user.groups_id:
                user.discuss_role = "manager"
            elif group_user and group_user in user.groups_id:
                user.discuss_role = "agent"
            else:
                user.discuss_role = False

    def _inverse_discuss_role(self):
        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_manager = self.env.ref(
            "mail_discuss_hub.group_discuss_hub_manager", raise_if_not_found=False
        )
        group_system = self.env.ref("base.group_system", raise_if_not_found=False)
        role_map = {
            "agent": group_user,
            "manager": group_manager,
            "admin": group_system,
        }
        role_group_ids = {
            group.id
            for group in (group_user, group_manager, group_system)
            if group
        }
        for user in self:
            target_group = role_map.get(user.discuss_role)
            commands = []
            for group_id in role_group_ids:
                if target_group and group_id == target_group.id:
                    continue
                if group_id in user.groups_id.ids:
                    commands.append(Command.unlink(group_id))
            if target_group and target_group.id not in user.groups_id.ids:
                commands.append(Command.link(target_group.id))
            if commands:
                user.write({"groups_id": commands})

    def _get_discuss_team_groups(self):
        teams = self.env["mail.discuss.team"].sudo().search(
            [("access_group_id", "!=", False)]
        )
        return teams.mapped("access_group_id")

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        groups = users._get_discuss_team_groups()
        if groups:
            group_ids = set(users.mapped("groups_id").ids) & set(groups.ids)
            if group_ids:
                teams = self.env["mail.discuss.team"].sudo().search(
                    [("access_group_id", "in", list(group_ids))]
                )
                teams._sync_members_from_access_group()
        return users

    def write(self, vals):
        groups = None
        before = None
        if "groups_id" in vals:
            groups = self._get_discuss_team_groups()
            if groups:
                group_ids = set(groups.ids)
                # Team/group synchronization should not depend on the current user
                # keeping read access to res.users while their own groups change.
                users_for_sync = self.sudo()
                before = {
                    user.id: set(user.groups_id.ids) & group_ids
                    for user in users_for_sync
                }
        res = super().write(vals)
        if "groups_id" in vals and groups:
            group_ids = set(groups.ids)
            changed_group_ids = set()
            for user in self.sudo():
                after = set(user.groups_id.ids) & group_ids
                changed_group_ids |= before.get(user.id, set()) ^ after
            if changed_group_ids:
                teams = self.env["mail.discuss.team"].sudo().search(
                    [("access_group_id", "in", list(changed_group_ids))]
                )
                teams._sync_members_from_access_group()
        return res
