"""S3 / S3-compatible storage backend.

Works with AWS S3, Cloudflare R2, MinIO and any S3-compatible endpoint.
Provider-specific knowledge lives here only -- ``ir.attachment`` never
talks to boto3 directly.
"""

import io
import logging

from odoo.addons.external_attachment_storage.services.storage import (
    ExternalStorageError,
    StorageBackend,
)

try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError
    HAS_BOTO3 = True
    # BotoCoreError covers connection/timeout/credential issues,
    # ClientError covers HTTP-level errors (403, 404, ...).
    _BOTO_ERRORS = (BotoCoreError, ClientError)
except ImportError:  # pragma: no cover - depends on the environment
    boto3 = None
    BotoConfig = None
    _BOTO_ERRORS = ()
    HAS_BOTO3 = False

_logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = {'404', 'NoSuchKey', 'NotFound'}


class S3Storage(StorageBackend):
    """StorageBackend implementation on top of boto3."""

    def __init__(self, config):
        if not HAS_BOTO3:
            raise ExternalStorageError(
                "The Python library 'boto3' is not installed. "
                "Install it with: pip install boto3")
        self.config = config
        self._client = self._build_client()

    def _build_client(self):
        boto_config = BotoConfig(
            connect_timeout=10,
            read_timeout=60,
            retries={'max_attempts': 3, 'mode': 'standard'},
        )
        if self.config.endpoint_url:
            # Most S3-compatible services (MinIO, R2, ...) expect path-style
            # addressing when a custom endpoint is used.
            boto_config = boto_config.merge(
                BotoConfig(s3={'addressing_style': 'path'}))
        return boto3.client(
            's3',
            endpoint_url=self.config.endpoint_url or None,
            region_name=self.config.region or None,
            aws_access_key_id=self.config.access_key_id,
            aws_secret_access_key=self.config.secret_access_key,
            config=boto_config,
        )

    def _error_code(self, error):
        response = getattr(error, 'response', None) or {}
        return (response.get('Error') or {}).get('Code') or ''

    def _wrap(self, operation, key, error):
        """Log (without any secret) and re-raise as ExternalStorageError."""
        code = self._error_code(error)
        _logger.error(
            "External storage: S3 %s failed for key %s (code %s)",
            operation, key, code or 'n/a', exc_info=True)
        suffix = ' (code %s)' % code if code else ''
        raise ExternalStorageError(
            'S3 operation %r failed for key %r%s.'
            % (operation, key, suffix)) from error

    def write(self, key, content):
        # upload_fileobj transparently uses multipart uploads for large
        # payloads and wraps (does not copy) the given buffer.
        try:
            self._client.upload_fileobj(
                io.BytesIO(content), self.config.bucket, key)
        except _BOTO_ERRORS as error:
            self._wrap('write', key, error)

    def read(self, key):
        try:
            response = self._client.get_object(
                Bucket=self.config.bucket, Key=key)
            return response['Body'].read()
        except _BOTO_ERRORS as error:
            self._wrap('read', key, error)

    def delete(self, key):
        try:
            # Deleting an absent key is a no-op on S3 (idempotent).
            self._client.delete_object(
                Bucket=self.config.bucket, Key=key)
        except _BOTO_ERRORS as error:
            self._wrap('delete', key, error)

    def exists(self, key):
        try:
            self._client.head_object(Bucket=self.config.bucket, Key=key)
            return True
        except _BOTO_ERRORS as error:
            if self._error_code(error) in _NOT_FOUND_CODES:
                return False
            self._wrap('head', key, error)

    def check_connection(self):
        try:
            self._client.head_bucket(Bucket=self.config.bucket)
        except _BOTO_ERRORS as error:
            self._wrap('head_bucket', '<bucket %s>' % self.config.bucket, error)
