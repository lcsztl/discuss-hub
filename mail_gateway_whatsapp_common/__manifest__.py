# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Gateway WhatsApp Common",
    "summary": "Shared DTO and service helpers for WhatsApp gateways",
    "version": "18.0.1.1.3",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_gateway"],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_guest_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_gateway_whatsapp_common/static/src/core/common/message_model_patch.esm.js",
            "mail_gateway_whatsapp_common/static/src/core/common/notification_model_patch.esm.js",
            "mail_gateway_whatsapp_common/static/src/core/common/notification_status.scss",
            "mail_gateway_whatsapp_common/static/src/components/message/gateway_status.xml",
        ],
    },
    "installable": True,
}
