"""
Critical Model Tests - High Priority
Comprehensive tests for critical models with edge cases and validation
"""

import uuid
import json
import tempfile
import os
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock, Mock
import pytest

from api.backup.models import (
    Backup, BackupStorageLocation, BackupSchedule, BackupRestoration,
    BackupLog, RetentionPolicy, BackupNotificationConfig, DeltaBackupTracker,
    BackupVerification, BackupEncryption, BackupAlert
)
from api.backup.choices import BackupType, BackupStatus, StorageType, ScheduleFrequency

User = get_user_model()


class BackupModelCriticalTests(TestCase):
    """Critical tests for Backup model"""
    
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
            storage_type='local',
            is_active=True,
            is_connected=True,
            total_space=10737418240,  # 10GB
            used_space=0,
            free_space=10737418240,
            endpoint='/tmp/test_backups'
        )
    
    def test_backup_creation_with_all_fields(self):
        """Test backup creation with all required fields"""
        backup = Backup.objects.create(
            name='Test Backup',
            description='Test Description',
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            storage_type=StorageType.LOCAL,
            database_name='test_db',
            created_by=self.user,
            file_size=1024000,
            file_path='/tmp/test_backup.sql',
            retention_days=30,
            metadata={'test': 'data'}
        )
        
        self.assertEqual(backup.name, 'Test Backup')
        self.assertEqual(backup.backup_type, BackupType.FULL)
        self.assertEqual(backup.status, BackupStatus.PENDING)
        self.assertEqual(backup.created_by, self.user)
        self.assertTrue(backup.is_healthy)
        self.assertEqual(backup.health_score, 100)
    
    def test_backup_validation_required_fields(self):
        """Test backup validation for required fields"""
        # Test missing name
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='',  # Empty name should fail
                backup_type=BackupType.FULL,
                status=BackupStatus.PENDING,
                database_name='test_db'
            )
            backup.full_clean()
        
        # Test invalid backup_type
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type='invalid_type',  # Invalid type
                status=BackupStatus.PENDING,
                database_name='test_db'
            )
            backup.full_clean()
    
    def test_backup_file_size_validation(self):
        """Test backup file size validation"""
        # Test negative file size
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.PENDING,
                database_name='test_db',
                file_size=-1000  # Negative size
            )
            backup.full_clean()
        
        # Test extremely large file size
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.PENDING,
                database_name='test_db',
                file_size=999999999999999999  # Too large
            )
            backup.full_clean()
    
    def test_backup_retention_validation(self):
        """Test backup retention policy validation"""
        # Test invalid retention days
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.PENDING,
                database_name='test_db',
                retention_days=-1  # Negative retention
            )
            backup.full_clean()
        
        # Test retention > 365 days
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.PENDING,
                database_name='test_db',
                retention_days=400  # Too long
            )
            backup.full_clean()
    
    def test_backup_timestamp_validation(self):
        """Test backup timestamp validation"""
        past_time = timezone.now() - timedelta(days=1)
        future_time = timezone.now() + timedelta(days=1)
        
        # Test end_time before start_time
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                database_name='test_db',
                start_time=future_time,
                end_time=past_time  # End before start
            )
            backup.full_clean()
    
    def test_backup_compression_ratio_calculation(self):
        """Test backup compression ratio calculation"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            original_size=1000000,
            compressed_size=500000
        )
        
        expected_ratio = 1000000 / 500000
        self.assertEqual(backup.compression_ratio, expected_ratio)
        self.assertEqual(backup.compression_percentage, 50.0)
    
    def test_backup_age_calculation(self):
        """Test backup age calculation"""
        created_time = timezone.now() - timedelta(days=5)
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_at=created_time
        )
        
        self.assertEqual(backup.age_days, 5)
    
    def test_backup_expiration_check(self):
        """Test backup expiration check"""
        # Test expired backup
        expired_time = timezone.now() - timedelta(days=40)
        backup = Backup.objects.create(
            name='Expired Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            retention_days=30,
            created_at=expired_time
        )
        
        # Manually set expires_at
        backup.expires_at = expired_time + timedelta(days=30)
        backup.save()
        
        self.assertTrue(backup.is_expired)
        
        # Test non-expired backup
        fresh_backup = Backup.objects.create(
            name='Fresh Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            retention_days=30
        )
        
        self.assertFalse(fresh_backup.is_expired)
    
    def test_backup_unique_name_per_database(self):
        """Test unique backup name constraint per database"""
        Backup.objects.create(
            name='Same Name',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db'
        )
        
        # Should fail - same name for same database
        with self.assertRaises(IntegrityError):
            Backup.objects.create(
                name='Same Name',
                backup_type=BackupType.INCREMENTAL,
                status=BackupStatus.PENDING,
                database_name='test_db'
            )
        
        # Should succeed - same name for different database
        backup2 = Backup.objects.create(
            name='Same Name',
            backup_type=BackupType.INCREMENTAL,
            status=BackupStatus.PENDING,
            database_name='different_db'
        )
        self.assertIsNotNone(backup2.id)
    
    def test_backup_file_hash_generation(self):
        """Test backup file hash generation"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db'
        )
        
        # Create a test file
        test_content = b'Test backup content'
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_content)
            test_file_path = f.name
        
        try:
            backup.file_path = test_file_path
            backup.save()
            
            hash_value = backup.calculate_file_hash()
            self.assertIsNotNone(hash_value)
            self.assertEqual(len(hash_value), 64)  # SHA256 hex length
            
            # Test that hash is consistent
            hash_value2 = backup.calculate_file_hash()
            self.assertEqual(hash_value, hash_value2)
            
        finally:
            os.unlink(test_file_path)
    
    def test_backup_health_score_boundaries(self):
        """Test backup health score boundaries"""
        # Test minimum health score
        backup = Backup.objects.create(
            name='Unhealthy Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.FAILED,
            database_name='test_db',
            health_score=0
        )
        self.assertEqual(backup.health_score, 0)
        
        # Test maximum health score
        backup2 = Backup.objects.create(
            name='Healthy Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            health_score=100
        )
        self.assertEqual(backup2.health_score, 100)
        
        # Test invalid health score
        with self.assertRaises(ValidationError):
            backup3 = Backup(
                name='Invalid Backup',
                backup_type=BackupType.FULL,
                status=BackupStatus.PENDING,
                database_name='test_db',
                health_score=150  # Above 100
            )
            backup3.full_clean()
    
    def test_backup_metadata_json_validation(self):
        """Test backup metadata JSON validation"""
        # Valid JSON
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            metadata={'key': 'value', 'number': 123}
        )
        self.assertEqual(backup.metadata['key'], 'value')
        
        # Test with complex JSON
        complex_metadata = {
            'nested': {
                'array': [1, 2, 3],
                'object': {'inner': 'value'}
            },
            'boolean': True,
            'null': None
        }
        backup2 = Backup.objects.create(
            name='Complex Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            metadata=complex_metadata
        )
        self.assertEqual(backup2.metadata['nested']['array'][0], 1)


