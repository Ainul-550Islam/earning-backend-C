"""BackupServiceFactory"""
from .services import BackupService

class BackupServiceFactory:
    @classmethod
    def create(cls, backend='local', **kwargs):
        return BackupService(**kwargs) if BackupService else None

    @classmethod
    def get_available_backends(cls):
        return ['local', 's3', 'gcs', 'azure']
