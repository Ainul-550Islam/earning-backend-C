"""
Test Restore Management Command
Test restore backups to staging database for verification
"""

import os
import sys
import json
import logging
import tempfile
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import connection
from django.conf import settings

from api.backup.models import Backup, BackupRestoration, BackupAlert
from api.backup.services.factory import BackupServiceFactory
from api.backup.services.DatabaseBackup import DatabaseBackupService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test restore backups to staging database for verification'
    
    def add_arguments(self, parser):
        # Backup selection
        parser.add_argument(
            '--backup-id',
            type=str,
            help='Test restore specific backup by ID'
        )
        
        parser.add_argument(
            '--latest',
            action='store_true',
            help='Test restore the latest backup'
        )
        
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Test restore backups from last N days (default: 1)'
        )
        
        parser.add_argument(
            '--backup-type',
            type=str,
            choices=['full', 'incremental', 'differential', 'partial'],
            help='Only test specific backup types'
        )
        
        parser.add_argument(
            '--storage-type',
            type=str,
            help='Only test specific storage types'
        )
        
        # Database configuration
        parser.add_argument(
            '--staging-db-prefix',
            type=str,
            default='test_restore_',
            help='Prefix for staging database names (default: test_restore_)'
        )
        
        parser.add_argument(
            '--staging-db-suffix',
            type=str,
            default='',
            help='Suffix for staging database names'
        )
        
        parser.add_argument(
            '--use-existing-staging',
            action='store_true',
            help='Use existing staging database instead of creating new one'
        )
        
        parser.add_argument(
            '--staging-db-name',
            type=str,
            help='Specific staging database name to use'
        )
        
        # Restore options
        parser.add_argument(
            '--restore-type',
            type=str,
            choices=['full', 'partial', 'schema-only', 'data-only'],
            default='full',
            help='Type of restore to perform (default: full)'
        )
        
        parser.add_argument(
            '--tables',
            type=str,
            help='Comma-separated list of tables to restore (for partial restore)'
        )
        
        parser.add_argument(
            '--exclude-tables',
            type=str,
            help='Comma-separated list of tables to exclude'
        )
        
        parser.add_argument(
            '--point-in-time',
            type=str,
            help='Point-in-time restore (YYYY-MM-DD HH:MM:SS)'
        )
        
        # Safety options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be restored without actually restoring'
        )
        
        parser.add_argument(
            '--skip-download',
            action='store_true',
            help='Skip backup download (use local file)'
        )
        
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only verify backup file integrity without restoring'
        )
        
        parser.add_argument(
            '--cleanup-after',
            action='store_true',
            default=True,
            help='Clean up staging database after test (default: True)'
        )
        
        parser.add_argument(
            '--keep-staging',
            action='store_true',
            help='Keep staging database for manual inspection'
        )
        
        # Validation options
        parser.add_argument(
            '--validate-data',
            action='store_true',
            help='Validate restored data integrity'
        )
        
        parser.add_argument(
            '--check-tables',
            type=str,
            help='Comma-separated list of tables to check after restore'
        )
        
        parser.add_argument(
            '--row-count-threshold',
            type=int,
            default=0,
            help='Minimum row count threshold for validation'
        )
        
        # Output options
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json', 'csv'],
            default='table',
            help='Output format (default: table)'
        )
        
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress verbose output'
        )
        
        parser.add_argument(
            '--log-file',
            type=str,
            help='Log test restore results to file'
        )
        
        parser.add_argument(
            '--create-alerts',
            action='store_true',
            help='Create alerts for failed test restores'
        )
        
        parser.add_argument(
            '--parallel',
            type=int,
            default=1,
            help='Number of parallel test restores'
        )
        
        # Performance options
        parser.add_argument(
            '--timeout',
            type=int,
            default=3600,
            help='Test restore timeout in seconds (default: 3600)'
        )
        
        parser.add_argument(
            '--max-size',
            type=str,
            help='Maximum backup size to test restore (e.g., 1GB, 500MB)'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        try:
            # Setup logging
            self._setup_logging(options)
            
            # Get backups to test
            backups = self._get_backups_to_test(options)
            
            if not backups:
                self.stdout.write(self.style.WARNING('No backups found for test restore'))
                return
            
            self.stdout.write(f"Found {len(backups)} backups to test restore")
            
            # Perform test restores
            results = self._test_restore_backups(backups, options)
            
            # Generate report
            self._generate_report(results, options)
            
            # Create alerts if requested
            if options.get('create_alerts'):
                self._create_test_restore_alerts(results, options)
            
            # Final summary
            self._print_summary(results)
            
        except KeyboardInterrupt:
            self.stderr.write(self.style.ERROR('Test restore interrupted by user'))
            sys.exit(1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Test restore failed: {str(e)}'))
            if options.get('verbose'):
                import traceback
                self.stderr.write(traceback.format_exc())
            sys.exit(1)
    
    def _setup_logging(self, options):
        """Setup logging configuration"""
        log_level = logging.DEBUG if options.get('verbose') else logging.INFO
        
        if options.get('log_file'):
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(options['log_file']),
                    logging.StreamHandler()
                ]
            )
        else:
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    
    def _get_backups_to_test(self, options) -> List[Backup]:
        """Get list of backups to test restore"""
        queryset = Backup.objects.filter(status='completed')
        
        # Filter by backup ID
        if options.get('backup_id'):
            queryset = queryset.filter(backup_id=options['backup_id'])
        elif options.get('latest'):
            queryset = queryset.order_by('-created_at')[:1]
        else:
            # Filter by date range
            days = options.get('days', 1)
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff_date)
        
        # Apply filters
        if options.get('backup_type'):
            queryset = queryset.filter(backup_type=options['backup_type'])
        
        if options.get('storage_type'):
            queryset = queryset.filter(storage_type=options['storage_type'])
        
        if options.get('max_size'):
            max_bytes = self._parse_size_string(options['max_size'])
            if max_bytes:
                queryset = queryset.filter(file_size__lte=max_bytes)
        
        return list(queryset.order_by('-created_at'))
    
    def _parse_size_string(self, size_str):
        """Parse size string like '1GB', '500MB' to bytes"""
        size_str = size_str.upper().strip()
        
        if size_str.endswith('TB'):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024 * 1024)
        elif size_str.endswith('GB'):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
        elif size_str.endswith('MB'):
            return int(float(size_str[:-2]) * 1024 * 1024)
        elif size_str.endswith('KB'):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith('B'):
            return int(float(size_str[:-1]))
        else:
            return int(size_str)
    
    def _test_restore_backups(self, backups: List[Backup], options) -> List[Dict]:
        """Perform test restore operations"""
        results = []
        parallel = options.get('parallel', 1)
        
        if parallel > 1:
            # Parallel test restores
            results = self._test_restore_backups_parallel(backups, options)
        else:
            # Sequential test restores
            for backup in backups:
                result = self._test_single_restore(backup, options)
                results.append(result)
                
                if not options.get('quiet'):
                    status = "✓" if result['success'] else "✗"
                    self.stdout.write(f"{status} {backup.name} - {result['message']}")
        
        return results
    
    def _test_single_restore(self, backup: Backup, options) -> Dict:
        """Test restore a single backup"""
        result = {
            'backup_id': str(backup.backup_id),
            'backup_name': backup.name,
            'backup_type': backup.backup_type,
            'storage_type': backup.storage_type,
            'file_size': backup.file_size,
            'created_at': backup.created_at.isoformat(),
            'success': False,
            'message': '',
            'staging_db': None,
            'restore_time': 0,
            'validation_results': {},
            'error': None
        }
        
        start_time = timezone.now()
        staging_db_name = None
        
        try:
            # Generate staging database name
            if options.get('staging_db_name'):
                staging_db_name = options['staging_db_name']
            else:
                prefix = options.get('staging_db_prefix', 'test_restore_')
                suffix = options.get('staging_db_suffix', '')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                staging_db_name = f"{prefix}{backup.backup_id.replace('-', '')}{suffix}_{timestamp}"
            
            result['staging_db'] = staging_db_name
            
            if options.get('dry_run'):
                result['success'] = True
                result['message'] = 'Would test restore (dry run)'
                return result
            
            if options.get('verify_only'):
                # Only verify backup file integrity
                success = self._verify_backup_integrity(backup, options)
                result['success'] = success
                result['message'] = 'Backup integrity verified' if success else 'Backup integrity check failed'
                return result
            
            # Create staging database
            if not options.get('use_existing_staging'):
                self._create_staging_database(staging_db_name, backup)
            
            # Download and prepare backup
            backup_file_path = self._prepare_backup_file(backup, options)
            
            # Perform test restore
            restore_success = self._perform_test_restore(
                backup, backup_file_path, staging_db_name, options
            )
            
            result['success'] = restore_success
            
            if restore_success:
                # Validate restored data if requested
                if options.get('validate_data'):
                    validation_results = self._validate_restored_data(
                        staging_db_name, backup, options
                    )
                    result['validation_results'] = validation_results
                
                result['message'] = 'Test restore completed successfully'
            else:
                result['message'] = 'Test restore failed'
            
        except Exception as e:
            error_msg = str(e)
            result['error'] = error_msg
            result['message'] = f'Test restore error: {error_msg}'
            logger.error(f"Test restore failed for {backup.name}: {error_msg}")
        
        finally:
            # Calculate restore time
            end_time = timezone.now()
            result['restore_time'] = (end_time - start_time).total_seconds()
            
            # Clean up staging database if requested
            if staging_db_name and options.get('cleanup_after', True) and not options.get('keep_staging'):
                try:
                    self._cleanup_staging_database(staging_db_name, backup)
                except Exception as e:
                    logger.error(f"Failed to cleanup staging database {staging_db_name}: {str(e)}")
        
        return result
    
    def _verify_backup_integrity(self, backup: Backup, options) -> bool:
        """Verify backup file integrity without restoring"""
        try:
            # Get storage service
            storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
            
            # Check if backup exists
            if not storage_service.backup_exists(backup):
                return False
            
            # Download backup to temp location for verification
            with tempfile.NamedTemporaryFile() as temp_file:
                if hasattr(storage_service, 'download_backup'):
                    storage_service.download_backup(backup.backup_file.name, temp_file.name)
                else:
                    # Alternative download method
                    self._download_backup_file(backup, temp_file.name, options)
                
                # Verify file integrity
                if backup.file_hash:
                    import hashlib
                    sha256 = hashlib.sha256()
                    with open(temp_file.name, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            sha256.update(chunk)
                    
                    calculated_hash = sha256.hexdigest()
                    return calculated_hash == backup.file_hash
            
            return True
            
        except Exception as e:
            logger.error(f"Backup integrity verification failed: {str(e)}")
            return False
    
    def _create_staging_database(self, staging_db_name: str, backup: Backup):
        """Create staging database"""
        db_config = settings.DATABASES['default']
        db_engine = db_config['ENGINE']
        
        if 'postgresql' in db_engine:
            self._create_postgresql_database(staging_db_name, db_config)
        elif 'mysql' in db_engine:
            self._create_mysql_database(staging_db_name, db_config)
        elif 'sqlite' in db_engine:
            self._create_sqliteDatabase(staging_db_name, db_config)
        else:
            raise Exception(f"Unsupported database engine: {db_engine}")
    
    def _create_postgresql_database(self, db_name: str, db_config: Dict):
        """Create PostgreSQL staging database"""
        import subprocess
        
        cmd = [
            'createdb',
            '-h', db_config.get('HOST', 'localhost'),
            '-p', str(db_config.get('PORT', '5432')),
            '-U', db_config.get('USER', 'postgres'),
            db_name
        ]
        
        env = os.environ.copy()
        if 'PASSWORD' in db_config:
            env['PGPASSWORD'] = db_config['PASSWORD']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to create PostgreSQL database: {result.stderr}")
    
    def _create_mysql_database(self, db_name: str, db_config: Dict):
        """Create MySQL staging database"""
        import subprocess
        
        cmd = [
            'mysql',
            '-h', db_config.get('HOST', 'localhost'),
            '-P', str(db_config.get('PORT', '3306')),
            '-u', db_config.get('USER', 'root'),
            f"-p{db_config.get('PASSWORD', '')}",
            '-e', f"CREATE DATABASE {db_name}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to create MySQL database: {result.stderr}")
    
    def _create_sqliteDatabase(self, db_name: str, db_config: Dict):
        """Create SQLite staging database"""
        db_path = os.path.join(os.path.dirname(db_config['NAME']), f"{db_name}.sqlite3")
        
        # Create empty SQLite database
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.close()
    
    def _prepare_backup_file(self, backup: Backup, options) -> str:
        """Download and prepare backup file"""
        if options.get('skip_download'):
            # Use existing local file
            return backup.backup_file.path
        
        # Download to temporary location
        temp_dir = tempfile.mkdtemp()
        backup_filename = f"test_restore_{backup.backup_id}.sql"
        backup_path = os.path.join(temp_dir, backup_filename)
        
        # Get storage service and download
        storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
        
        if hasattr(storage_service, 'download_backup'):
            storage_service.download_backup(backup.backup_file.name, backup_path)
        else:
            # Alternative download method
            self._download_backup_file(backup, backup_path, options)
        
        # Decrypt if needed
        if backup.encryption_enabled and backup.encryption_key:
            backup_path = self._decrypt_backup_file(backup_path, backup.encryption_key)
        
        # Decompress if needed
        if backup.compression_enabled and backup_path.endswith('.zip'):
            backup_path = self._extract_backup_file(backup_path)
        
        return backup_path
    
    def _download_backup_file(self, backup: Backup, local_path: str, options: Dict):
        """Download backup file using storage service"""
        storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
        
        if hasattr(storage_service, 'get_backup_file'):
            backup_file = storage_service.get_backup_file(backup)
            with open(local_path, 'wb') as f:
                for chunk in backup_file.chunks():
                    f.write(chunk)
        else:
            raise Exception("Storage service does not support file download")
    
    def _decrypt_backup_file(self, file_path: str, encryption_key: str) -> str:
        """Decrypt backup file"""
        from cryptography.fernet import Fernet
        
        cipher = Fernet(encryption_key.encode())
        
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = cipher.decrypt(encrypted_data)
        
        decrypted_path = file_path.replace('.enc', '')
        with open(decrypted_path, 'wb') as f:
            f.write(decrypted_data)
        
        os.remove(file_path)
        return decrypted_path
    
    def _extract_backup_file(self, file_path: str) -> str:
        """Extract compressed backup file"""
        import zipfile
        
        extract_dir = os.path.dirname(file_path)
        
        with zipfile.ZipFile(file_path, 'r') as zipf:
            zipf.extractall(extract_dir)
        
        # Find the extracted SQL file
        extracted_files = [f for f in os.listdir(extract_dir) if f.endswith('.sql')]
        if extracted_files:
            extracted_path = os.path.join(extract_dir, extracted_files[0])
            os.remove(file_path)
            return extracted_path
        
        raise Exception("No SQL file found in extracted archive")
    
    def _perform_test_restore(self, backup: Backup, backup_file_path: str, 
                            staging_db_name: str, options: Dict) -> bool:
        """Perform the actual test restore"""
        db_service = DatabaseBackupService()
        
        # Create temporary backup instance for restore
        temp_backup = Backup(
            backup_id=backup.backup_id,
            name=backup.name,
            backup_file=backup_file_path,
            database_name=staging_db_name,
            storage_type=backup.storage_type,
            encryption_enabled=backup.encryption_enabled,
            encryption_key=backup.encryption_key
        )
        
        # Perform restore
        try:
            restore_result = db_service.restore_backup(temp_backup)
            return restore_result
        except Exception as e:
            logger.error(f"Test restore failed: {str(e)}")
            return False
    
    def _validate_restored_data(self, staging_db_name: str, backup: Backup, options: Dict) -> Dict:
        """Validate restored data integrity"""
        validation_results = {
            'tables_checked': 0,
            'total_rows': 0,
            'invalid_tables': [],
            'validation_passed': True
        }
        
        try:
            # Get tables to check
            check_tables = options.get('check_tables')
            if check_tables:
                tables = [t.strip() for t in check_tables.split(',')]
            else:
                tables = self._get_database_tables(staging_db_name)
            
            # Check each table
            for table in tables:
                row_count = self._get_table_row_count(staging_db_name, table)
                validation_results['total_rows'] += row_count
                validation_results['tables_checked'] += 1
                
                # Check row count threshold
                threshold = options.get('row_count_threshold', 0)
                if row_count < threshold:
                    validation_results['invalid_tables'].append({
                        'table': table,
                        'issue': f'Row count {row_count} below threshold {threshold}'
                    })
                    validation_results['validation_passed'] = False
            
        except Exception as e:
            validation_results['error'] = str(e)
            validation_results['validation_passed'] = False
        
        return validation_results
    
    def _get_database_tables(self, db_name: str) -> List[str]:
        """Get list of tables in database"""
        db_config = settings.DATABASES['default']
        db_engine = db_config['ENGINE']
        
        if 'postgresql' in db_engine:
            return self._get_postgresql_tables(db_name, db_config)
        elif 'mysql' in db_engine:
            return self._get_mysql_tables(db_name, db_config)
        elif 'sqlite' in db_engine:
            return self._get_sqlite_tables(db_name, db_config)
        else:
            return []
    
    def _get_postgresql_tables(self, db_name: str, db_config: Dict) -> List[str]:
        """Get PostgreSQL tables"""
        import subprocess
        
        cmd = [
            'psql',
            '-h', db_config.get('HOST', 'localhost'),
            '-p', str(db_config.get('PORT', '5432')),
            '-U', db_config.get('USER', 'postgres'),
            '-d', db_name,
            '-t', '-c', "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ]
        
        env = os.environ.copy()
        if 'PASSWORD' in db_config:
            env['PGPASSWORD'] = db_config['PASSWORD']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.split('\n') if line.strip()]
        
        return []
    
    def _get_mysql_tables(self, db_name: str, db_config: Dict) -> List[str]:
        """Get MySQL tables"""
        import subprocess
        
        cmd = [
            'mysql',
            '-h', db_config.get('HOST', 'localhost'),
            '-P', str(db_config.get('PORT', '3306')),
            '-u', db_config.get('USER', 'root'),
            f"-p{db_config.get('PASSWORD', '')}",
            db_name,
            '-e', 'SHOW TABLES'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')[1:]  # Skip header
            return [line.split('\t')[0] for line in lines if line.strip()]
        
        return []
    
    def _get_sqlite_tables(self, db_name: str, db_config: Dict) -> List[str]:
        """Get SQLite tables"""
        import sqlite3
        
        db_path = os.path.join(os.path.dirname(db_config['NAME']), f"{db_name}.sqlite3")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return tables
    
    def _get_table_row_count(self, db_name: str, table: str) -> int:
        """Get row count for a table"""
        db_config = settings.DATABASES['default']
        db_engine = db_config['ENGINE']
        
        if 'postgresql' in db_engine:
            return self._get_postgresql_row_count(db_name, table, db_config)
        elif 'mysql' in db_engine:
            return self._get_mysql_row_count(db_name, table, db_config)
        elif 'sqlite' in db_engine:
            return self._get_sqlite_row_count(db_name, table, db_config)
        else:
            return 0
    
    def _get_postgresql_row_count(self, db_name: str, table: str, db_config: Dict) -> int:
        """Get PostgreSQL table row count"""
        import subprocess
        
        cmd = [
            'psql',
            '-h', db_config.get('HOST', 'localhost'),
            '-p', str(db_config.get('PORT', '5432')),
            '-U', db_config.get('USER', 'postgres'),
            '-d', db_name,
            '-t', '-c', f"SELECT COUNT(*) FROM {table}"
        ]
        
        env = os.environ.copy()
        if 'PASSWORD' in db_config:
            env['PGPASSWORD'] = db_config['PASSWORD']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            return int(result.stdout.strip())
        
        return 0
    
    def _get_mysql_row_count(self, db_name: str, table: str, db_config: Dict) -> int:
        """Get MySQL table row count"""
        import subprocess
        
        cmd = [
            'mysql',
            '-h', db_config.get('HOST', 'localhost'),
            '-P', str(db_config.get('PORT', '3306')),
            '-u', db_config.get('USER', 'root'),
            f"-p{db_config.get('PASSWORD', '')}",
            db_name,
            '-e', f'SELECT COUNT(*) FROM {table}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            if len(lines) > 1:
                return int(lines[1].strip())
        
        return 0
    
    def _get_sqlite_row_count(self, db_name: str, table: str, db_config: Dict) -> int:
        """Get SQLite table row count"""
        import sqlite3
        
        db_path = os.path.join(os.path.dirname(db_config['NAME']), f"{db_name}.sqlite3")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def _cleanup_staging_database(self, staging_db_name: str, backup: Backup):
        """Clean up staging database"""
        db_config = settings.DATABASES['default']
        db_engine = db_config['ENGINE']
        
        if 'postgresql' in db_engine:
            self._drop_postgresql_database(staging_db_name, db_config)
        elif 'mysql' in db_engine:
            self._drop_mysql_database(staging_db_name, db_config)
        elif 'sqlite' in db_engine:
            self._drop_sqliteDatabase(staging_db_name, db_config)
    
    def _drop_postgresql_database(self, db_name: str, db_config: Dict):
        """Drop PostgreSQL staging database"""
        import subprocess
        
        cmd = [
            'dropdb',
            '-h', db_config.get('HOST', 'localhost'),
            '-p', str(db_config.get('PORT', '5432')),
            '-U', db_config.get('USER', 'postgres'),
            db_name
        ]
        
        env = os.environ.copy()
        if 'PASSWORD' in db_config:
            env['PGPASSWORD'] = db_config['PASSWORD']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning(f"Failed to drop PostgreSQL database: {result.stderr}")
    
    def _drop_mysql_database(self, db_name: str, db_config: Dict):
        """Drop MySQL staging database"""
        import subprocess
        
        cmd = [
            'mysql',
            '-h', db_config.get('HOST', 'localhost'),
            '-P', str(db_config.get('PORT', '3306')),
            '-u', db_config.get('USER', 'root'),
            f"-p{db_config.get('PASSWORD', '')}",
            '-e', f"DROP DATABASE {db_name}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning(f"Failed to drop MySQL database: {result.stderr}")
    
    def _drop_sqliteDatabase(self, db_name: str, db_config: Dict):
        """Drop SQLite staging database"""
        db_path = os.path.join(os.path.dirname(db_config['NAME']), f"{db_name}.sqlite3")
        
        if os.path.exists(db_path):
            os.remove(db_path)
    
    def _test_restore_backups_parallel(self, backups: List[Backup], options: Dict) -> List[Dict]:
        """Test restore backups in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        parallel = options.get('parallel', 1)
        
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all test restore tasks
            future_to_backup = {
                executor.submit(self._test_single_restore, backup, options): backup
                for backup in backups
            }
            
            # Collect results
            for future in as_completed(future_to_backup):
                backup = future_to_backup[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if not options.get('quiet'):
                        status = "✓" if result['success'] else "✗"
                        self.stdout.write(f"{status} {backup.name} - {result['message']}")
                        
                except Exception as e:
                    error_result = {
                        'backup_id': str(backup.backup_id),
                        'backup_name': backup.name,
                        'success': False,
                        'message': f'Test restore error: {str(e)}',
                        'error': str(e)
                    }
                    results.append(error_result)
        
        return results
    
    def _generate_report(self, results: List[Dict], options: Dict):
        """Generate test restore report"""
        format_type = options.get('format', 'table')
        
        if format_type == 'json':
            self._generate_json_report(results)
        elif format_type == 'csv':
            self._generate_csv_report(results)
        else:
            self._generate_table_report(results)
    
    def _generate_table_report(self, results: List[Dict]):
        """Generate table format report"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write("TEST RESTORE REPORT")
        self.stdout.write("="*80)
        
        # Summary
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = total - successful
        
        self.stdout.write(f"Total: {total}, Successful: {successful}, Failed: {failed}")
        self.stdout.write("-" * 80)
        
        # Detailed results
        for result in results:
            status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
            restore_time = f"{result['restore_time']:.1f}s" if result['restore_time'] else "N/A"
            staging_db = result.get('staging_db', 'N/A')[:20]
            
            self.stdout.write(f"{status} | {result['backup_name'][:25]:25} | {restore_time[:10]:10} | {staging_db[:20]:20} | {result['message'][:30]:30}")
    
    def _generate_json_report(self, results: List[Dict]):
        """Generate JSON format report"""
        total_time = sum(r['restore_time'] or 0 for r in results)
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'total_backups': len(results),
            'successful_backups': sum(1 for r in results if r['success']),
            'failed_backups': sum(1 for r in results if not r['success']),
            'total_restore_time': total_time,
            'results': results
        }
        
        self.stdout.write(json.dumps(report, indent=2))
    
    def _generate_csv_report(self, results: List[Dict]):
        """Generate CSV format report"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'backup_id', 'backup_name', 'backup_type', 'storage_type',
            'file_size', 'created_at', 'success', 'message', 'staging_db', 'restore_time'
        ])
        
        # Data
        for result in results:
            writer.writerow([
                result['backup_id'],
                result['backup_name'],
                result['backup_type'],
                result['storage_type'],
                result['file_size'],
                result['created_at'],
                result['success'],
                result['message'],
                result.get('staging_db', ''),
                result.get('restore_time', '')
            ])
        
        self.stdout.write(output.getvalue())
    
    def _create_test_restore_alerts(self, results: List[Dict], options: Dict):
        """Create alerts for failed test restores"""
        failed_results = [r for r in results if not r['success']]
        
        for result in failed_results:
            try:
                backup = Backup.objects.get(backup_id=result['backup_id'])
                
                BackupAlert.create_alert(
                    alert_type='verification_failed',
                    message=f"Test restore failed: {result['message']}",
                    backup=backup,
                    severity='high',
                    metadata={
                        'test_restore': True,
                        'staging_db': result.get('staging_db'),
                        'restore_time': result.get('restore_time'),
                        'error': result.get('error')
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to create test restore alert for {result['backup_name']}: {str(e)}")
        
        if failed_results:
            self.stdout.write(f"Created {len(failed_results)} alerts for failed test restores")
    
    def _print_summary(self, results: List[Dict]):
        """Print final test restore summary"""
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = total - successful
        total_time = sum(r['restore_time'] or 0 for r in results)
        success_rate = (successful / total * 100) if total > 0 else 0
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("TEST RESTORE SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Total Backups: {total}")
        self.stdout.write(f"Successful: {successful} ({success_rate:.1f}%)")
        self.stdout.write(f"Failed: {failed}")
        self.stdout.write(f"Total Time: {total_time:.1f}s")
        self.stdout.write(f"Average Time: {total_time/total:.1f}s" if total > 0 else "Average Time: 0s")
        self.stdout.write("="*50)