class BackupStorageLocationCriticalTests(TestCase):
    """Critical tests for BackupStorageLocation model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_storage_location_creation(self):
        """Test storage location creation"""
        location = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type=StorageType.LOCAL,
            is_active=True,
            is_connected=True,
            total_space=10737418240,  # 10GB
            used_space=0,
            free_space=10737418240,
            endpoint='/tmp/test_backups'
        )
        
        self.assertEqual(location.name, 'Test Storage')
        self.assertEqual(location.storage_type, StorageType.LOCAL)
        self.assertTrue(location.is_active)
        self.assertTrue(location.is_connected)
    
    def test_storage_location_space_validation(self):
        """Test storage location space validation"""
        # Test used_space > total_space
        with self.assertRaises(ValidationError):
            location = BackupStorageLocation(
                name='Invalid Storage',
                storage_type=StorageType.LOCAL,
                total_space=1000,
                used_space=2000,  # More than total
                free_space=0
            )
            location.full_clean()
        
        # Test negative space values
        with self.assertRaises(ValidationError):
            location = BackupStorageLocation(
                name='Invalid Storage',
                storage_type=StorageType.LOCAL,
                total_space=-1000,  # Negative
                used_space=0,
                free_space=0
            )
            location.full_clean()
    
    def test_storage_location_usage_percentage(self):
        """Test storage location usage percentage calculation"""
        location = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type=StorageType.LOCAL,
            total_space=10000,
            used_space=2500,
            free_space=7500
        )
        
        expected_percentage = (2500 / 10000) * 100
        self.assertEqual(location.space_used_percentage, expected_percentage)
    
    def test_storage_location_unique_name(self):
        """Test unique storage location name constraint"""
        BackupStorageLocation.objects.create(
            name='Same Name',
            storage_type=StorageType.LOCAL,
            total_space=10000,
            used_space=0,
            free_space=10000
        )
        
        # Should fail - duplicate name
        with self.assertRaises(IntegrityError):
            BackupStorageLocation.objects.create(
                name='Same Name',
                storage_type=StorageType.S3,
                total_space=10000,
                used_space=0,
                free_space=10000
            )
    
    def test_storage_location_config_validation(self):
        """Test storage location configuration validation"""
        # Test S3 configuration validation
        location = BackupStorageLocation.objects.create(
            name='S3 Storage',
            storage_type=StorageType.S3,
            total_space=10000,
            used_space=0,
            free_space=10000,
            config={
                'access_key': 'test_key',
                'secret_key': 'test_secret',
                'bucket_name': 'test_bucket',
                'region': 'us-east-1'
            }
        )
        
        self.assertEqual(location.config['bucket_name'], 'test_bucket')


class BackupScheduleCriticalTests(TestCase):
    """Critical tests for BackupSchedule model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_backup_schedule_creation(self):
        """Test backup schedule creation"""
        schedule = BackupSchedule.objects.create(
            name='Daily Backup',
            description='Daily backup schedule',
            frequency=ScheduleFrequency.DAILY,
            backup_type=BackupType.FULL,
            is_active=True,
            created_by=self.user,
            cron_expression='0 2 * * *'  # 2 AM daily
        )
        
        self.assertEqual(schedule.name, 'Daily Backup')
        self.assertEqual(schedule.frequency, ScheduleFrequency.DAILY)
        self.assertEqual(schedule.backup_type, BackupType.FULL)
        self.assertTrue(schedule.is_active)
    
    def test_backup_schedule_cron_validation(self):
        """Test backup schedule cron expression validation"""
        # Valid cron expressions
        valid_crons = [
            '0 2 * * *',     # Daily at 2 AM
            '0 2 * * 0',     # Weekly on Sunday at 2 AM
            '0 2 1 * *',     # Monthly on 1st at 2 AM
            '*/15 * * * *'   # Every 15 minutes
        ]
        
        for cron_expr in valid_crons:
            schedule = BackupSchedule.objects.create(
                name=f'Test {cron_expr}',
                cron_expression=cron_expr,
                frequency=ScheduleFrequency.CUSTOM,
                backup_type=BackupType.FULL,
                created_by=self.user
            )
            self.assertEqual(schedule.cron_expression, cron_expr)
        
        # Invalid cron expressions
        invalid_crons = [
            '',              # Empty
            'invalid',       # Invalid format
            '60 * * * *',    # Invalid minute
            '* 25 * * *',    # Invalid hour
            '* * 32 * *',    # Invalid day
        ]
        
        for cron_expr in invalid_crons:
            with self.assertRaises(ValidationError):
                schedule = BackupSchedule(
                    name='Invalid Schedule',
                    cron_expression=cron_expr,
                    frequency=ScheduleFrequency.CUSTOM,
                    backup_type=BackupType.FULL,
                    created_by=self.user
                )
                schedule.full_clean()
    
    def test_backup_schedule_frequency_validation(self):
        """Test backup schedule frequency validation"""
        # Test all valid frequencies
        for freq_choice in ScheduleFrequency.CHOICES:
            schedule = BackupSchedule.objects.create(
                name=f'Test {freq_choice[0]}',
                frequency=freq_choice[0],
                backup_type=BackupType.FULL,
                created_by=self.user
            )
            self.assertEqual(schedule.frequency, freq_choice[0])
    
    def test_backup_schedule_next_run_calculation(self):
        """Test backup schedule next run calculation"""
        # Test daily schedule
        schedule = BackupSchedule.objects.create(
            name='Daily Schedule',
            frequency=ScheduleFrequency.DAILY,
            backup_type=BackupType.FULL,
            scheduled_time='02:00:00',
            is_active=True,
            created_by=self.user
        )
        
        schedule.calculate_next_run()
        self.assertIsNotNone(schedule.next_run)
        self.assertGreater(schedule.next_run, timezone.now())
    
    def test_backup_schedule_success_rate_calculation(self):
        """Test backup schedule success rate calculation"""
        schedule = BackupSchedule.objects.create(
            name='Test Schedule',
            frequency=ScheduleFrequency.DAILY,
            backup_type=BackupType.FULL,
            created_by=self.user
        )
        
        # Test with no runs
        self.assertEqual(schedule.success_rate, 0.0)
        
        # Test with some runs
        schedule.total_runs = 10
        schedule.successful_runs = 8
        schedule.save()
        
        expected_rate = (8 / 10) * 100
        self.assertEqual(schedule.success_rate, expected_rate)
    
    def test_backup_schedule_table_inclusion_exclusion(self):
        """Test backup schedule table inclusion/exclusion"""
        schedule = BackupSchedule.objects.create(
            name='Selective Backup',
            frequency=ScheduleFrequency.DAILY,
            backup_type=BackupType.PARTIAL,
            tables_include=['users', 'orders'],
            tables_exclude=['logs', 'temp'],
            created_by=self.user
        )
        
        self.assertEqual(schedule.tables_include, ['users', 'orders'])
        self.assertEqual(schedule.tables_exclude, ['logs', 'temp'])
    
    def test_backup_schedule_retention_validation(self):
        """Test backup schedule retention validation"""
        # Valid retention days
        valid_days = [1, 7, 30, 90, 365]
        
        for days in valid_days:
            schedule = BackupSchedule.objects.create(
                name=f'Retention {days}',
                frequency=ScheduleFrequency.DAILY,
                backup_type=BackupType.FULL,
                retention_days=days,
                created_by=self.user
            )
            self.assertEqual(schedule.retention_days, days)
        
        # Invalid retention days
        invalid_days = [-1, 0, 400]
        
        for days in invalid_days:
            with self.assertRaises(ValidationError):
                schedule = BackupSchedule(
                    name='Invalid Retention',
                    frequency=ScheduleFrequency.DAILY,
                    backup_type=BackupType.FULL,
                    retention_days=days,
                    created_by=self.user
                )
                schedule.full_clean()


