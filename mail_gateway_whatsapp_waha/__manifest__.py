# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Gateway WhatsApp WAHA",
    "summary": "Gateway integration for WhatsApp via WAHA",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_gateway", "mail_gateway_whatsapp_common"],
    "data": [
        "security/ir.model.access.csv",
        "data/waha_webhook_event.xml",
        "views/mail_gateway_waha.xml",
    ],
    "installable": True,
}
