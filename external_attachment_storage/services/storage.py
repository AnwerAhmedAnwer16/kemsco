"""Storage abstraction for external attachment storage.

This module is deliberately free of Odoo imports so that the abstraction,
the key strategy and the configuration validation can be reasoned about
(and tested) independently of the ORM.

Design notes
------------
* ``ir.attachment.store_fname`` holds a *location pseudo-uri* for external
  objects: ``eas://<base_path>/<checksum[:2]>/<checksum>``. This mirrors the
  extension point documented in
  ``odoo/addons/base/models/ir_attachment.py`` ("Such methods should check
  for other location pseudo uri"). Dispatching between local and external
  storage is done on this prefix, which makes the decision data-driven and
  independent of runtime configuration.
* Object keys are content-addressed by the attachment SHA1 checksum, exactly
  like Odoo's local filestore (``sha[:2]/sha``), which gives free dedupli-
  cation and idempotent writes.
"""

import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache

_logger = logging.getLogger(__name__)

# Pseudo-uri scheme written into ir.attachment.store_fname for objects that
# live in the external backend. Keep it short: it is stored on every row.
SCHEME = 'eas://'

DEFAULT_BASE_PATH = 'attachments'
DEFAULT_GC_MIN_AGE_HOURS = 24.0

# A base path may only contain letters, digits, '-' and '_' separated by
# single '/'. In particular it cannot contain '..', start with '/', be
# absolute, or contain dots at all. This is a hard guarantee that object
# keys are safe to embed in filesystem paths (the GC checklist spool) and
# free of path traversal.
_SAFE_PATH_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_/\-]*$')


class ExternalStorageError(Exception):
    """Raised for any failure or misconfiguration of the external backend."""


class StorageConfig:
    """Validated configuration of a storage backend.

    Raises :class:`ExternalStorageError` when the configuration is unusable,
    so that misconfiguration can never result in silently storing data
    somewhere else than intended.
    """

    __slots__ = ('provider', 'endpoint_url', 'bucket', 'region',
                 'access_key_id', 'secret_access_key', 'base_path')

    def __init__(self, provider, bucket, endpoint_url='', region='',
                 access_key_id=None, secret_access_key=None,
                 base_path=DEFAULT_BASE_PATH):
        if not provider:
            raise ExternalStorageError('The storage provider is not set.')
        if provider != 's3':
            raise ExternalStorageError('Unknown storage provider %r.' % (provider,))
        if not bucket:
            raise ExternalStorageError('The bucket name is not set.')
        if (access_key_id is None) != (secret_access_key is None):
            raise ExternalStorageError(
                'Both an access key and a secret key must be provided, or '
                'neither (to use the boto3 credential chain).')
        base_path = (base_path or DEFAULT_BASE_PATH).strip().strip('/')
        if not base_path or not _SAFE_PATH_RE.fullmatch(base_path):
            raise ExternalStorageError(
                'Invalid base path %r: use only letters, digits, "-" and '
                '"_", separated by "/".' % (base_path,))
        self.provider = provider
        self.bucket = bucket
        self.endpoint_url = endpoint_url or ''
        self.region = region or ''
        self.access_key_id = access_key_id or None
        self.secret_access_key = secret_access_key or None
        self.base_path = base_path

    def key_for_checksum(self, checksum):
        return key_for_checksum(self.base_path, checksum)


def key_for_checksum(base_path, checksum):
    """Deterministic, content-addressed object key for ``checksum``.

    ``<base_path>/<checksum[:2]>/<checksum>`` -- the two-level sharding
    mirrors the local filestore layout, keeps S3 listings (used by
    maintenance tooling) efficient, and avoids any user-controlled
    component in the key (no filename, no mimetype, no extension).
    """
    return '%s/%s/%s' % (base_path, checksum[:2], checksum)


def split_external_key(fname):
    """Return the object key encoded in ``fname``, or ``None`` if it is not
    an external-storage location (i.e. it belongs to the local filestore).
    """
    if isinstance(fname, str) and fname.startswith(SCHEME):
        return fname[len(SCHEME):]
    return None


def make_external_fname(key):
    """Return the value to store in ``ir.attachment.store_fname`` for an
    object stored under ``key`` in the external backend."""
    return SCHEME + key


def is_safe_key(key):
    """Whether ``key`` is a safe object key (no traversal, filesystem-safe).

    Used defensively before writing keys to the GC checklist spool, which
    maps keys to filesystem paths.
    """
    return bool(key) and bool(_SAFE_PATH_RE.fullmatch(key))


class StorageBackend(ABC):
    """Interface every storage provider must implement.

    Implementations must be thread-safe and must not keep mutable global
    state besides connection pooling.
    """

    @abstractmethod
    def write(self, key, content):
        """Store ``content`` (bytes) under ``key``. Idempotent."""

    @abstractmethod
    def read(self, key):
        """Return the bytes stored under ``key``."""

    @abstractmethod
    def delete(self, key):
        """Delete the object stored under ``key``.

        Must tolerate keys that do not exist (no error).
        """

    @abstractmethod
    def exists(self, key):
        """Return ``True`` when an object is stored under ``key``."""

    def check_connection(self):
        """Raise :class:`ExternalStorageError` when the backend is
        unreachable or misconfigured. Used by the settings test button."""


@lru_cache(maxsize=8)
def get_backend(provider, endpoint_url, bucket, region,
                access_key_id, secret_access_key, base_path):
    """Build (and cache) the backend matching the given configuration.

    The cache is keyed by the full configuration so a settings change
    transparently builds a fresh backend. ``boto3`` is imported lazily so
    the addon loads even before the dependency is installed (the manifest
    ``external_dependencies`` check guards the installation itself).
    """
    config = StorageConfig(
        provider,
        bucket,
        endpoint_url=endpoint_url,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        base_path=base_path,
    )
    from odoo.addons.external_attachment_storage.providers.s3 import S3Storage
    return S3Storage(config)
