"""
Test Restore Functionality
Comprehensive tests for backup restoration operations
"""
from django.conf import settings

import os
import tempfile
import subprocess
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import transaction
from unittest.mock import patch, Mock, MagicMock, mock_open
import pytest

from api.backup.models import Backup, BackupRestoration, BackupLog
from api.backup.services.DatabaseBackup import DatabaseBackupService
from api.backup.services.factory import BackupServiceFactory
from api.backup.models import BackupStorageLocation

User = get_user_model()


class BackupRestoreTest(TestCase):
    """Test backup restoration functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.backup_service = DatabaseBackupService()
    
    def test_restoration_creation(self):
        """Test backup restoration model creation"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            initiated_by=self.user,
            status='completed'
        )
        
        self.assertEqual(str(restoration), f"Restore of {backup.name}")
        self.assertEqual(restoration.backup, backup)
        self.assertEqual(restoration.restoration_type, 'full')
        self.assertEqual(restoration.initiated_by, self.user)
        self.assertEqual(restoration.status, 'completed')
    
    def test_restoration_uuid_generation(self):
        """Test UUID generation for restoration_id"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full'
        )
        
        # Test UUID generation
        self.assertIsInstance(restoration.restoration_id, str)
        # Should be valid UUID string
        import uuid
        try:
            uuid.UUID(restoration.restoration_id)
            self.assertTrue(True)
        except ValueError:
            self.fail("restoration_id should be a valid UUID")
    
    def test_restoration_types(self):
        """Test different restoration types"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Test each restoration type
        restoration_types = ['full', 'partial', 'schema-only', 'data-only']
        
        for restoration_type in restoration_types:
            restoration = BackupRestoration.objects.create(
                backup=backup,
                restoration_type=restoration_type,
                initiated_by=self.user
            )
            
            self.assertEqual(restoration.restoration_type, restoration_type)
            self.assertEqual(str(restoration), f"Restore of {backup.name}")
    
    def test_restoration_status_flow(self):
        """Test restoration status progression"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration with initial status
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            initiated_by=self.user,
            status='pending'
        )
        
        # Test status progression
        restoration.status = 'running'
        restoration.save()
        self.assertEqual(restoration.status, 'running')
        
        restoration.status = 'completed'
        restoration.save()
        self.assertEqual(restoration.status, 'completed')
        
        restoration.status = 'failed'
        restoration.save()
        self.assertEqual(restoration.status, 'failed')
    
    def test_restoration_duration_calculation(self):
        """Test restoration duration calculation"""
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=30, seconds=45)
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration with duration
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            started_at=start_time,
            completed_at=end_time,
            status='completed'
        )
        
        # Test duration calculation
        expected_duration = (end_time - start_time).total_seconds()
        actual_duration = restoration.get_duration()
        self.assertEqual(actual_duration, expected_duration)
    
    def test_restoration_with_tables(self):
        """Test restoration with specific tables"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='partial',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration with tables
        tables_to_restore = ['users', 'orders', 'products']
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='partial',
            tables_to_restore=tables_to_restore,
            initiated_by=self.user
        )
        
        self.assertEqual(restoration.tables_to_restore, tables_to_restore)
        self.assertEqual(restoration.restoration_type, 'partial')
    
    def test_restoration_with_rollback(self):
        """Test restoration with rollback enabled"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration with rollback
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            rollback_enabled=True,
            initiated_by=self.user,
            status='completed'
        )
        
        self.assertTrue(restoration.rollback_enabled)
        
        # Test rollback functionality
        restoration.perform_rollback()
        self.assertTrue(restoration.rollback_performed)
        self.assertEqual(restoration.status, 'rolled_back')
    
    def test_restoration_verification(self):
        """Test restoration verification"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration with verification
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            verification_passed=True,
            verification_details={
                'tables_restored': 10,
                'rows_restored': 1000,
                'checksum_verified': True
            },
            initiated_by=self.user,
            status='completed'
        )
        
        self.assertTrue(restoration.verification_passed)
        self.assertIn('tables_restored', restoration.verification_details)
        self.assertEqual(restoration.verification_details['rows_restored'], 1000)
    
    def test_restoration_with_point_in_time(self):
        """Test point-in-time restoration"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create restoration with point-in-time
        restore_point = timezone.now() - timedelta(hours=2)
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            restore_point=restore_point,
            initiated_by=self.user
        )
        
        self.assertEqual(restoration.restore_point, restore_point)
        self.assertIsNotNone(restoration.restore_point)


class DatabaseRestoreServiceTest(TestCase):
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
    def test_postgresql_restore_success(self, mock_subprocess):
        """Test successful PostgreSQL restore"""
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
            # Create test backup
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
            
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify psql was called with correct parameters
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            
            # Check psql command structure
            command = args[0][0] if args else []
            self.assertEqual(command[0], 'psql')
            self.assertIn('-h', command)
            self.assertIn('-p', command)
            self.assertIn('-U', command)
            self.assertIn('-d', command)
            
            self.assertTrue(result)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_mysql_restore_success(self, mock_subprocess):
        """Test successful MySQL restore"""
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
            # Create test backup
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
            
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Verify mysql was called with correct parameters
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            
            # Check mysql command structure
            command = args[0][0] if args else []
            self.assertEqual(command[0], 'mysql')
            self.assertIn('-h', command)
            self.assertIn('-p', command)
            self.assertIn('-u', command)
            
            self.assertTrue(result)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_sqlite_restore_success(self, mock_subprocess):
        """Test successful SQLite restore"""
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
            # Create test backup
            backup = Backup.objects.create(
                name='Test SQLite Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sqlite3') as f:
                f.write('SQLite database content')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Should handle SQLite restore (file copy)
            self.assertTrue(result)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_restore_failure_handling(self, mock_subprocess):
        """Test restore failure handling"""
        # Configure test database
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
            # Create test backup
            backup = Backup.objects.create(
                name='Test Failed Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('Invalid SQL that will fail')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Mock failed restore
            mock_subprocess.return_value = Mock(
                returncode=1,
                stdout=b'',
                stderr=b'ERROR: syntax error at line 1'
            )
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Should handle failure gracefully
            self.assertFalse(result)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_partial_restore(self, mock_subprocess):
        """Test partial restore with specific tables"""
        # Configure test database
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
            # Create test backup
            backup = Backup.objects.create(
                name='Test Partial Restore',
                backup_type='partial',
                storage_type='local',
                database_name='test_db',
                tables_to_restore=['users', 'orders']
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('Partial restore data for users and orders')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Mock successful restore
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Partial restore completed',
                stderr=b''
            )
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Should handle partial restore
            self.assertTrue(result)
            
            # Verify command includes table filtering
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            command = args[0][0] if args else []
            command_str = ' '.join(command)
            
            # Check for table-specific options
            self.assertIn('--table', command_str) or '-t' in command_str
            self.assertIn('users', command_str)
            self.assertIn('orders', command_str)
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_restore_with_database_creation(self, mock_subprocess):
        """Test restore with database creation"""
        # Configure test database
        test_settings = {
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.db.backends.postgresql',
                    'NAME': 'new_test_db',
                    'USER': 'postgres',
                    'PASSWORD': 'testpass',
                    'HOST': 'localhost',
                    'PORT': '5432'
                }
            }
        }
        
        with patch.object(settings, 'DATABASES', test_settings['DATABASES']):
            # Create test backup
            backup = Backup.objects.create(
                name='Test DB Creation Restore',
                backup_type='full',
                storage_type='local',
                database_name='new_test_db'
            )
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql') as f:
                f.write('Database creation restore data')
                backup.backup_file = ContentFile(f.read().encode())
                backup.backup_file.name = f.name
            
            # Mock successful database creation and restore
            mock_subprocess.side_effect = [
                Mock(returncode=0, stdout=b'', stderr=b''),  # createdb
                Mock(returncode=0, stdout=b'Restore completed', stderr=b'')  # psql restore
            ]
            
            # Test restore
            result = self.backup_service.restore_backup(backup)
            
            # Should handle database creation
            self.assertTrue(result)
            
            # Verify both commands were called
            self.assertEqual(mock_subprocess.call_count, 2)
    
    def test_restore_with_encryption(self):
        """Test restore with encrypted backup"""
        # Create test backup with encryption
        backup = Backup.objects.create(
            name='Test Encrypted Restore',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=True,
            encryption_key='test_encryption_key',
            encryption_method='AES-256-GCM'
        )
        
        # Create encrypted backup file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql.enc') as f:
            f.write('Encrypted backup content')
            backup.backup_file = ContentFile(f.read().encode())
            backup.backup_file.name = f.name
        
        # Test restore with encryption
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            with patch('backup.services.DatabaseBackup.decrypt_file') as mock_decrypt:
                mock_decrypt.return_value = b'Decrypted backup content'
                mock_subprocess.return_value = Mock(
                    returncode=0,
                    stdout=b'Restore completed',
                    stderr=b''
                )
                
                result = self.backup_service.restore_backup(backup)
                
                # Should decrypt before restore
                mock_decrypt.assert_called_once()
                self.assertTrue(result)
    
    def test_restore_with_compression(self):
        """Test restore with compressed backup"""
        # Create test backup with compression
        backup = Backup.objects.create(
            name='Test Compressed Restore',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            compression_enabled=True,
            compression_method='gzip'
        )
        
        # Create compressed backup file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql.gz') as f:
            f.write('Compressed backup content')
            backup.backup_file = ContentFile(f.read().encode())
            backup.backup_file.name = f.name
        
        # Test restore with compression
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            with patch('backup.services.DatabaseBackup.extract_file') as mock_extract:
                mock_extract.return_value = 'decompressed_file.sql'
                mock_subprocess.return_value = Mock(
                    returncode=0,
                    stdout=b'Restore completed',
                    stderr=b''
                )
                
                result = self.backup_service.restore_backup(backup)
                
                # Should decompress before restore
                mock_extract.assert_called_once()
                self.assertTrue(result)


class RestoreIntegrationTest(TestCase):
    """Test restore integration with backup service"""
    
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
    
    @patch('backup.services.factory.BackupServiceFactory')
    @patch('backup.services.DatabaseBackup.subprocess.run')
    def test_full_restore_workflow(self, mock_factory, mock_subprocess):
        """Test complete restore workflow"""
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        # Mock successful download
        mock_storage_service.download_backup.return_value = b'Downloaded backup content'
        
        # Mock successful restore
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout=b'Restore completed',
            stderr=b''
        )
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Workflow Restore',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            storage_location=self.storage_location
        )
        
        # Test restore workflow
        from api.backup.services import BackupService
        backup_service = BackupService()
        
        restoration = backup_service.restore_backup(
            str(backup.backup_id),
            restoration_type='full',
            initiated_by=self.user
        )
        
        # Verify workflow steps
        self.assertIsNotNone(restoration)
        self.assertEqual(restoration.backup, backup)
        self.assertEqual(restoration.status, 'completed')
        self.assertTrue(restoration.success)
        
        # Verify service calls
        mock_factory.get_storage_service.assert_called_once_with('local')
        mock_storage_service.download_backup.assert_called_once()
        mock_subprocess.assert_called_once()
    
    def test_restore_with_rollback_on_failure(self):
        """Test restore with rollback on failure"""
        # Mock services
        with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
            mock_storage_service = Mock()
            mock_factory.get_storage_service.return_value = mock_storage_service
            
            # Mock successful download
            mock_storage_service.download_backup.return_value = b'Downloaded backup content'
            
            # Mock failed restore
            from api.backup.services.DatabaseBackup.subprocess.run import Mock as SubprocessMock
            mock_subprocess.return_value = SubprocessMock(
                returncode=1,
                stdout=b'',
                stderr=b'Restore failed: constraint violation'
            )
            
            # Create test backup
            backup = Backup.objects.create(
                name='Test Rollback Restore',
                backup_type='full',
                storage_type='local',
                database_name='test_db',
                storage_location=self.storage_location
            )
            
            # Test restore workflow with rollback
            from api.backup.services import BackupService
            backup_service = BackupService()
            
            restoration = backup_service.restore_backup(
                str(backup.backup_id),
                restoration_type='full',
                initiated_by=self.user,
                rollback_enabled=True
            )
            
            # Verify rollback was attempted
            self.assertIsNotNone(restoration)
            self.assertEqual(restoration.backup, backup)
            # Should be marked as failed
            self.assertEqual(restoration.status, 'failed')
            self.assertFalse(restoration.success)
    
    def test_concurrent_restorations(self):
        """Test concurrent restoration operations"""
        import threading
        import time
        
        results = []
        
        def create_restoration(index):
            # Create test backup for each thread
            backup = Backup.objects.create(
                name=f'Concurrent Restore {index}',
                backup_type='full',
                storage_type='local',
                database_name=f'test_db_{index}'
            )
            
            # Mock restore
            with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(
                    returncode=0,
                    stdout=f'Restore completed {index}'.encode(),
                    stderr=b''
                )
                
                from api.backup.services import BackupService
                backup_service = BackupService()
                
                restoration = backup_service.restore_backup(
                    str(backup.backup_id),
                    restoration_type='full'
                )
                results.append(restoration)
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_restoration, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all restorations completed
        self.assertEqual(len(results), 3)
        for restoration in results:
            self.assertIsNotNone(restoration)
    
    def test_restore_performance_metrics(self):
        """Test restore performance metrics"""
        import time
        
        # Create test backup
        backup = Backup.objects.create(
            name='Test Performance Restore',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Measure restore time
        with patch('backup.services.DatabaseBackup.subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            from api.backup.services import BackupService
            backup_service = BackupService()
            
            start_time = time.time()
            restoration = backup_service.restore_backup(
                str(backup.backup_id),
                restoration_type='full'
            )
            end_time = time.time()
            
            # Verify performance tracking
            self.assertIsNotNone(restoration)
            restore_time = end_time - start_time
            
            # Should complete within reasonable time (less than 5 seconds for mock)
            self.assertLess(restore_time, 5.0)
            
            # Duration should be recorded
            self.assertIsNotNone(restoration.started_at)
            self.assertIsNotNone(restoration.completed_at)
            self.assertGreater(
                restoration.completed_at,
                restoration.started_at
            )
