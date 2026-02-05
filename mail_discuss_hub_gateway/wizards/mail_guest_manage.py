# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models
from odoo.addons.mail.tools.discuss import Store

_logger = logging.getLogger(__name__)


class MailGuestManage(models.TransientModel):
    _inherit = "mail.guest.manage"

    def _get_partner_vals(self):
        vals = super()._get_partner_vals()
        guest = self.guest_id
        partner_model = self.env["res.partner"]
        if (
            "gateway_phone" in partner_model._fields
            and guest.gateway_phone
            and not vals.get("gateway_phone")
        ):
            vals["gateway_phone"] = guest.gateway_phone
        if "tag_ids" in guest._fields and guest.tag_ids:
            vals["category_id"] = [(6, 0, guest.tag_ids.ids)]
        return vals

    def _merge_partner(self, partner):
        self._sync_gateway_channels(partner)
        self._apply_guest_tags(partner)
        self._apply_gateway_phone(partner)
        for member in self.env["discuss.channel.member"].search(
            [("guest_id", "=", self.guest_id.id)]
        ):
            self.env["discuss.channel.member"].create(
                self._channel_member_vals(member, partner)
            )
            member.unlink()
        messages = self.env["mail.message"].search(
            [("author_guest_id", "=", self.guest_id.id)]
        )
        if messages:
            messages.write(
                {
                    "author_id": partner.id,
                    "author_guest_id": False,
                }
            )
            messages.invalidate_recordset(["author_id", "author_guest_id"])
            store = Store()
            messages._author_to_store(store)
            # Update current user UI immediately.
            self.env.user._bus_send_store(store)
            # Update all channel members listening to the channel bus.
            channels = self.env["discuss.channel"].browse(
                messages.filtered(
                    lambda message: message.model == "discuss.channel" and message.res_id
                ).mapped("res_id")
            )
            if channels:
                channels._bus_send_store(store)

    def _apply_guest_tags(self, partner):
        guest = self.guest_id
        if "category_id" not in partner._fields:
            return
        if "tag_ids" not in guest._fields or not guest.tag_ids:
            return
        existing = set(partner.category_id.ids)
        desired = set(guest.tag_ids.ids)
        if desired.issubset(existing):
            return
        partner.category_id = [(6, 0, sorted(existing | desired))]

    def _apply_gateway_phone(self, partner):
        guest = self.guest_id
        if (
            "gateway_phone" in partner._fields
            and guest.gateway_phone
            and not partner.gateway_phone
        ):
            partner.gateway_phone = guest.gateway_phone

    def _sync_gateway_channels(self, partner):
        guest = self.guest_id
        token = getattr(guest, "gateway_phone", False)
        gateways = self._get_guest_gateways(guest)
        if not gateways:
            return
        if not token:
            _logger.warning(
                "Guest %s has no gateway_phone; skipping gateway partner links.",
                guest.id,
            )
            return
        gateway_channel_model = self.env["res.partner.gateway.channel"]
        for gateway in gateways:
            existing = gateway_channel_model.search(
                [("partner_id", "=", partner.id), ("gateway_id", "=", gateway.id)],
                limit=1,
            )
            if existing:
                if existing.gateway_token != token:
                    existing.write({"gateway_token": token})
                continue
            gateway_channel_model.create(
                {
                    "partner_id": partner.id,
                    "gateway_id": gateway.id,
                    "gateway_token": token,
                }
            )

    def _get_guest_gateways(self, guest):
        members = self.env["discuss.channel.member"].search(
            [("guest_id", "=", guest.id)]
        )
        channels = members.mapped("channel_id")
        channels = channels.filtered(
            lambda channel: channel.channel_type == "gateway" and channel.gateway_id
        )
        return channels.mapped("gateway_id")
