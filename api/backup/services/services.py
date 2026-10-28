# api/backup/services.py
"""
Business logic for backup. Move complex logic out of views.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from api.backup.models import Backup
from api.backup.models import BackupRestoration
from api.backup.models import BackupVerification
from api.backup.models import BackupSchedule

logger = logging.getLogger(__name__)


class BackupService:
    """Main service for backup operations - orchestrates all backup services."""
    
    def __init__(self, enable_failover: bool = True, enable_compression: bool = True,
                 enable_verification: bool = True):
        self.db_service = None
        self.storage_adapter = None
        self.failover_manager = None
        self.compressor = None
        self.verifier = None
        self.enable_failover = enable_failover
        self.enable_compression = enable_compression
        self.enable_verification = enable_verification
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize service dependencies"""
        try:
            from .services.DatabaseBackup import DatabaseBackupService
            from .services.storage import StorageAdapterFactory
            from .services.storage.failover import create_failover_manager, FailoverStrategy
            from .services.storage.compression import create_compressor
            from .services.storage.verification import create_verifier
            
            self.db_service = DatabaseBackupService()
            self.storage_factory = StorageAdapterFactory()
            
            # Initialize failover manager
            if self.enable_failover:
                self.failover_manager = create_failover_manager(
                    primary_storage='s3',
                    fallback_storages=['local'],
                    strategy=FailoverStrategy.FAILOVER_ON_FAILURE
                )
            
            # Initialize compressor
            if self.enable_compression:
                self.compressor = create_compressor('gzip', compression_level=6)
            
            # Initialize verifier
            if self.enable_verification:
                self.verifier = create_verifier()
                
        except ImportError as e:
            logger.warning(f"Could not initialize backup services: {e}")
    
    def create_backup(self, backup_type: str, storage_type: str, **kwargs) -> Optional['Backup']:
        """
        Create a new backup with specified type and storage.
        
        Args:
            backup_type: Type of backup (full, incremental, differential, etc.)
            storage_type: Storage backend (local, s3, azure, gcp, etc.)
            **kwargs: Additional backup configuration options
            
        Returns:
            Backup instance or None if failed
        """
        try:
            from .models import Backup, BackupSchedule
            
            # Create backup record
            backup = Backup.objects.create(
                name=kwargs.get('name', f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                backup_type=backup_type,
                storage_type=storage_type,
                database_name=kwargs.get('database_name', settings.DATABASES['default']['NAME']),
                description=kwargs.get('description', ''),
                created_by=kwargs.get('created_by'),
                encryption_enabled=kwargs.get('encrypt', False),
                compression_enabled=kwargs.get('compress', True),
                retention_days=kwargs.get('retention_days', 30),
                metadata=kwargs.get('metadata', {})
            )
            
            # Get storage adapter
            storage_config = self._get_storage_config(storage_type, kwargs)
            
            # Create database dump
            backup_result = self.db_service.create_backup(backup)
            
            if not hasattr(backup_result, 'backup_file'):
                logger.error("Database backup did not return a backup file")
                backup.status = 'failed'
                backup.error_message = 'Database backup failed'
                backup.save()
                return None
            
            # Compress backup if enabled
            backup_file = backup_result.backup_file
            if self.enable_compression and self.compressor:
                compression_result = self.compressor.compress_file_obj(backup_file)
                if compression_result.success:
                    backup_file = compression_result.compressed_file_obj
                    backup.compression_ratio = compression_result.compression_ratio
                    backup.compressed_size = compression_result.compressed_size
                    logger.info(f"Backup compressed: {compression_result.compression_ratio:.1f}% reduction")
                else:
                    logger.warning(f"Compression failed: {compression_result.error_message}")
            
            # Calculate checksum if verification enabled
            if self.enable_verification and self.verifier:
                try:
                    integrity = self.verifier.create_backup_integrity(
                        backup_file, str(backup.backup_id), 'sha256'
                    )
                    backup.checksum = integrity.checksum
                    backup.checksum_algorithm = integrity.algorithm
                    backup.file_size = integrity.file_size
                    logger.info(f"Backup checksum calculated: {integrity.checksum}")
                except Exception as e:
                    logger.warning(f"Failed to calculate checksum: {e}")
            
            # Save to storage with failover
            if self.enable_failover and self.failover_manager:
                success = self.failover_manager.save_backup_with_failover(backup_file, backup)
            else:
                # Use traditional single adapter
                self.storage_adapter = self.storage_factory.get_adapter(storage_type, storage_config)
                success = self.storage_adapter.save_backup(backup_file, backup)
            
            if not success:
                backup.status = 'failed'
                backup.error_message = 'Storage save failed'
                backup.save()
                
                # Trigger DR alert if failover is enabled and storage failed
                if self.enable_failover:
                    self._trigger_dr_alert_on_storage_failure(backup)
                
                return None
            
            logger.info(f"Backup created successfully: {backup.name}")
            return backup
            
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            if 'backup' in locals():
                backup.status = 'failed'
                backup.error_message = str(e)
                backup.save()
            return None
    
    def _get_storage_config(self, storage_type: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get storage configuration based on storage type.
        
        Args:
            storage_type: Type of storage (local, s3, etc.)
            kwargs: Additional configuration options
            
        Returns:
            Dict: Storage configuration
        """
        if storage_type == 'local':
            return {
                'base_path': kwargs.get('local_path', '/tmp/backups'),
                'create_dirs': True,
                'backup_subdir': 'backups'
            }
        elif storage_type == 's3':
            return {
                'access_key': kwargs.get('s3_access_key'),
                'secret_key': kwargs.get('s3_secret_key'),
                'bucket_name': kwargs.get('s3_bucket'),
                'region': kwargs.get('s3_region', 'us-east-1'),
                'use_ssl': kwargs.get('s3_use_ssl', True)
            }
        else:
            # Try to get from storage location model
            storage_location_id = kwargs.get('storage_location_id')
            if storage_location_id:
                try:
                    from .models import BackupStorageLocation
                    storage_location = BackupStorageLocation.objects.get(id=storage_location_id)
                    return storage_location.config or {}
                except Exception:
                    pass
            
            return {}
    
    def get_storage_adapter(self, storage_type: str, config: Dict[str, Any] = None):
        """
        Get storage adapter instance.
        
        Args:
            storage_type: Type of storage
            config: Storage configuration
            
        Returns:
            Storage adapter instance
        """
        return self.storage_factory.get_adapter(storage_type, config or {})
    
    def _trigger_dr_alert_on_storage_failure(self, backup):
        """
        Trigger disaster recovery alert when all storage adapters fail.
        
        Args:
            backup: Backup model instance
        """
        try:
            # Log critical storage failure - DR integration removed (backup app is self-contained)
            logger.critical(
                f"CRITICAL: All storage adapters failed for backup {backup.backup_id}. "
                f"Manual intervention required."
            )
        except Exception:
            pass
        except Exception as e:
            logger.error(f"Failed to trigger DR alert: {e}")
    
    def get_failover_status(self):
        """
        Get current failover status.
        
        Returns:
            Dict: Failover status information
        """
        if self.enable_failover and self.failover_manager:
            return self.failover_manager.get_failover_status()
        return {'failover_enabled': False}
    
    def check_and_maintain_failover(self):
        """
        Check health of all adapters and maintain failover status.
        
        Returns:
            Dict: Failover maintenance results
        """
        if self.enable_failover and self.failover_manager:
            return self.failover_manager.check_and_maintain_failover()
        return {'failover_enabled': False}
    
    def force_switch_storage(self, target_storage: str, reason: str = "manual") -> bool:
        """
        Force switch to a specific storage adapter.
        
        Args:
            target_storage: Target storage type
            reason: Reason for switching
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.enable_failover and self.failover_manager:
            return self.failover_manager.force_switch_adapter(target_storage, reason)
        return False
    
    def restore_backup(self, backup_id: str, **kwargs) -> Optional['BackupRestoration']:
        """
        Restore a backup from backup ID.
        
        Args:
            backup_id: UUID of the backup to restore
            **kwargs: Additional restore options
            
        Returns:
            BackupRestoration instance or None if failed
        """
        try:
            from .models import Backup, BackupRestoration
            
            # Get backup
            backup = Backup.objects.get(backup_id=backup_id)
            
            # Create restoration record
            restoration = BackupRestoration.objects.create(
                backup=backup,
                restoration_type=kwargs.get('restoration_type', 'full'),
                tables_to_restore=kwargs.get('tables', []),
                initiated_by=kwargs.get('initiated_by'),
                notes=kwargs.get('notes', ''),
                restore_point=kwargs.get('restore_point', timezone.now())
            )
            
            # Get storage adapter and download backup
            storage_config = self._get_storage_config(backup.storage_type, {})
            
            # Retrieve backup with failover
            if self.enable_failover and self.failover_manager:
                backup_file = self.failover_manager.retrieve_backup_with_failover(backup)
            else:
                self.storage_adapter = self.storage_factory.get_adapter(backup.storage_type, storage_config)
                backup_file = self.storage_adapter.retrieve_backup(backup)
            
            if not backup_file:
                restoration.status = 'failed'
                restoration.error_message = 'Failed to retrieve backup file'
                restoration.save()
                return restoration
            
            # Verify backup before restoration if enabled
            if self.enable_verification and self.verifier:
                try:
                    is_verified, verification_result = self.verifier.verify_before_restoration(
                        self.failover_manager.get_active_adapter() if self.enable_failover else self.storage_adapter,
                        backup
                    )
                    
                    if not is_verified:
                        restoration.status = 'failed'
                        restoration.error_message = f'Backup verification failed: {verification_result.error_message}'
                        restoration.save()
                        logger.error(f"Backup verification failed: {verification_result.error_message}")
                        return restoration
                    
                    logger.info(f"Backup verification passed: {verification_result.actual_checksum}")
                    
                except Exception as e:
                    logger.warning(f"Backup verification error: {e}")
                    # Continue with restoration but log the error
            
            # Decompress backup if needed
            if backup.compression_enabled and self.enable_compression and self.compressor:
                try:
                    decompression_result = self.compressor.decompress_file_obj(backup_file)
                    if decompression_result.success:
                        backup_file = decompression_result.compressed_file_obj
                        logger.info(f"Backup decompressed successfully")
                    else:
                        logger.warning(f"Decompression failed: {decompression_result.error_message}")
                except Exception as e:
                    logger.warning(f"Decompression error: {e}")
            
            # Perform restoration
            restore_result = self.db_service.restore_backup(backup, backup_file=backup_file, **kwargs)
            
            # Update restoration record
            restoration.status = 'completed' if restore_result else 'failed'
            restoration.success = restore_result
            restoration.completed_at = timezone.now()
            restoration.save()
            
            logger.info(f"Backup restoration completed: {backup.name}")
            return restoration
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {str(e)}")
            if 'restoration' in locals():
                restoration.status = 'failed'
                restoration.error_message = str(e)
                restoration.save()
            return None
    
    def verify_backup(self, backup_id: str, verification_method: str = 'hash') -> Optional['BackupVerification']:
        """
        Verify backup integrity.
        
        Args:
            backup_id: UUID of the backup to verify
            verification_method: Method of verification (hash, size, test_restore, full)
            
        Returns:
            BackupVerification instance or None if failed
        """
        try:
            from .models import Backup, BackupVerification
            from .services.BackupValidator import BackupValidator
            
            # Get backup
            backup = Backup.objects.get(backup_id=backup_id)
            
            # Create verification record
            verification = BackupVerification.objects.create(
                backup=backup,
                verification_method=verification_method,
                verified_by=None  # Can be set to current user
            )
            
            # Perform verification
            validator = BackupValidator()
            
            if verification_method == 'hash':
                # Verify file hash
                checksum_match = validator.verify_file_integrity(
                    backup.storage_location, 
                    backup.file_hash
                )
                verification.checksum_match = checksum_match
                verification.is_valid = checksum_match
                
            elif verification_method == 'size':
                # Verify file size
                size_match = validator.verify_file_size(
                    backup.storage_location,
                    backup.file_size
                )
                verification.size_match = size_match
                verification.is_valid = size_match
                
            elif verification_method == 'test_restore':
                # Test restore to temporary database
                test_result = validator.test_restore_backup(backup)
                verification.is_valid = test_result
                verification.verification_details = {'test_restore': test_result}
                
            elif verification_method == 'full':
                # Full verification including hash, size, and test restore
                checksum_match = validator.verify_file_integrity(
                    backup.storage_location, 
                    backup.file_hash
                )
                size_match = validator.verify_file_size(
                    backup.storage_location,
                    backup.file_size
                )
                test_result = validator.test_restore_backup(backup)
                
                verification.checksum_match = checksum_match
                verification.size_match = size_match
                verification.is_valid = checksum_match and size_match and test_result
                verification.verification_details = {
                    'checksum_match': checksum_match,
                    'size_match': size_match,
                    'test_restore': test_result
                }
            
            verification.save()
            logger.info(f"Backup verification completed: {backup.name} - {'Valid' if verification.is_valid else 'Invalid'}")
            return verification
            
        except Exception as e:
            logger.error(f"Failed to verify backup: {str(e)}")
            if 'verification' in locals():
                verification.is_valid = False
                verification.error_message = str(e)
                verification.save()
            return None
    
    def schedule_backup(self, cron_expr: str, backup_type: str, **kwargs) -> Optional['BackupSchedule']:
        """
        Schedule a backup with cron expression.
        
        Args:
            cron_expr: Cron expression for scheduling
            backup_type: Type of backup to schedule
            **kwargs: Additional schedule configuration
            
        Returns:
            BackupSchedule instance or None if failed
        """
        try:
            from .models import BackupSchedule
            
            # Create schedule
            schedule = BackupSchedule.objects.create(
                name=kwargs.get('name', f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                cron_expression=cron_expr,
                backup_type=backup_type,
                frequency=kwargs.get('frequency', 'custom'),
                database_alias=kwargs.get('database_alias', 'default'),
                storage_type=kwargs.get('storage_type', 'local'),
                storage_locations=kwargs.get('storage_locations', []),
                encryption_enabled=kwargs.get('encrypt', False),
                compression_enabled=kwargs.get('compress', True),
                retention_days=kwargs.get('retention_days', 30),
                is_active=kwargs.get('is_active', True),
                created_by=kwargs.get('created_by'),
                description=kwargs.get('description', ''),
                databases=kwargs.get('databases', ['default']),
                tables_include=kwargs.get('tables_include', []),
                tables_exclude=kwargs.get('tables_exclude', [])
            )
            
            # Calculate next run time
            schedule.calculate_next_run()
            schedule.save()
            
            logger.info(f"Backup schedule created: {schedule.name}")
            return schedule
            
        except Exception as e:
            logger.error(f"Failed to create backup schedule: {str(e)}")
            return None

    @staticmethod
    def get_last_backup_status() -> Dict[str, Any]:
        """Return status of most recent backup."""
        try:
            from .models import Backup
            last = Backup.objects.order_by('-created_at').first()
            if not last:
                return {"status": "none", "last_run": None}
            return {
                "status": getattr(last, 'status', 'unknown'),
                "last_run": getattr(last, 'created_at', None),
                "backup_type": getattr(last, 'backup_type', None),
            }
        except Exception as e:
            logger.debug("Backup status: %s", e)
            return {"status": "error", "last_run": None}
