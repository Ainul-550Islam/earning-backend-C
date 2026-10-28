"""
System Backup for alerts app - Comprehensive backup and restore system
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
import asyncio
import logging
from .sql_utils import quote_identifier
import json
import uuid
import os
import shutil
import gzip
import hashlib
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Backup type enumeration"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    CONFIG_ONLY = "config_only"


class BackupStatus(Enum):
    """Backup status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESTORING = "restoring"


class StorageBackend(ABC):
    """Abstract base class for storage backends"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
        
    @abstractmethod
    async def store_backup(self, backup_data: bytes, backup_path: str) -> Dict[str, Any]:
        """Store backup data"""
        pass
    
    @abstractmethod
    async def retrieve_backup(self, backup_path: str) -> bytes:
        """Retrieve backup data"""
        pass
    
    @abstractmethod
    async def list_backups(self, prefix: str = None) -> List[Dict[str, Any]]:
        """List available backups"""
        pass
    
    @abstractmethod
    async def delete_backup(self, backup_path: str) -> bool:
        """Delete backup"""
        pass
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get backend information"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'config': self.config
        }


class LocalStorageBackend(StorageBackend):
    """Local file system storage backend"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_path = config.get('base_path', '/var/backups/alerts')
        self.compression = config.get('compression', True)
        
        # Ensure backup directory exists
        os.makedirs(self.base_path, exist_ok=True)
    
    async def store_backup(self, backup_data: bytes, backup_path: str) -> Dict[str, Any]:
        """Store backup to local filesystem"""
        try:
            full_path = os.path.join(self.base_path, backup_path)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Compress if enabled
            if self.compression:
                backup_data = gzip.compress(backup_data)
                full_path += '.gz'
            
            # Write backup file
            with open(full_path, 'wb') as f:
                f.write(backup_data)
            
            # Calculate checksum
            checksum = hashlib.sha256(backup_data).hexdigest()
            
            return {
                'success': True,
                'path': full_path,
                'size': len(backup_data),
                'checksum': checksum,
                'compressed': self.compression,
                'stored_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Local storage error: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    async def retrieve_backup(self, backup_path: str) -> bytes:
        """Retrieve backup from local filesystem"""
        try:
            full_path = os.path.join(self.base_path, backup_path)
            
            # Check for compressed version
            if not os.path.exists(full_path) and os.path.exists(full_path + '.gz'):
                full_path += '.gz'
                compressed = True
            else:
                compressed = full_path.endswith('.gz')
            
            # Read backup file
            with open(full_path, 'rb') as f:
                backup_data = f.read()
            
            # Decompress if needed
            if compressed:
                backup_data = gzip.decompress(backup_data)
            
            return backup_data
            
        except Exception as e:
            logger.error(f"Local retrieval error: {e}")
            raise
    
    async def list_backups(self, prefix: str = None) -> List[Dict[str, Any]]:
        """List backups in local storage"""
        try:
            backups = []
            
            for root, dirs, files in os.walk(self.base_path):
                for file in files:
                    if file.endswith('.gz') or not file.endswith('.gz'):
                        rel_path = os.path.relpath(os.path.join(root, file), self.base_path)
                        
                        if prefix and not rel_path.startswith(prefix):
                            continue
                        
                        file_path = os.path.join(root, file)
                        stat = os.stat(file_path)
                        
                        backups.append({
                            'path': rel_path,
                            'size': stat.st_size,
                            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'compressed': file.endswith('.gz')
                        })
            
            return sorted(backups, key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Local list error: {e}")
            return []
    
    async def delete_backup(self, backup_path: str) -> bool:
        """Delete backup from local filesystem"""
        try:
            full_path = os.path.join(self.base_path, backup_path)
            
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            elif os.path.exists(full_path + '.gz'):
                os.remove(full_path + '.gz')
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Local delete error: {e}")
            return False


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bucket_name = config.get('bucket_name')
        self.access_key = config.get('access_key')
        self.secret_key = config.get('secret_key')
        self.region = config.get('region', 'us-east-1')
        self.prefix = config.get('prefix', 'alerts-backups')
        
    async def store_backup(self, backup_data: bytes, backup_path: str) -> Dict[str, Any]:
        """Store backup to S3"""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            # Prepare S3 key
            s3_key = f"{self.prefix}/{backup_path}"
            
            # Upload to S3
            s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=backup_data,
                ServerSideEncryption='AES256'
            )
            
            # Calculate checksum
            checksum = hashlib.sha256(backup_data).hexdigest()
            
            return {
                'success': True,
                's3_key': s3_key,
                'bucket': self.bucket_name,
                'size': len(backup_data),
                'checksum': checksum,
                'stored_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"S3 storage error: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    async def retrieve_backup(self, backup_path: str) -> bytes:
        """Retrieve backup from S3"""
        try:
            import boto3
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            # Prepare S3 key
            s3_key = f"{self.prefix}/{backup_path}"
            
            # Download from S3
            response = s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read()
            
        except Exception as e:
            logger.error(f"S3 retrieval error: {e}")
            raise
    
    async def list_backups(self, prefix: str = None) -> List[Dict[str, Any]]:
        """List backups in S3"""
        try:
            import boto3
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            # List objects
            list_prefix = f"{self.prefix}/{prefix}" if prefix else self.prefix
            
            response = s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=list_prefix
            )
            
            backups = []
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    backups.append({
                        'path': obj['Key'].replace(f"{self.prefix}/", ''),
                        'size': obj['Size'],
                        'created_at': obj['LastModified'].isoformat(),
                        's3_key': obj['Key']
                    })
            
            return sorted(backups, key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"S3 list error: {e}")
            return []
    
    async def delete_backup(self, backup_path: str) -> bool:
        """Delete backup from S3"""
        try:
            import boto3
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            # Prepare S3 key
            s3_key = f"{self.prefix}/{backup_path}"
            
            # Delete from S3
            s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
            
        except Exception as e:
            logger.error(f"S3 delete error: {e}")
            return False


class BackupTask:
    """Represents a backup task"""
    
    def __init__(self, backup_type: BackupType, description: str = None):
        self.id = str(uuid.uuid4())
        self.backup_type = backup_type
        self.description = description or f"{backup_type.value} backup"
        self.created_at = timezone.now()
        self.started_at = None
        self.completed_at = None
        self.status = BackupStatus.PENDING
        self.progress = 0
        self.total_files = 0
        self.processed_files = 0
        self.backup_size = 0
        self.error_message = None
        self.backup_path = None
        self.checksum = None
        
    def start(self):
        """Start backup task"""
        self.status = BackupStatus.IN_PROGRESS
        self.started_at = timezone.now()
        
    def complete(self, backup_path: str, backup_size: int, checksum: str):
        """Complete backup task"""
        self.status = BackupStatus.COMPLETED
        self.completed_at = timezone.now()
        self.backup_path = backup_path
        self.backup_size = backup_size
        self.checksum = checksum
        self.progress = 100
        
    def fail(self, error_message: str):
        """Fail backup task"""
        self.status = BackupStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        
    def cancel(self):
        """Cancel backup task"""
        self.status = BackupStatus.CANCELLED
        self.completed_at = timezone.now()
        
    def update_progress(self, processed_files: int, total_files: int):
        """Update backup progress"""
        self.processed_files = processed_files
        self.total_files = total_files
        if total_files > 0:
            self.progress = int((processed_files / total_files) * 100)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'backup_type': self.backup_type.value,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'progress': self.progress,
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'backup_size': self.backup_size,
            'error_message': self.error_message,
            'backup_path': self.backup_path,
            'checksum': self.checksum
        }


