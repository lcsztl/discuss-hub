# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Based on concepts from:
#   - https://github.com/discusshub/discuss_hub

{
    "name": "Mail Gateway WhatsApp Evolution API",
    "summary": "Gateway integration for WhatsApp via Evolution API",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "contributors": [
        "DiscussHub Team <https://github.com/discusshub/discuss_hub>",
    ],
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_gateway", "mail_gateway_whatsapp_common"],
    "data": [
        "security/ir.model.access.csv",
        "data/evolution_webhook_event.xml",
        "views/mail_gateway_evolution.xml",
    ],
    "installable": True,
}
