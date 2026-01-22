# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    lead_ids = fields.Many2many(
        "crm.lead",
        "crm_lead_discuss_channel_rel",
        "channel_id",
        "lead_id",
        string="CRM Leads",
    )
    lead_count = fields.Integer(compute="_compute_lead_count", string="Leads")

    def _compute_lead_count(self):
        for channel in self:
            channel.lead_count = len(channel.lead_ids)

    def action_get_discuss_lead_panel_data(self):
        self.ensure_one()
        # Check if user can create leads - try group first, fallback to model access
        can_create = (
            self.env.user.has_group("crm.group_crm_user")
            or self.env["crm.lead"].check_access_rights("create", raise_exception=False)
        )
        try:
            leads = self.lead_ids.read(["id", "name"]) if self.lead_ids else []
        except AccessError:
            leads = []
        default_team_id = (
            self.discuss_team_id.crm_team_id.id
            if self.discuss_team_id and self.discuss_team_id.crm_team_id
            else False
        )
        return {
            "can_create": can_create,
            "leads": leads,
            "default_team_id": default_team_id,
        }

    def action_create_discuss_lead(self, values):
        self.ensure_one()
        # Check if user can create leads
        if not (
            self.env.user.has_group("crm.group_crm_user")
            or self.env["crm.lead"].check_access_rights("create", raise_exception=False)
        ):
            raise AccessError(_("You do not have access to create CRM leads."))

        name = (values or {}).get("name") or ""
        name = name.strip()
        if not name:
            raise UserError(_("Lead title is required."))

        team_id = (values or {}).get("team_id") or False
        team = self.env["crm.team"].browse(team_id).exists() if team_id else False
        if not team and self.discuss_team_id and self.discuss_team_id.crm_team_id:
            team = self.discuss_team_id.crm_team_id

        # Get partner from channel members (exclude current user)
        partner = False
        channel_partners = self.channel_member_ids.mapped("partner_id").filtered(
            lambda p: p.id != self.env.user.partner_id.id
        )
        if channel_partners:
            partner = channel_partners[0]  # Take the first non-user partner

        lead_vals = {
            "name": name,
            "team_id": team.id if team else False,
            "user_id": self.env.user.id,
            "description": self._prepare_discuss_lead_description(),
            "referred": self.env.user.partner_id.name,
        }
        if partner:
            lead_vals["partner_id"] = partner.id
        lead = self.env["crm.lead"].create(lead_vals)
        self.lead_ids = [(4, lead.id)]
        return {"id": lead.id, "name": lead.name}

    def _prepare_discuss_lead_description(self, limit=50):
        lines = []
        messages = self.message_ids.sorted("id")
        if limit:
            messages = messages[-limit:]
        for message in messages:
            author = message.author_id.name or self.anonymous_name or _("Unknown")
            body = html2plaintext(message.body or "").strip()
            if not body:
                continue
            lines.append(f"{author}: {body}")
        return "<br/>".join(lines)
