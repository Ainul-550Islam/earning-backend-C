"""
Storage Model — SQLAlchemy model for backup storage locations.
Tracks all storage backends (S3, Azure, GCP, local, NAS, tape)
with capacity, usage, and accessibility status.
"""
from ..sa_models import StorageLocation

__all__ = ["StorageLocation"]

STORAGE_LOCATION_EXAMPLES = [
    {
        "name": "AWS S3 Primary (us-east-1)",
        "provider": "aws_s3",
        "region": "us-east-1",
        "bucket_or_container": "company-dr-backups-prod",
        "path_prefix": "/production/",
        "is_primary": True,
        "total_capacity_gb": 102400.0,
        "used_capacity_gb": 12288.0,
    },
    {
        "name": "AWS Glacier Archive",
        "provider": "aws_glacier",
        "region": "us-east-1",
        "bucket_or_container": "company-dr-archive",
        "is_primary": False,
        "total_capacity_gb": None,
        "used_capacity_gb": 51200.0,
    },
    {
        "name": "Azure Blob DR Region",
        "provider": "azure_blob",
        "region": "westeurope",
        "bucket_or_container": "dr-backups-eu",
        "is_primary": False,
    },
]
