# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from markupsafe import Markup

from odoo import _, api, fields, models


class MailGateway(models.Model):
    _inherit = "mail.gateway"

    discuss_team_ids = fields.Many2many(
        "mail.discuss.team",
        string="Discuss Teams",
        help="Teams allowed to handle this inbox.",
    )
    discuss_agent_ids = fields.Many2many(
        "res.users",
        "mail_gateway_discuss_agent_rel",
        "gateway_id",
        "user_id",
        string="Discuss Agents",
        help="Agents allowed to handle this inbox.",
    )
    outgoing_signature = fields.Boolean(
        string="Outgoing signature",
        default=False,
        help=(
            "When enabled, Odoo prepends the message author name to outbound text "
            "messages (e.g. '*Mitchel Admin:* Hello'). Useful when multiple internal "
            "users share the same gateway."
        ),
    )
    reopen_archived_conversations = fields.Boolean(
        string="Reopen archived conversations",
        default=True,
        help=(
            "When enabled, any inbound or outbound gateway message will reopen "
            "archived conversations instead of creating a new one."
        ),
    )
    outgoing_signature_format = fields.Char(
        string="Signature format",
        default="*{author}:*\\n",
        help=(
            "Format used when 'Outgoing signature' is enabled. "
            "Supports: {author}. Tip: you can use \\n for a new line. "
            "Example: '*{author}:*\\n'."
        ),
    )
    access_group_id = fields.Many2one(
        "res.groups",
        string="Gateway Access Group",
        readonly=True,
        help="Access group managed automatically for this gateway.",
    )

    def _get_access_group_name(self):
        self.ensure_one()
        return f"Gateway: {self.name}"

    def _get_channel_id(self, chat_token):
        self.ensure_one()
        if (
            "reopen_archived_conversations" in self._fields
            and self.reopen_archived_conversations
        ):
            return (
                self.env["discuss.channel"]
                .with_context(active_test=False)
                .search(
                    [
                        ("gateway_channel_token", "=", str(chat_token)),
                        ("gateway_id", "=", self.id),
                    ],
                    limit=1,
                )
                .id
            )
        return super()._get_channel_id(chat_token)

    def _ensure_access_group(self):
        self.ensure_one()
        if self.access_group_id:
            return self.access_group_id
        vals = {"name": self._get_access_group_name()}
        category = self.env.ref(
            "mail_gateway.module_category_gateway", raise_if_not_found=False
        )
        if category:
            vals["category_id"] = category.id
        group = self.env["res.groups"].sudo().create(vals)
        self.sudo().with_context(
            mail_discuss_hub_gateway_skip_group_sync=True
        ).write({"access_group_id": group.id})
        return group

    def _ensure_inbox(self):
        Inbox = self.env["discuss.hub.inbox"].sudo()
        for gateway in self:
            inbox = Inbox.search(
                [("inbox_type", "=", "gateway"), ("gateway_id", "=", gateway.id)],
                limit=1,
            )
            if inbox:
                if inbox.name != gateway.name:
                    inbox.write({"name": gateway.name})
                continue
            Inbox.create(
                {
                    "inbox_type": "gateway",
                    "gateway_id": gateway.id,
                    "name": gateway.name,
                }
            )

    def _get_auto_assign_users(self):
        self.ensure_one()
        users = self.member_ids
        group = self.access_group_id or self._ensure_access_group()
        if not users and group:
            users = group.users
        if group:
            users = users.filtered(lambda user: group in user.groups_id)
        return users.filtered(lambda user: user.active and user.partner_id and not user._is_public())

    def _apply_outgoing_signature(self, author_name, body):
        self.ensure_one()
        if not self.outgoing_signature or not author_name:
            return body
        author = str(author_name or "").strip()
        if not author:
            return body
        fmt = (self.outgoing_signature_format or "").strip()
        if not fmt:
            fmt = "*{author}:*\\n"
        fmt = fmt.replace("\\n", "\n").replace("\\t", "\t")
        try:
            prefix = fmt.format(author=author)
        except Exception:
            prefix = "*{author}:*\\n".format(author=author)
        if not prefix:
            return body
        normalized_body = (body or "").lstrip()
        if normalized_body.startswith(prefix):
            return body
        return f"{prefix}{body or ''}"

    def _should_reopen_archived(self):
        self.ensure_one()
        return bool(self.reopen_archived_conversations)

    def _reopen_channel_if_needed(self, channel, reopened_by=None):
        self.ensure_one()
        if not channel or channel.active or not self._should_reopen_archived():
            return channel
        channel.sudo().action_unarchive()
        if reopened_by:
            notification = Markup('<div class="o_mail_notification">%s</div>') % _(
                "reopened the conversation"
            )
            channel.sudo().message_post(
                author_id=reopened_by.id,
                body=notification,
                message_type="notification",
                subtype_xmlid="mail.mt_comment",
            )
        return channel

    def _sync_access_group(self):
        for gateway in self:
            group = gateway._ensure_access_group()
            desired_name = gateway._get_access_group_name()
            if group.name != desired_name:
                group.sudo().with_context(
                    mail_discuss_hub_gateway_skip_group_sync=True
                ).write({"name": desired_name})

    def _sync_access_group_implied_groups(self):
        Team = self.env["mail.discuss.team"].sudo()
        gateways = self.sudo()
        for gateway in gateways.filtered(lambda record: not record.access_group_id):
            gateway._ensure_access_group()

        gateway_group_ids = gateways.mapped("access_group_id").ids
        if not gateway_group_ids:
            return

        linked_teams = gateways.mapped("discuss_team_ids")
        implied_teams = Team.search(
            [("access_group_id.implied_ids", "in", gateway_group_ids)]
        )
        teams = (linked_teams | implied_teams).sudo()
        for team in teams.filtered(lambda record: not record.access_group_id):
            team._ensure_access_group()

        team_group_ids = teams.mapped("access_group_id").ids
        if team_group_ids:
            for group in gateways.mapped("access_group_id"):
                invalid_implied = group.implied_ids.filtered(
                    lambda implied: implied.id in team_group_ids
                )
                if invalid_implied:
                    group.sudo().write(
                        {"implied_ids": [(3, group_id) for group_id in invalid_implied.ids]}
                    )

        all_gateway_group_ids = set(
            self.env["mail.gateway"]
            .sudo()
            .search([("access_group_id", "!=", False)])
            .mapped("access_group_id")
            .ids
        )
        for team in teams:
            if not team.access_group_id:
                continue
            gateways_for_team = self.env["mail.gateway"].sudo().search(
                [("discuss_team_ids", "in", team.id)]
            )
            desired_gateway_group_ids = set(
                gateways_for_team.mapped("access_group_id").ids
            )
            current_gateway_group_ids = set(
                team.access_group_id.implied_ids.ids
            ) & all_gateway_group_ids
            to_add = desired_gateway_group_ids - current_gateway_group_ids
            to_remove = current_gateway_group_ids - desired_gateway_group_ids
            updates = [(4, group_id) for group_id in to_add] + [
                (3, group_id) for group_id in to_remove
            ]
            if updates:
                team.access_group_id.sudo().write({"implied_ids": updates})

    def _sync_access_group_agents(self, previous_agent_ids=None):
        previous_agent_ids = previous_agent_ids or {}
        for gateway in self.sudo():
            group = gateway._ensure_access_group()
            if not group:
                continue
            desired_agent_ids = set(gateway.discuss_agent_ids.ids)
            current_group_user_ids = set(group.users.ids)
            to_add = desired_agent_ids - current_group_user_ids
            to_remove = set()
            if gateway.id in previous_agent_ids:
                removed_agent_ids = set(previous_agent_ids[gateway.id]) - desired_agent_ids
                if removed_agent_ids:
                    team_user_ids = set(gateway.discuss_team_ids.mapped("member_ids").ids)
                    to_remove = {
                        user_id
                        for user_id in removed_agent_ids
                        if user_id not in team_user_ids
                    }
            if to_add or to_remove:
                updates = [(4, user_id) for user_id in to_add] + [
                    (3, user_id) for user_id in to_remove
                ]
                group.sudo().write({"users": updates})

    def _sync_channels_access_group(self):
        channel_model = self.env["discuss.channel"].sudo()
        for gateway in self:
            group_id = gateway.access_group_id.id if gateway.access_group_id else False
            channels = channel_model.search([("gateway_id", "=", gateway.id)])
            if channels:
                channels.write({"group_public_id": group_id})

    @api.model_create_multi
    def create(self, vals_list):
        gateways = super().create(vals_list)
        gateways._sync_access_group()
        gateways._sync_access_group_implied_groups()
        gateways._sync_access_group_agents()
        gateways._sync_channels_access_group()
        gateways._ensure_inbox()
        return gateways

    def write(self, vals):
        previous_agent_ids = {}
        if "discuss_agent_ids" in vals:
            for gateway in self:
                previous_agent_ids[gateway.id] = gateway.discuss_agent_ids.ids
        result = super().write(vals)
        if not self.env.context.get("mail_discuss_hub_gateway_skip_group_sync"):
            if "name" in vals:
                self._sync_access_group()
                self._ensure_inbox()
            self._sync_access_group_implied_groups()
            if "discuss_agent_ids" in vals or "access_group_id" in vals:
                self._sync_access_group_agents(previous_agent_ids)
        if "access_group_id" in vals:
            self._sync_channels_access_group()
        return result

    def unlink(self):
        groups = self.mapped("access_group_id")
        result = super().unlink()
        if groups:
            remaining = self.env["mail.gateway"].with_context(active_test=False).search(
                [("access_group_id", "in", groups.ids)]
            )
            groups_to_remove = groups - remaining.mapped("access_group_id")
            if groups_to_remove:
                groups_to_remove.sudo().unlink()
        return result
