"""Automated tests of the external_attachment_storage addon.

All S3/network operations are faked (``FakeStorageBackend`` / mocks); no
real object storage account is required.
"""

import base64
import contextlib
import hashlib
import os
import shutil
import unittest.mock as mock

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.external_attachment_storage.services import storage as storage_service

EXTERNAL_SCHEME = storage_service.SCHEME

# 1x1 transparent PNG, used to exercise binary-field attachments.
TINY_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
    'AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


class FakeStorageBackend(storage_service.StorageBackend):
    """In-memory stand-in for the S3 backend that records every call."""

    def __init__(self):
        self.objects = {}
        self.calls = []
        self.fail_write = False
        self.fail_read = False
        self.fail_delete = False

    def _record(self, operation, key):
        self.calls.append((operation, key))

    def write(self, key, content):
        self._record('write', key)
        if self.fail_write:
            raise storage_service.ExternalStorageError('write failed (500)')
        self.objects[key] = bytes(content)

    def read(self, key):
        self._record('read', key)
        if self.fail_read:
            raise storage_service.ExternalStorageError('read failed (500)')
        return self.objects.get(key, b'')

    def delete(self, key):
        self._record('delete', key)
        if self.fail_delete:
            raise storage_service.ExternalStorageError('delete failed (500)')
        self.objects.pop(key, None)

    def exists(self, key):
        self._record('exists', key)
        return key in self.objects

    def check_connection(self):
        self._record('check', '')


