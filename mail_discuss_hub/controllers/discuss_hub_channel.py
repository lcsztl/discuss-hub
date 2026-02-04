# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import http
from odoo.http import request

from odoo.addons.mail.tools.discuss import Store


class DiscussHubChannelController(http.Controller):
    @http.route("/discuss_hub/channel/fetch", methods=["POST"], type="json", auth="user")
    def discuss_hub_channel_fetch(
        self,
        channel_types=None,
        known_channel_ids=None,
        limit=50,
    ):
        channel_types = channel_types or []
        if isinstance(channel_types, str):
            channel_types = [channel_types]
        known_channel_ids = known_channel_ids or []
        limit = max(1, min(int(limit or 0), 200))
        domain = []
        if channel_types:
            domain.append(("channel_type", "in", channel_types))
        # Avoid returning sub-channels as top-level threads in the sidebar.
        # They should be fetched via the parent channel and rendered grouped.
        domain.append(("parent_channel_id", "=", False))
        if known_channel_ids:
            domain.append(("id", "not in", known_channel_ids))
        channels = request.env["discuss.channel"].search(
            domain, order="last_interest_dt desc, id desc", limit=limit
        )
        if not channels:
            return {}
        store = Store(channels)
        store.add(channels._get_last_messages(), for_current_user=True)
        return store.get_result()
