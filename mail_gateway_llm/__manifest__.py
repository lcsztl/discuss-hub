# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Gateway LLM",
    "summary": "LLM assistants for gateway conversations",
    "version": "18.0.2.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_gateway_base", "llm_assistant"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/mail_gateway_views.xml",
        "views/discuss_channel_views.xml",
        "views/mail_gateway_llm_access_binding_views.xml",
        "views/mail_gateway_llm_run_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_gateway_llm/static/src/discuss/thread_actions.esm.js",
        ],
    },
    "installable": True,
}
