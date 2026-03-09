# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class MailDiscussTeam(models.Model):
    _name = "mail.discuss.team"
    _description = "Discuss Team"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Team Leader",
        check_company=True,
    )
    member_ids = fields.Many2many(
        "res.users",
        string="Members",
    )
    access_group_id = fields.Many2one(
        "res.groups",
        string="Access Group",
        readonly=True,
        help="Access group managed automatically for this team.",
    )
    color = fields.Integer(default=0)
    description = fields.Text()

    has_integrations = fields.Boolean(
        compute="_compute_has_integrations",
        help="Technical flag used to show/hide the Integrations tab.",
    )

    def _compute_has_integrations(self):
        for team in self:
            team.has_integrations = any(
                field_name in team._fields
                for field_name in ("crm_team_id", "helpdesk_team_id")
            )

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        teams._ensure_team_leader_in_members()
        if not self.env.context.get("mail_discuss_hub_skip_group_sync"):
            teams._sync_access_group()
        return teams

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("mail_discuss_hub_skip_group_sync"):
            if (
                not self.env.context.get("mail_discuss_hub_skip_team_leader_check")
                and ("user_id" in vals or "member_ids" in vals)
            ):
                self._ensure_team_leader_in_members()
            if {"name", "member_ids", "user_id"} & set(vals):
                self._sync_access_group()
        return result

    def _ensure_team_leader_in_members(self):
        for team in self:
            if team.user_id and team.user_id not in team.member_ids:
                team.sudo().with_context(
                    mail_discuss_hub_skip_team_leader_check=True
                ).write({"member_ids": [(4, team.user_id.id)]})

    def _get_access_group_name(self):
        self.ensure_one()
        return f"Discuss Team: {self.name}"

    @api.model
    def _get_access_group_category(self):
        return self.env.ref(
            "mail_discuss_hub.module_category_discuss_hub", raise_if_not_found=False
        )

    def _ensure_access_group(self):
        self.ensure_one()
        category = self._get_access_group_category()
        if self.access_group_id:
            if category and self.access_group_id.category_id != category:
                self.access_group_id.sudo().write({"category_id": category.id})
            return self.access_group_id
        vals = {"name": self._get_access_group_name()}
        if category:
            vals["category_id"] = category.id
        group = self.env["res.groups"].sudo().create(vals)
        self.sudo().with_context(mail_discuss_hub_skip_group_sync=True).write(
            {"access_group_id": group.id}
        )
        return group

    def _sync_access_group(self):
        category = self._get_access_group_category()
        for team in self:
            group = team._ensure_access_group()
            desired_user_ids = team.member_ids.ids
            updates = {"users": [(6, 0, desired_user_ids)]}
            desired_name = team._get_access_group_name()
            if group.name != desired_name:
                updates["name"] = desired_name
            if category and group.category_id != category:
                updates["category_id"] = category.id
            group.sudo().with_context(mail_discuss_hub_skip_group_sync=True).write(updates)

    @api.model
    def _backfill_access_group_categories(self):
        category = self._get_access_group_category()
        self.sudo().search([("access_group_id", "!=", False)])._sync_access_group()
        if not category:
            return
        legacy_groups = self.env["res.groups"].sudo().search(
            [
                ("name", "=like", "Discuss Team:%"),
                ("category_id", "!=", category.id),
            ]
        )
        if legacy_groups:
            legacy_groups.write({"category_id": category.id})

    def _sync_members_from_access_group(self):
        for team in self:
            group = team.access_group_id
            if not group:
                continue
            desired_user_ids = group.users.ids
            if set(team.member_ids.ids) != set(desired_user_ids):
                team.write({"member_ids": [(6, 0, desired_user_ids)]})

    def unlink(self):
        groups = self.mapped("access_group_id")
        result = super().unlink()
        if groups:
            remaining = self.env["mail.discuss.team"].with_context(
                active_test=False
            ).search([("access_group_id", "in", groups.ids)])
            groups_to_remove = groups - remaining.mapped("access_group_id")
            if groups_to_remove:
                groups_to_remove.sudo().unlink()
        return result
