# External Attachment Storage (Odoo 17)

Store **newly uploaded** `ir.attachment` files on an external S3-compatible
object storage backend (AWS S3, Cloudflare R2, MinIO, ...) instead of the
local Odoo filestore — without touching a single pre-existing attachment and
without modifying any business module.

```
Odoo models (sale.order, account.move, res.partner, ...)
        |
        v
   ir.attachment  ---------------->  local filestore   (existing attachments)
        |
        +----------------------->  S3-compatible       (new attachments)
                                   object storage
```

---

## 1. Guarantees

* **Existing attachments are never migrated, moved, modified or deleted.**
  Installing or enabling the addon leaves every pre-existing row and file
  exactly as it is.
* **Only new attachments** created while the feature is enabled are uploaded
  to the external backend.
* The feature can be **switched off at any time**; existing external
  attachments keep working (read/delete) because dispatching is based on the
  stored location, not on the enabled flag.
* Downloads keep going **through Odoo** (`/web/content`, `/web/image`) and
  therefore keep the normal `ir.attachment` access control. No presigned
  URLs, no direct browser-to-S3 access.
* Any feature that creates a standard `ir.attachment` automatically uses the
  configured backend — **no business module is modified**.

---

## 2. How Odoo 17's `ir.attachment` lifecycle is overridden

Odoo 17's `ir.attachment` class documents three overridable storage hooks:

```python
_file_write(bin_value, checksum)   # returns the value stored in store_fname
_file_read(fname)                  # returns bytes
_file_delete(fname)                # removes content
```

`_get_datas_related_values()` calls `_file_write()` and puts its result in
`store_fname`; `_compute_raw()` calls `_file_read(store_fname)`;
`unlink()` deletes the DB row first and then calls `_file_delete(store_fname)`.

The addon overrides exactly those hooks:

| Override | Behavior when external storage is enabled |
|---|---|
| `_file_write` | Uploads the bytes and returns an `eas://<key>` pseudo-uri; when disabled falls back to `super()`. |
| `_file_read` | Reads the object for `eas://` locations, otherwise `super()`. |
| `_file_delete` | Marks the object for deferred, reference-checked GC, otherwise `super()`. |

The `ir.attachment.store_fname` value is the authoritative switch:

```
local attachment    : "ab/abcdef0123..."                  (Odoo's usual layout)
external attachment : "eas://attachments/ab/abcdef0123..." (S3 object key)
```

This "location pseudo-uri" pattern is the mechanism the Odoo 17 class
docstring itself recommends (`Such methods should check for other location
pseudo uri`).

### The one non-obvious Odoo 17 detail: serving

`/web/content` and `/web/image` do **not** call `_file_read()`. In Odoo 17
they go through `odoo.http.Stream.from_attachment()`, which builds a *local
filesystem path* from `filestore + store_fname` and `os.stat()`s it. An
external key would crash the request. The addon intercepts the two core call
sites with plain model inheritance (no monkey-patching):

* `ir.binary._record_to_stream()` — an explicit extension hook in the Odoo 17
  source; covers `/web/content`, `/web/image` and binary/image fields of any
  model (both direct attachments and field attachments).
* `ir.http._serve_fallback()` — resolved through the registry; covers
  serving attachments such as asset bundles.

External attachments are served as `odoo.http.Stream(type='data', ...)`,
mirroring what the base method already does for `db_datas` attachments,
*after* Odoo's normal access checks.

### `storage_backend` marker field

A stored computed field is added to `ir.attachment`:

```python
storage_backend = fields.Selection(
    [('local', 'Local Filestore'), ('external', 'External Storage')],
    compute='_compute_storage_backend', store=True, readonly=True,
    default='local')
```

* It is **derived from the `store_fname` prefix** (`@api.depends('store_fname')`),
  so it can never drift out of sync and cannot be forged via `create()`/`write()`.
* Odoo fills the new column with the default and computes it for existing rows
  at install — every pre-existing attachment becomes `local`. No migration.
* It gives administrators a simple, indexed-free way to query, e.g.
  `env['ir.attachment'].search([('storage_backend', '=', 'external')])`.

> A plain `required=True, default='local'` field was considered (and is what
> the specification sketched). It was rejected because a second
> `create()` override on `ir.attachment` is dangerous in Odoo 17: base
> `ir.attachment.create()` re-processes any values it receives from
> `super().create()`, so a copied create implementation strips
> `store_fname`/`checksum`/`file_size` before `BaseModel.create()` and files
> silently lose their metadata. Deriving the marker from `store_fname`
> avoids overriding `create()` at all and is strictly more robust.

---

## 3. How existing attachments stay untouched

1. **No migration and no scan.** The addon never reads, rewrites, uploads or
   deletes pre-existing rows or files. It only reacts to new write operations.
2. **Dispatch by stored location.** `_file_read`/`_file_delete` route on the
   `eas://` prefix. A local `store_fname` (`ab/abcdef...`) is always handled by
   the original base implementation, even when the feature is enabled.
3. **Additive column only.** The new `storage_backend` column is the only
   schema change; its default/computation is `local` for every old row.
