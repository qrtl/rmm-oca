# Copyright 2024 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model
    def get_param(self, key, default=False):
        res_model = self.env.context.get("resize_target_model")
        if not res_model or key != "base.image_autoresize_max_px":
            return super().get_param(key, default=default)
        model_rec = self.env["ir.model"].search([("model", "=", res_model)], limit=1)
        if model_rec.attachment_image_max_resolution:
            return model_rec.attachment_image_max_resolution
        models = self.env.company.attachment_image_resize_models
        if models and res_model in [model.strip() for model in models.split(",")]:
            return self.env.company.attachment_image_max_resolution or "1920x1920"
        return super().get_param(key, default=default)
