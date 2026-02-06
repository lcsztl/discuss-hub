# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Discuss Hub Core",
    "summary": "Discuss configuration menus for message administration",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "contributors": [
        "DiscussHub Team <https://github.com/discusshub/discuss_hub>",
    ],
    "website": "https://github.com/lcsztl/discuss_hub",
    "depends": ["mail"],
    "data": [
        "data/discuss_hub_groups.xml",
        "data/discuss_hub_roles.xml",
        "security/ir.model.access.csv",
        "views/discuss_hub_inbox_views.xml",
        "views/res_config_settings_views.xml",
        "views/discuss_channel_views.xml",
        "views/discuss_hub_tag_views.xml",
        "views/res_users_views.xml",
        "views/mail_discuss_team_views.xml",
        "views/mail_discuss_team_menus.xml",
        "views/mail_discuss_inbox_menus.xml",
        "views/mail_discuss_agent_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_discuss_hub/static/src/xml/discuss_sidebar_filters.xml",
            "mail_discuss_hub/static/src/xml/discuss_sidebar_categories.xml",
            "mail_discuss_hub/static/src/js/discuss_sidebar_filters.esm.js",
            "mail_discuss_hub/static/src/js/discuss_sidebar_filter_registry.esm.js",
            "mail_discuss_hub/static/src/scss/discuss_sidebar_filters.scss",
        ],
    },
    "installable": True,
}