class BackupModelEdgeCaseTests(TransactionTestCase):
    """Edge case tests for backup models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_backup_with_maximum_values(self):
        """Test backup with maximum allowed values"""
        max_name = 'A' * 255  # Maximum name length
        max_description = 'B' * 1000  # Long description
        
        backup = Backup.objects.create(
            name=max_name,
            description=max_description,
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='test_db',
            file_size=9223372036854775807,  # Max BigInt
            retention_days=365,
            metadata={'large': 'C' * 1000}
        )
        
        self.assertEqual(len(backup.name), 255)
        self.assertEqual(backup.file_size, 9223372036854775807)
    
    def test_backup_with_unicode_content(self):
        """Test backup with unicode content"""
        unicode_name = '测试备份 🚀'
        unicode_description = '描述 with émojis 🎉 and ñoñ-latin chars'
        
        backup = Backup.objects.create(
            name=unicode_name,
            description=unicode_description,
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='测试数据库'
        )
        
        self.assertEqual(backup.name, unicode_name)
        self.assertEqual(backup.description, unicode_description)
        self.assertEqual(backup.database_name, '测试数据库')
    
    def test_backup_concurrent_creation(self):
        """Test concurrent backup creation"""
        import threading
        import time
        
        created_backups = []
        
        def create_backup(index):
            try:
                backup = Backup.objects.create(
                    name=f'Concurrent Backup {index}',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.PENDING,
                    database_name=f'test_db_{index}'
                )
                created_backups.append(backup.id)
            except Exception as e:
                print(f"Error creating backup {index}: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_backup, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all backups were created
        self.assertEqual(len(created_backups), 10)
        self.assertEqual(Backup.objects.filter(name__startswith='Concurrent Backup').count(), 10)
    
    def test_backup_cascade_deletion(self):
        """Test backup cascade deletion"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db'
        )
        
        # Create related objects
        BackupLog.objects.create(
            backup=backup,
            level='info',
            message='Test log'
        )
        
        BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True
        )
        
        # Verify related objects exist
        self.assertEqual(BackupLog.objects.filter(backup=backup).count(), 1)
        self.assertEqual(BackupVerification.objects.filter(backup=backup).count(), 1)
        
        # Delete backup and check cascade
        backup_id = backup.id
        backup.delete()
        
        # Verify related objects are deleted
        self.assertEqual(BackupLog.objects.filter(backup_id=backup_id).count(), 0)
        self.assertEqual(BackupVerification.objects.filter(backup_id=backup_id).count(), 0)
    
    def test_backup_with_null_values(self):
        """Test backup with null optional fields"""
        backup = Backup.objects.create(
            name='Minimal Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            database_name='test_db'
            # All optional fields left as null/blank
        )
        
        self.assertIsNone(backup.description)
        self.assertIsNone(backup.end_time)
        self.assertIsNone(backup.file_path)
        self.assertIsNone(backup.error_message)
        self.assertEqual(backup.tags, [])  # Default empty list
    
    def test_backup_large_metadata_handling(self):
        """Test backup with large metadata"""
        large_metadata = {
            'large_array': list(range(10000)),
            'nested_data': {
                'level1': {
                    'level2': {
                        'level3': {'deep': 'value'}
                    }
                }
            },
            'unicode_data': '测试' * 1000
        }
        
        backup = Backup.objects.create(
            name='Large Metadata Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            metadata=large_metadata
        )
        
        # Verify metadata is stored and retrieved correctly
        self.assertEqual(len(backup.metadata['large_array']), 10000)
        self.assertEqual(backup.metadata['nested_data']['level1']['level2']['level3']['deep'], 'value')
        self.assertTrue(backup.metadata['unicode_data'].startswith('测试'))


