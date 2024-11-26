# Copyright 2024 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    attachment_image_resize_models = fields.Char(
        related="company_id.attachment_image_resize_models",
        readonly=False,
        help="When users attach images to these models, the images will be resized "
        "based on the maximum resolution specified for attachments.",
    )
    attachment_image_max_resolution = fields.Char(
        related="company_id.attachment_image_max_resolution",
        readonly=False,
        help="This resolution will be applied to the resizing of images"
        " for the specified models.",
    )