4. **No local filestore changes.** The GC spool lives in a *new* subdirectory
   (`filestore/<db>/external_checklist/`); the normal `checklist/` and every
   existing blob are never touched by this addon.

You can verify point 2 at any time:

```python
# metadata of an old attachment must be identical before/after enabling
a = env['ir.attachment'].browse(<old_id>)
a.store_fname, a.checksum, a.storage_backend   # -> ('ab/...', '<sha1>', 'local')
```

---

## 4. Storage key strategy

```
<base_path>/<checksum[:2]>/<checksum>       e.g. attachments/cd/cdf73e...
```

* **Content-addressed** by the attachment SHA1 checksum — identical to Odoo's
  own local layout, so deduplication is free and writes are idempotent.
* **No user-controlled component**: no original filename, no mimetype, no
  extension, no path traversal. `base_path` is validated against
  `^[A-Za-z0-9][A-Za-z0-9_/\-]*$` (no `.`, no `..`, no absolute paths).
* **Sharded** by the first two hex characters (256 prefixes), which keeps S3
  listings and lifecycle tooling efficient.
* Multiple attachment rows may reference the same key (dedup). Deletion is
  therefore **reference-checked**: an object is only deleted when no
  `ir.attachment.store_fname` references it anymore.

Changing `base_path` later does not break existing objects (their full
`store_fname` is stored on the row), but objects under the old prefix are no
longer cleaned automatically — see §9.

---

## 5. Transaction safety and orphan handling

An object store cannot participate in a PostgreSQL transaction. The addon
uses the **same strategy as Odoo's local filestore GC**, applied to S3:

1. Before uploading, a **marker file** is written to
   `filestore/<db>/external_checklist/<key>`. Like Odoo's own checklist, this
   is a filesystem write and therefore **survives a database rollback**.
2. The object is uploaded, then the row is inserted/updated. On upload
   failure the whole transaction aborts (`UserError`), so the database never
   believes a missing object exists.
3. A daily autovacuum job (`ir.autovacuum` → `_gc_external_file_store`)
   processes the spool:
   * it commits, takes `LOCK ir_attachment IN SHARE MODE` (same as base
     `_gc_file_store`, so it sees the freshest committed state and cannot
     race concurrent creates),
   * deletes an object **only if no `store_fname` references it**, and only
     when its marker is older than `gc_min_age_hours` (default **24 h**),
   * removes the marker, and keeps it on backend failure for a later retry.

Resulting behavior:

| Scenario | Outcome |
|---|---|
| Upload fails | `UserError`; no row; marker is later collected. |
| Upload succeeds, DB rolls back | Object is orphaned **temporarily**; GC deletes it after the safety delay. |
| Attachment deleted, no other row shares the key | Object deleted by GC, not synchronously. |
| Attachment deleted, another row shares the key | Object kept. |
| GC crashed / backend down | Markers are retained and retried on the next vacuum. |

The `gc_min_age_hours` delay must exceed the longest plausible upload
transaction (default 24 h is generous). This is the deliberate trade-off:
guaranteed no false deletion of live data, at the cost of delayed orphan
cleanup.

---

## 6. Installation

```bash
# 1. Install the Python dependency in the Odoo virtualenv
/path/to/odoo/.venv/bin/pip install -r external_attachment_storage/requirements.txt
# or simply:  pip install 'boto3>=1.26'

# 2. Ensure the addon directory is on the Odoo addons_path, then install
/path/to/odoo/odoo-bin -c /etc/odoo/odoo.conf \
    -d <your_db> -i external_attachment_storage --stop-after-init

# 3. Restart Odoo
sudo systemctl restart odoo
```

The manifest declares `external_dependencies: {'python': ['boto3']}`, so
installation fails with a clear message if boto3 is missing. The addon is
**inert until enabled**.

### CI / tests

```bash
odoo-bin -d test_db -i external_attachment_storage \
    --test-tags /external_attachment_storage --test-enable --stop-after-init
```

48 tests, all S3/network operations mocked. Verified on Odoo 17.0:
`0 failed, 0 error(s) of 48 tests`.

---

## 7. Configuration

**Settings → General Settings → External Attachment Storage.**

| Setting | Notes |
|---|---|
| Enabled | Master switch. Only affects *new* uploads. |
| Provider | `S3 / S3-compatible`. |
| Endpoint URL | Empty for AWS S3; e.g. `https://<account>.r2.cloudflarestorage.com`, `http://minio.internal:9000`. |
| Bucket | Required when enabled. |
| Region | e.g. `us-east-1`; optional for providers that infer it. |
| Base Path | Key prefix, default `attachments`. |
| Access Key ID / Secret Access Key | Optional; see below. |
| *Test Connection* | Calls `HeadBucket` with the values currently in the form. |

### Trade-off: where to keep credentials

Odoo's settings persist values in `ir.config_parameter` (database). This is
convenient and admin-only, but credentials live in the DB and in backups.
The addon therefore supports three sources, in order:

1. system parameters (the settings form),
2. environment variables `EAS_ACCESS_KEY_ID` / `EAS_SECRET_ACCESS_KEY`,
3. boto3's default credential chain (standard `AWS_*` variables, IAM
   instance/task roles, `~/.aws/credentials`).

