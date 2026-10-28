"""
Test Backup Service
Comprehensive tests for BackupService orchestration
"""

import uuid
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from unittest.mock import patch, MagicMock, Mock

from api.backup.services import BackupService
from api.backup.models import (
    Backup, BackupSchedule, BackupRestoration, BackupVerification,
    BackupEncryption, BackupAlert
)

User = get_user_model()


class BackupServiceTest(TestCase):
    """Test BackupService orchestration"""
    
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
        
        self.backup_service = BackupService()
    
    def test_service_initialization(self):
        """Test BackupService initialization"""
        service = BackupService()
        
        # Test that service initializes without errors
        self.assertIsNotNone(service)
        
        # Test that service has expected attributes
        self.assertTrue(hasattr(service, '_initialize_services'))
        self.assertTrue(hasattr(service, 'create_backup'))
        self.assertTrue(hasattr(service, 'restore_backup'))
        self.assertTrue(hasattr(service, 'verify_backup'))
        self.assertTrue(hasattr(service, 'schedule_backup'))
    
    @patch('backup.services.DatabaseBackupService')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_create_backup_success(self, mock_factory, mock_db_service):
        """Test successful backup creation"""
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        mock_db_instance = Mock()
        mock_db_service.return_value = mock_db_instance
        
        # Test backup creation
        backup = self.backup_service.create_backup(
            backup_type='full',
            storage_type='local',
            name='Test Backup',
            created_by=self.user,
            encrypt=True,
            compress=True
        )
        
        # Verify backup was created
        self.assertIsNotNone(backup)
        self.assertEqual(backup.name, 'Test Backup')
        self.assertEqual(backup.backup_type, 'full')
        self.assertEqual(backup.storage_type, 'local')
        self.assertEqual(backup.created_by, self.user)
        self.assertTrue(backup.encryption_enabled)
        self.assertTrue(backup.compression_enabled)
        
        # Verify service calls
        mock_factory.get_storage_service.assert_called_once_with('local')
        mock_db_service.create_backup.assert_called_once()
    
    @patch('backup.services.DatabaseBackupService')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_create_backup_with_defaults(self, mock_factory, mock_db_service):
        """Test backup creation with default values"""
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        mock_db_instance = Mock()
        mock_db_service.return_value = mock_db_instance
        
        # Test backup creation with minimal parameters
        backup = self.backup_service.create_backup(
            backup_type='full',
            storage_type='s3'
        )
        
        # Verify default values
        self.assertIsNotNone(backup)
        self.assertTrue(backup.name.startswith('backup_'))  # Auto-generated name
        self.assertEqual(backup.backup_type, 'full')
        self.assertEqual(backup.storage_type, 's3')
        self.assertFalse(backup.encryption_enabled)
        self.assertTrue(backup.compression_enabled)
        self.assertEqual(backup.retention_days, 30)
    
    @patch('backup.services.DatabaseBackupService')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_create_backup_failure(self, mock_factory, mock_db_service):
        """Test backup creation failure"""
        # Mock service to raise exception
        mock_db_service.return_value.create_backup.side_effect = Exception("Database error")
        
        # Test backup creation failure
        backup = self.backup_service.create_backup(
            backup_type='full',
            storage_type='local'
        )
        
        # Verify failure handling
        self.assertIsNone(backup)
        
        # Verify backup status is set to failed
        created_backups = Backup.objects.filter(name__startswith='backup_')
        self.assertEqual(created_backups.count(), 1)
        self.assertEqual(created_backups.first().status, 'failed')
    
    @patch('backup.services.DatabaseBackupService')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_restore_backup_success(self, mock_factory, mock_db_service):
        """Test successful backup restoration"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        mock_db_instance = Mock()
        mock_db_service.return_value = mock_db_instance
        mock_db_instance.restore_backup.return_value = True
        
        # Test restoration
        restoration = self.backup_service.restore_backup(
            str(backup.backup_id),
            restoration_type='full',
            initiated_by=self.user
        )
        
        # Verify restoration was created
        self.assertIsNotNone(restoration)
        self.assertEqual(restoration.backup, backup)
        self.assertEqual(restoration.restoration_type, 'full')
        self.assertEqual(restoration.initiated_by, self.user)
        self.assertEqual(restoration.status, 'completed')
        self.assertTrue(restoration.success)
        
        # Verify service calls
        mock_factory.get_storage_service.assert_called_once_with('local')
        mock_db_instance.restore_backup.assert_called_once()
    
    def test_restore_backup_not_found(self):
        """Test restoration with non-existent backup"""
        # Test restoration with invalid backup ID
        restoration = self.backup_service.restore_backup(
            str(uuid.uuid4()),  # Random UUID
            restoration_type='full'
        )
        
        # Verify failure
        self.assertIsNone(restoration)
    
    @patch('backup.services.DatabaseBackupService')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_restore_backup_failure(self, mock_factory, mock_db_service):
        """Test backup restoration failure"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Mock service to raise exception
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        mock_db_instance = Mock()
        mock_db_service.return_value = mock_db_instance
        mock_db_instance.restore_backup.side_effect = Exception("Restore error")
        
        # Test restoration
        restoration = self.backup_service.restore_backup(
            str(backup.backup_id),
            restoration_type='full'
        )
        
        # Verify failure handling
        self.assertIsNotNone(restoration)
        self.assertEqual(restoration.status, 'failed')
        self.assertFalse(restoration.success)
    
    @patch('backup.services.BackupValidator')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_verify_backup_hash_method(self, mock_factory, mock_validator):
        """Test backup verification with hash method"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_hash='sha256hash123',
            file_size=1024000
        )
        
        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.verify_file_integrity.return_value = True
        
        # Test verification
        verification = self.backup_service.verify_backup(
            str(backup.backup_id),
            verification_method='hash'
        )
        
        # Verify verification was created
        self.assertIsNotNone(verification)
        self.assertEqual(verification.backup, backup)
        self.assertEqual(verification.verification_method, 'hash')
        self.assertTrue(verification.is_valid)
        self.assertTrue(verification.checksum_match)
        
        # Verify validator calls
        mock_validator_instance.verify_file_integrity.assert_called_once()
    
    @patch('backup.services.BackupValidator')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_verify_backup_size_method(self, mock_factory, mock_validator):
        """Test backup verification with size method"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_size=1024000
        )
        
        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.verify_file_size.return_value = True
        
        # Test verification
        verification = self.backup_service.verify_backup(
            str(backup.backup_id),
            verification_method='size'
        )
        
        # Verify verification was created
        self.assertIsNotNone(verification)
        self.assertEqual(verification.verification_method, 'size')
        self.assertTrue(verification.is_valid)
        self.assertTrue(verification.size_match)
        
        # Verify validator calls
        mock_validator_instance.verify_file_size.assert_called_once()
    
    @patch('backup.services.BackupValidator')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_verify_backup_test_restore_method(self, mock_factory, mock_validator):
        """Test backup verification with test_restore method"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.test_restore_backup.return_value = True
        
        # Test verification
        verification = self.backup_service.verify_backup(
            str(backup.backup_id),
            verification_method='test_restore'
        )
        
        # Verify verification was created
        self.assertIsNotNone(verification)
        self.assertEqual(verification.verification_method, 'test_restore')
        self.assertTrue(verification.is_valid)
        self.assertEqual(verification.verification_details, {'test_restore': True})
        
        # Verify validator calls
        mock_validator_instance.test_restore_backup.assert_called_once()
    
    @patch('backup.services.BackupValidator')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_verify_backup_full_method(self, mock_factory, mock_validator):
        """Test backup verification with full method"""
        # Create test backup
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_hash='sha256hash123',
            file_size=1024000
        )
        
        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.verify_file_integrity.return_value = True
        mock_validator_instance.verify_file_size.return_value = True
        mock_validator_instance.test_restore_backup.return_value = True
        
        # Test verification
        verification = self.backup_service.verify_backup(
            str(backup.backup_id),
            verification_method='full'
        )
        
        # Verify verification was created
        self.assertIsNotNone(verification)
        self.assertEqual(verification.verification_method, 'full')
        self.assertTrue(verification.is_valid)
        self.assertTrue(verification.checksum_match)
        self.assertTrue(verification.size_match)
        
        # Verify all validation methods were called
        mock_validator_instance.verify_file_integrity.assert_called_once()
        mock_validator_instance.verify_file_size.assert_called_once()
        mock_validator_instance.test_restore_backup.assert_called_once()
    
    def test_verify_backup_not_found(self):
        """Test verification with non-existent backup"""
        # Test verification with invalid backup ID
        verification = self.backup_service.verify_backup(
            str(uuid.uuid4()),  # Random UUID
            verification_method='hash'
        )
        
        # Verify failure
        self.assertIsNone(verification)
    
    def test_schedule_backup_success(self):
        """Test successful backup scheduling"""
        # Test schedule creation
        schedule = self.backup_service.schedule_backup(
            cron_expr='0 2 * * *',
            backup_type='full',
            name='Daily Backup',
            storage_type='local',
            created_by=self.user
        )
        
        # Verify schedule was created
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.name, 'Daily Backup')
        self.assertEqual(schedule.cron_expression, '0 2 * * *')
        self.assertEqual(schedule.backup_type, 'full')
        self.assertEqual(schedule.storage_type, 'local')
        self.assertEqual(schedule.created_by, self.user)
        self.assertTrue(schedule.is_active)
        self.assertIsNotNone(schedule.next_run)
    
    def test_schedule_backup_with_custom_options(self):
        """Test backup scheduling with custom options"""
        # Test schedule creation with custom options
        schedule = self.backup_service.schedule_backup(
            cron_expr='0 3 * * 0',  # Sundays at 3 AM
            backup_type='incremental',
            name='Weekly Incremental',
            storage_type='s3',
            encrypt=True,
            compress=False,
            retention_days=90,
            databases=['default', 'analytics'],
            tables_include=['users', 'orders'],
            tables_exclude=['sessions']
        )
        
        # Verify custom options
        self.assertEqual(schedule.frequency, 'custom')
        self.assertEqual(schedule.encrypt, True)
        self.assertEqual(schedule.compress, False)
        self.assertEqual(schedule.retention_days, 90)
        self.assertEqual(schedule.databases, ['default', 'analytics'])
        self.assertEqual(schedule.tables_include, ['users', 'orders'])
        self.assertEqual(schedule.tables_exclude, ['sessions'])
    
    def test_schedule_backup_next_run_calculation(self):
        """Test next run time calculation"""
        # Test schedule with daily frequency
        schedule = self.backup_service.schedule_backup(
            cron_expr='0 2 * * *',  # Daily at 2 AM
            backup_type='full',
            name='Daily Backup'
        )
        
        # Verify next run is calculated
        self.assertIsNotNone(schedule.next_run)
        self.assertGreater(schedule.next_run, timezone.now())
        
        # Should be approximately 2 AM tomorrow
        tomorrow = timezone.now() + timedelta(days=1)
        expected_time = tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)
        self.assertAlmostEqual(
            schedule.next_run,
            expected_time,
            delta=timedelta(minutes=5)  # Allow 5 minute tolerance
        )
    
    def test_get_last_backup_status_empty(self):
        """Test getting last backup status when no backups exist"""
        # Test with no backups
        status = BackupService.get_last_backup_status()
        
        self.assertEqual(status['status'], 'none')
        self.assertIsNone(status['last_run'])
    
    def test_get_last_backup_status_with_backups(self):
        """Test getting last backup status with existing backups"""
        # Create test backups
        old_backup = Backup.objects.create(
            name='Old Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_at=timezone.now() - timedelta(days=2)
        )
        
        new_backup = Backup.objects.create(
            name='New Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_at=timezone.now() - timedelta(days=1),
            status='completed'
        )
        
        # Test status
        status = BackupService.get_last_backup_status()
        
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['last_run'], new_backup.created_at)
        self.assertEqual(status['backup_type'], 'full')
    
    def test_get_last_backup_status_error_handling(self):
        """Test error handling in get_last_backup_status"""
        # Mock database error
        with patch('backup.models.Backup.objects.order_by') as mock_order:
            mock_order.side_effect = Exception("Database error")
            
            status = BackupService.get_last_backup_status()
            
            self.assertEqual(status['status'], 'error')
            self.assertIsNone(status['last_run'])


class BackupServiceIntegrationTest(TestCase):
    """Test BackupService integration with other components"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = BackupService()
    
    def test_full_backup_workflow(self):
        """Test complete backup workflow"""
        with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
            with patch('backup.services.DatabaseBackupService') as mock_db_service:
                # Mock services
                mock_storage_service = Mock()
                mock_factory.get_storage_service.return_value = mock_storage_service
                mock_db_instance = Mock()
                mock_db_service.return_value = mock_db_instance
                mock_db_instance.create_backup.return_value = Mock(backup_file=Mock())
                
                # Create backup
                backup = self.backup_service.create_backup(
                    backup_type='full',
                    storage_type='local',
                    name='Workflow Test Backup',
                    created_by=self.user
                )
                
                # Verify backup creation
                self.assertIsNotNone(backup)
                self.assertEqual(backup.name, 'Workflow Test Backup')
                
                # Verify backup
                with patch('backup.services.BackupValidator') as mock_validator:
                    mock_validator_instance = Mock()
                    mock_validator.return_value = mock_validator_instance
                    mock_validator_instance.verify_file_integrity.return_value = True
                    
                    verification = self.backup_service.verify_backup(
                        str(backup.backup_id),
                        verification_method='hash'
                    )
                    
                    self.assertIsNotNone(verification)
                    self.assertTrue(verification.is_valid)
    
    def test_backup_service_error_recovery(self):
        """Test backup service error recovery"""
        with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
            # Mock factory to raise exception
            mock_factory.get_storage_service.side_effect = Exception("Service unavailable")
            
            # Test service initialization error handling
            service = BackupService()
            
            # Service should still be created but with warning
            self.assertIsNotNone(service)
    
    def test_backup_service_transaction_safety(self):
        """Test backup service transaction safety"""
        with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
            with patch('backup.services.DatabaseBackupService') as mock_db_service:
                # Mock services
                mock_storage_service = Mock()
                mock_factory.get_storage_service.return_value = mock_storage_service
                mock_db_instance = Mock()
                mock_db_service.return_value = mock_db_instance
                
                # Test transaction rollback on error
                with transaction.atomic():
                    mock_db_instance.create_backup.side_effect = Exception("Rollback test")
                    
                    backup = self.backup_service.create_backup(
                        backup_type='full',
                        storage_type='local'
                    )
                    
                    # Should return None due to error
                    self.assertIsNone(backup)
                
                # Verify no partial data was saved
                created_backups = Backup.objects.filter(name__startswith='backup_')
                self.assertEqual(created_backups.count(), 0)


