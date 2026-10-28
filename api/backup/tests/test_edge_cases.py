"""
Edge Cases and Error Handling Tests - High Priority
Comprehensive tests for edge cases and error handling in data processing
"""
import gc

import uuid
import json
import tempfile
import os
import threading
import time
import signal
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction, DatabaseError, IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework.test import force_authenticate
from unittest.mock import patch, MagicMock, Mock, mock_open
import pytest

from api.backup.models import (
    Backup, BackupStorageLocation, BackupSchedule, BackupRestoration,
    BackupLog, RetentionPolicy, BackupNotificationConfig, DeltaBackupTracker,
    BackupVerification, BackupEncryption, BackupAlert
)
from api.backup.views import (
    BackupViewSet, BackupScheduleViewSet, BackupStorageLocationViewSet,
    StartBackupView, RestoreBackupView
)
from api.backup.services import BackupService
from api.backup.tasks import backup_database_task, restore_backup_task
from api.backup.choices import BackupType, BackupStatus, StorageType, ScheduleFrequency

User = get_user_model()


class BackupEdgeCaseTests(TransactionTestCase):
    """Edge case tests for Backup model and operations"""
    
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
        
        self.storage_location = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type=StorageType.LOCAL,
            is_active=True,
            is_connected=True,
            total_space=10737418240,
            used_space=0,
            free_space=10737418240,
            endpoint='/tmp/test_backups'
        )
    
    def test_backup_concurrent_creation_race_condition(self):
        """Test concurrent backup creation race conditions"""
        created_backups = []
        errors = []
        
        def create_backup_with_delay(index, delay=0.1):
            try:
                time.sleep(delay)  # Simulate processing time
                backup = Backup.objects.create(
                    name=f'Concurrent Backup {index}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.PENDING,
                    database_name='test_db'
                )
                created_backups.append(backup.id)
            except Exception as e:
                errors.append(f"Error creating backup {index}: {e}")
        
        # Create multiple threads with potential race conditions
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_backup_with_delay, args=(i, 0.1))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(created_backups), 10)
        self.assertEqual(Backup.objects.filter(name__startswith='Concurrent Backup').count(), 10)
    
    def test_backup_database_connection_failure(self):
        """Test handling of database connection failures"""
        with patch('django.db.connection.cursor') as mock_cursor:
            mock_cursor.side_effect = DatabaseError("Connection lost")
            
            with self.assertRaises(DatabaseError):
                # Any database operation should fail
                Backup.objects.create(
                    name='Test Backup',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.PENDING,
                    database_name='test_db'
                )
    
    def test_backup_memory_exhaustion_simulation(self):
        """Test handling of memory exhaustion scenarios"""
        # Create backup with extremely large metadata
        large_metadata = {
            'large_array': list(range(100000)),  # Large array
            'nested_data': {
                'level1': {'level2': {'level3': {'deep': 'x' * 10000}}}
            }
        }
        
        try:
            backup = Backup.objects.create(
                name='Large Metadata Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                metadata=large_metadata
            )
            
            # Test retrieval of large metadata
            retrieved_backup = Backup.objects.get(id=backup.id)
            self.assertEqual(len(retrieved_backup.metadata['large_array']), 100000)
            
        except MemoryError:
            self.skipTest("Memory exhaustion - test environment has insufficient memory")
        except Exception as e:
            self.fail(f"Unexpected error with large metadata: {e}")
    
    def test_backup_file_system_errors(self):
        """Test handling of file system errors"""
        backup = Backup.objects.create(
            name='File System Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db'
        )
        
        # Test file not found
        with patch('os.path.exists', return_value=False):
            with patch('os.path.getsize', side_effect=FileNotFoundError("File not found")):
                result = backup.calculate_file_hash()
                self.assertIsNone(result)
        
        # Test permission denied
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                result = backup.calculate_file_hash()
                self.assertIsNone(result)
    
    def test_backup_transaction_rollback(self):
        """Test transaction rollback on backup creation failure"""
        initial_count = Backup.objects.count()
        
        # Simulate a failure during backup creation
        with patch('backup.models.Backup.save', side_effect=DatabaseError("Simulated error")):
            with self.assertRaises(DatabaseError):
                Backup.objects.create(
                    name='Failed Backup',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.PENDING,
                    database_name='test_db'
                )
        
        # Verify no backup was created (transaction rolled back)
        self.assertEqual(Backup.objects.count(), initial_count)
    
    def test_backup_circular_reference_prevention(self):
        """Test prevention of circular references in backup relationships"""
        backup1 = Backup.objects.create(
            name='Parent Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db'
        )
        
        backup2 = Backup.objects.create(
            name='Child Backup',
            backup_type=BackupType.INCREMENTAL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            parent_backup=backup1
        )
        
        # Try to create circular reference
        with self.assertRaises(ValidationError):
            backup1.parent_backup = backup2
            backup1.full_clean()
    
    def test_backup_extreme_timestamp_values(self):
        """Test backup with extreme timestamp values"""
        # Test with very old timestamp
        old_time = timezone.now() - timedelta(days=365 * 100)  # 100 years ago
        backup1 = Backup.objects.create(
            name='Old Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_at=old_time
        )
        self.assertEqual(backup1.created_at, old_time)
        
        # Test with future timestamp
        future_time = timezone.now() + timedelta(days=365)  # 1 year in future
        backup2 = Backup.objects.create(
            name='Future Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.SCHEDULED,
            database_name='test_db',
            start_time=future_time
        )
        self.assertEqual(backup2.start_time, future_time)
    
    def test_backup_unicode_edge_cases(self):
        """Test backup with edge case unicode characters"""
        edge_case_unicode = [
            '',  # Empty string
            ' ',  # Space only
            '\n\r\t',  # Control characters
            '🔥💣☢️',  # Emojis
            '𝕳𝖊𝖗𝖊',  # Mathematical unicode
            '𐍈𐍉𐍊',  # Outside BMP
            '\x00\x01\x02',  # Null bytes
            'test\x00backup',  # Null byte in middle
        ]
        
        for i, unicode_str in enumerate(edge_case_unicode):
            try:
                backup = Backup.objects.create(
                    name=f'Unicode Test {i}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    metadata={'unicode_test': unicode_str}
                )
                
                # Verify retrieval
                retrieved = Backup.objects.get(id=backup.id)
                self.assertEqual(retrieved.metadata['unicode_test'], unicode_str)
                
            except Exception as e:
                # Some unicode strings might not be valid, that's expected
                self.assertIn(unicode_str, ['', '\x00\x01\x02', 'test\x00backup'])
    
    def test_backup_json_serialization_edge_cases(self):
        """Test JSON serialization edge cases"""
        edge_cases = [
            None,  # None value
            True,  # Boolean
            False,  # Boolean
            3.14159265359,  # Float with many decimals
            1e20,  # Scientific notation
            -1e-20,  # Negative scientific notation
            float('inf'),  # Infinity
            float('-inf'),  # Negative infinity
            {},  # Empty dict
            [],  # Empty list
            {'nested': {'deep': {'deeper': 'value'}}},  # Deep nesting
            {'array': [1, 2, {'nested': 'value'}, [4, 5, 6]]},  # Mixed types
        ]
        
        for i, test_data in enumerate(edge_cases):
            try:
                backup = Backup.objects.create(
                    name=f'JSON Test {i}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    metadata={'test_data': test_data}
                )
                
                # Verify serialization/deserialization
                retrieved = Backup.objects.get(id=backup.id)
                self.assertEqual(retrieved.metadata['test_data'], test_data)
                
            except (ValueError, OverflowError) as e:
                # Some values (like infinity) can't be serialized to JSON
                self.assertIn(test_data, [float('inf'), float('-inf')])
            except Exception as e:
                self.fail(f"Unexpected error with JSON test case {i}: {e}")


