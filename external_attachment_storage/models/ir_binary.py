"""Serving overrides for attachments stored in the external backend.

In Odoo 17, ``/web/content`` and ``/web/image`` stream attachment content
through ``odoo.http.Stream.from_attachment()``, which -- for attachments
with a ``store_fname`` -- builds a *local filesystem* path from
``config.filestore(db) + store_fname`` and ``os.stat``s it, completely
bypassing ``ir.attachment._file_read``.

External keys would therefore crash the request. ``ir.binary._record_to_stream``
is overridden here; it is documented in the Odoo 17 source as "an extensible
hook for other modules" and covers ``/web/content``, ``/web/image`` and the
binary/image fields of any model (both direct attachments and field
attachments).

The other core call site (``ir.http._serve_fallback``) is overridden in
``models/ir_http.py``.

Local attachments keep the untouched base behavior: the override only
intercepts records whose ``store_fname`` carries the external ``eas://``
prefix, and always runs *after* Odoo's normal access checks.
"""

from odoo import models
from odoo.exceptions import MissingError
from odoo.http import Stream


class IrBinary(models.AbstractModel):
    _inherit = 'ir.binary'

    def _record_to_stream(self, record, field_name):
        if record._name == 'ir.attachment' and field_name in ('raw', 'datas', 'db_datas'):
            if record._is_external():
                return record._get_external_attachment_stream()
            return super()._record_to_stream(record, field_name)

        record.check_field_access_rights('read', [field_name])

        if record._fields[field_name].attachment:
            field_attachment = self.env['ir.attachment'].sudo().search(
                domain=[('res_model', '=', record._name),
                        ('res_id', '=', record.id),
                        ('res_field', '=', field_name)],
                limit=1)
            if not field_attachment:
                raise MissingError("The related attachment does not exist.")
            if field_attachment._is_external():
                return field_attachment._get_external_attachment_stream()
            return Stream.from_attachment(field_attachment)

        return Stream.from_binary_field(record, field_name)
