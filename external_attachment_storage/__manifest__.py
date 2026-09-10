# Part of KEMSCO. See README.md for full documentation.
{
    'name': 'External Attachment Storage',
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'summary': 'Store newly uploaded attachments on an S3-compatible object storage backend',
    'description': """
External Attachment Storage
===========================

Routes *newly uploaded* ir.attachment files to an external S3-compatible
object storage backend (AWS S3, Cloudflare R2, MinIO, ...) instead of the
local Odoo filestore.

* Existing attachments are never migrated, moved or modified: they keep
  using the standard local filestore.
* New attachments created while the feature is enabled are content-addressed
  by their SHA1 checksum and uploaded to the external backend.
* Downloads go through Odoo (/web/content, /web/image), preserving the
  normal authorization flow. No presigned URLs.
* Deletions of external objects are deferred to a garbage collector that
  only removes objects no attachment record references anymore.

Requirements: the ``boto3`` Python library (see requirements.txt).
    """,
    'author': 'KEMSCO',
    'website': 'https://github.com/anwer/kemsco',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'base_setup',  # anchor for the settings block (auto-installed by Odoo)
    ],
    'external_dependencies': {
        'python': ['boto3'],
    },
    'data': [
        # No new models are introduced, so no access rules are required.
        # The file is kept (header only) to document that decision.
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
