# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Based on concepts from:
#   - https://github.com/discusshub/discuss_hub

{
    "name": "Mail Discuss Hub CRM",
    "summary": "CRM integration for Discuss Teams",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "contributors": [
        "DiscussHub Team <https://github.com/discusshub/discuss_hub>",
    ],
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_discuss_hub", "crm"],
    "post_init_hook": "post_init_hook",
    "data": [
        "views/crm_lead_views.xml",
        "views/crm_team_views.xml",
        "views/mail_discuss_team_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_discuss_hub_crm/static/src/discuss/*.js",
            "mail_discuss_hub_crm/static/src/discuss/*.xml",
        ],
    },
    "installable": True,
}
