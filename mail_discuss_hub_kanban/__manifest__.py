# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Discuss Hub Kanban",
    "summary": "Kanban pipeline for Discuss Hub conversations",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Soloz Technologies",
    "website": "https://github.com/lcsztl/discuss-hub",
    "depends": ["mail_discuss_hub_gateway"],
    "data": [
        "security/ir.model.access.csv",
        "data/discuss_hub_stage_data.xml",
        "views/discuss_hub_stage_views.xml",
        "views/discuss_channel_views.xml",
        "views/discuss_hub_kanban_views.xml",
    ],
    "installable": True,
}
