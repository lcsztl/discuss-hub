# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Discuss Hub Gateway Devtools LLM",
    "summary": "Recursos opcionais de tracing LLM para o devtools do Discuss Hub",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": [
        "mail_discuss_hub_gateway_devtools",
        "mail_gateway_llm",
    ],
    "data": [
        "views/devtools_settings_views.xml",
        "views/mail_gateway_llm_run_views.xml",
    ],
    "installable": True,
}
