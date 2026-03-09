# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from psycopg2 import IntegrityError
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    gateway_display_name = fields.Char(
        related="gateway_id.display_name",
        string="Gateway Name",
        readonly=True,
    )

    _sql_constraints = [
        (
            "discuss_channel_gateway_unique",
            "unique(gateway_id, gateway_channel_token)",
            "Gateway channel token must be unique per gateway.",
        ),
    ]

    @api.constrains("group_public_id", "group_ids")
    def _constraint_group_id_channel_gateway(self):
        unauthorized_channels = self.sudo().filtered(
            lambda channel: channel.channel_type not in ("channel", "gateway")
            and channel.group_public_id
        )
        if unauthorized_channels:
            raise ValidationError(
                _("Group authorization is only supported on channels and gateway channels.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        if "gateway_id" in self._fields and "group_public_id" in self._fields:
            gateway_ids = {
                vals.get("gateway_id")
                for vals in vals_list
                if vals.get("gateway_id") and not vals.get("group_public_id")
            }
            if gateway_ids:
                gateways = self.env["mail.gateway"].browse(list(gateway_ids)).sudo()
                gateway_map = {}
                for gateway in gateways:
                    group = gateway._ensure_access_group()
                    gateway_map[gateway.id] = {"group_id": group.id if group else False}
                for vals in vals_list:
                    gateway_id = vals.get("gateway_id")
                    if gateway_id:
                        gateway_info = gateway_map.get(gateway_id) or {}
                        if not vals.get("group_public_id") and gateway_info.get("group_id"):
                            vals["group_public_id"] = gateway_info["group_id"]
        return super().create(vals_list)

    def write(self, vals):
        if "gateway_id" in vals and "gateway_id" in self._fields:
            gateway = self.env["mail.gateway"].browse(vals["gateway_id"]).sudo()
            vals = dict(vals)
            if "group_public_id" not in vals:
                group = gateway._ensure_access_group() if gateway else False
                vals["group_public_id"] = group.id if group else False
        return super().write(vals)

    def _find_or_create_member_for_self(self):
        self.ensure_one()
        if self.channel_type != "gateway":
            return super()._find_or_create_member_for_self()

        member_domain = [("channel_id", "=", self.id), ("is_self", "=", True)]
        member = self.env["discuss.channel.member"].search(member_domain, limit=1)
        if member:
            return member

        try:
            # Typing/join requests can race on first access to a visible gateway channel.
            with mute_logger("odoo.sql_db"), self.env.cr.savepoint():
                return super()._find_or_create_member_for_self()
        except IntegrityError:
            member = self.env["discuss.channel.member"].search(member_domain, limit=1)
            if member:
                return member
            raise

    def action_archive(self):
        to_log = self.filtered(
            lambda channel: channel.active and channel.channel_type == "gateway"
        )
        result = super().action_archive()
        if to_log:
            partner = self.env.user.partner_id
            notification = Markup('<div class="o_mail_notification">%s</div>') % _(
                "archived the conversation"
            )
            for channel in to_log:
                channel.sudo().message_post(
                    author_id=partner.id,
                    body=notification,
                    message_type="notification",
                    subtype_xmlid="mail.mt_comment",
                )
        return result