class BackupManager:
    """Main backup management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.storage_backends = {}
        self.tasks = {}
        self.enabled = config.get('enabled', True)
        self.default_storage = config.get('default_storage', 'local')
        self.max_concurrent_backups = config.get('max_concurrent_backups', 2)
        self.retention_days = config.get('retention_days', 30)
        
        # Initialize storage backends
        self._initialize_storage_backends()
        
        # Start cleanup task
        self.cleanup_running = False
        
    def _initialize_storage_backends(self):
        """Initialize storage backends"""
        backend_configs = self.config.get('storage_backends', {})
        
        for backend_name, backend_config in backend_configs.items():
            backend_type = backend_config.get('type', 'local')
            
            if backend_type == 'local':
                backend = LocalStorageBackend(backend_config)
            elif backend_type == 's3':
                backend = S3StorageBackend(backend_config)
            else:
                logger.error(f"Unknown storage backend type: {backend_type}")
                continue
            
            self.storage_backends[backend_name] = backend
            logger.info(f"Initialized storage backend: {backend_name}")
    
    def create_backup_task(self, backup_type: BackupType, description: str = None) -> BackupTask:
        """Create backup task"""
        # Check concurrent backup limit
        active_tasks = [t for t in self.tasks.values() if t.status == BackupStatus.IN_PROGRESS]
        if len(active_tasks) >= self.max_concurrent_backups:
            raise Exception(f"Maximum concurrent backups reached: {self.max_concurrent_backups}")
        
        # Create task
        task = BackupTask(backup_type, description)
        self.tasks[task.id] = task
        
        logger.info(f"Created backup task {task.id} of type {backup_type.value}")
        return task
    
    async def execute_backup(self, task: BackupTask) -> Dict[str, Any]:
        """Execute backup task"""
        if not self.enabled:
            task.fail("Backup manager is disabled")
            return {'success': False, 'error': 'Backup manager is disabled'}
        
        try:
            task.start()
            
            # Get storage backend
            storage = self.storage_backends.get(self.default_storage)
            if not storage:
                task.fail(f"Storage backend {self.default_storage} not found")
                return {'success': False, 'error': f'Storage backend {self.default_storage} not found'}
            
            # Collect backup data
            backup_data = await self._collect_backup_data(task)
            
            if not backup_data:
                task.fail("No data to backup")
                return {'success': False, 'error': 'No data to backup'}
            
            # Generate backup path
            backup_path = self._generate_backup_path(task)
            
            # Store backup
            storage_result = await storage.store_backup(backup_data, backup_path)
            
            if storage_result['success']:
                task.complete(
                    backup_path=storage_result.get('path', backup_path),
                    backup_size=len(backup_data),
                    checksum=storage_result.get('checksum')
                )
                
                logger.info(f"Backup {task.id} completed successfully")
                return {
                    'success': True,
                    'task_id': task.id,
                    'backup_path': storage_result.get('path'),
                    'backup_size': len(backup_data),
                    'checksum': storage_result.get('checksum')
                }
            else:
                task.fail(storage_result.get('error', 'Storage failed'))
                return {
                    'success': False,
                    'error': storage_result.get('error'),
                    'task_id': task.id
                }
                
        except Exception as e:
            task.fail(str(e))
            logger.error(f"Backup execution error: {e}")
            return {
                'success': False,
                'error': 'Operation failed',
                'task_id': task.id
            }
    
    async def _collect_backup_data(self, task: BackupTask) -> bytes:
        """Collect backup data"""
        try:
            backup_data = {}
            
            if task.backup_type == BackupType.FULL:
                backup_data = await self._collect_full_backup(task)
            elif task.backup_type == BackupType.INCREMENTAL:
                backup_data = await self._collect_incremental_backup(task)
            elif task.backup_type == BackupType.DIFFERENTIAL:
                backup_data = await self._collect_differential_backup(task)
            elif task.backup_type == BackupType.CONFIG_ONLY:
                backup_data = await self._collect_config_backup(task)
            
            # Serialize backup data
            backup_json = json.dumps(backup_data, default=str, indent=2)
            return backup_json.encode('utf-8')
            
        except Exception as e:
            logger.error(f"Backup data collection error: {e}")
            raise
    
    async def _collect_full_backup(self, task: BackupTask) -> Dict[str, Any]:
        """Collect full backup data"""
        backup_data = {
            'backup_type': 'full',
            'created_at': timezone.now().isoformat(),
            'version': '1.0',
            'data': {}
        }
        
        # Backup database
        backup_data['data']['database'] = await self._backup_database(task)
        
        # Backup configuration
        backup_data['data']['configuration'] = await self._backup_configuration()
        
        # Backup files
        backup_data['data']['files'] = await self._backup_files(task)
        
        # Backup cache
        backup_data['data']['cache'] = await self._backup_cache()
        
        return backup_data
    
    async def _collect_incremental_backup(self, task: BackupTask) -> Dict[str, Any]:
        """Collect incremental backup data"""
        # Get last backup timestamp
        last_backup_time = await self._get_last_backup_time()
        
        backup_data = {
            'backup_type': 'incremental',
            'created_at': timezone.now().isoformat(),
            'since': last_backup_time.isoformat() if last_backup_time else None,
            'data': {}
        }
        
        # Collect changes since last backup
        if last_backup_time:
            backup_data['data']['database_changes'] = await self._backup_database_changes(last_backup_time, task)
            backup_data['data']['file_changes'] = await self._backup_file_changes(last_backup_time, task)
        else:
            # Fall back to full backup if no previous backup
            return await self._collect_full_backup(task)
        
        return backup_data
    
    async def _collect_differential_backup(self, task: BackupTask) -> Dict[str, Any]:
        """Collect differential backup data"""
        # Get last full backup timestamp
        last_full_backup_time = await self._get_last_full_backup_time()
        
        backup_data = {
            'backup_type': 'differential',
            'created_at': timezone.now().isoformat(),
            'since': last_full_backup_time.isoformat() if last_full_backup_time else None,
            'data': {}
        }
        
        # Collect all changes since last full backup
        if last_full_backup_time:
            backup_data['data']['database_changes'] = await self._backup_database_changes(last_full_backup_time, task)
            backup_data['data']['file_changes'] = await self._backup_file_changes(last_full_backup_time, task)
        else:
            # Fall back to full backup if no previous full backup
            return await self._collect_full_backup(task)
        
        return backup_data
    
    async def _collect_config_backup(self, task: BackupTask) -> Dict[str, Any]:
        """Collect configuration backup data"""
        backup_data = {
            'backup_type': 'config_only',
            'created_at': timezone.now().isoformat(),
            'data': {
                'configuration': await self._backup_configuration()
            }
        }
        
        return backup_data
    
    async def _backup_database(self, task: BackupTask) -> Dict[str, Any]:
        """Backup database data"""
        try:
            from asgiref.sync import sync_to_async
            return await sync_to_async(self._backup_database_sync)(task)
        except Exception as e:
            logger.error(f"Database backup error: {e}")
            raise

    def _backup_database_sync(self, task: BackupTask) -> Dict[str, Any]:
        """Synchronous cursor work for _backup_database (run via sync_to_async —
        raw DB cursor access is not permitted directly inside an async def)."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = [row[0] for row in cursor.fetchall()]

        # Backup each table
        database_backup = {}
        total_tables = len(tables)

        for i, table in enumerate(tables):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SELECT * FROM {quote_identifier(table, what='table')}")  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()

                    database_backup[table] = {
                        'columns': columns,
                        'rows': rows,
                        'row_count': len(rows)
                    }

                # Update progress
                task.update_progress(i + 1, total_tables)

            except Exception as e:
                logger.error(f"Error backing up table {table}: {e}")
                database_backup[table] = {'error': str(e)}

        return database_backup
    
    async def _backup_database_changes(self, since: datetime, task: BackupTask) -> Dict[str, Any]:
        """Backup database changes since given time"""
        try:
            from asgiref.sync import sync_to_async
            return await sync_to_async(self._backup_database_changes_sync)(since, task)
        except Exception as e:
            logger.error(f"Database changes backup error: {e}")
            raise

    def _backup_database_changes_sync(self, since: datetime, task: BackupTask) -> Dict[str, Any]:
        """Synchronous cursor work for _backup_database_changes (run via sync_to_async)."""
        from django.db import connection

        changes = {}

        # Get tables with timestamp columns
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name, column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND data_type IN ('timestamp', 'timestamptz', 'datetime')
            """)
            timestamp_columns = cursor.fetchall()

        for table, column in timestamp_columns:
            try:
                with connection.cursor() as cursor:
                    query = f"SELECT * FROM {quote_identifier(table, what='table')} WHERE {quote_identifier(column, what='column')} > %s"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                    cursor.execute(query, [since])

                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()

                        if rows:
                            changes[table] = {
                                'columns': columns,
                                'rows': rows,
                                'row_count': len(rows),
                                'since_column': column
                            }

            except Exception as e:
                logger.error(f"Error backing up changes for table {table}: {e}")

        return changes
    
    async def _backup_configuration(self) -> Dict[str, Any]:
        """Backup configuration data"""
        try:
            from django.conf import settings
            
            config_backup = {
                'django_settings': {
                    key: str(value) for key, value in settings.__dict__.items()
                    if not key.startswith('_') and not callable(value)
                },
                'environment_variables': dict(os.environ),
                'backup_config': self.config
            }
            
            return config_backup
            
        except Exception as e:
            logger.error(f"Configuration backup error: {e}")
            raise
    
    async def _backup_files(self, task: BackupTask) -> Dict[str, Any]:
        """Backup important files"""
        try:
            files_backup = {}
            
            # Files to backup
            important_files = [
                'settings.py',
                'urls.py',
                'wsgi.py',
                'manage.py'
            ]
            
            for file_path in important_files:
                try:
                    full_path = os.path.join(settings.BASE_DIR, file_path)
                    if os.path.exists(full_path):
                        with open(full_path, 'r') as f:
                            files_backup[file_path] = f.read()
                except Exception as e:
                    logger.error(f"Error backing up file {file_path}: {e}")
                    files_backup[file_path] = {'error': str(e)}
            
            return files_backup
            
        except Exception as e:
            logger.error(f"Files backup error: {e}")
            raise
    
    async def _backup_file_changes(self, since: datetime, task: BackupTask) -> Dict[str, Any]:
        """Backup file changes since given time"""
        try:
            changes = {}
            
            # This would track file modifications
            # For now, return empty dict
            return changes
            
        except Exception as e:
            logger.error(f"File changes backup error: {e}")
            raise
    
    async def _backup_cache(self) -> Dict[str, Any]:
        """Backup cache data"""
        try:
            cache_backup = {}
            
            # Get cache keys
            if hasattr(cache, 'keys'):
                keys = cache.keys('*')
                for key in keys[:100]:  # Limit to first 100 keys
                    try:
                        value = cache.get(key)
                        cache_backup[key] = str(value)
                    except Exception as e:
                        cache_backup[key] = {'error': str(e)}
            
            return cache_backup
            
        except Exception as e:
            logger.error(f"Cache backup error: {e}")
            raise
    
    async def _get_last_backup_time(self) -> Optional[datetime]:
        """Get timestamp of last backup"""
        try:
            storage = self.storage_backends.get(self.default_storage)
            if not storage:
                return None
            
            backups = await storage.list_backups()
            if backups:
                last_backup = backups[0]
                return datetime.fromisoformat(last_backup['created_at'])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last backup time: {e}")
            return None
    
    async def _get_last_full_backup_time(self) -> Optional[datetime]:
        """Get timestamp of last full backup"""
        try:
            storage = self.storage_backends.get(self.default_storage)
            if not storage:
                return None
            
            backups = await storage.list_backups()
            full_backups = [b for b in backups if 'full' in b['path']]
            
            if full_backups:
                last_full_backup = full_backups[0]
                return datetime.fromisoformat(last_full_backup['created_at'])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last full backup time: {e}")
            return None
    
    def _generate_backup_path(self, task: BackupTask) -> str:
        """Generate backup file path"""
        timestamp = task.created_at.strftime('%Y-%m-%d_%H-%M-%S')
        return f"{task.backup_type.value}/{timestamp}_{task.id[:8]}.json"
    
    async def restore_backup(self, backup_path: str, storage_backend: str = None) -> Dict[str, Any]:
        """Restore from backup"""
        try:
            storage = self.storage_backends.get(storage_backend or self.default_storage)
            if not storage:
                return {'success': False, 'error': 'Storage backend not found'}
            
            # Retrieve backup data
            backup_data = await storage.retrieve_backup(backup_path)
            backup_json = json.loads(backup_data.decode('utf-8'))
            
            # Process restore
            restore_result = await self._process_restore(backup_json)
            
            return {
                'success': True,
                'restore_result': restore_result
            }
            
        except Exception as e:
            logger.error(f"Restore error: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    async def _process_restore(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process backup restore"""
        try:
            restore_results = {}
            
            # Restore database
            if 'database' in backup_data.get('data', {}):
                restore_results['database'] = await self._restore_database(backup_data['data']['database'])
            
            # Restore configuration
            if 'configuration' in backup_data.get('data', {}):
                restore_results['configuration'] = await self._restore_configuration(backup_data['data']['configuration'])
            
            return restore_results
            
        except Exception as e:
            logger.error(f"Restore processing error: {e}")
            raise
    
    async def _restore_database(self, database_backup: Dict[str, Any]) -> Dict[str, Any]:
        """Restore database from backup"""
        try:
            from django.db import connection
            
            restore_results = {}
            
            for table, data in database_backup.items():
                if 'error' in data:
                    restore_results[table] = {'success': False, 'error': data['error']}
                    continue
                
                try:
                    # The backup file is untrusted input: only touch tables that really exist and
                    # only splice validated, quoted identifiers into the statements.
                    if table not in connection.introspection.table_names():
                        restore_results[table] = {'success': False, 'error': 'Unknown table'}
                        continue
                    quoted_table = quote_identifier(table, what='table')
                    quoted_columns = ', '.join(quote_identifier(c, what='column') for c in data['columns'])
                    with connection.cursor() as cursor:
                        # Clear existing data
                        cursor.execute(f"DELETE FROM {quoted_table}")  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                        
                        # Insert backup data
                        if data['rows']:
                            placeholders = ', '.join(['%s'] * len(data['columns']))
                            query = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                            
                            for row in data['rows']:
                                cursor.execute(query, row)
                    
                    restore_results[table] = {'success': True, 'rows_restored': len(data['rows'])}
                    
                except Exception as e:
                    restore_results[table] = {'success': False, 'error': str(e)}
            
            return restore_results
            
        except Exception as e:
            logger.error(f"Database restore error: {e}")
            raise
    
    async def _restore_configuration(self, config_backup: Dict[str, Any]) -> Dict[str, Any]:
        """Restore configuration from backup"""
        try:
            # This would restore configuration files
            # For now, just return the config data
            return {
                'success': True,
                'config_restored': config_backup
            }
            
        except Exception as e:
            logger.error(f"Configuration restore error: {e}")
            raise
    
    def get_task(self, task_id: str) -> Optional[BackupTask]:
        """Get backup task by ID"""
        return self.tasks.get(task_id)
    
    def get_tasks(self, status: BackupStatus = None) -> List[BackupTask]:
        """Get backup tasks"""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return sorted(tasks, key=lambda x: x.created_at, reverse=True)
    
    async def cleanup_old_backups(self):
        """Clean up old backups based on retention policy"""
        try:
            storage = self.storage_backends.get(self.default_storage)
            if not storage:
                return
            
            cutoff_date = timezone.now() - timezone.timedelta(days=self.retention_days)
            backups = await storage.list_backups()
            
            deleted_count = 0
            
            for backup in backups:
                backup_date = datetime.fromisoformat(backup['created_at'])
                
                if backup_date < cutoff_date:
                    success = await storage.delete_backup(backup['path'])
                    if success:
                        deleted_count += 1
                        logger.info(f"Deleted old backup: {backup['path']}")
            
            logger.info(f"Cleanup completed. Deleted {deleted_count} old backups")
            
        except Exception as e:
            logger.error(f"Backup cleanup error: {e}")
    
    def get_manager_status(self) -> Dict[str, Any]:
        """Get backup manager status"""
        active_tasks = [t for t in self.tasks.values() if t.status == BackupStatus.IN_PROGRESS]
        
        return {
            'manager_enabled': self.enabled,
            'total_tasks': len(self.tasks),
            'active_tasks': len(active_tasks),
            'max_concurrent_backups': self.max_concurrent_backups,
            'retention_days': self.retention_days,
            'default_storage': self.default_storage,
            'storage_backends': {
                name: backend.get_backend_info()
                for name, backend in self.storage_backends.items()
            },
            'recent_tasks': [task.to_dict() for task in self.get_tasks()[:10]],
            'timestamp': timezone.now().isoformat()
        }


# Global backup manager
backup_manager = None


def get_backup_manager() -> Optional[BackupManager]:
    """Get the global backup manager"""
    return backup_manager


def initialize_backup_system():
    """Initialize backup system from settings"""
    from django.conf import settings
    
    global backup_manager
    
    config = getattr(settings, 'BACKUP_CONFIG', {
        'enabled': True,
        'default_storage': 'local',
        'max_concurrent_backups': 2,
        'retention_days': 30,
        'storage_backends': {
            'local': {
                'type': 'local',
                'enabled': True,
                'base_path': '/var/backups/alerts',
                'compression': True
            }
        }
    })
    
    try:
        backup_manager = BackupManager(config)
        logger.info("Backup system initialized")
    except Exception as e:
        logger.error(f"Error initializing backup system: {e}")


# Initialize on module import
try:
    initialize_backup_system()
except Exception as e:
    logger.error(f"Error initializing backup system: {e}")
