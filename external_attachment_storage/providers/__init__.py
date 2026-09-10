# providers.s3 is imported lazily by services.storage.get_backend so that
# boto3 is only required when the external storage feature is actually
# used. Keep this file empty on purpose.
