# Copyright 2023 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Base API Connection",
    "version": "15.0.1.0.0",
    "category": "API",
    "website": "https://www.quartile.co",
    "author": "Quartile, Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/api_config_views.xml",
    ],
    "installable": True,
}
