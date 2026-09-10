"""Serving override for the ``ir.http`` fallback mechanism.

``IrHttp._serve_fallback`` serves "serving attachments" (attachments whose
``url`` matches the request path, e.g. asset bundles) by calling
``odoo.http.Stream.from_attachment()`` directly, which reads the local
filestore and would crash on external keys.

The method is resolved through the model registry
(``self.registry['ir.http']._serve_fallback()`` in ``odoo/http.py``), so a
plain model inheritance is the supported way to extend it -- no
monkey-patching needed.

Local attachments keep the untouched base behavior; only records whose
``store_fname`` carries the external ``eas://`` prefix are intercepted, and
they are served after Odoo's normal access checks (unchanged).
"""

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _serve_fallback(cls):
        attach = request.env['ir.attachment'].sudo()._get_serve_attachment(
            request.httprequest.path)
        if attach and attach.store_fname and attach._is_external():
            return attach._get_external_attachment_stream().get_response()
        return super()._serve_fallback()