class BackupServicePerformanceTest(TestCase):
    """Test BackupService performance characteristics"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = BackupService()
    
    def test_service_initialization_performance(self):
        """Test service initialization performance"""
        import time
        
        # Measure initialization time
        start_time = time.time()
        for _ in range(100):
            service = BackupService()
        end_time = time.time()
        
        # Should initialize quickly (less than 1 second for 100 instances)
        self.assertLess(end_time - start_time, 1.0)
    
    def test_backup_creation_performance(self):
        """Test backup creation performance"""
        import time
        
        # Create test storage location
        from api.backup.models import BackupStorageLocation
        storage = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type='local',
            is_active=True
        )
        
        with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
            with patch('backup.services.DatabaseBackupService') as mock_db_service:
                # Mock services
                mock_storage_service = Mock()
                mock_factory.get_storage_service.return_value = mock_storage_service
                mock_db_instance = Mock()
                mock_db_service.return_value = mock_db_instance
                mock_db_instance.create_backup.return_value = Mock(backup_file=Mock())
                
                # Measure backup creation time
                start_time = time.time()
                for i in range(10):
                    backup = self.backup_service.create_backup(
                        backup_type='full',
                        storage_type='local',
                        name=f'Performance Test Backup {i}'
                    )
                    self.assertIsNotNone(backup)
                end_time = time.time()
                
                # Should create backups quickly (less than 2 seconds for 10 backups)
                self.assertLess(end_time - start_time, 2.0)


class BackupServiceEdgeCaseTest(TestCase):
    """Test BackupService edge cases and boundary conditions"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = BackupService()
    
    def test_create_backup_with_extreme_parameters(self):
        """Test backup creation with extreme parameter values"""
        with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
            with patch('backup.services.DatabaseBackupService') as mock_db_service:
                # Mock services
                mock_storage_service = Mock()
                mock_factory.get_storage_service.return_value = mock_storage_service
                mock_db_instance = Mock()
                mock_db_service.return_value = mock_db_instance
                
                # Test with very long name
                long_name = 'A' * 1000
                backup = self.backup_service.create_backup(
                    backup_type='full',
                    storage_type='local',
                    name=long_name
                )
                
                # Should handle long names gracefully
                self.assertIsNotNone(backup)
                self.assertEqual(backup.name[:255], long_name[:255])  # Truncated to DB limit
    
    def test_create_backup_with_unicode_characters(self):
        """Test backup creation with unicode characters"""
        with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
            with patch('backup.services.DatabaseBackupService') as mock_db_service:
                # Mock services
                mock_storage_service = Mock()
                mock_factory.get_storage_service.return_value = mock_storage_service
                mock_db_instance = Mock()
                mock_db_service.return_value = mock_db_instance
                
                # Test with unicode name
                unicode_name = '测试备份 🚀'
                backup = self.backup_service.create_backup(
                    backup_type='full',
                    storage_type='local',
                    name=unicode_name
                )
                
                # Should handle unicode correctly
                self.assertIsNotNone(backup)
                self.assertEqual(backup.name, unicode_name)
    
    def test_schedule_backup_with_invalid_cron(self):
        """Test scheduling with invalid cron expression"""
        # Test with invalid cron expression
        schedule = self.backup_service.schedule_backup(
            cron_expr='invalid cron',
            backup_type='full',
            name='Invalid Schedule'
        )
        
        # Should still create schedule but next_run might be None
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.cron_expression, 'invalid cron')
    
    def test_concurrent_backup_operations(self):
        """Test concurrent backup operations"""
        import threading
        import time
        
        results = []
        
        def create_backup(index):
            with patch('backup.services.factory.BackupServiceFactory') as mock_factory:
                with patch('backup.services.DatabaseBackupService') as mock_db_service:
                    # Mock services
                    mock_storage_service = Mock()
                    mock_factory.get_storage_service.return_value = mock_storage_service
                    mock_db_instance = Mock()
                    mock_db_service.return_value = mock_db_instance
                    mock_db_instance.create_backup.return_value = Mock(backup_file=Mock())
                    
                    backup = self.backup_service.create_backup(
                        backup_type='full',
                        storage_type='local',
                        name=f'Concurrent Backup {index}'
                    )
                    results.append(backup)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_backup, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all backups were created
        self.assertEqual(len(results), 5)
        for backup in results:
            self.assertIsNotNone(backup)
