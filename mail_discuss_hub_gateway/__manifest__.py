# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Discuss Hub Gateway",
    "summary": "Discuss UI helpers for gateway channels",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_gateway", "mail_discuss_hub"],
    "data": [
        "data/rule_update.xml",
        "security/mail_discuss_hub_gateway_security.xml",
        "views/discuss_channel_views.xml",
        "views/mail_guest_views.xml",
        "views/mail_gateway_views.xml",
        "views/res_partner_views.xml",
        "views/discuss_inbox_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_discuss_hub_gateway/static/src/js/contact_sidebar_service.esm.js",
            "mail_discuss_hub_gateway/static/src/js/contact_sidebar_panel.esm.js",
            "mail_discuss_hub_gateway/static/src/js/contact_sidebar_patch.esm.js",
            "mail_discuss_hub_gateway/static/src/js/gateway_transfer_panel.esm.js",
            "mail_discuss_hub_gateway/static/src/js/gateway_instance_sidebar.esm.js",
            "mail_discuss_hub_gateway/static/src/js/gateway_sidebar_filter_provider.esm.js",
            "mail_discuss_hub_gateway/static/src/js/message_patch.esm.js",
            "mail_discuss_hub_gateway/static/src/js/thread_actions.esm.js",
            "mail_discuss_hub_gateway/static/src/xml/contact_sidebar_panel.xml",
            "mail_discuss_hub_gateway/static/src/xml/gateway_transfer_panel.xml",
        ],
    },
    "installable": True,
}
