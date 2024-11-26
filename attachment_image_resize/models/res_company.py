# Copyright 2024 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    attachment_image_resize_models = fields.Char(
        help="When users attach images to these models, the images will be resized "
        "based on the maximum resolution specified for attachments."
    )
    attachment_image_max_resolution = fields.Char(
        help="This resolution will be applied to the resizing of images"
        " for the specified models."
    )
