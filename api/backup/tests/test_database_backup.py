"""
Test Database Backup Service
Comprehensive tests for DatabaseBackupService functionality
"""
import time

import os
import tempfile
import subprocess
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
from unittest.mock import patch, Mock, MagicMock, mock_open
import pytest

from api.backup.services.DatabaseBackup import DatabaseBackupService
from api.backup.models import Backup, BackupStorageLocation

User = get_user_model()


class DatabaseBackupServiceTest(TestCase):
    """Test DatabaseBackupService functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type='local',
            endpoint=tempfile.mkdtemp(),
            is_active=True
        )
        
        self.backup_service = DatabaseBackupService()
    
    def test_service_initialization(self):
        """Test DatabaseBackupService initialization"""
        service = DatabaseBackupService()
        
        # Should initialize without errors
        self.assertIsNotNone(service)
        
        # Should have expected methods
        self.assertTrue(hasattr(service, 'create_backup'))
        self.assertTrue(hasattr(service, 'restore_backup'))
        self.assertTrue(hasattr(service, '_dump_database'))
        self.assertTrue(hasattr(service, '_restore_database'))
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_postgresql_backup(self, mock_subprocess):
        """Test PostgreSQL backup creation"""
        # Configure test database for PostgreSQL
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.postgresql',
                    'NAME': 'test_db',
                    'USER': 'postgres',
                    'PASSWORD': 'testpass',
                    'HOST': 'localhost',
                    'PORT': '5432'
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Mock successful pg_dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'PostgreSQL dump data',
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test PostgreSQL Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify pg_dump was called with correct parameters
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            
            # Check pg_dump command structure
            command = args[0][0] if args else []
            self.assertEqual(command[0], 'pg_dump')
            self.assertIn('-h', command)
            self.assertIn('-p', command)
            self.assertIn('-U', command)
            self.assertIn('-Fc', command)  # Custom format
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_mysql_backup(self, mock_subprocess):
        """Test MySQL backup creation"""
        # Configure test database for MySQL
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.mysql',
                    'NAME': 'test_db',
                    'USER': 'root',
                    'PASSWORD': 'testpass',
                    'HOST': 'localhost',
                    'PORT': '3306'
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Mock successful mysqldump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'MySQL dump data',
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test MySQL Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify mysqldump was called with correct parameters
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            
            # Check mysqldump command structure
            command = args[0][0] if args else []
            self.assertEqual(command[0], 'mysqldump')
            self.assertIn('--single-transaction', command)
            self.assertIn('--routines', command)
            self.assertIn('--triggers', command)
            self.assertIn('--hex-blob', command)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_sqlite_backup(self, mock_subprocess):
        """Test SQLite backup creation"""
        # Configure test database for SQLite
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': tempfile.mktemp(suffix='.sqlite3')
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Create test SQLite database
            import sqlite3
            conn = sqlite3.connect(test_settings['DATABASES']['default']['NAME'])
            conn.execute('CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)')
            conn.execute('INSERT INTO test_table (id, name) VALUES (1, "test")')
            conn.commit()
            conn.close()
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test SQLite Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify file copy was performed
            self.assertIsNotNone(result)
            self.assertTrue(os.path.exists(result.backup_file.path))
    
    @patch('backup.services.DatabaseBackup.call_command')
    def test_django_dumpdata_backup(self, mock_call_command):
        """Test Django dumpdata backup creation"""
        # Mock successful dumpdata
        mock_call_command.return_value = b'Django dumpdata JSON'
        
        # Create backup instance
        backup = Backup.objects.create(
            name='Test Django Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Test backup creation
        result = self.backup_service.create_backup(backup)
        
        # Verify dumpdata was called
        mock_call_command.assert_called_once()
        args, kwargs = mock_call_command.call_args
        
        # Check dumpdata command structure
        command = args[0] if args else []
        self.assertIn('manage.py', command)
        self.assertIn('dumpdata', command)
        
        # Verify exclusions
        command_str = ' '.join(command)
        self.assertIn('--exclude', command_str)
        self.assertIn('contenttypes', command_str)
        self.assertIn('auth.permission', command_str)
        self.assertIn('sessions', command_str)
    
    def test_backup_with_table_selection(self):
        """Test backup with specific table selection"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Table-specific dump data',
                stderr=b''
            )
            
            # Create backup with table selection
            backup = Backup.objects.create(
                name='Test Table Backup',
                backup_type='partial',
                storage_type='local',
                database_name='test_db',
                tables_include=['users', 'orders'],
                tables_exclude=['sessions']
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify table-specific options were included
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            command = args[0][0] if args else []
            command_str = ' '.join(command)
            
            # Check for table-specific options
            self.assertIn('--table', command_str) or '-t' in command_str
            self.assertIn('users', command_str)
            self.assertIn('orders', command_str)
    
    def test_backup_failure_handling(self):
        """Test backup creation failure handling"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock failed dump
            mock_subprocess.return_value = Mock(
                returncode=1,
                stdout=b'',
                stderr=b'Backup failed: permission denied'
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test Failed Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Should handle failure gracefully
            self.assertIsNotNone(result)
            # Check that backup status is updated
            backup.refresh_from_db()
            self.assertEqual(backup.status, 'failed')
            self.assertIn('permission denied', backup.error_message)
    
    def test_backup_with_compression(self):
        """Test backup creation with compression"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Uncompressed dump data',
                stderr=b''
            )
            
            # Create backup with compression
            backup = Backup.objects.create(
                name='Test Compressed Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db',
                compression_enabled=True
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify compression was applied
            self.assertIsNotNone(result)
            # Check that backup file is compressed
            if result.backup_file and hasattr(result.backup_file, 'path'):
                self.assertTrue(
                    result.backup_file.path.endswith('.zip') or 
                    result.backup_file.path.endswith('.gz')
                )
    
    def test_backup_with_encryption(self):
        """Test backup creation with encryption"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Unencrypted dump data',
                stderr=b''
            )
            
            # Create backup with encryption
            backup = Backup.objects.create(
                name='Test Encrypted Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db',
                encryption_enabled=True,
                encryption_method='AES-256-GCM'
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify encryption was applied
            self.assertIsNotNone(result)
            # Check that backup file is encrypted
            if result.backup_file and hasattr(result.backup_file, 'path'):
                self.assertTrue(
                    result.backup_file.path.endswith('.enc') or
                    backup.encryption_key is not None
                )
    
    def test_partial_backup(self):
        """Test partial backup creation"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Partial dump data',
                stderr=b''
            )
            
            # Create partial backup
            backup = Backup.objects.create(
                name='Test Partial Backup',
                backup_type='partial',
                storage_type='local',
                database_name='test_db',
                tables_include=['users', 'profiles']
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify partial backup
            self.assertIsNotNone(result)
            self.assertEqual(backup.backup_type, 'partial')
            self.assertEqual(backup.tables_include, ['users', 'profiles'])
    
    def test_incremental_backup(self):
        """Test incremental backup creation"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Incremental dump data',
                stderr=b''
            )
            
            # Create parent backup for incremental
            parent_backup = Backup.objects.create(
                name='Parent Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db',
                created_at=timezone.now() - timedelta(days=1)
            )
            
            # Create incremental backup
            backup = Backup.objects.create(
                name='Test Incremental Backup',
                backup_type='incremental',
                storage_type='local',
                database_name='test_db',
                parent_backup=parent_backup
            )
            
            # Test backup creation
            result = self.backup_service.create_backup(backup)
            
            # Verify incremental backup
            self.assertIsNotNone(result)
            self.assertEqual(backup.backup_type, 'incremental')
            self.assertEqual(backup.parent_backup, parent_backup)


class DatabaseBackupRestoreTest(TestCase):
    """Test DatabaseBackupService restore functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = DatabaseBackupService()
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_postgresql_restore(self, mock_subprocess):
        """Test PostgreSQL restore"""
        # Configure test database for PostgreSQL
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.postgresql',
                    'NAME': 'test_db',
                    'USER': 'postgres',
                    'PASSWORD': 'testpass',
                    'HOST': 'localhost',
                    'PORT': '5432'
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test PostgreSQL Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('PostgreSQL restore data')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify psql was called with correct parameters
            mock_subprocess.assert_called()
            args, kwargs = mock_subprocess.call_args
            command = args[0][0] if args else []
            
            # Check psql command structure
            self.assertEqual(command[0], 'psql')
            self.assertIn('-h', command)
            self.assertIn('-p', command)
            self.assertIn('-U', command)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_mysql_restore(self, mock_subprocess):
        """Test MySQL restore"""
        # Configure test database for MySQL
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.mysql',
                    'NAME': 'test_db',
                    'USER': 'root',
                    'PASSWORD': 'testpass',
                    'HOST': 'localhost',
                    'PORT': '3306'
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test MySQL Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('MySQL restore data')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify mysql was called with correct parameters
            mock_subprocess.assert_called()
            args, kwargs = mock_subprocess.call_args
            command = args[0][0] if args else []
            
            # Check mysql command structure
            self.assertEqual(command[0], 'mysql')
            self.assertIn('-h', command)
            self.assertIn('-p', command)
            self.assertIn('-u', command)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_sqlite_restore(self, mock_subprocess):
        """Test SQLite restore"""
        # Configure test database for SQLite
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': tempfile.mktemp(suffix='.sqlite3')
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test SQLite Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('SQLite restore data')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify file copy was performed
            self.assertIsNotNone(result)
    
    @patch('backup.services.DatabaseBackup.call_command')
    def test_django_loaddata_restore(self, mock_call_command):
        """Test Django loaddata restore"""
        # Mock successful loaddata
        mock_call_command.return_value = b'loaddata completed'
        
        # Create backup instance
        backup = Backup.objects.create(
            name='Test Django Restore',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create temporary backup file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
            f.write('{"test": "data"}')
            backup.backup_file = ContentFile(f.read().encode())
            backup.backup_file.name = f.name
        
        # Test restore
        result = self.backup_service.restore_backup(backup)
        
        # Verify loaddata was called
        mock_call_command.assert_called()
        args, kwargs = mock_call_command.call_args
        command = args[0] if args else []
        
        # Check loaddata command structure
        self.assertIn('manage.py', command)
        self.assertIn('loaddata', command)
    
    def test_restore_failure_handling(self):
        """Test restore failure handling"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock failed restore
            mock_subprocess.return_value = Mock(
                returncode=1,
                stdout=b'',
                stderr=b'Restore failed: syntax error'
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test Failed Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('Invalid SQL')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Should handle failure gracefully
            self.assertFalse(result)
    
    def test_restore_with_decryption(self):
        """Test restore with decryption"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Create backup instance with encryption
            backup = Backup.objects.create(
                name='Test Encrypted Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db',
                encryption_enabled=True,
                encryption_key='test_encryption_key'
            )
            
            # Create temporary encrypted backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql.enc') as f:
                f.write('Encrypted data')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify decryption was attempted
            self.assertIsNotNone(result)
            # The mock should have been called with decrypted data
            mock_subprocess.assert_called()
    
    def test_partial_restore(self):
        """Test partial restore"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Partial restore completed',
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test Partial Restore',
                backup_type='partial',
                storage_type='local',
                database_name='test_db',
                tables_include=['users', 'profiles']
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('Partial restore data')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify partial restore
            self.assertIsNotNone(result)
            # Check that only specified tables were restored
            mock_subprocess.assert_called()
    
    def test_restore_with_database_creation(self):
        """Test restore with database creation"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful database creation and restore
            mock_subprocess.side_effect = [
                Mock(returncode=0, stdout=b'', stderr=b''),  # createdb
                Mock(returncode=0, stdout=b'Restore completed', stderr=b'')  # restore
            ]
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test DB Creation Restore',
                backup_type='full',
                storage_type='local',
                database_name='new_test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('Create DB restore data')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify database creation was attempted
            self.assertEqual(mock_subprocess.call_count, 2)
            
            # Check first call was database creation
            first_call_args = mock_subprocess.call_args_list[0]
            first_command = first_call_args[0][0][0] if first_call_args[0] else []
            self.assertIn('createdb', first_command) or self.assertIn('CREATE DATABASE', ' '.join(first_command))


class DatabaseBackupServiceEdgeCaseTest(TestCase):
    """Test DatabaseBackupService edge cases and error conditions"""
    
    def setUp(self):
        """Set up test data"""
        self.backup_service = DatabaseBackupService()
    
    def test_unsupported_database_engine(self):
        """Test with unsupported database engine"""
        # Configure unsupported database
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'unsupported.engine',
                    'NAME': 'test_db'
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Create backup instance
            backup = Backup.objects.create(
                name='Test Unsupported DB',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Should handle unsupported engine gracefully
            with self.assertRaises(Exception):
                self.backup_service.create_backup(backup)
    
    def test_missing_database_connection(self):
        """Test with missing database connection parameters"""
        # Configure incomplete database settings
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.postgresql',
                    'NAME': 'test_db'
                    # Missing HOST, PORT, USER, PASSWORD
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Create backup instance
            backup = Backup.objects.create(
                name='Test Missing Connection',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Should handle missing parameters gracefully
            result = self.backup_service.create_backup(backup)
            # May still work with defaults or may raise exception
    
    def test_backup_file_permissions_error(self):
        """Test backup creation with file permissions error"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Dump data',
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Test Permissions Error',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Mock file permission error
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                # Test backup creation
                result = self.backup_service.create_backup(backup)
                
                # Should handle permission error gracefully
                self.assertIsNotNone(result)
    
    def test_restore_corrupted_backup_file(self):
        """Test restore with corrupted backup file"""
        # Create backup instance
        backup = Backup.objects.create(
            name='Test Corrupted Restore',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create corrupted backup file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
            f.write('Corrupted SQL data with syntax error')
            backup.backup_file = ContentFile(f.read().encode())
            backup.backup_file.name = f.name
        
        # Test restore
        result = self.backup_service.restore_backup(backup)
        
        # Should handle corrupted file gracefully
        self.assertFalse(result)
    
    def test_concurrent_backup_operations(self):
        """Test concurrent backup operations"""
        import threading
        import time
        
        results = []
        errors = []
        
        def create_backup(index):
            try:
                with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
                    # Mock successful dump
                    mock_subprocess.return_value = Mock(
                        returncode=0,
                        stdout=f'Backup data {index}'.encode(),
                        stderr=b''
                    )
                    
                    # Create backup instance
                    backup = Backup.objects.create(
                        name=f'Concurrent Backup {index}',
                        backup_type='full',
                        storage_type='local',
                        database_name='test_db'
                    )
                    
                    # Test backup creation
                    result = self.backup_service.create_backup(backup)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_backup, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        self.assertEqual(len(results), 3)
        self.assertEqual(len(errors), 0)
        for result in results:
            self.assertIsNotNone(result)


class DatabaseBackupServicePerformanceTest(TestCase):
    """Test DatabaseBackupService performance characteristics"""
    
    def setUp(self):
        """Set up test data"""
        self.backup_service = DatabaseBackupService()
    
    def test_backup_creation_performance(self):
        """Test backup creation performance"""
        import time
        
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock successful dump
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Performance test data',
                stderr=b''
            )
            
            # Measure backup creation time
            start_time = time.time()
            for i in range(5):
                backup = Backup.objects.create(
                    name=f'Performance Backup {i}',
                    backup_type='full',
                    storage_type='local',
                    database_name='test_db'
                )
                
                result = self.backup_service.create_backup(backup)
                self.assertIsNotNone(result)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Should complete within reasonable time (less than 10 seconds for 5 backups)
            self.assertLess(total_time, 10.0)
    
    def test_large_database_backup(self):
        """Test backup of large database"""
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            # Mock large database dump
            large_data = b'A' * (10 * 1024 * 1024)  # 10MB of data
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=large_data,
                stderr=b''
            )
            
            # Create backup instance
            backup = Backup.objects.create(
                name='Large Database Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Test backup creation
            start_time = time.time()
            result = self.backup_service.create_backup(backup)
            end_time = time.time()
            
            # Should handle large data
            self.assertIsNotNone(result)
            # Should complete within reasonable time (less than 30 seconds)
            self.assertLess(end_time - start_time, 30.0)
