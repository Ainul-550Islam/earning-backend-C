"""
Serializer Validation Tests - Medium Priority
Comprehensive tests for data input validation in serializers
"""

import uuid
import json
import tempfile
import os
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers
from rest_framework.test import APIRequestFactory
from unittest.mock import patch, MagicMock, Mock

from api.backup.models import (
    Backup, BackupStorageLocation, BackupSchedule, BackupRestoration,
    BackupLog, RetentionPolicy, BackupNotificationConfig, DeltaBackupTracker,
    BackupVerification, BackupEncryption, BackupAlert
)
from api.backup.serializers import (
    BackupSerializer, BackupScheduleSerializer, BackupStorageLocationSerializer,
    BackupLogSerializer, BackupRestorationSerializer, RetentionPolicySerializer,
    BackupNotificationConfigSerializer, DeltaBackupTrackerSerializer,
    BackupVerificationSerializer, BackupEncryptionSerializer, BackupAlertSerializer,
    BackupTaskRequestSerializer, RestoreRequestSerializer
)
from api.backup.choices import BackupType, BackupStatus, StorageType, ScheduleFrequency

User = get_user_model()


class BackupSerializerValidationTests(TestCase):
    """Validation tests for BackupSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.factory = APIRequestFactory()
        
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
    
    def test_backup_serializer_valid_data(self):
        """Test serializer with valid data"""
        data = {
            'name': 'Test Backup',
            'description': 'Test Description',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'retention_days': 30,
            'metadata': {'key': 'value'}
        }
        
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['name'], 'Test Backup')
        self.assertEqual(serializer.validated_data['backup_type'], BackupType.FULL)
    
    def test_backup_serializer_required_fields_validation(self):
        """Test serializer required fields validation"""
        # Test missing required fields
        data = {}  # Empty data
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        
        required_fields = ['name', 'backup_type', 'storage_type', 'database_name']
        for field in required_fields:
            self.assertIn(field, serializer.errors)
    
    def test_backup_serializer_name_validation(self):
        """Test backup name validation"""
        # Test empty name
        data = {
            'name': '',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        
        # Test name too long
        data['name'] = 'A' * 256  # Exceeds max length
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        
        # Test valid name
        data['name'] = 'Valid Backup Name'
        
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_backup_serializer_backup_type_validation(self):
        """Test backup type validation"""
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        # Test valid backup types
        for backup_type, display_name in BackupType.CHOICES:
            data['backup_type'] = backup_type
            serializer = BackupSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for backup_type: {backup_type}")
        
        # Test invalid backup type
        data['backup_type'] = 'invalid_type'
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('backup_type', serializer.errors)
    
    def test_backup_serializer_storage_type_validation(self):
        """Test storage type validation"""
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        # Test valid storage types
        for storage_type, display_name in StorageType.CHOICES:
            data['storage_type'] = storage_type
            serializer = BackupSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for storage_type: {storage_type}")
        
        # Test invalid storage type
        data['storage_type'] = 'invalid_storage'
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('storage_type', serializer.errors)
    
    def test_backup_serializer_file_size_validation(self):
        """Test file size validation"""
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'file_size': 1000
        }
        
        # Test valid file size
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test negative file size
        data['file_size'] = -1000
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('file_size', serializer.errors)
        
        # Test extremely large file size
        data['file_size'] = 999999999999999999999
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('file_size', serializer.errors)
    
    def test_backup_serializer_retention_days_validation(self):
        """Test retention days validation"""
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'retention_days': 30
        }
        
        # Test valid retention days
        valid_days = [1, 7, 30, 90, 365]
        for days in valid_days:
            data['retention_days'] = days
            serializer = BackupSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for retention_days: {days}")
        
        # Test invalid retention days
        invalid_days = [-1, 0, 400]
        for days in invalid_days:
            data['retention_days'] = days
            serializer = BackupSerializer(data=data)
            self.assertFalse(serializer.is_valid(), f"Should fail for retention_days: {days}")
            self.assertIn('retention_days', serializer.errors)
    
    def test_backup_serializer_metadata_validation(self):
        """Test metadata JSON validation"""
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'metadata': {'key': 'value', 'number': 123}
        }
        
        # Test valid JSON
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test invalid JSON (string instead of dict)
        data['metadata'] = 'invalid_json'
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('metadata', serializer.errors)
        
        # Test complex valid JSON
        data['metadata'] = {
            'nested': {'array': [1, 2, 3]},
            'boolean': True,
            'null': None,
            'unicode': '测试'
        }
        
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_backup_serializer_timestamp_validation(self):
        """Test timestamp validation"""
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        # Test valid timestamps
        past_time = timezone.now() - timedelta(hours=1)
        future_time = timezone.now() + timedelta(hours=1)
        
        data['start_time'] = past_time
        data['end_time'] = future_time
        
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test end_time before start_time
        data['start_time'] = future_time
        data['end_time'] = past_time
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
    
    def test_backup_serializer_unique_name_validation(self):
        """Test unique name validation per database"""
        # Create existing backup
        Backup.objects.create(
            name='Existing Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db'
        )
        
        # Test duplicate name for same database
        data = {
            'name': 'Existing Backup',
            'backup_type': BackupType.INCREMENTAL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
        
        # Test same name for different database (should be valid)
        data['database_name'] = 'different_db'
        
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_backup_serializer_tags_validation(self):
        """Test tags validation"""
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'tags': ['tag1', 'tag2', 'tag3']
        }
        
        # Test valid tags
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test invalid tags (not a list)
        data['tags'] = 'not_a_list'
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('tags', serializer.errors)
        
        # Test empty tags
        data['tags'] = []
        
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class BackupScheduleSerializerValidationTests(TestCase):
    """Validation tests for BackupScheduleSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.factory = APIRequestFactory()
    
    def test_backup_schedule_serializer_valid_data(self):
        """Test serializer with valid data"""
        data = {
            'name': 'Daily Backup',
            'description': 'Daily backup schedule',
            'frequency': ScheduleFrequency.DAILY,
            'backup_type': BackupType.FULL,
            'cron_expression': '0 2 * * *',
            'retention_days': 30,
            'tables_include': ['users', 'orders'],
            'tables_exclude': ['logs']
        }
        
        serializer = BackupScheduleSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['name'], 'Daily Backup')
        self.assertEqual(serializer.validated_data['frequency'], ScheduleFrequency.DAILY)
    
    def test_backup_schedule_serializer_cron_validation(self):
        """Test cron expression validation"""
        data = {
            'name': 'Test Schedule',
            'frequency': ScheduleFrequency.CUSTOM,
            'backup_type': BackupType.FULL,
            'cron_expression': '0 2 * * *'
        }
        
        # Test valid cron expressions
        valid_crons = [
            '0 2 * * *',     # Daily at 2 AM
            '0 2 * * 0',     # Weekly on Sunday at 2 AM
            '0 2 1 * *',     # Monthly on 1st at 2 AM
            '*/15 * * * *'   # Every 15 minutes
        ]
        
        for cron_expr in valid_crons:
            data['cron_expression'] = cron_expr
            serializer = BackupScheduleSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for cron: {cron_expr}")
        
        # Test invalid cron expressions
        invalid_crons = [
            '',              # Empty
            'invalid',       # Invalid format
            '60 * * * *',    # Invalid minute
            '* 25 * * *',    # Invalid hour
            '* * 32 * *',    # Invalid day
        ]
        
        for cron_expr in invalid_crons:
            data['cron_expression'] = cron_expr
            serializer = BackupScheduleSerializer(data=data)
            self.assertFalse(serializer.is_valid(), f"Should fail for cron: {cron_expr}")
            self.assertIn('cron_expression', serializer.errors)
    
    def test_backup_schedule_serializer_frequency_validation(self):
        """Test frequency validation"""
        data = {
            'name': 'Test Schedule',
            'backup_type': BackupType.FULL
        }
        
        # Test all valid frequencies
        for freq_choice in ScheduleFrequency.CHOICES:
            data['frequency'] = freq_choice[0]
            serializer = BackupScheduleSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for frequency: {freq_choice[0]}")
        
        # Test invalid frequency
        data['frequency'] = 'invalid_frequency'
        
        serializer = BackupScheduleSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('frequency', serializer.errors)
    
    def test_backup_schedule_serializer_tables_validation(self):
        """Test tables inclusion/exclusion validation"""
        data = {
            'name': 'Test Schedule',
            'frequency': ScheduleFrequency.DAILY,
            'backup_type': BackupType.PARTIAL,
            'tables_include': ['users', 'orders'],
            'tables_exclude': ['logs', 'temp']
        }
        
        # Test valid table lists
        serializer = BackupScheduleSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test invalid table lists (not lists)
        data['tables_include'] = 'not_a_list'
        data['tables_exclude'] = 'also_not_a_list'
        
        serializer = BackupScheduleSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('tables_include', serializer.errors)
        self.assertIn('tables_exclude', serializer.errors)
        
        # Test empty table lists
        data['tables_include'] = []
        data['tables_exclude'] = []
        
        serializer = BackupScheduleSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_backup_schedule_serializer_scheduled_time_validation(self):
        """Test scheduled time validation"""
        data = {
            'name': 'Test Schedule',
            'frequency': ScheduleFrequency.DAILY,
            'backup_type': BackupType.FULL,
            'scheduled_time': '02:00:00'
        }
        
        # Test valid time formats
        valid_times = ['02:00:00', '14:30:00', '00:00:00', '23:59:59']
        
        for time_str in valid_times:
            data['scheduled_time'] = time_str
            serializer = BackupScheduleSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for time: {time_str}")
        
        # Test invalid time formats
        invalid_times = [
            '25:00:00',    # Invalid hour
            '12:60:00',    # Invalid minute
            '12:30:60',    # Invalid second
            'invalid',     # Invalid format
            '2:00'         # Missing seconds
        ]
        
        for time_str in invalid_times:
            data['scheduled_time'] = time_str
            serializer = BackupScheduleSerializer(data=data)
            self.assertFalse(serializer.is_valid(), f"Should fail for time: {time_str}")
            self.assertIn('scheduled_time', serializer.errors)