class BackupModelSecurityTests(TestCase):
    """Security-related tests for backup models"""
    
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
    
    def test_backup_sensitive_data_protection(self):
        """Test that sensitive backup data is properly protected"""
        backup = Backup.objects.create(
            name='Sensitive Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='sensitive_db',
            encryption_enabled=True,
            encryption_method='AES-256',
            metadata={'api_key': 'secret_key_123'}
        )
        
        # Verify encryption fields are set
        self.assertTrue(backup.encryption_enabled)
        self.assertEqual(backup.encryption_method, 'AES-256')
        
        # Metadata should be accessible (it's not encrypted at model level)
        self.assertEqual(backup.metadata['api_key'], 'secret_key_123')
    
    def test_backup_user_isolation(self):
        """Test that users can only access their own backups"""
        # Create backups for different users
        user1_backup = Backup.objects.create(
            name='User1 Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='db1',
            created_by=self.user
        )
        
        user2_backup = Backup.objects.create(
            name='User2 Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='db2',
            created_by=self.admin_user
        )
        
        # Test user isolation
        user1_backups = Backup.objects.filter(created_by=self.user)
        user2_backups = Backup.objects.filter(created_by=self.admin_user)
        
        self.assertEqual(user1_backups.count(), 1)
        self.assertEqual(user2_backups.count(), 1)
        self.assertEqual(user1_backups.first().name, 'User1 Backup')
        self.assertEqual(user2_backups.first().name, 'User2 Backup')
    
    def test_backup_file_path_injection(self):
        """Test protection against file path injection"""
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config\\sam',
            '/etc/shadow',
            'C:\\Windows\\System32\\drivers\\etc\\hosts'
        ]
        
        for malicious_path in malicious_paths:
            with self.assertRaises(ValidationError):
                backup = Backup(
                    name='Malicious Backup',
                    backup_type=BackupType.FULL,
                    status=BackupStatus.COMPLETED,
                    database_name='test_db',
                    file_path=malicious_path
                )
                backup.full_clean()
    
    def test_backup_sql_injection_protection(self):
        """Test protection against SQL injection in backup names"""
        sql_injection_attempts = [
            "'; DROP TABLE backups; --",
            "' OR '1'='1",
            "'; DELETE FROM users; --",
            "'; UPDATE users SET is_superuser=True; --"
        ]
        
        for injection in sql_injection_attempts:
            # This should not cause SQL injection
            backup = Backup.objects.create(
                name=injection,
                backup_type=BackupType.FULL,
                status=BackupStatus.PENDING,
                database_name='test_db'
            )
            
            # Verify the name is stored as-is, not executed
            retrieved_backup = Backup.objects.get(id=backup.id)
            self.assertEqual(retrieved_backup.name, injection)
            
            # Verify no tables were dropped (basic check)
            self.assertTrue(Backup.objects.filter(id=backup.id).exists())
