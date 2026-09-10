import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.external_attachment_storage.services import storage as storage_service

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Configuration is persisted in system parameters (ir.config_parameter).
    # Credentials may alternatively be provided through the environment
    # variables EAS_ACCESS_KEY_ID / EAS_SECRET_ACCESS_KEY (or the boto3
    # credential chain): leave the fields empty then. Never commit
    # credentials to source control.
    external_attachment_enabled = fields.Boolean(
        string='External Attachment Storage',
        config_parameter='external_attachment_storage.enabled',
        help='Store newly uploaded attachments on the external object '
             'storage backend. Existing attachments always keep using the '
             'local filestore.')
    external_attachment_provider = fields.Selection(
        [('s3', 'S3 / S3-compatible')],
        string='Provider',
        default='s3',
        config_parameter='external_attachment_storage.provider',
    )
    external_attachment_endpoint_url = fields.Char(
        string='Endpoint URL',
        config_parameter='external_attachment_storage.endpoint_url',
        help='Leave empty for AWS S3. Example for other providers: '
             'https://<account-id>.r2.cloudflarestorage.com or '
             'http://minio.internal:9000')
    external_attachment_bucket = fields.Char(
        string='Bucket',
        config_parameter='external_attachment_storage.bucket',
    )
    external_attachment_region = fields.Char(
        string='Region',
        config_parameter='external_attachment_storage.region',
        help='e.g. us-east-1. Leave empty when the provider does not use '
             'regions or infers it from the endpoint.')
    external_attachment_base_path = fields.Char(
        string='Base Path',
        default=storage_service.DEFAULT_BASE_PATH,
        config_parameter='external_attachment_storage.base_path',
        help='Key prefix for stored objects, e.g. "attachments". Object '
             'keys look like: <base path>/<checksum[:2]>/<checksum>.')
    external_attachment_access_key_id = fields.Char(
        string='Access Key ID',
        config_parameter='external_attachment_storage.access_key_id',
        help='Leave empty to use the EAS_ACCESS_KEY_ID environment variable '
             'or the boto3 credential chain (IAM role, ...).')
    external_attachment_secret_access_key = fields.Char(
        string='Secret Access Key',
        config_parameter='external_attachment_storage.secret_access_key',
        help='Leave empty to use the EAS_SECRET_ACCESS_KEY environment '
             'variable or the boto3 credential chain (IAM role, ...).')

    def action_test_external_attachment_connection(self):
        """Validate the values currently entered in the settings form
        against the backend (they do not need to be saved yet)."""
        self.ensure_one()
        try:
            backend = storage_service.get_backend(
                self.external_attachment_provider or 's3',
                self.external_attachment_endpoint_url or '',
                self.external_attachment_bucket or '',
                self.external_attachment_region or '',
                self.external_attachment_access_key_id or None,
                self.external_attachment_secret_access_key or None,
                self.external_attachment_base_path or storage_service.DEFAULT_BASE_PATH,
            )
            backend.check_connection()
        except storage_service.ExternalStorageError as error:
            _logger.error(
                'External storage: connection test failed: %s', error)
            raise UserError(_(
                'Connection to the external storage backend failed: %s', error,
            )) from error
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('External Attachment Storage'),
                'message': _('Connection successful.'),
                'type': 'success',
                'sticky': False,
            },
        }