**Recommendation for production:** leave the key fields empty and rely on
IAM roles (EC2/ECS/EKS) or `EAS_*`/`AWS_*` environment variables injected by
your orchestrator. Nothing sensitive is ever written to source control.

Minimal IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject",
               "s3:ListBucket", "s3:GetBucketLocation"],
    "Resource": ["arn:aws:s3:::<bucket>", "arn:aws:s3:::<bucket>/*"]
  }]
}
```

---

## 8. Deployment checklist & verification

1. Install `boto3` (§6).
2. Configure the backend (§7) and use **Test Connection**.
3. Enable the feature and save.
4. Upload a file through any business flow, e.g. attach a document to an
   invoice or set a contact photo.
5. Verify in the database:

   ```python
   a = env['ir.attachment'].search([('name', 'like', '<file>')], limit=1)
   a.store_fname        # -> 'eas://attachments/xx/<sha1>'
   a.storage_backend    # -> 'external'
   ```
6. Verify the object exists in the bucket: `<base_path>/xx/<sha1>`.
7. Verify the download opens from the UI (`/web/content`).
8. Verify a **pre-existing** attachment is still `local`, still readable and
   unchanged.

### Performance notes

* Reads and writes pass the full payload once, exactly like the base
  `_file_write`/`_file_read`; downloads are served as an in-memory stream
  (the same memory profile as `db_datas` attachments). No extra DB queries
  per operation beyond reading the system parameters (same pattern as
  `_storage()`).
* Large uploads use boto3 multipart upload (`upload_fileobj`).
* Successful downloads are not logged unless debug logging is enabled;
  uploads are logged at INFO, failures at ERROR (never logging file contents
  or credentials).

---

## 9. Rollback

### Option A — disable the feature (recommended, non-destructive)

Uncheck **Enabled**. New attachments go back to the local filestore.
Existing external attachments keep working normally (read, download, delete)
because routing uses the stored `store_fname`, not the flag.

### Option B — uninstall the addon

External attachments must **not** be left unreachable. Run the admin-only
rescue tool from an Odoo shell **before** uninstalling:

```python
# Odoo shell
env['ir.attachment']._migrate_external_to_local()   # copies content back locally
env.cr.commit()
```

* It only touches records that are currently `external`; pre-existing local
  attachments are ignored.
* It copies each object into the local filestore and rewrites `store_fname`
  to the standard `xx/<sha1>` path.
* It **never deletes external objects**, so a partial/failed run can be
  retried and the objects remain as a backup.
* The backend configuration must still be readable, so run it while the
  addon is installed and configured.

After the migration:

```python
env['ir.attachment'].search_count([('storage_backend', '=', 'external')])  # 0
```

then uninstall the addon. (If you uninstall without migrating, external
attachments are *not* silently broken: reads log an ERROR and downloads
raise a `UserError` instead of serving empty files. Restore the addon and
run the rescue to recover.)

### Bucket hygiene

Rollback never deletes objects. Once you are satisfied no rollback is needed,
remove the `<base_path>/` prefix from the bucket manually (or via lifecycle
rules). Never point the addon at a bucket prefix shared with unrelated data.

---

## 10. Known trade-offs & limitations

* **Asset bundles are also externalized** (they are ordinary
  `ir.attachment` records). This means first page renders depend on the
  object store; if you prefer to keep assets local, disable the feature
  while regenerating assets or exclude them by policy in a follow-up.
* **`force_storage` / Settings → Technical "migrate storage"** rewrites
  attachments through the normal write path and would relocate them
  according to the current setting. Do not run it while the addon is enabled
  unless that is what you intend.
* **SHA1 collision handling**: like Odoo's local filestore, keys are
  content-addressed by SHA1; collisions are considered cryptographically
  negligible.
* **Deletes are eventually consistent**: objects are removed by the daily
  autovacuum after `gc_min_age_hours`, not instantly. This is intentional
  (reference checking + rollback safety).
* **Multi-server setups**: the GC spool lives in the database's filestore
  directory, which is shared when servers share the filestore (the usual
  Odoo HA setup). Any server may run the GC; the reference check makes it
  safe.

---

## 11. Package layout

```
external_attachment_storage/
├── __init__.py
├── __manifest__.py
├── requirements.txt
├── models/
│   ├── ir_attachment.py        # _file_write/_file_read/_file_delete, GC, rescue
│   ├── ir_binary.py            # /web/content, /web/image serving hook
│   ├── ir_http.py              # serving-attachment fallback hook
│   └── res_config_settings.py  # settings + Test Connection
├── services/
│   └── storage.py              # StorageBackend ABC, StorageConfig, factory
├── providers/
│   └── s3.py                   # boto3 S3-compatible implementation
├── views/res_config_settings_views.xml
├── security/ir.model.access.csv   # header only: no new models
└── tests/
    ├── test_external_attachment_storage.py
    └── test_s3_provider.py
```

Adding another backend (e.g. Azure Blob) means implementing
`services.storage.StorageBackend` and registering it in
`services.storage.get_backend` — `ir.attachment` stays untouched.