@tagged('post_install', '-at_install')
class TestExternalAttachmentStorage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Attachment = self.env['ir.attachment']
        self.ICP = self.env['ir.config_parameter'].sudo()
        self.filestore = self.Attachment._filestore()
        self.content = b'kemsco-external-storage-test-content'
        self.checksum = hashlib.sha1(self.content).hexdigest()
        self.key = 'attachments/%s/%s' % (self.checksum[:2], self.checksum)
        self.backend = None
        # The test filestore is persistent across runs: remove leftovers of
        # previous runs for this test content so assertions about the local
        # filestore are meaningful.
        local_rel = self.checksum[:2] + '/' + self.checksum
        local_path = os.path.join(self.filestore, local_rel)
        if os.path.exists(local_path):
            with contextlib.suppress(OSError):
                os.remove(local_path)
        shutil.rmtree(
            os.path.join(self.filestore, 'external_checklist'),
            ignore_errors=True)

    def tearDown(self):
        # The GC spool lives on the filesystem: clean what this test wrote.
        shutil.rmtree(
            os.path.join(self.filestore, 'external_checklist'),
            ignore_errors=True)
        super().tearDown()

    # ------------------------------------------------------------ helpers

    def patch_backend(self):
        """Route every backend construction to a FakeStorageBackend."""
        self.backend = FakeStorageBackend()
        patcher = mock.patch.object(
            storage_service, 'get_backend', mock.Mock(return_value=self.backend))
        patcher.start()
        self.addCleanup(patcher.stop)

    def enable(self, **overrides):
        params = {
            'enabled': 'True',
            'provider': 's3',
            'bucket': 'test-bucket',
            'region': 'eu-west-1',
            'endpoint_url': 'https://s3.example.test',
            'base_path': 'attachments',
        }
        params.update(overrides)
        for key, value in params.items():
            self.ICP.set_param('external_attachment_storage.%s' % key, value)

    def disable(self):
        self.ICP.set_param('external_attachment_storage.enabled', 'False')

    def set_gc_min_age(self, hours):
        self.ICP.set_param('external_attachment_storage.gc_min_age_hours', str(hours))

    def marker_path(self, key):
        return os.path.join(self.filestore, 'external_checklist', key)

    def gc(self, min_age_hours=0.0):
        self.Attachment._gc_external_file_store_unsafe(self.backend, min_age_hours)

    # ------------------------------------------------ existing attachments

    def test_local_attachment_created_when_disabled(self):
        att = self.Attachment.create({'name': 'local.txt', 'raw': self.content})
        self.assertEqual(att.store_fname, self.checksum[:2] + '/' + self.checksum)
        self.assertEqual(att.storage_backend, 'local')
        self.assertTrue(os.path.isfile(os.path.join(self.filestore, att.store_fname)))
        self.assertEqual(att.checksum, self.checksum)
        self.assertFalse(os.path.exists(self.marker_path(self.key)))

    def test_existing_local_attachment_unaffected_when_enabled(self):
        att = self.Attachment.create({'name': 'local.txt', 'raw': self.content})
        fname_before = att.store_fname
        checksum_before = att.checksum
        local_path = os.path.join(self.filestore, fname_before)

        self.enable()
        self.patch_backend()

        # Existing attachment still read from the local filestore.
        att.invalidate_recordset(['raw', 'datas'])
        self.assertEqual(att.raw, self.content)
        self.assertEqual(self.backend.calls, [])  # never routed to S3

        # Renaming does not touch storage metadata.
        att.write({'name': 'renamed.txt'})
        self.assertEqual(att.store_fname, fname_before)
        self.assertEqual(att.checksum, checksum_before)
        self.assertEqual(att.storage_backend, 'local')

        # The storage marker fields cannot be written by users.
        att.write({'store_fname': 'aa/bb', 'storage_backend': 'external'})
        self.assertEqual(att.store_fname, fname_before)
        self.assertEqual(att.storage_backend, 'local')

        # The local file is untouched and still deletable through Odoo.
        self.assertTrue(os.path.isfile(local_path))
        att.unlink()
        self.assertFalse(self.Attachment.search([('id', '=', att.id)]))
        # Deletion is delayed by the local GC: the file is still there but
        # marked, and nothing was deleted on the external backend.
        self.assertTrue(os.path.exists(local_path))
        self.assertNotIn('delete', [call for call, _ in self.backend.calls])

    def test_existing_local_attachment_metadata_stable_across_reads(self):
        att = self.Attachment.create({'name': 'local.txt', 'raw': self.content})
        before = (att.store_fname, att.checksum, att.storage_backend, att.file_size)
        self.enable()
        self.patch_backend()
        for _ in range(3):
            att.invalidate_recordset(['raw', 'datas'])
            self.assertEqual(att.raw, self.content)
            self.assertEqual(att.datas, base64.b64encode(self.content))
        self.assertEqual(
            (att.store_fname, att.checksum, att.storage_backend, att.file_size),
            before)

    # ----------------------------------------------------- new attachments

    def test_new_attachment_goes_to_external_storage(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})

        self.assertEqual(att.store_fname, EXTERNAL_SCHEME + self.key)
        self.assertEqual(att.storage_backend, 'external')
        self.assertEqual(att.checksum, self.checksum)
        self.assertEqual(att.file_size, len(self.content))
        self.assertFalse(att.db_datas)
        # Object uploaded with the exact content.
        self.assertIn(self.key, self.backend.objects)
        self.assertEqual(self.backend.objects[self.key], self.content)
        # Nothing was written to the local filestore for this attachment.
        self.assertFalse(os.path.exists(os.path.join(self.filestore, self.key)))
        self.assertFalse(os.path.exists(
            os.path.join(self.filestore, self.checksum[:2] + '/' + self.checksum)))
        # A GC marker was written before the upload.
        self.assertTrue(os.path.exists(self.marker_path(self.key)))

    def test_new_attachment_read_back_through_external_storage(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        att.invalidate_recordset(['raw', 'datas'])
        self.assertEqual(att.raw, self.content)
        self.assertEqual(att.datas, base64.b64encode(self.content))
        self.assertIn(('read', self.key), self.backend.calls)

    def test_duplicate_content_is_deduplicated(self):
        self.enable()
        self.patch_backend()
        a1 = self.Attachment.create({'name': 'a1.txt', 'raw': self.content})
        a2 = self.Attachment.create({'name': 'a2.txt', 'raw': self.content})
        self.assertEqual(a1.store_fname, a2.store_fname)
        writes = [key for call, key in self.backend.calls if call == 'write']
        self.assertEqual(writes, [self.key])  # uploaded only once

    def test_serving_stream_from_external_storage(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        stream = att._get_external_attachment_stream()
        self.assertEqual(stream.type, 'data')
        self.assertEqual(stream.data, self.content)
        self.assertEqual(stream.size, len(self.content))
        self.assertEqual(stream.etag, self.checksum)
        self.assertEqual(stream.mimetype, att.mimetype)
        self.assertEqual(stream.download_name, 'new.txt')

    def test_ir_binary_serves_external_attachment(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        stream = self.env['ir.binary']._record_to_stream(att, 'raw')
        self.assertEqual(stream.type, 'data')
        self.assertEqual(stream.data, self.content)

    def test_ir_binary_serves_external_field_attachment(self):
        png_b64 = base64.b64encode(TINY_PNG)
        self.enable()
        self.patch_backend()
        partner = self.env['res.partner'].create({
            'name': 'External Partner',
            'image_1920': png_b64,
        })
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
            ('res_field', '=', 'image_1920'),
        ])
        self.assertEqual(len(attachment), 1)
        self.assertEqual(attachment.storage_backend, 'external')
        self.assertTrue(attachment._is_external())
        stream = self.env['ir.binary']._record_to_stream(partner, 'image_1920')
        self.assertEqual(stream.type, 'data')
        self.assertEqual(stream.data, TINY_PNG)

    def test_copy_of_external_attachment(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        copy = att.copy()
        self.assertEqual(copy.store_fname, att.store_fname)
        self.assertEqual(copy.storage_backend, 'external')
        copy.invalidate_recordset(['raw'])
        self.assertEqual(copy.raw, self.content)

    # ---------------------------------------------------- disabled storage

    def test_disabled_storage_uses_local_filestore(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        self.assertEqual(att.storage_backend, 'external')

        self.disable()
        new_local = self.Attachment.create({'name': 'local.txt', 'raw': self.content})
        self.assertEqual(new_local.store_fname, self.checksum[:2] + '/' + self.checksum)
        self.assertEqual(new_local.storage_backend, 'local')
        self.assertTrue(os.path.isfile(os.path.join(self.filestore, new_local.store_fname)))

    def test_external_attachments_keep_working_when_disabled(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        key = att.store_fname[len(EXTERNAL_SCHEME):]

        self.disable()
        # Reads keep working: dispatch is based on the store_fname prefix.
        att.invalidate_recordset(['raw'])
        self.assertEqual(att.raw, self.content)
        stream = self.env['ir.binary']._record_to_stream(att, 'raw')
        self.assertEqual(stream.data, self.content)
        # Deletion of external content still works while disabled.
        att.unlink()
        self.gc()
        self.assertIn(('delete', key), self.backend.calls)
        self.assertNotIn(key, self.backend.objects)

    # ------------------------------------------------------------ deletion

    def test_external_delete_is_deferred_and_reference_checked(self):
        self.enable()
        self.patch_backend()
        a1 = self.Attachment.create({'name': 'a1.txt', 'raw': self.content})
        a2 = self.Attachment.create({'name': 'a2.txt', 'raw': self.content})
        self.assertEqual(a1.store_fname, a2.store_fname)
        key = a1.store_fname[len(EXTERNAL_SCHEME):]

        a1.unlink()
        self.assertFalse(self.Attachment.search([('id', '=', a1.id)]))
        # Not deleted synchronously...
        self.assertNotIn(('delete', key), self.backend.calls)
        self.assertTrue(os.path.exists(self.marker_path(key)))

        # ... and still referenced by a2, so the GC keeps the object.
        self.gc()
        self.assertIn(key, self.backend.objects)
        self.assertFalse(os.path.exists(self.marker_path(key)))

        # Once the last reference is gone, the GC removes the object.
        a2.unlink()
        self.assertTrue(os.path.exists(self.marker_path(key)))
        self.gc()
        self.assertIn(('delete', key), self.backend.calls)
        self.assertNotIn(key, self.backend.objects)
        self.assertFalse(os.path.exists(self.marker_path(key)))

    def test_gc_min_age_protects_recent_markers(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        key = att.store_fname[len(EXTERNAL_SCHEME):]
        att.unlink()
        # Default safety delay: nothing is deleted yet, marker is kept.
        self.gc(min_age_hours=storage_service.DEFAULT_GC_MIN_AGE_HOURS)
        self.assertNotIn(('delete', key), self.backend.calls)
        self.assertTrue(os.path.exists(self.marker_path(key)))
        # With a zero delay the object is collected.
        self.gc()
        self.assertNotIn(key, self.backend.objects)
        self.assertFalse(os.path.exists(self.marker_path(key)))

    # -------------------------------------------------- transaction safety

    def test_rolled_back_upload_is_cleaned_by_gc(self):
        self.enable()
        self.patch_backend()
        with self.assertRaises(ValueError):
            with self.env.cr.savepoint():
                self.Attachment.create({'name': 'rolled-back.txt', 'raw': self.content})
                raise ValueError('simulated failure after upload')
        # No database record, but the object and the marker exist: the GC
        # must collect the orphan.
        self.assertFalse(self.Attachment.search([('checksum', '=', self.checksum)]))
        self.assertIn(self.key, self.backend.objects)
        self.assertTrue(os.path.exists(self.marker_path(self.key)))
        self.gc()
        self.assertNotIn(self.key, self.backend.objects)
        self.assertFalse(os.path.exists(self.marker_path(self.key)))

    # ------------------------------------------------------ failure cases

    def test_upload_failure_aborts_and_rolls_back(self):
        self.enable()
        self.patch_backend()
        self.backend.fail_write = True
        with self.assertRaises(UserError):
            self.Attachment.create({'name': 'fail.txt', 'raw': self.content})
        # No record was left behind, no object was stored...
        self.assertFalse(self.Attachment.search([('checksum', '=', self.checksum)]))
        self.assertNotIn(self.key, self.backend.objects)
        # ...but the pre-upload marker remains so the GC can clean up any
        # object a partial upload might have left behind.
        self.assertTrue(os.path.exists(self.marker_path(self.key)))
        self.gc()
        self.assertNotIn(self.key, self.backend.objects)

    def test_read_failure_returns_empty_and_serving_raises(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        self.backend.fail_read = True
        att.invalidate_recordset(['raw'])
        # ORM-level reads fail soft (like the local filestore), but...
        self.assertEqual(att.raw, b'')
        # ...serving never presents an empty file as a success.
        with self.assertRaises(UserError):
            att._get_external_attachment_stream()
        with self.assertRaises(UserError):
            self.env['ir.binary']._record_to_stream(att, 'raw')

    def test_gc_delete_failure_keeps_marker_and_retries(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        key = att.store_fname[len(EXTERNAL_SCHEME):]
        att.unlink()
        self.backend.fail_delete = True
        self.gc()
        self.assertIn(('delete', key), self.backend.calls)
        self.assertTrue(os.path.exists(self.marker_path(key)))
        # A later successful cycle completes the cleanup.
        self.backend.fail_delete = False
        self.gc()
        self.assertNotIn(key, self.backend.objects)
        self.assertFalse(os.path.exists(self.marker_path(key)))

    def test_missing_bucket_fails_loudly(self):
        self.enable(bucket='')
        with self.assertRaises(UserError):
            self.Attachment.create({'name': 'fail.txt', 'raw': self.content})

    def test_invalid_base_path_fails_loudly(self):
        self.enable(base_path='../evil')
        with self.assertRaises(UserError):
            self.Attachment.create({'name': 'fail.txt', 'raw': self.content})

    def test_invalid_provider_fails_loudly(self):
        self.enable(provider='ftp')
        with self.assertRaises(UserError):
            self.Attachment.create({'name': 'fail.txt', 'raw': self.content})

    def test_partial_credentials_fail_loudly(self):
        self.enable(access_key_id='AKIA', secret_access_key='')
        with mock.patch.dict(os.environ, {
            'EAS_ACCESS_KEY_ID': '',
            'EAS_SECRET_ACCESS_KEY': '',
        }):
            with self.assertRaises(UserError):
                self.Attachment.create({'name': 'fail.txt', 'raw': self.content})

    # -------------------------------------------------------- key strategy

    def test_storage_key_is_deterministic_and_safe(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        self.assertEqual(
            att.store_fname,
            'eas://attachments/%s/%s' % (self.checksum[:2], self.checksum))
        # The key contains no user-controlled component: no filename, no
        # mimetype, no extension -- only the checksum and the base path.
        self.assertNotIn('new.txt', att.store_fname)

    def test_gc_whitelist_ignores_local_fnames(self):
        # A local filestore checklist entry must never be mistaken for an
        # external key (and vice versa): create one of each and make sure
        # the GC only touches external markers.
        local = self.Attachment.create({'name': 'local.txt', 'raw': self.content})
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'new.txt', 'raw': self.content})
        key = att.store_fname[len(EXTERNAL_SCHEME):]
        att.unlink()
        self.assertTrue(os.path.exists(self.marker_path(key)))
        # The local attachment is untouched by the external GC.
        self.gc()
        self.assertTrue(os.path.isfile(os.path.join(self.filestore, local.store_fname)))
        self.assertNotIn(key, self.backend.objects)

    # ------------------------------------------------------------- rescue

    def test_rescue_migration_external_to_local(self):
        self.enable()
        self.patch_backend()
        att = self.Attachment.create({'name': 'rescue.txt', 'raw': self.content})
        key = att.store_fname[len(EXTERNAL_SCHEME):]

        processed = self.Attachment._migrate_external_to_local()
        self.assertEqual(processed, 1)

        att.invalidate_recordset(['store_fname', 'storage_backend', 'raw', 'datas'])
        self.assertEqual(att.storage_backend, 'local')
        self.assertEqual(att.store_fname, self.checksum[:2] + '/' + self.checksum)
        self.assertTrue(os.path.isfile(os.path.join(self.filestore, att.store_fname)))
        self.assertEqual(att.raw, self.content)
        # External objects are never deleted automatically.
        self.assertIn(key, self.backend.objects)

    # ------------------------------------------------------------ settings

    def test_settings_persist_parameters(self):
        self.patch_backend()
        settings = self.env['res.config.settings'].create({
            'external_attachment_enabled': True,
            'external_attachment_provider': 's3',
            'external_attachment_endpoint_url': 'https://s3.example.test',
            'external_attachment_bucket': 'test-bucket',
            'external_attachment_region': 'eu-west-1',
            'external_attachment_base_path': 'attachments',
            'external_attachment_access_key_id': 'key-id',
            'external_attachment_secret_access_key': 'secret-value',
        })
        settings.execute()
        get_param = self.ICP.get_param
        self.assertEqual(get_param('external_attachment_storage.enabled'), 'True')
        self.assertEqual(get_param('external_attachment_storage.bucket'), 'test-bucket')
        self.assertEqual(get_param('external_attachment_storage.base_path'), 'attachments')

        result = settings.action_test_external_attachment_connection()
        self.assertEqual(result['tag'], 'display_notification')
        self.assertIn(('check', ''), self.backend.calls)

    def test_settings_test_connection_failure(self):
        settings = self.env['res.config.settings'].create({
            'external_attachment_enabled': True,
            'external_attachment_provider': 's3',
            'external_attachment_bucket': 'test-bucket',
        })
        with mock.patch.object(
                storage_service, 'get_backend',
                side_effect=storage_service.ExternalStorageError('boom')):
            with self.assertRaises(UserError):
                settings.action_test_external_attachment_connection()

    # ------------------------------------------------- configuration model

    def test_config_disabled_returns_none(self):
        self.disable()
        self.assertIsNone(self.Attachment._get_external_config())

    def test_config_forced_returns_even_when_disabled(self):
        self.enable()
        self.disable()
        config = self.Attachment._get_external_config(force=True)
        self.assertEqual(config['bucket'], 'test-bucket')

    def test_env_fallback_credentials(self):
        self.enable(access_key_id='', secret_access_key='')
        with mock.patch.dict(os.environ, {
            'EAS_ACCESS_KEY_ID': 'env-key',
            'EAS_SECRET_ACCESS_KEY': 'env-secret',
        }):
            config = self.Attachment._get_external_config(force=True)
            self.assertEqual(config['access_key_id'], 'env-key')
            self.assertEqual(config['secret_access_key'], 'env-secret')
