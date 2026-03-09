# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import http
from odoo.http import request


class DiscussHubGatewaySidebarController(http.Controller):
    @http.route(
        "/discuss_hub/gateway/sidebar",
        methods=["POST"],
        type="json",
        auth="user",
    )
    def discuss_hub_gateway_sidebar(self):
        Gateway = request.env["mail.gateway"]
        domain = [("company_id", "in", request.env.companies.ids + [False])]
        if "access_group_id" in Gateway._fields:
            domain = [
                *domain,
                "|",
                ("access_group_id", "=", False),
                ("access_group_id", "in", request.env.user.groups_id.ids),
            ]
        gateways = Gateway.search(domain, order="name asc, id asc")
        return [
            {
                "id": gateway.id,
                "name": gateway.display_name or gateway.name,
            }
            for gateway in gateways
        ]
