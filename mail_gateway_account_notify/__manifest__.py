# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Gateway Account Notify",
    "summary": "Send invoices through mail gateway from account send wizard",
    "version": "18.0.1.0.3",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["account", "mail_gateway_base"],
    "data": [
        "views/account_move_send_wizard_views.xml",
    ],
    "installable": True,
}
