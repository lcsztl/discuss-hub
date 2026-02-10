# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Discuss Hub Gateway Devtools",
    "summary": "Ferramentas tecnicas de gateway para desenvolvimento (menus, logs, replay, cleanup)",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": [
        "mail_gateway",
        "mail_discuss_hub",
        "mail_gateway_whatsapp_evolution_api_manager",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/webhook_log_base_views.xml",
        "views/webhook_log_views.xml",
        "views/mail_message_views.xml",
        "views/evolution_api_instance_views.xml",
        "views/mail_discuss_hub_menus.xml",
        "views/devtools_settings_views.xml",
        "views/dev_menus.xml",
        "views/timeline_wizard.xml",
        "views/error_panel_views.xml",
        "views/connection_simulator_views.xml",
        "views/provider_comparator_views.xml",
        "views/gap_checklist_views.xml",
        "wizards/webhook_replay_wizard.xml",
        "wizards/cleanup_wizard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_discuss_hub_gateway_devtools/static/src/js/message_actions_devtools.esm.js",
        ],
    },
    "installable": True,
}