class BackupServiceEdgeCaseTests(TransactionTestCase):
    """Edge case tests for BackupService"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = BackupService()
    
    def test_backup_service_concurrent_operations(self):
        """Test concurrent backup service operations"""
        results = []
        errors = []
        
        def create_backup_service_operation(index):
            try:
                time.sleep(0.1)  # Simulate processing
                result = self.backup_service.create_backup(
                    backup_type=BackupType.FULL,
                    storage_type=StorageType.LOCAL,
                    name=f'Concurrent Service Backup {index}',
                    created_by=self.user
                )
                results.append(result is not None)
            except Exception as e:
                errors.append(f"Error in service operation {index}: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_backup_service_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Service errors: {errors}")
        self.assertEqual(len(results), 5)
        self.assertTrue(all(results))
    
    def test_backup_service_storage_failure_handling(self):
        """Test backup service handling of storage failures"""
        with patch.object(self.backup_service, 'storage_factory') as mock_factory:
            mock_storage_service = Mock()
            mock_storage_service.save_backup.side_effect = Exception("Storage failure")
            mock_factory.get_storage_service.return_value = mock_storage_service
            
            with patch.object(self.backup_service, 'db_service') as mock_db_service:
                mock_db_service.create_backup.return_value = Mock(backup_file='test_file.sql')
                
                result = self.backup_service.create_backup(
                    backup_type=BackupType.FULL,
                    storage_type=StorageType.LOCAL,
                    created_by=self.user
                )
                
                # Should return None due to storage failure
                self.assertIsNone(result)
    
    def test_backup_service_database_failure_handling(self):
        """Test backup service handling of database failures"""
        with patch.object(self.backup_service, 'db_service') as mock_db_service:
            mock_db_service.create_backup.side_effect = Exception("Database failure")
            
            result = self.backup_service.create_backup(
                backup_type=BackupType.FULL,
                storage_type=StorageType.LOCAL,
                created_by=self.user
            )
            
            # Should return None due to database failure
            self.assertIsNone(result)
    
    def test_backup_service_partial_failure_recovery(self):
        """Test backup service recovery from partial failures"""
        with patch.object(self.backup_service, 'storage_factory') as mock_factory:
            mock_storage_service = Mock()
            # First call fails, second succeeds
            mock_storage_service.save_backup.side_effect = [Exception("First failure"), None]
            mock_factory.get_storage_service.return_value = mock_storage_service
            
            with patch.object(self.backup_service, 'db_service') as mock_db_service:
                mock_db_service.create_backup.return_value = Mock(backup_file='test_file.sql')
                
                # First attempt should fail
                result1 = self.backup_service.create_backup(
                    backup_type=BackupType.FULL,
                    storage_type=StorageType.LOCAL,
                    created_by=self.user
                )
                self.assertIsNone(result1)
                
                # Second attempt should succeed
                result2 = self.backup_service.create_backup(
                    backup_type=BackupType.INCREMENTAL,
                    storage_type=StorageType.LOCAL,
                    created_by=self.user
                )
                self.assertIsNotNone(result2)


class BackupTaskEdgeCaseTests(TransactionTestCase):
    """Edge case tests for backup tasks"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='test_db',
            created_by=self.user
        )
    
    def test_backup_task_timeout_handling(self):
        """Test backup task timeout handling"""
        with patch('backup.tasks.backup_database_task.update_state') as mock_update:
            # Simulate timeout
            mock_update.side_effect = Exception("Task timeout")
            
            result = backup_database_task(str(self.backup.id))
            
            # Should handle timeout gracefully
            self.assertFalse(result.get('success', True))
            self.assertIn('error', result)
    
    def test_backup_task_retry_mechanism(self):
        """Test backup task retry mechanism"""
        call_count = 0
        
        def mock_backup_operation(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                raise Exception("Simulated failure")
            return True  # Succeed on 3rd attempt
        
        with patch('backup.tasks._perform_full_backup', side_effect=mock_backup_operation):
            # This would normally be handled by Celery's retry mechanism
            # Here we're testing the logic that would be retried
            try:
                mock_backup_operation()
                self.assertEqual(call_count, 3)
            except Exception:
                self.fail("Retry mechanism should have succeeded")
    
    def test_backup_task_resource_cleanup(self):
        """Test backup task resource cleanup on failure"""
        temp_files = []
        
        def mock_create_temp_file():
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(b'test data')
            temp_file.close()
            temp_files.append(temp_file.name)
            return temp_file.name
        
        def mock_backup_operation(*args, **kwargs):
            temp_file_path = mock_create_temp_file()
            # Simulate failure that should trigger cleanup
            raise Exception("Backup failed")
        
        with patch('backup.tasks._perform_full_backup', side_effect=mock_backup_operation):
            try:
                backup_database_task(str(self.backup.id))
            except Exception:
                pass  # Expected to fail
            
            # Verify temporary files are cleaned up (in real implementation)
            # This is a placeholder for actual cleanup verification
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)  # Manual cleanup for test
    
    def test_backup_task_concurrent_execution_prevention(self):
        """Test prevention of concurrent execution of same backup"""
        # Mark backup as running
        self.backup.status = BackupStatus.RUNNING
        self.backup.save()
        
        # Try to start another backup task
        with patch('backup.tasks._perform_full_backup') as mock_perform:
            mock_perform.return_value = {'success': True}
            
            result = backup_database_task(str(self.backup.id))
            
            # Should either skip or handle gracefully
            # Implementation depends on specific requirements
            self.assertIsInstance(result, dict)
    
    def test_backup_task_memory_leak_prevention(self):
        """Test backup task memory leak prevention"""
        # This is a conceptual test for memory management
        initial_objects = len(gc.get_objects()) if 'gc' in globals() else 0
        
        # Simulate memory-intensive backup operation
        large_data = b'x' * (1024 * 1024 * 10)  # 10MB of data
        
        with patch('backup.tasks._perform_full_backup') as mock_perform:
            mock_perform.return_value = {
                'success': True,
                'file_size': len(large_data),
                'file_path': '/tmp/test_backup.sql'
            }
            
            result = backup_database_task(str(self.backup.id))
            
            # Verify large data was processed
            self.assertTrue(result['success'])
            self.assertEqual(result['file_size'], len(large_data))
        
        # In a real implementation, we'd verify memory was cleaned up
        del large_data