class BackupStorageLocationSerializerValidationTests(TestCase):
    """Validation tests for BackupStorageLocationSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_storage_location_serializer_valid_data(self):
        """Test serializer with valid data"""
        data = {
            'name': 'Test Storage',
            'storage_type': StorageType.LOCAL,
            'is_active': True,
            'is_connected': True,
            'total_space': 10737418240,
            'used_space': 0,
            'free_space': 10737418240,
            'endpoint': '/tmp/test_backups',
            'config': {'test': 'config'}
        }
        
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['name'], 'Test Storage')
        self.assertEqual(serializer.validated_data['storage_type'], StorageType.LOCAL)
    
    def test_storage_location_serializer_space_validation(self):
        """Test space validation"""
        data = {
            'name': 'Test Storage',
            'storage_type': StorageType.LOCAL,
            'total_space': 10000,
            'used_space': 0,
            'free_space': 10000
        }
        
        # Test valid space values
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test used_space > total_space
        data['used_space'] = 15000
        data['free_space'] = 0
        
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
        
        # Test negative space values
        data['total_space'] = -1000
        data['used_space'] = 0
        data['free_space'] = 0
        
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('total_space', serializer.errors)
    
    def test_storage_location_serializer_config_validation(self):
        """Test configuration validation based on storage type"""
        data = {
            'name': 'Test Storage',
            'storage_type': StorageType.S3,
            'total_space': 10000,
            'used_space': 0,
            'free_space': 10000
        }
        
        # Test missing required S3 config
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('config', serializer.errors)
        
        # Test valid S3 config
        data['config'] = {
            'access_key': 'test_key',
            'secret_key': 'test_secret',
            'bucket_name': 'test_bucket',
            'region': 'us-east-1'
        }
        
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test valid GCS config
        data['storage_type'] = StorageType.GCS
        data['config'] = {
            'project_id': 'test_project',
            'bucket_name': 'test_bucket',
            'credentials_file': '/path/to/credentials.json'
        }
        
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test valid Azure config
        data['storage_type'] = StorageType.AZURE
        data['config'] = {
            'account_name': 'test_account',
            'account_key': 'test_key',
            'container_name': 'test_container'
        }
        
        serializer = BackupStorageLocationSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class BackupTaskRequestSerializerValidationTests(TestCase):
    """Validation tests for BackupTaskRequestSerializer"""
    
    def test_backup_task_request_serializer_valid_data(self):
        """Test serializer with valid data"""
        data = {
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'name': 'Task Backup',
            'description': 'Task backup description',
            'retention_days': 30
        }
        
        serializer = BackupTaskRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['backup_type'], BackupType.FULL)
    
    def test_backup_task_request_serializer_optional_data(self):
        """Test serializer with minimal data"""
        data = {}  # All fields are optional
        
        serializer = BackupTaskRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())  # Should be valid with no data
    
    def test_backup_task_request_serializer_backup_type_validation(self):
        """Test backup type validation"""
        data = {'backup_type': BackupType.FULL}
        
        # Test valid backup types
        for backup_type, display_name in BackupType.CHOICES:
            data['backup_type'] = backup_type
            serializer = BackupTaskRequestSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for backup_type: {backup_type}")
        
        # Test invalid backup type
        data['backup_type'] = 'invalid_type'
        
        serializer = BackupTaskRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('backup_type', serializer.errors)
    
    def test_backup_task_request_serializer_storage_type_validation(self):
        """Test storage type validation"""
        data = {'storage_type': StorageType.LOCAL}
        
        # Test valid storage types
        for storage_type, display_name in StorageType.CHOICES:
            data['storage_type'] = storage_type
            serializer = BackupTaskRequestSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for storage_type: {storage_type}")
        
        # Test invalid storage type
        data['storage_type'] = 'invalid_storage'
        
        serializer = BackupTaskRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('storage_type', serializer.errors)


class RestoreRequestSerializerValidationTests(TestCase):
    """Validation tests for RestoreRequestSerializer"""
    
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
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.user
        )
    
    def test_restore_request_serializer_valid_data(self):
        """Test serializer with valid data"""
        data = {
            'backup_id': self.backup.backup_id,
            'restoration_type': 'full',
            'tables_to_restore': ['users', 'orders']
        }
        
        serializer = RestoreRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(str(serializer.validated_data['backup_id']), str(self.backup.backup_id))
    
    def test_restore_request_serializer_required_fields(self):
        """Test required fields validation"""
        data = {}  # Empty data
        
        serializer = RestoreRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('backup_id', serializer.errors)
    
    def test_restore_request_serializer_backup_id_validation(self):
        """Test backup ID validation"""
        # Test invalid UUID
        data = {
            'backup_id': 'invalid_uuid'
        }
        
        serializer = RestoreRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('backup_id', serializer.errors)
        
        # Test valid UUID
        data['backup_id'] = uuid.uuid4()
        
        serializer = RestoreRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_restore_request_serializer_tables_validation(self):
        """Test tables to restore validation"""
        data = {
            'backup_id': self.backup.backup_id,
            'tables_to_restore': ['users', 'orders']
        }
        
        # Test valid table list
        serializer = RestoreRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Test invalid table list (not a list)
        data['tables_to_restore'] = 'not_a_list'
        
        serializer = RestoreRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('tables_to_restore', serializer.errors)
        
        # Test empty table list
        data['tables_to_restore'] = []
        
        serializer = RestoreRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class SerializerSecurityValidationTests(TestCase):
    """Security validation tests for serializers"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_backup_serializer_xss_protection(self):
        """Test XSS protection in backup names and descriptions"""
        xss_attempts = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src="x" onerror="alert(\'xss\')">',
            '"><script>alert("xss")</script>',
            '<svg onload="alert(\'xss\')">'
        ]
        
        for xss_attempt in xss_attempts:
            data = {
                'name': xss_attempt,
                'description': xss_attempt,
                'backup_type': BackupType.FULL,
                'storage_type': StorageType.LOCAL,
                'database_name': 'test_db'
            }
            
            serializer = BackupSerializer(data=data)
            # Should be valid (XSS protection is typically handled at template/rendering level)
            self.assertTrue(serializer.is_valid())
            # But the data should be stored as-is for proper sanitization later
            self.assertEqual(serializer.validated_data['name'], xss_attempt)
    
    def test_backup_serializer_sql_injection_protection(self):
        """Test SQL injection protection"""
        sql_injection_attempts = [
            "'; DROP TABLE backups; --",
            "' OR '1'='1",
            "'; DELETE FROM users; --",
            "'; UPDATE users SET is_superuser=True; --"
        ]
        
        for injection in sql_injection_attempts:
            data = {
                'name': injection,
                'backup_type': BackupType.FULL,
                'storage_type': StorageType.LOCAL,
                'database_name': 'test_db'
            }
            
            serializer = BackupSerializer(data=data)
            # Should be valid (SQL injection protection is handled by Django ORM)
            self.assertTrue(serializer.is_valid())
            self.assertEqual(serializer.validated_data['name'], injection)
    
    def test_backup_serializer_file_path_injection(self):
        """Test file path injection protection"""
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config\\sam',
            '/etc/shadow',
            'C:\\Windows\\System32\\drivers\\etc\\hosts'
        ]
        
        for malicious_path in malicious_paths:
            data = {
                'name': 'Test Backup',
                'backup_type': BackupType.FULL,
                'storage_type': StorageType.LOCAL,
                'database_name': 'test_db',
                'file_path': malicious_path
            }
            
            serializer = BackupSerializer(data=data)
            # Should be valid (path validation is typically handled at model level)
            self.assertTrue(serializer.is_valid())
    
    def test_backup_serializer_large_data_protection(self):
        """Test protection against extremely large data"""
        # Test extremely large name
        large_name = 'A' * 10000  # Much larger than max length
        
        data = {
            'name': large_name,
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        serializer = BackupSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        
        # Test extremely large metadata
        large_metadata = {
            'large_array': list(range(100000)),  # Very large array
            'large_string': 'B' * 1000000  # Very large string
        }
        
        data = {
            'name': 'Test Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'metadata': large_metadata
        }
        
        # Should be valid but may cause performance issues
        serializer = BackupSerializer(data=data)
        self.assertTrue(serializer.is_valid())
