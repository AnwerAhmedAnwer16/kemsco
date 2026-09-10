"""Unit tests of the S3Storage provider (boto3 layer).

These tests mock the boto3 client entirely, so no network access and no
AWS account are required. They are skipped when boto3 is not installed
(the main test suite does not need it).
"""

import io
import unittest
from unittest import mock

from odoo.tests import TransactionCase, tagged

from odoo.addons.external_attachment_storage.services import storage as storage_service

try:
    import boto3  # noqa: F401
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _client_error(code):
    return ClientError({'Error': {'Code': code, 'Message': code}}, 'Operation')


@tagged('post_install', '-at_install')
@unittest.skipUnless(HAS_BOTO3, 'boto3 is not installed')
class TestS3Provider(TransactionCase):

    def _make_storage(self):
        from odoo.addons.external_attachment_storage.providers.s3 import S3Storage
        config = storage_service.StorageConfig(
            's3',
            'test-bucket',
            endpoint_url='https://s3.example.test',
            region='us-east-1',
            access_key_id='AKIA-TEST',
            secret_access_key='SECRET',
            base_path='attachments',
        )
        with mock.patch('boto3.client') as client_factory:
            storage = S3Storage(config)
        return storage, client_factory, client_factory.return_value

    def test_client_is_configured_for_s3_compatible_endpoints(self):
        _storage, factory, _client = self._make_storage()
        self.assertEqual(factory.call_count, 1)
        kwargs = factory.call_args.kwargs
        self.assertEqual(kwargs['endpoint_url'], 'https://s3.example.test')
        self.assertEqual(kwargs['region_name'], 'us-east-1')
        self.assertEqual(kwargs['aws_access_key_id'], 'AKIA-TEST')
        self.assertEqual(kwargs['aws_secret_access_key'], 'SECRET')
        # Path-style addressing for custom endpoints.
        self.assertEqual(kwargs['config'].s3['addressing_style'], 'path')
        self.assertEqual(kwargs['config'].retries['max_attempts'], 3)

    def test_write_uses_upload_fileobj(self):
        storage, _factory, client = self._make_storage()
        storage.write('attachments/ab/' + 'a' * 38, b'payload')
        args = client.upload_fileobj.call_args.args
        self.assertEqual(args[1:], ('test-bucket', 'attachments/ab/' + 'a' * 38))
        self.assertEqual(args[0].getvalue(), b'payload')

    def test_read_returns_body_content(self):
        storage, _factory, client = self._make_storage()
        client.get_object.return_value = {'Body': io.BytesIO(b'payload')}
        self.assertEqual(storage.read('some/key'), b'payload')
        client.get_object.assert_called_once_with(
            Bucket='test-bucket', Key='some/key')

    def test_delete_calls_delete_object(self):
        storage, _factory, client = self._make_storage()
        storage.delete('some/key')
        client.delete_object.assert_called_once_with(
            Bucket='test-bucket', Key='some/key')

    def test_exists_true_false_and_error(self):
        storage, _factory, client = self._make_storage()
        client.head_object.return_value = {}
        self.assertTrue(storage.exists('some/key'))
        client.head_object.side_effect = _client_error('404')
        self.assertFalse(storage.exists('some/key'))
        client.head_object.side_effect = _client_error('403')
        with self.assertRaises(storage_service.ExternalStorageError):
            storage.exists('some/key')

    def test_errors_are_wrapped_without_secrets(self):
        storage, _factory, client = self._make_storage()
        client.upload_fileobj.side_effect = _client_error('AccessDenied')
        with self.assertRaises(storage_service.ExternalStorageError) as ctx:
            storage.write('some/key', b'payload')
        message = str(ctx.exception)
        self.assertIn('write', message)
        self.assertIn('some/key', message)
        self.assertNotIn('SECRET', message)

    def test_check_connection_success_and_failure(self):
        storage, _factory, client = self._make_storage()
        client.head_bucket.return_value = {}
        storage.check_connection()
        client.head_bucket.side_effect = _client_error('403')
        with self.assertRaises(storage_service.ExternalStorageError):
            storage.check_connection()

    def test_aws_default_endpoint_when_none(self):
        from odoo.addons.external_attachment_storage.providers.s3 import S3Storage
        config = storage_service.StorageConfig(
            's3', 'test-bucket', region='eu-west-1',
            access_key_id='AKIA-TEST', secret_access_key='SECRET')
        with mock.patch('boto3.client') as client_factory:
            S3Storage(config)
        self.assertIsNone(client_factory.call_args.kwargs['endpoint_url'])

    def test_boto3_missing_raises_explicit_error(self):
        from odoo.addons.external_attachment_storage.providers import s3
        with mock.patch.object(s3, 'HAS_BOTO3', False):
            with self.assertRaises(storage_service.ExternalStorageError) as ctx:
                s3.S3Storage(storage_service.StorageConfig(
                    's3', 'test-bucket', access_key_id='k', secret_access_key='s'))
            self.assertIn('pip install boto3', str(ctx.exception))


class TestStorageConfig(TransactionCase):

    def test_key_for_checksum_layout(self):
        config = storage_service.StorageConfig(
            's3', 'bucket', base_path='attachments')
        self.assertEqual(
            config.key_for_checksum('0123456789abcdef' * 3),
            'attachments/01/0123456789abcdef0123456789abcdef0123456789abcdef')

    def test_base_path_sanitized(self):
        config = storage_service.StorageConfig(
            's3', 'bucket', base_path='/attachments/')
        self.assertEqual(config.base_path, 'attachments')

    def test_invalid_base_paths_rejected(self):
        for bad in ('../evil', 'a/../b', '.', 'a/./b', 'a b', 'a;b'):
            with self.assertRaises(storage_service.ExternalStorageError):
                storage_service.StorageConfig('s3', 'bucket', base_path=bad)

    def test_empty_base_path_falls_back_to_default(self):
        config = storage_service.StorageConfig('s3', 'bucket', base_path='')
        self.assertEqual(config.base_path, storage_service.DEFAULT_BASE_PATH)

    def test_missing_bucket_rejected(self):
        with self.assertRaises(storage_service.ExternalStorageError):
            storage_service.StorageConfig('s3', '')

    def test_unknown_provider_rejected(self):
        with self.assertRaises(storage_service.ExternalStorageError):
            storage_service.StorageConfig('ftp', 'bucket')

    def test_partial_credentials_rejected(self):
        with self.assertRaises(storage_service.ExternalStorageError):
            storage_service.StorageConfig('s3', 'bucket', access_key_id='k')
        with self.assertRaises(storage_service.ExternalStorageError):
            storage_service.StorageConfig('s3', 'bucket', secret_access_key='s')

    def test_none_credentials_allowed(self):
        # Neither key set -> boto3 default credential chain.
        config = storage_service.StorageConfig('s3', 'bucket')
        self.assertIsNone(config.access_key_id)
        self.assertIsNone(config.secret_access_key)

    def test_external_fname_roundtrip(self):
        key = 'attachments/ab/' + 'a' * 38
        fname = storage_service.make_external_fname(key)
        self.assertEqual(fname, 'eas://' + key)
        self.assertEqual(storage_service.split_external_key(fname), key)
        # Local filestore names are not external locations.
        self.assertIsNone(storage_service.split_external_key('ab/' + 'a' * 38))
