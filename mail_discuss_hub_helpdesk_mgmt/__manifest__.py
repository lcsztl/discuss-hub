# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Based on concepts from:
#   - https://github.com/discusshub/discuss_hub

{
    "name": "Mail Discuss Hub Helpdesk Mgmt",
    "summary": "Helpdesk Mgmt integration for Discuss Teams",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "contributors": [
        "DiscussHub Team <https://github.com/discusshub/discuss_hub>",
    ],
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_discuss_hub", "helpdesk_mgmt"],
    "post_init_hook": "post_init_hook",
    "data": [
        "views/mail_discuss_team_views.xml",
        "views/helpdesk_ticket_team_views.xml",
    ],
    "installable": True,
}
