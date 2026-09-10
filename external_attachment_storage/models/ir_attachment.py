import contextlib
import logging
import os
import time

import psycopg2

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from odoo.addons.external_attachment_storage.services import storage as storage_service


_logger = logging.getLogger(__name__)

ICP_PREFIX = 'external_attachment_storage.'

# Filesystem spool used to garbage-collect external objects. It mirrors the
# "checklist" pattern of the local filestore: markers are written *before*
# the upload, in the same transaction, so they survive PostgreSQL rollbacks
# and allow a later, reference-checked cleanup of orphaned objects.
EXTERNAL_CHECKLIST_DIRNAME = 'external_checklist'

_GC_CHUNK_SIZE = 1000


def _split_external(fname):
    return storage_service.split_external_key(fname)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    # -------------------------------------------------------------
    # Storage identification
    # -------------------------------------------------------------
    # Explicit, queryable marker of where the *content* of the attachment
    # lives. It is a stored *computed* field derived from the 'eas://'
    # prefix of store_fname, so it is always consistent with the actual
    # storage location and cannot be forged through create()/write().
    #
    # On install, Odoo backfills the new column with the field default and
    # computes it for every existing row; since existing rows carry a local
    # 'sha[:2]/sha' store_fname, they all end up as 'local' -- no migration
    # step, and no existing record is otherwise modified.
    storage_backend = fields.Selection(
        [('local', 'Local Filestore'), ('external', 'External Storage')],
        string='Storage Backend',
        compute='_compute_storage_backend',
        store=True,
        readonly=True,
        default='local',
        help="Where the file content of this attachment is stored. 'local' "
             "means the standard Odoo filestore, 'external' means the "
             "configured S3-compatible object storage.",
    )

    @api.depends('store_fname')
    def _compute_storage_backend(self):
        for attachment in self:
            attachment.storage_backend = (
                'external' if attachment._is_external() else 'local')

    # -------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------

    @api.model
    def _get_external_config(self, force=False):
        """Return the backend configuration as a plain dict, or ``None``
        when the feature is disabled.

        :param bool force: build the configuration even when the feature is
            disabled. Read/delete/garbage-collection paths use ``force=True``
            so that *existing* external attachments keep working when the
            feature is switched off; only new uploads require it enabled.
        """
        get_param = self.env['ir.config_parameter'].sudo().get_param
        enabled = tools.str2bool(str(get_param(ICP_PREFIX + 'enabled', 'False') or 'False'))
        if not force and not enabled:
            return None
        # Credentials resolution order:
        #   1. system parameters (Settings > General Settings)
        #   2. environment variables (EAS_ACCESS_KEY_ID / EAS_SECRET_ACCESS_KEY)
        #   3. None -> boto3 default credential chain (env vars, IAM role, ...)
        return {
            'provider': get_param(ICP_PREFIX + 'provider', 's3') or 's3',
            'endpoint_url': get_param(ICP_PREFIX + 'endpoint_url', '') or '',
            'bucket': get_param(ICP_PREFIX + 'bucket', '') or '',
            'region': get_param(ICP_PREFIX + 'region', '') or '',
            'base_path': get_param(ICP_PREFIX + 'base_path', '') or storage_service.DEFAULT_BASE_PATH,
            'access_key_id': get_param(ICP_PREFIX + 'access_key_id', '') or os.environ.get('EAS_ACCESS_KEY_ID') or None,
            'secret_access_key': get_param(ICP_PREFIX + 'secret_access_key', '') or os.environ.get('EAS_SECRET_ACCESS_KEY') or None,
        }

    @api.model
    def _get_external_backend(self, config):
        """Build the storage backend, converting misconfiguration into an
        explicit UserError. Failures must never silently succeed."""
        try:
            return storage_service.get_backend(
                config['provider'],
                config['endpoint_url'],
                config['bucket'],
                config['region'],
                config['access_key_id'],
                config['secret_access_key'],
                config['base_path'],
            )
        except storage_service.ExternalStorageError as error:
            _logger.error("External attachment storage misconfigured: %s", error)
            raise UserError(_(
                "The external attachment storage is not properly configured: %s",
                error,
            )) from error

    def _is_external(self):
        """True when this attachment's content lives in the external backend."""
        self.ensure_one()
        return bool(self.store_fname) and _split_external(self.store_fname) is not None

    # -------------------------------------------------------------
    # Storage lifecycle overrides (see odoo/addons/base/models/ir_attachment.py)
    # -------------------------------------------------------------

    @api.model
    def _file_write(self, bin_value, checksum):
        """Upload new content to the external backend when the feature is
        enabled; otherwise fall back to the standard local filestore.

        The returned value is stored in ``ir.attachment.store_fname``:
        an ``eas://`` pseudo-uri for external objects, the usual
        ``sha[:2]/sha`` relative path for local ones.
        """
        config = self._get_external_config()
        if config is None:
            return super()._file_write(bin_value, checksum)

        backend = self._get_external_backend(config)
        key = storage_service.key_for_checksum(config['base_path'], checksum)

        # Mark for garbage collection *before* uploading (like the local
        # filestore does). The marker survives transaction rollbacks, which
        # is what allows the GC to clean up orphaned objects later.
        self._mark_external_for_gc(key)

        try:
            try:
                already_stored = backend.exists(key)
            except storage_service.ExternalStorageError as error:
                # A transient failure on HEAD must not block the upload:
                # PUT is authoritative and idempotent anyway.
                _logger.warning(
                    "External storage: existence check failed for key %s, "
                    "uploading anyway (%s)", key, error)
                already_stored = False
            if not already_stored:
                backend.write(key, bin_value)
                _logger.info(
                    "External storage: uploaded key=%s bucket=%s size=%s",
                    key, config['bucket'], len(bin_value))
        except storage_service.ExternalStorageError as error:
            _logger.error(
                "External storage: upload failed for key %s", key, exc_info=True)
            raise UserError(_(
                "The file could not be stored on the external storage "
                "backend. The operation has been cancelled. (%s)", error,
            )) from error
        return storage_service.make_external_fname(key)

    @api.model
    def _file_read(self, fname):
        """Read content either from the external backend (when ``fname`` is
        an external location) or from the local filestore.

        Following the base implementation, read failures are logged and
        return empty bytes instead of raising (an empty read is detected
        and surfaced properly at serving time, see
        ``_get_external_attachment_stream``).
        """
        key = _split_external(fname)
        if key is None:
            return super()._file_read(fname)

        config = self._get_external_config(force=True)
        if config is None:
            _logger.error(
                "External storage: attachment with key %s cannot be read, "
                "no backend is configured.", key)
            return b''
        try:
            backend = self._get_external_backend(config)
        except UserError:
            return b''
        try:
            data = backend.read(key)
        except storage_service.ExternalStorageError:
            _logger.error(
                "External storage: failed to read key %s", key, exc_info=True)
            return b''
        _logger.debug("External storage: read key=%s size=%s", key, len(data))
        return data

    @api.model
    def _file_delete(self, fname):
        """Schedule the removal of a stored file.

        External objects are *never* deleted synchronously: they are marked
        in the GC spool and removed later only once no ir.attachment row
        references them anymore (content-addressed keys are shared between
        records). Local files keep the standard base behavior.
        """
        key = _split_external(fname)
        if key is None:
            return super()._file_delete(fname)
        self._mark_external_for_gc(key)

    # -------------------------------------------------------------
    # Serving (downloads)
    # -------------------------------------------------------------

    def _get_external_attachment_stream(self):
        """Build an ``odoo.http.Stream`` serving this attachment from the
        external backend.

        ``Stream.from_attachment`` builds a *local filesystem* path from
        ``store_fname`` and would crash on external keys, so external
        attachments are served as data streams instead -- mirroring what
        the base method does for ``db_datas`` attachments. This method is
        called from ``ir.binary._record_to_stream`` and
        ``ir.http._serve_fallback`` only for external attachments, after
        Odoo's normal access checks have run.
        """
        self.ensure_one()
        data = self._file_read(self.store_fname)
        if not data and self.file_size:
            # Never silently serve an empty file for content we know exists.
            raise UserError(_(
                "The file content could not be retrieved from the external "
                "storage backend. Please contact your administrator."))
        from odoo.http import Stream
        return Stream(
            type='data',
            data=data,
            mimetype=self.mimetype,
            download_name=self.name,
            etag=self.checksum,
            public=self.public,
            last_modified=self.write_date,
            size=len(data),
        )

    # -------------------------------------------------------------
    # Garbage collection of external objects
    # -------------------------------------------------------------

    @api.model
    def _external_checklist_path(self, key=None):
        path = os.path.join(self._filestore(), EXTERNAL_CHECKLIST_DIRNAME)
        if key:
            path = os.path.join(path, key)
        return path

    @api.model
    def _mark_external_for_gc(self, key):
        """Add ``key`` to the external GC spool.

        The spool is part of this database's filestore directory but only
        *adds* a dedicated subdirectory; existing filestore files are never
        touched. Keys are validated so the resulting path is always safe.
        """
        if not storage_service.is_safe_key(key):
            _logger.error("External storage: refusing to mark unsafe key %r", key)
            raise UserError(_("Invalid external storage key."))
        marker = self._external_checklist_path(key)
        dirname = os.path.dirname(marker)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, exist_ok=True)
        if not os.path.exists(marker):
            with open(marker, 'ab'):
                pass

    @api.model
    def _get_gc_min_age_hours(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            ICP_PREFIX + 'gc_min_age_hours', '')
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return storage_service.DEFAULT_GC_MIN_AGE_HOURS

    @api.autovacuum
    def _gc_external_file_store(self):
        """Garbage-collect orphaned external objects.

        Follows the exact pattern of the local filestore GC
        (``_gc_file_store``): commit first, then take a SHARE lock on
        ``ir_attachment`` so the whitelist query below sees the freshest
        committed state, then process the spool. An object is deleted only
        when no ``store_fname`` references it anymore, and only when its
        marker is old enough (safety delay covering rollback windows).
        """
        if not os.path.isdir(self._external_checklist_path()):
            return

        config = self._get_external_config(force=True)
        try:
            backend = self._get_external_backend(config)
        except UserError:
            return

        # Continue in a fresh transaction; the LOCK must be the first
        # statement of the new transaction (see base _gc_file_store).
        cr = self._cr
        cr.commit()
        cr.execute("SET LOCAL lock_timeout TO '10s'")
        try:
            cr.execute("LOCK ir_attachment IN SHARE MODE")
        except psycopg2.errors.LockNotAvailable:
            cr.rollback()
            return False

        self._gc_external_file_store_unsafe(backend, self._get_gc_min_age_hours())

        # commit to release the lock
        cr.commit()

    def _gc_external_file_store_unsafe(self, backend=None, min_age_hours=None):
        """Actual GC logic, without transaction management (testable)."""
        if backend is None:
            config = self._get_external_config(force=True)
            backend = self._get_external_backend(config)
        if min_age_hours is None:
            min_age_hours = self._get_gc_min_age_hours()

        spool = self._external_checklist_path()
        markers = []
        for dirpath, _dirnames, filenames in os.walk(spool):
            rel_dir = os.path.relpath(dirpath, spool)
            for filename in filenames:
                markers.append(
                    filename if rel_dir == '.' else '%s/%s' % (rel_dir, filename))
        if not markers:
            return

        cutoff = time.time() - max(0.0, min_age_hours) * 3600.0
        stale = [
            marker for marker in markers
            if os.path.getmtime(os.path.join(spool, marker)) <= cutoff
        ]
        if not stale:
            return

        # Whitelist keys still referenced by any attachment record.
        to_delete = []
        for start in range(0, len(stale), _GC_CHUNK_SIZE):
            chunk = stale[start:start + _GC_CHUNK_SIZE]
            self.env.cr.execute(
                "SELECT store_fname FROM ir_attachment WHERE store_fname = ANY(%s)",
                [[storage_service.make_external_fname(marker) for marker in chunk]],
            )
            referenced = {row[0] for row in self.env.cr.fetchall()}
            to_delete.extend(
                marker for marker in chunk
                if storage_service.make_external_fname(marker) not in referenced)

        deleted = 0
        for marker in stale:
            if marker in to_delete:
                try:
                    backend.delete(marker)
                except storage_service.ExternalStorageError:
                    # Keep the marker: the object is retried next cycle.
                    _logger.error(
                        "External storage: GC could not delete key %s, "
                        "will retry later", marker)
                    continue
            # Referenced objects are kept; their (now useless) marker is
            # dropped. If the object is deleted later through unlink(),
            # _file_delete() writes a fresh marker.
            with contextlib.suppress(OSError):
                os.unlink(os.path.join(spool, marker))
            deleted += 1

        _logger.info(
            "External storage GC: %d stale markers checked, %d processed "
            "(%d objects deleted)", len(stale), deleted, len(to_delete))

    # -------------------------------------------------------------
    # Rescue / rollback helper
    # -------------------------------------------------------------

    def _migrate_external_to_local(self, batch_size=100):
        """Copy externally stored content back into the local filestore.

        Admin-only rescue tool, to run from an Odoo shell *before*
        uninstalling the addon so external attachments never become broken:

            env['ir.attachment']._migrate_external_to_local()
            env.cr.commit()

        It only touches attachments whose content is currently external
        (i.e. records created while the feature was enabled); pre-existing
        local attachments are ignored. External objects are NOT deleted,
        so a botched run can always be retried idempotently.
        """
        if not self.env.is_admin():
            raise AccessError(_('Only administrators can execute this action.'))
        config = self._get_external_config(force=True)
        backend = self._get_external_backend(config)
        attachments = self.sudo().with_context(
            skip_res_field_check=True,
        ).search([('storage_backend', '=', 'external')])

        processed = 0
        for attachment in attachments:
            if not attachment._is_external():
                continue
            data = attachment._file_read(attachment.store_fname)
            if not data and attachment.file_size:
                raise UserError(_(
                    "The content of attachment %s (key %s) could not be "
                    "retrieved from the external storage; aborting the "
                    "migration so it can be fixed and retried.",
                    attachment.id, attachment.store_fname))
            checksum = attachment.checksum or attachment._compute_checksum(data)
            # super() call: force the *local* filestore write regardless of
            # the feature being enabled.
            local_fname = super(IrAttachment, attachment)._file_write(data, checksum)
            # store_fname is popped by write(), so update it directly, then
            # have the ORM recompute the computed storage_backend field from
            # its new value.
            self.env.cr.execute(
                "UPDATE ir_attachment SET store_fname = %s WHERE id = %s",
                [local_fname, attachment.id],
            )
            attachment.invalidate_recordset(['store_fname', 'storage_backend'])
            self.env.add_to_compute(
                self._fields['storage_backend'], attachment)
            attachment._recompute_recordset(['storage_backend'])
            processed += 1
            if processed % batch_size == 0:
                self.env.cr.commit()
                _logger.info(
                    "External->local migration: %d/%d done",
                    processed, len(attachments))
        _logger.info(
            "External->local migration finished: %d attachments migrated", processed)
        return processed

    # -------------------------------------------------------------
    # create/write guards
    # -------------------------------------------------------------
    # storage_backend is a stored computed field (derived from the
    # store_fname prefix), so it is recomputed by the ORM on every content
    # change. These minimal guards only reject user-provided values; they
    # deliberately do NOT re-implement the base create()/write() logic:
    # base ir.attachment.create() re-processes anything super().create()
    # receives, and duplicating its data processing here would strip
    # store_fname/checksum/file_size from the values before they reach
    # BaseModel.create.

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            {key: value for key, value in vals.items() if key != 'storage_backend'}
            for vals in vals_list
        ]
        return super().create(vals_list)

    def write(self, vals):
        vals.pop('storage_backend', None)
        return super().write(vals)
