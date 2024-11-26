# Copyright 2024 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import io
import logging

from PIL import Image

from odoo import api, fields, models
from odoo.tools import ImageProcess

_logger = logging.getLogger(__name__)

IMAGE_TYPES = ["image/png", "image/jpeg", "image/bmp", "image/tiff"]


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    resize_done = fields.Boolean()

    @api.model
    def _resize_image(self, datas, is_raw=False):
        ICP = self.env["ir.config_parameter"].sudo().get_param
        max_resolution = self.env.company.attachment_image_max_resolution or "1920x1920"
        max_width, max_height = map(int, max_resolution.split("x"))
        quality = int(ICP("base.image_autoresize_quality", 80))
        try:
            # Use odoo standard resize
            if is_raw:
                img = ImageProcess(False, verify_resolution=False)
                img.image = Image.open(io.BytesIO(datas))
                img.original_format = (img.image.format or "").upper()
            else:
                img = ImageProcess(datas, verify_resolution=False)
            width, height = img.image.size
            if width > max_width or height > max_height:
                img = img.resize(max_width, max_height)
                return (
                    img.image_quality(quality=quality)
                    if is_raw
                    else img.image_base64(quality=quality)
                )
        except Exception as e:
            _logger.warning(f"Failed to resize image: {e}")
            return datas
        return datas

    @api.model
    def _cron_resize_attachment_image(self, limit):
        models = self.env.company.attachment_image_resize_models
        model_list = models.split(",") if models else []
        if model_list:
            attachments = self.sudo().search(
                [
                    ("res_model", "in", model_list),
                    ("mimetype", "in", IMAGE_TYPES),
                    ("resize_done", "=", False),
                    # Added this filter because the default search only
                    # retrieves records with no res_field.
                    "|",
                    ("res_field", "=", False),
                    ("res_field", "!=", False),
                ],
                limit=limit,
            )
            for attachment in attachments:
                attachment.datas = self._resize_image(attachment.datas)
                attachments.resize_done = True
            if len(attachments) == limit:
                self.env.ref(
                    "attachment_image_resize.resize_attachment_image"
                )._trigger()

    @api.model_create_multi
    def create(self, vals_list):
        # here we resize the image first to avoid bloating the filestore
        for values in vals_list:
            res_model = values.get("res_model")
            models = self.env.company.attachment_image_resize_models
            mimetype = values.get("mimetype") or self._compute_mimetype(values)
            if (
                res_model
                and models
                and res_model in models.split(",")
                and mimetype in IMAGE_TYPES
            ):
                # Resize raw binary or Base64 data
                if "raw" in values and values["raw"]:
                    values["raw"] = self._resize_image(values["raw"], is_raw=True)
                elif "datas" in values and values["datas"]:
                    values["datas"] = self._resize_image(values["datas"], is_raw=False)
        return super(IrAttachment, self).create(vals_list)
