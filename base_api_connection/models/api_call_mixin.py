# Copyright 2023 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

import requests

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class APICallMixin(models.AbstractModel):
    _name = "api.call.mixin"
    _description = "API Call Mixin"

    def get_api_key(self, config):
        if config.token_type:
            return f"{config.token_type} {config.api_key}"
        return config.api_key

    def make_api_call(
        self,
        code,
        external_system="generic",
        endpoint=None,
        custom_headers=None,
        params=None,
        json=None,
        http_method="get",
    ):
        config = self.env["api.config"].search(
            [("external_system", "=", external_system), ("code", "=", code)], limit=1
        )
        if not config:
            raise UserError(_("API configuration not found."))
        url = f"{config.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        if custom_headers:
            headers.update(custom_headers)
        api_key = self.get_api_key(config)
        headers[config.header_api_key_string] = api_key
        function = getattr(requests, http_method)
        kwargs = {"headers": headers, "params": params}
        if json:
            kwargs["json"] = json
        try:
            response = function(url, **kwargs)
            response.raise_for_status()  # Raises HTTPError for bad responses
            _logger.info(
                f"Successful API call to {url}. Response status code: {response.status_code}"
            )
        except requests.exceptions.HTTPError as e:
            r = getattr(e, "response", None)
            status = getattr(r, "status_code", "n/a")
            rid = getattr(getattr(r, "headers", {}), "get", lambda *_: None)(
                "x-request-id"
            )
            body_text = ""
            if r is not None:
                try:
                    body_text = json.dumps(r.json(), ensure_ascii=False)
                except Exception:
                    body_text = r.text or "<no body>"
            raise UserError(
                f"HTTP Error {status} (x-request-id={rid})\n{body_text[:2000]}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise UserError(f"Request Error: {str(e)}") from e
        return response