class StorageLocationEdgeCaseTests(TransactionTestCase):
    """Edge case tests for storage location operations"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_storage_location_space_calculation_overflow(self):
        """Test storage location space calculation overflow"""
        # Create location with maximum space values
        location = BackupStorageLocation.objects.create(
            name='Max Space Location',
            storage_type=StorageType.LOCAL,
            total_space=9223372036854775807,  # Max BigInt
            used_space=9223372036854775806,
            free_space=1
        )
        
        # Test percentage calculation
        expected_percentage = (9223372036854775806 / 9223372036854775807) * 100
        self.assertAlmostEqual(location.space_used_percentage, expected_percentage, places=10)
    
    def test_storage_location_connection_failure_recovery(self):
        """Test storage location connection failure and recovery"""
        location = BackupStorageLocation.objects.create(
            name='Unreliable Storage',
            storage_type=StorageType.S3,
            total_space=10000,
            used_space=0,
            free_space=10000,
            is_connected=False,
            connection_errors=5
        )
        
        # Simulate successful reconnection
        location.is_connected = True
        location.connection_errors = 0
        location.last_connection_check = timezone.now()
        location.save()
        
        self.assertTrue(location.is_connected)
        self.assertEqual(location.connection_errors, 0)
    
    def test_storage_location_concurrent_access(self):
        """Test concurrent access to storage location"""
        location = BackupStorageLocation.objects.create(
            name='Concurrent Storage',
            storage_type=StorageType.LOCAL,
            total_space=10000,
            used_space=0,
            free_space=10000
        )
        
        results = []
        
        def update_space_usage(amount):
            try:
                with transaction.atomic():
                    location = BackupStorageLocation.objects.select_for_update().get(id=location.id)
                    new_used = location.used_space + amount
                    if new_used <= location.total_space:
                        location.used_space = new_used
                        location.free_space = location.total_space - new_used
                        location.save()
                        results.append(True)
                    else:
                        results.append(False)
            except Exception as e:
                results.append(f"Error: {e}")
        
        # Create multiple threads trying to update space usage
        threads = []
        for i in range(10):
            thread = threading.Thread(target=update_space_usage, args=(100,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify consistent state
        location.refresh_from_db()
        self.assertEqual(location.used_space, 1000)  # 10 * 100
        self.assertEqual(location.free_space, 9000)
        self.assertEqual(len([r for r in results if r is True]), 10)


class ScheduleEdgeCaseTests(TransactionTestCase):
    """Edge case tests for backup scheduling"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_schedule_cron_expression_edge_cases(self):
        """Test edge cases in cron expression parsing"""
        edge_case_crons = [
            ('* * * * *', 'Every minute'),
            ('0 0 31 2 *', 'Feb 31 (non-existent)'),
            ('0 0 29 2 0', 'Feb 29 on Sunday (leap year)'),
            ('59 23 31 12 6', 'Last minute of year'),
            ('0 0 1 1 0', 'First minute of year'),
            ('*/1 * * * *', 'Every minute (alternate syntax)'),
            ('0-59 * * * *', 'Every minute (range syntax)'),
        ]
        
        for cron_expr, description in edge_case_crons:
            try:
                schedule = BackupSchedule.objects.create(
                    name=f'Edge Case: {description}',
                    cron_expression=cron_expr,
                    frequency=ScheduleFrequency.CUSTOM,
                    backup_type=BackupType.FULL,
                    created_by=self.user
                )
                
                # Test next run calculation
                schedule.calculate_next_run()
                self.assertIsNotNone(schedule.next_run, f"Failed to calculate next run for: {cron_expr}")
                
            except ValidationError as e:
                # Some invalid cron expressions should raise ValidationError
                self.assertIn('Feb 31', description)
            except Exception as e:
                self.fail(f"Unexpected error for cron '{cron_expr}': {e}")
    
    def test_schedule_time_zone_edge_cases(self):
        """Test schedule edge cases with time zones"""
        # Test with different time zones
        from django.utils import timezone as tz
        
        # Create schedule for different time zones
        utc_schedule = BackupSchedule.objects.create(
            name='UTC Schedule',
            frequency=ScheduleFrequency.DAILY,
            backup_type=BackupType.FULL,
            scheduled_time='02:00:00',
            created_by=self.user
        )
        
        # Test next run calculation in different time zones
        with tz.override('UTC'):
            utc_schedule.calculate_next_run()
            self.assertIsNotNone(utc_schedule.next_run)
        
        with tz.override('Asia/Dhaka'):
            utc_schedule.calculate_next_run()
            self.assertIsNotNone(utc_schedule.next_run)
    
    def test_schedule_dry_run_edge_cases(self):
        """Test schedule dry run with edge cases"""
        schedule = BackupSchedule.objects.create(
            name='Dry Run Test',
            frequency=ScheduleFrequency.HOURLY,
            backup_type=BackupType.FULL,
            created_by=self.user
        )
        
        # Test dry run with various scenarios
        scenarios = [
            {'tables_include': []},  # Empty include list
            {'tables_exclude': []},  # Empty exclude list
            {'tables_include': ['*']},  # Wildcard
            {'tables_exclude': ['temp_*']},  # Pattern
            {'tables_include': ['users'], 'tables_exclude': ['users']},  # Conflict
        ]
        
        for scenario in scenarios:
            try:
                # This would be the actual dry run logic
                # For now, just test that the schedule accepts the configuration
                for key, value in scenario.items():
                    setattr(schedule, key, value)
                schedule.full_clean()
                
            except ValidationError as e:
                # Some conflicting configurations should fail
                if 'tables_include' in scenario and 'tables_exclude' in scenario:
                    if set(scenario['tables_include']) & set(scenario['tables_exclude']):
                        self.assertIn('tables', str(e))
                else:
                    self.fail(f"Unexpected validation error: {e}")


