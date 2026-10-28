"""
View Input Validation Tests - Medium Priority
Comprehensive tests for view endpoints that accept user input (POST/PUT operations)
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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework.test import force_authenticate
from unittest.mock import patch, MagicMock, Mock
import pytest

from api.backup.models import (
    Backup, BackupStorageLocation, BackupSchedule, BackupRestoration,
    BackupLog, RetentionPolicy, BackupNotificationConfig, DeltaBackupTracker,
    BackupVerification, BackupEncryption, BackupAlert
)
from api.backup.views import (
    BackupViewSet, BackupScheduleViewSet, BackupStorageLocationViewSet,
    BackupNotificationConfigViewSet, RetentionPolicyViewSet, DeltaBackupTrackerViewSet,
    BackupLogViewSet, BackupRestorationViewSet, BackupVerificationViewSet,
    BackupEncryptionViewSet, BackupAlertViewSet, StartBackupView, RestoreBackupView
)
from api.backup.choices import BackupType, BackupStatus, StorageType, ScheduleFrequency

User = get_user_model()


class BackupViewSetInputValidationTests(APITestCase):
    """Input validation tests for BackupViewSet"""
    
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
        
        # Create existing backup for testing
        self.existing_backup = Backup.objects.create(
            name='Existing Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user
        )
    
    def test_backup_create_valid_data(self):
        """Test POST request with valid data"""
        url = reverse('backup-list')
        data = {
            'name': 'New Backup',
            'description': 'New backup description',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'retention_days': 30,
            'metadata': {'key': 'value'}
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Backup.objects.count(), 2)  # Existing + new
        self.assertEqual(Backup.objects.latest('created_at').name, 'New Backup')
    
    def test_backup_create_missing_required_fields(self):
        """Test POST request with missing required fields"""
        url = reverse('backup-list')
        data = {}  # Empty data
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        required_fields = ['name', 'backup_type', 'storage_type', 'database_name']
        for field in required_fields:
            self.assertIn(field, response.data)
    
    def test_backup_create_invalid_backup_type(self):
        """Test POST request with invalid backup type"""
        url = reverse('backup-list')
        data = {
            'name': 'Invalid Backup',
            'backup_type': 'invalid_type',
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('backup_type', response.data)
    
    def test_backup_create_invalid_storage_type(self):
        """Test POST request with invalid storage type"""
        url = reverse('backup-list')
        data = {
            'name': 'Invalid Backup',
            'backup_type': BackupType.FULL,
            'storage_type': 'invalid_storage',
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('storage_type', response.data)
    
    def test_backup_create_negative_file_size(self):
        """Test POST request with negative file size"""
        url = reverse('backup-list')
        data = {
            'name': 'Invalid Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'file_size': -1000
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file_size', response.data)
    
    def test_backup_create_invalid_retention_days(self):
        """Test POST request with invalid retention days"""
        url = reverse('backup-list')
        data = {
            'name': 'Invalid Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db',
            'retention_days': -1
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('retention_days', response.data)
    
    def test_backup_create_duplicate_name_same_database(self):
        """Test POST request with duplicate name for same database"""
        url = reverse('backup-list')
        data = {
            'name': 'Existing Backup',  # Same name as existing backup
            'backup_type': BackupType.INCREMENTAL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'  # Same database
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_backup_update_valid_data(self):
        """Test PUT request with valid data"""
        url = reverse('backup-detail', kwargs={'pk': self.existing_backup.pk})
        data = {
            'name': 'Updated Backup',
            'description': 'Updated description',
            'retention_days': 60
        }
        
        request = self.factory.put(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'put': 'update'})
        response = view(request, pk=self.existing_backup.pk)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.existing_backup.refresh_from_db()
        self.assertEqual(self.existing_backup.name, 'Updated Backup')
        self.assertEqual(self.existing_backup.description, 'Updated description')
        self.assertEqual(self.existing_backup.retention_days, 60)
    
    def test_backup_update_invalid_data(self):
        """Test PUT request with invalid data"""
        url = reverse('backup-detail', kwargs={'pk': self.existing_backup.pk})
        data = {
            'backup_type': 'invalid_type',
            'retention_days': -1
        }
        
        request = self.factory.put(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'put': 'update'})
        response = view(request, pk=self.existing_backup.pk)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('backup_type', response.data)
        self.assertIn('retention_days', response.data)
    
    def test_backup_partial_update_valid_data(self):
        """Test PATCH request with valid data"""
        url = reverse('backup-detail', kwargs={'pk': self.existing_backup.pk})
        data = {
            'description': 'Partially updated description'
        }
        
        request = self.factory.patch(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'patch': 'partial_update'})
        response = view(request, pk=self.existing_backup.pk)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.existing_backup.refresh_from_db()
        self.assertEqual(self.existing_backup.description, 'Partially updated description')
        # Original name should remain unchanged
        self.assertEqual(self.existing_backup.name, 'Existing Backup')
    
    def test_backup_create_xss_attempt(self):
        """Test POST request with XSS attempt"""
        url = reverse('backup-list')
        xss_payload = '<script>alert("xss")</script>'
        data = {
            'name': xss_payload,
            'description': xss_payload,
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should be valid (XSS protection is typically handled at template/rendering level)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_backup = Backup.objects.latest('created_at')
        self.assertEqual(created_backup.name, xss_payload)
        self.assertEqual(created_backup.description, xss_payload)
    
    def test_backup_create_sql_injection_attempt(self):
        """Test POST request with SQL injection attempt"""
        url = reverse('backup-list')
        sql_payload = "'; DROP TABLE backups; --"
        data = {
            'name': sql_payload,
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should be valid (SQL injection protection is handled by Django ORM)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_backup = Backup.objects.latest('created_at')
        self.assertEqual(created_backup.name, sql_payload)
        
        # Verify table wasn't dropped
        self.assertTrue(Backup.objects.filter(id=self.existing_backup.id).exists())
    
    def test_backup_create_unauthorized_user(self):
        """Test POST request by unauthorized user"""
        url = reverse('backup-list')
        data = {
            'name': 'Unauthorized Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        # Don't authenticate - should be unauthorized
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_backup_create_non_admin_user(self):
        """Test POST request by non-admin user"""
        url = reverse('backup-list')
        data = {
            'name': 'Non-Admin Backup',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.user)  # Regular user, not admin
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class BackupScheduleViewSetInputValidationTests(APITestCase):
    """Input validation tests for BackupScheduleViewSet"""
    
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
        
        self.factory = APIRequestFactory()
        
        # Create existing schedule for testing
        self.existing_schedule = BackupSchedule.objects.create(
            name='Existing Schedule',
            frequency=ScheduleFrequency.DAILY,
            backup_type=BackupType.FULL,
            created_by=self.admin_user
        )
    
    def test_schedule_create_valid_data(self):
        """Test POST request with valid data"""
        url = reverse('schedule-list')
        data = {
            'name': 'New Schedule',
            'description': 'New backup schedule',
            'frequency': ScheduleFrequency.DAILY,
            'backup_type': BackupType.FULL,
            'cron_expression': '0 2 * * *',
            'retention_days': 30,
            'tables_include': ['users', 'orders'],
            'tables_exclude': ['logs']
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupScheduleViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BackupSchedule.objects.count(), 2)
        self.assertEqual(BackupSchedule.objects.latest('created_at').name, 'New Schedule')
    
    def test_schedule_create_invalid_cron_expression(self):
        """Test POST request with invalid cron expression"""
        url = reverse('schedule-list')
        data = {
            'name': 'Invalid Schedule',
            'frequency': ScheduleFrequency.CUSTOM,
            'backup_type': BackupType.FULL,
            'cron_expression': 'invalid_cron'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupScheduleViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cron_expression', response.data)
    
    def test_schedule_create_invalid_frequency(self):
        """Test POST request with invalid frequency"""
        url = reverse('schedule-list')
        data = {
            'name': 'Invalid Schedule',
            'frequency': 'invalid_frequency',
            'backup_type': BackupType.FULL
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupScheduleViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('frequency', response.data)
    
    def test_schedule_create_invalid_tables_list(self):
        """Test POST request with invalid tables list"""
        url = reverse('schedule-list')
        data = {
            'name': 'Invalid Schedule',
            'frequency': ScheduleFrequency.DAILY,
            'backup_type': BackupType.PARTIAL,
            'tables_include': 'not_a_list',
            'tables_exclude': 'also_not_a_list'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupScheduleViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tables_include', response.data)
        self.assertIn('tables_exclude', response.data)
    
    def test_schedule_update_valid_data(self):
        """Test PUT request with valid data"""
        url = reverse('schedule-detail', kwargs={'pk': self.existing_schedule.pk})
        data = {
            'name': 'Updated Schedule',
            'description': 'Updated description',
            'retention_days': 60,
            'cron_expression': '0 3 * * *'
        }
        
        request = self.factory.put(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupScheduleViewSet.as_view({'put': 'update'})
        response = view(request, pk=self.existing_schedule.pk)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.existing_schedule.refresh_from_db()
        self.assertEqual(self.existing_schedule.name, 'Updated Schedule')
        self.assertEqual(self.existing_schedule.cron_expression, '0 3 * * *')


class BackupStorageLocationViewSetInputValidationTests(APITestCase):
    """Input validation tests for BackupStorageLocationViewSet"""
    
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
        
        self.factory = APIRequestFactory()
        
        # Create existing storage location for testing
        self.existing_location = BackupStorageLocation.objects.create(
            name='Existing Storage',
            storage_type=StorageType.LOCAL,
            total_space=10000,
            used_space=0,
            free_space=10000
        )
    
    def test_storage_location_create_valid_data(self):
        """Test POST request with valid data"""
        url = reverse('storage-location-list')
        data = {
            'name': 'New Storage',
            'storage_type': StorageType.LOCAL,
            'is_active': True,
            'is_connected': True,
            'total_space': 10737418240,
            'used_space': 0,
            'free_space': 10737418240,
            'endpoint': '/tmp/test_backups',
            'config': {'test': 'config'}
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupStorageLocationViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BackupStorageLocation.objects.count(), 2)
        self.assertEqual(BackupStorageLocation.objects.latest('created_at').name, 'New Storage')
    
    def test_storage_location_create_invalid_space_values(self):
        """Test POST request with invalid space values"""
        url = reverse('storage-location-list')
        data = {
            'name': 'Invalid Storage',
            'storage_type': StorageType.LOCAL,
            'total_space': 10000,
            'used_space': 15000,  # More than total
            'free_space': 0
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupStorageLocationViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_storage_location_create_s3_missing_config(self):
        """Test POST request for S3 storage without required config"""
        url = reverse('storage-location-list')
        data = {
            'name': 'S3 Storage',
            'storage_type': StorageType.S3,
            'total_space': 10000,
            'used_space': 0,
            'free_space': 10000
            # Missing S3 config
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupStorageLocationViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('config', response.data)
    
    def test_storage_location_create_duplicate_name(self):
        """Test POST request with duplicate name"""
        url = reverse('storage-location-list')
        data = {
            'name': 'Existing Storage',  # Same name as existing
            'storage_type': StorageType.S3,
            'total_space': 10000,
            'used_space': 0,
            'free_space': 10000,
            'config': {
                'access_key': 'test_key',
                'secret_key': 'test_secret',
                'bucket_name': 'test_bucket'
            }
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupStorageLocationViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)


class StartBackupViewInputValidationTests(APITestCase):
    """Input validation tests for StartBackupView"""
    
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
        
        self.factory = APIRequestFactory()
    
    def test_start_backup_valid_data(self):
        """Test POST request with valid data"""
        url = reverse('start-backup')
        data = {
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'name': 'Task Backup',
            'description': 'Task backup description',
            'retention_days': 30
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = StartBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('backup_id', response.data)
    
    def test_start_backup_invalid_backup_type(self):
        """Test POST request with invalid backup type"""
        url = reverse('start-backup')
        data = {
            'backup_type': 'invalid_type',
            'storage_type': StorageType.LOCAL
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = StartBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('backup_type', response.data)
    
    def test_start_backup_invalid_storage_type(self):
        """Test POST request with invalid storage type"""
        url = reverse('start-backup')
        data = {
            'backup_type': BackupType.FULL,
            'storage_type': 'invalid_storage'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = StartBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('storage_type', response.data)
    
    @patch('backup.views.backup_database_task')
    def test_start_backup_task_creation(self, mock_task):
        """Test that backup task is created properly"""
        mock_task.delay.return_value = Mock(id='task_id')
        
        url = reverse('start-backup')
        data = {
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'name': 'Task Backup'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = StartBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_task.delay.assert_called_once()
        
        # Check task arguments
        call_args = mock_task.delay.call_args
        self.assertIn('backup_id', call_args[1])
        self.assertIn('backup_type', call_args[1])


class RestoreBackupViewInputValidationTests(APITestCase):
    """Input validation tests for RestoreBackupView"""
    
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
        
        self.factory = APIRequestFactory()
        
        # Create backup for restoration
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            database_name='test_db',
            created_by=self.admin_user
        )
    
    def test_restore_backup_valid_data(self):
        """Test POST request with valid data"""
        url = reverse('restore-backup')
        data = {
            'backup_id': self.backup.backup_id,
            'restoration_type': 'full',
            'tables_to_restore': ['users', 'orders']
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = RestoreBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('restoration_id', response.data)
    
    def test_restore_backup_missing_backup_id(self):
        """Test POST request with missing backup ID"""
        url = reverse('restore-backup')
        data = {
            'restoration_type': 'full'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = RestoreBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('backup_id', response.data)
    
    def test_restore_backup_invalid_backup_id(self):
        """Test POST request with invalid backup ID"""
        url = reverse('restore-backup')
        data = {
            'backup_id': 'invalid_uuid',
            'restoration_type': 'full'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = RestoreBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('backup_id', response.data)
    
    def test_restore_backup_nonexistent_backup(self):
        """Test POST request with nonexistent backup ID"""
        url = reverse('restore-backup')
        fake_uuid = uuid.uuid4()
        data = {
            'backup_id': fake_uuid,
            'restoration_type': 'full'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = RestoreBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_restore_backup_invalid_tables_list(self):
        """Test POST request with invalid tables list"""
        url = reverse('restore-backup')
        data = {
            'backup_id': self.backup.backup_id,
            'restoration_type': 'partial',
            'tables_to_restore': 'not_a_list'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = RestoreBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tables_to_restore', response.data)
    
    @patch('backup.views.restore_backup_task')
    def test_restore_backup_task_creation(self, mock_task):
        """Test that restore task is created properly"""
        mock_task.delay.return_value = Mock(id='task_id')
        
        url = reverse('restore-backup')
        data = {
            'backup_id': self.backup.backup_id,
            'restoration_type': 'full'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = RestoreBackupView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_task.delay.assert_called_once()
        
        # Check task arguments
        call_args = mock_task.delay.call_args
        self.assertIn('restoration_id', call_args[1])


class ViewSecurityInputValidationTests(APITestCase):
    """Security input validation tests for views"""
    
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
        
        self.factory = APIRequestFactory()
    
    def test_view_xss_protection(self):
        """Test XSS protection in view inputs"""
        url = reverse('backup-list')
        xss_payload = '<script>alert("xss")</script>'
        data = {
            'name': xss_payload,
            'description': xss_payload,
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should be valid (XSS protection is typically handled at template/rendering level)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify data is stored as-is for proper sanitization later
        created_backup = Backup.objects.latest('created_at')
        self.assertEqual(created_backup.name, xss_payload)
        self.assertEqual(created_backup.description, xss_payload)
    
    def test_view_sql_injection_protection(self):
        """Test SQL injection protection in view inputs"""
        url = reverse('backup-list')
        sql_payload = "'; DROP TABLE backups; --"
        data = {
            'name': sql_payload,
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # Should be valid (SQL injection protection is handled by Django ORM)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify data is stored as-is
        created_backup = Backup.objects.latest('created_at')
        self.assertEqual(created_backup.name, sql_payload)
        
        # Verify table wasn't dropped (basic check)
        self.assertTrue(Backup.objects.filter(id=created_backup.id).exists())
    
    def test_view_large_data_protection(self):
        """Test protection against extremely large data in views"""
        url = reverse('backup-list')
        large_name = 'A' * 10000  # Much larger than max length
        
        data = {
            'name': large_name,
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': 'test_db'
        }
        
        request = self.factory.post(url, data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
    
    def test_view_unicode_handling(self):
        """Test unicode handling in view inputs"""
        url = reverse('backup-list')
        unicode_data = {
            'name': '测试备份 🚀',
            'description': '描述 with émojis 🎉',
            'backup_type': BackupType.FULL,
            'storage_type': StorageType.LOCAL,
            'database_name': '测试数据库'
        }
        
        request = self.factory.post(url, unicode_data, format='json')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        created_backup = Backup.objects.latest('created_at')
        self.assertEqual(created_backup.name, '测试备份 🚀')
        self.assertEqual(created_backup.description, '描述 with émojis 🎉')
        self.assertEqual(created_backup.database_name, '测试数据库')
    
    def test_view_malformed_json(self):
        """Test handling of malformed JSON"""
        url = reverse('backup-list')
        
        # Create request with malformed JSON
        request = self.factory.post(
            url,
            '{"name": "test", "backup_type":}',  # Malformed JSON
            content_type='application/json'
        )
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_view_content_type_validation(self):
        """Test content type validation"""
        url = reverse('backup-list')
        data = {'name': 'test'}
        
        # Request with wrong content type
        request = self.factory.post(url, data, content_type='text/plain')
        force_authenticate(request, self.admin_user)
        view = BackupViewSet.as_view({'post': 'create'})
        response = view(request)
        
        # DRF typically handles this gracefully but let's verify
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE])
