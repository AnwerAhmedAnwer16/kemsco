# models/ir_attachment.py

from odoo import models, fields, api

# Pseudo-uri scheme used by external_attachment_storage in store_fname.
EXTERNAL_SCHEME = 'eas://'
EXTERNAL_ICP_PREFIX = 'external_attachment_storage.'


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    task_report_url = fields.Char(
        string="Report URL",
        compute='_compute_task_report_url',
        help="Absolute URL used in the printed task report. For attachments "
             "stored on the external object storage it points directly at the "
             "object (the bucket must be publicly readable); otherwise it "
             "falls back to the Odoo /web/content download link.",
    )

    @api.depends('store_fname', 'access_token')
    def _compute_task_report_url(self):
        base_url = (self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '') or '').rstrip('/')
        for attachment in self:
            attachment.task_report_url = (
                attachment._task_report_external_url()
                or attachment._task_report_content_url(base_url))

    def _task_report_external_url(self):
        """Direct object-storage URL for externally stored attachments, or
        ``False`` when the attachment is not stored externally or the backend
        is not configured."""
        self.ensure_one()
        store_fname = self.store_fname or ''
        if not store_fname.startswith(EXTERNAL_SCHEME):
            return False

        get_param = self.env['ir.config_parameter'].sudo().get_param
        bucket = get_param(EXTERNAL_ICP_PREFIX + 'bucket', '') or ''
        if not bucket:
            return False

        key = store_fname[len(EXTERNAL_SCHEME):]
        endpoint = (get_param(EXTERNAL_ICP_PREFIX + 'endpoint_url', '') or '').rstrip('/')
        if endpoint:
            # S3-compatible providers (MinIO, R2, ...) use path-style URLs.
            return '%s/%s/%s' % (endpoint, bucket, key)

        region = get_param(EXTERNAL_ICP_PREFIX + 'region', '') or ''
        if region and region != 'us-east-1':
            host = '%s.s3.%s.amazonaws.com' % (bucket, region)
        else:
            host = '%s.s3.amazonaws.com' % bucket
        return 'https://%s/%s' % (host, key)

    def _task_report_content_url(self, base_url):
        """Standard Odoo download URL, with the access token when present so
        the link also works for users who are not logged in."""
        self.ensure_one()
        token = self.sudo().access_token
        suffix = '&access_token=%s' % token if token else ''
        return '%s/web/content/%s?download=true%s' % (base_url, self.id, suffix)