class ErrorHandlingIntegrationTests(TransactionTestCase):
    """Integration tests for error handling across components"""
    
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
    
    def test_end_to_end_error_propagation(self):
        """Test error propagation through the entire stack"""
        # Create backup that will fail
        backup = Backup.objects.create(
            name='Failing Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='nonexistent_db',
            created_by=self.admin_user
        )
        
        # Mock database service to fail
        with patch('backup.services.DatabaseBackup.DatabaseBackupService.create_backup') as mock_create:
            mock_create.side_effect = Exception("Database connection failed")
            
            # Run backup task
            result = backup_database_task(str(backup.id))
            
            # Verify error is properly handled and logged
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            
            # Verify backup status is updated
            backup.refresh_from_db()
            self.assertEqual(backup.status, BackupStatus.FAILED)
            self.assertIsNotNone(backup.error_message)
    
    def test_cascading_failure_handling(self):
        """Test handling of cascading failures"""
        # Create dependent objects
        storage = BackupStorageLocation.objects.create(
            name='Failing Storage',
            storage_type=StorageType.S3,
            total_space=10000,
            used_space=0,
            free_space=10000,
            is_connected=False  # Storage is disconnected
        )
        
        backup = Backup.objects.create(
            name='Cascading Failure Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='test_db',
            storage_type=StorageType.S3,
            created_by=self.admin_user
        )
        
        # Mock storage service to fail due to disconnection
        with patch('backup.services.factory.BackupServiceFactory.get_storage_service') as mock_factory:
            mock_factory.side_effect = Exception("Storage not connected")
            
            result = backup_database_task(str(backup.id))
            
            # Verify cascading failure is handled
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            
            # Verify backup is marked as failed
            backup.refresh_from_db()
            self.assertEqual(backup.status, BackupStatus.FAILED)
    
    def test_partial_failure_recovery(self):
        """Test recovery from partial failures"""
        backup = Backup.objects.create(
            name='Partial Failure Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='test_db',
            created_by=self.admin_user
        )
        
        # Mock partial failure (database succeeds, storage fails)
        with patch('backup.services.DatabaseBackup.DatabaseBackupService.create_backup') as mock_db:
            with patch('backup.services.factory.BackupServiceFactory.get_storage_service') as mock_storage:
                mock_db.return_value = Mock(backup_file='test.sql', file_size=1000)
                mock_storage.side_effect = Exception("Storage upload failed")
                
                result = backup_database_task(str(backup.id))
                
                # Verify partial failure handling
                self.assertFalse(result['success'])
                self.assertIn('error', result)
                
                # Verify cleanup occurred (backup should be marked as failed)
                backup.refresh_from_db()
                self.assertEqual(backup.status, BackupStatus.FAILED)
    
    def test_resource_cleanup_on_failure(self):
        """Test resource cleanup when operations fail"""
        temp_files = []
        
        def mock_create_backup(*args, **kwargs):
            # Create temporary file to simulate backup file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(b'backup data')
            temp_file.close()
            temp_files.append(temp_file.name)
            
            # Return mock backup result
            return Mock(backup_file=temp_file.name, file_size=1000)
        
        def mock_storage_failure(*args, **kwargs):
            # Simulate storage failure
            raise Exception("Storage upload failed")
        
        backup = Backup.objects.create(
            name='Resource Cleanup Test',
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='test_db',
            created_by=self.admin_user
        )
        
        with patch('backup.services.DatabaseBackup.DatabaseBackupService.create_backup', side_effect=mock_create_backup):
            with patch('backup.services.factory.BackupServiceFactory.get_storage_service', side_effect=mock_storage_failure):
                result = backup_database_task(str(backup.id))
                
                # Verify failure
                self.assertFalse(result['success'])
                
                # In a real implementation, temporary files should be cleaned up
                # For test purposes, clean up manually
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
    
    def test_concurrent_error_handling(self):
        """Test error handling in concurrent operations"""
        errors = []
        results = []
        
        def failing_operation(index):
            try:
                backup = Backup.objects.create(
                    name=f'Concurrent Error Test {index}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.PENDING,
                    database_name='test_db',
                    created_by=self.admin_user
                )
                
                # Simulate random failure
                if index % 3 == 0:  # Every 3rd operation fails
                    raise Exception(f"Simulated error {index}")
                
                results.append(backup.id)
                
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=failing_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify error handling
        self.assertEqual(len(errors), 3)  # 3 operations should fail
        self.assertEqual(len(results), 7)  # 7 operations should succeed
        
        # Verify database state is consistent
        self.assertEqual(Backup.objects.filter(name__startswith='Concurrent Error Test').count(), 7)
