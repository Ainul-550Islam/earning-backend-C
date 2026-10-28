"""
Test Models for Backup Module
Comprehensive tests for all 13 backup models
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
from unittest.mock import patch, MagicMock

from api.backup.models import (
    Backup, BackupStorageLocation, BackupSchedule, BackupRestoration,
    BackupLog, RetentionPolicy, BackupNotificationConfig, DeltaBackupTracker,
    BackupVerification, BackupEncryption, BackupAlert,
    HealthyBackupManager, ExpiredBackupManager
)

User = get_user_model()


class BackupModelTest(TestCase):
    """Test Backup model"""
    
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
            is_active=True,
            is_connected=True,
            max_capacity=10737418240,  # 10GB
            used_space=0,
            free_space=10737418240,
            endpoint='/tmp/test_backups'
        )
    
    def test_backup_creation(self):
        """Test backup model creation"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user,
            storage_location=self.storage_location,
            file_size=1024000,
            file_hash='sha256hash123',
            status='completed'
        )
        
        self.assertEqual(str(backup), 'Test Backup')
        self.assertEqual(backup.backup_type, 'full')
        self.assertEqual(backup.status, 'completed')
        self.assertEqual(backup.created_by, self.user)
        self.assertTrue(backup.is_healthy())
        self.assertFalse(backup.is_expired())
    
    def test_backup_uuid_generation(self):
        """Test UUID generation for backup_id"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        self.assertIsInstance(backup.backup_id, uuid.UUID)
        self.assertTrue(backup.backup_id.version == 4)  # UUID v4
    
    def test_backup_status_flow(self):
        """Test backup status transitions"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            status='pending'
        )
        
        # Test status progression
        backup.status = 'running'
        backup.save()
        self.assertEqual(backup.status, 'running')
        
        backup.status = 'completed'
        backup.save()
        self.assertEqual(backup.status, 'completed')
    
    def test_backup_retention_calculation(self):
        """Test retention date calculation"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            retention_days=30
        )
        
        expected_expiry = backup.created_at + timedelta(days=30)
        self.assertEqual(backup.expires_at.date(), expected_expiry.date())
    
    def test_backup_health_scoring(self):
        """Test backup health scoring"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_size=1024000,
            verification_passed=True,
            status='completed'
        )
        
        # Test health score calculation
        score = backup.calculate_health_score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
    
    def test_backup_managers(self):
        """Test custom managers"""
        # Create test backups
        healthy_backup = Backup.objects.create(
            name='Healthy Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            status='completed',
            is_healthy=True
        )
        
        expired_backup = Backup.objects.create(
            name='Expired Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            expires_at=timezone.now() - timedelta(days=1),
            is_permanent=False
        )
        
        # Test healthy manager
        healthy_backups = list(Backup.healthy_objects.all())
        self.assertIn(healthy_backup, healthy_backups)
        self.assertNotIn(expired_backup, healthy_backups)
        
        # Test expired manager
        expired_backups = list(Backup.expired_objects.all())
        self.assertIn(expired_backup, expired_backups)
        self.assertNotIn(healthy_backup, expired_backups)


class BackupStorageLocationTest(TestCase):
    """Test BackupStorageLocation model"""
    
    def test_storage_location_creation(self):
        """Test storage location creation"""
        storage = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type='s3',
            endpoint='s3.amazonaws.com/test-bucket',
            is_active=True,
            max_capacity=107374182400,  # 100GB
            used_space=1073741824,   # 1GB
            free_space=9630035392     # 89GB
        )
        
        self.assertEqual(str(storage), 'Test Storage')
        self.assertEqual(storage.storage_type, 's3')
        self.assertTrue(storage.is_active)
        self.assertEqual(storage.get_usage_percentage(), 10.0)
    
    def test_storage_capacity_calculation(self):
        """Test storage capacity calculations"""
        storage = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type='local',
            max_capacity=10737418240,  # 10GB
            used_space=5368709120,     # 5GB
        )
        
        # Test capacity calculations
        expected_free = storage.max_capacity - storage.used_space
        self.assertEqual(storage.free_space, expected_free)
        self.assertEqual(storage.get_usage_percentage(), 50.0)
    
    def test_storage_health_check(self):
        """Test storage health check"""
        storage = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type='local',
            endpoint='/tmp/test_backups',
            is_connected=True
        )
        
        # Mock health check
        with patch('backup.models.storage_health_check') as mock_check:
            mock_check.return_value = True
            
            is_healthy = storage.check_health()
            self.assertTrue(is_healthy)
            mock_check.assert_called_once_with(storage.endpoint)


class BackupScheduleTest(TestCase):
    """Test BackupSchedule model"""
    
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
            is_active=True,
            endpoint='/tmp/test_backups'
        )
    
    def test_schedule_creation(self):
        """Test backup schedule creation"""
        schedule = BackupSchedule.objects.create(
            name='Daily Backup',
            frequency='daily',
            scheduled_time='02:00:00',
            backup_type='full',
            database_alias='default',
            storage_type='local',
            is_active=True,
            created_by=self.user
        )
        
        self.assertEqual(str(schedule), 'Daily Backup')
        self.assertEqual(schedule.frequency, 'daily')
        self.assertTrue(schedule.is_active)
    
    def test_cron_expression_generation(self):
        """Test cron expression generation"""
        schedule = BackupSchedule.objects.create(
            name='Daily Backup',
            frequency='daily',
            scheduled_time='02:00:00',
            backup_type='full',
            database_alias='default',
            storage_type='local'
        )
        
        cron_expr = schedule.get_cron_expression()
        self.assertEqual(cron_expr, '0 2 * * *')
    
    def test_next_run_calculation(self):
        """Test next run time calculation"""
        schedule = BackupSchedule.objects.create(
            name='Hourly Backup',
            frequency='hourly',
            backup_type='full',
            database_alias='default',
            storage_type='local'
        )
        
        next_run = schedule.calculate_next_run()
        self.assertGreater(next_run, timezone.now())
        self.assertLess(next_run, timezone.now() + timedelta(hours=2))
    
    def test_schedule_success_rate(self):
        """Test schedule success rate calculation"""
        schedule = BackupSchedule.objects.create(
            name='Test Schedule',
            frequency='daily',
            backup_type='full',
            database_alias='default',
            storage_type='local',
            total_runs=10,
            successful_runs=8
        )
        
        success_rate = schedule.get_success_rate()
        self.assertEqual(success_rate, 80.0)


class BackupRestorationTest(TestCase):
    """Test BackupRestoration model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
    
    def test_restoration_creation(self):
        """Test backup restoration creation"""
        restoration = BackupRestoration.objects.create(
            backup=self.backup,
            restoration_type='full',
            initiated_by=self.user,
            status='completed'
        )
        
        self.assertEqual(str(restoration), f"Restore of {self.backup.name}")
        self.assertEqual(restoration.backup, self.backup)
        self.assertEqual(restoration.initiated_by, self.user)
        self.assertEqual(restoration.status, 'completed')
    
    def test_restoration_uuid_generation(self):
        """Test UUID generation for restoration_id"""
        restoration = BackupRestoration.objects.create(
            backup=self.backup,
            restoration_type='full'
        )
        
        self.assertIsInstance(restoration.restoration_id, uuid.UUID)
        self.assertTrue(restoration.restoration_id.version == 4)
    
    def test_restoration_duration_calculation(self):
        """Test restoration duration calculation"""
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=30)
        
        restoration = BackupRestoration.objects.create(
            backup=self.backup,
            restoration_type='full',
            started_at=start_time,
            completed_at=end_time,
            status='completed'
        )
        
        expected_duration = (end_time - start_time).total_seconds()
        self.assertEqual(restoration.get_duration(), expected_duration)
    
    def test_restoration_rollback(self):
        """Test restoration rollback functionality"""
        restoration = BackupRestoration.objects.create(
            backup=self.backup,
            restoration_type='full',
            rollback_enabled=True,
            status='completed'
        )
        
        # Test rollback
        restoration.perform_rollback()
        self.assertTrue(restoration.rollback_performed)
        self.assertEqual(restoration.status, 'rolled_back')


class BackupLogTest(TestCase):
    """Test BackupLog model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
    
    def test_log_creation(self):
        """Test backup log creation"""
        log = BackupLog.objects.create(
            backup=self.backup,
            log_level='info',
            category='backup',
            action='create',
            message='Backup created successfully',
            source='command',
            user=self.user
        )
        
        self.assertEqual(str(log), f"Log for {self.backup.name} - create")
        self.assertEqual(log.backup, self.backup)
        self.assertEqual(log.log_level, 'info')
        self.assertEqual(log.category, 'backup')
    
    def test_log_factory_methods(self):
        """Test log factory methods"""
        # Test backup start log
        start_log = BackupLog.log_backup_start(
            backup=self.backup,
            user=self.user,
            metadata={'test': 'data'}
        )
        self.assertEqual(start_log.action, 'start')
        self.assertEqual(start_log.category, 'backup')
        
        # Test backup complete log
        complete_log = BackupLog.log_backup_complete(
            backup=self.backup,
            user=self.user,
            duration=300
        )
        self.assertEqual(complete_log.action, 'complete')
        self.assertEqual(complete_log.duration, 300)
        
        # Test backup error log
        error_log = BackupLog.log_backup_error(
            backup=self.backup,
            error_message='Test error',
            error_traceback='Traceback here'
        )
        self.assertEqual(error_log.action, 'fail')
        self.assertEqual(error_log.error_message, 'Test error')
    
    def test_log_performance_tracking(self):
        """Test log performance tracking"""
        log = BackupLog.objects.create(
            backup=self.backup,
            log_level='info',
            category='performance',
            action='create',
            message='Performance metrics',
            duration=300,
            memory_usage=1024000,
            cpu_usage=50.5,
            bytes_transferred=1024000
        )
        
        self.assertEqual(log.duration, 300)
        self.assertEqual(log.memory_usage, 1024000)
        self.assertEqual(log.cpu_usage, 50.5)
        self.assertEqual(log.bytes_transferred, 1024000)


class RetentionPolicyTest(TestCase):
    """Test RetentionPolicy model"""
    
    def test_retention_policy_creation(self):
        """Test retention policy creation"""
        policy = RetentionPolicy.objects.create(
            name='Standard Policy',
            keep_all=False,
            keep_weekly=4,
            keep_monthly=12,
            keep_yearly=5
        )
        
        self.assertEqual(str(policy), 'Standard Policy')
        self.assertFalse(policy.keep_all)
        self.assertEqual(policy.keep_weekly, 4)
        self.assertEqual(policy.keep_monthly, 12)
        self.assertEqual(policy.keep_yearly, 5)


class BackupNotificationConfigTest(TestCase):
    """Test BackupNotificationConfig model"""
    
    def test_notification_config_creation(self):
        """Test notification config creation"""
        config = BackupNotificationConfig.objects.create(
            name='Default Config',
            notify_on_failure=True,
            notify_on_warning=True
        )
        
        self.assertEqual(str(config), 'Default Config')
        self.assertTrue(config.notify_on_failure)
        self.assertTrue(config.notify_on_warning)


class DeltaBackupTrackerTest(TestCase):
    """Test DeltaBackupTracker model"""
    
    def setUp(self):
        """Set up test data"""
        self.parent_backup = Backup.objects.create(
            name='Parent Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        self.child_backup = Backup.objects.create(
            name='Child Backup',
            backup_type='delta',
            storage_type='local',
            database_name='test_db'
        )
    
    def test_delta_tracker_creation(self):
        """Test delta backup tracker creation"""
        tracker = DeltaBackupTracker.objects.create(
            parent_backup=self.parent_backup,
            child_backup=self.child_backup,
            changed_tables=['users', 'orders'],
            changed_row_count=100,
            change_percentage=5.2
        )
        
        self.assertEqual(str(tracker), f"Delta: {self.parent_backup.name} -> {self.child_backup.name}")
        self.assertEqual(tracker.parent_backup, self.parent_backup)
        self.assertEqual(tracker.child_backup, self.child_backup)
        self.assertEqual(tracker.changed_row_count, 100)
        self.assertEqual(tracker.change_percentage, 5.2)
    
    def test_delta_tracker_unique_constraint(self):
        """Test unique constraint on parent_backup + child_backup"""
        DeltaBackupTracker.objects.create(
            parent_backup=self.parent_backup,
            child_backup=self.child_backup
        )
        
        # Should raise IntegrityError on duplicate
        with self.assertRaises(Exception):
            DeltaBackupTracker.objects.create(
                parent_backup=self.parent_backup,
                child_backup=self.child_backup
            )


class BackupVerificationTest(TestCase):
    """Test BackupVerification model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
    
    def test_verification_creation(self):
        """Test backup verification creation"""
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=True,
            checksum_match=True,
            size_match=True,
            verified_by=self.user
        )
        
        self.assertEqual(str(verification), f"Verification of {self.backup.name} - Valid")
        self.assertEqual(verification.backup, self.backup)
        self.assertEqual(verification.verification_method, 'hash')
        self.assertTrue(verification.is_valid)
        self.assertTrue(verification.checksum_match)
        self.assertTrue(verification.size_match)
        self.assertEqual(verification.verified_by, self.user)
    
    def test_verification_uuid_generation(self):
        """Test UUID generation for verification_id"""
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash'
        )
        
        self.assertIsInstance(verification.verification_id, uuid.UUID)
        self.assertTrue(verification.verification_id.version == 4)
    
    def test_verification_details_storage(self):
        """Test verification details JSON storage"""
        details = {
            'hash_algorithm': 'sha256',
            'expected_hash': 'abc123',
            'actual_hash': 'abc123',
            'file_size': 1024000
        }
        
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='full',
            is_valid=True,
            verification_details=details
        )
        
        self.assertEqual(verification.verification_details, details)
    
    def test_verification_error_handling(self):
        """Test verification error handling"""
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=False,
            checksum_match=False,
            error_message='Hash mismatch detected'
        )
        
        self.assertFalse(verification.is_valid)
        self.assertFalse(verification.checksum_match)
        self.assertEqual(verification.error_message, 'Hash mismatch detected')


class BackupEncryptionTest(TestCase):
    """Test BackupEncryption model"""
    
    def setUp(self):
        """Set up test data"""
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
    
    def test_encryption_creation(self):
        """Test backup encryption creation"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='AES-256-GCM',
            key_hash='sha256hash123',
            is_encrypted=True,
            encryption_key='encrypted_key_data'
        )
        
        self.assertEqual(str(encryption), f"Encryption of {self.backup.name} - AES-256-GCM")
        self.assertEqual(encryption.backup, self.backup)
        self.assertEqual(encryption.algorithm, 'AES-256-GCM')
        self.assertTrue(encryption.is_encrypted)
        self.assertEqual(encryption.key_hash, 'sha256hash123')
    
    def test_encryption_one_to_one_relationship(self):
        """Test one-to-one relationship with backup"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='Fernet',
            is_encrypted=True
        )
        
        # Test reverse relationship
        self.assertEqual(self.backup.encryption_info, encryption)
        
        # Test uniqueness
        with self.assertRaises(Exception):
            BackupEncryption.objects.create(
                backup=self.backup,
                algorithm='AES-256-GCM',
                is_encrypted=True
            )
    
    def test_key_hash_generation(self):
        """Test key hash generation"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='AES-256-GCM',
            is_encrypted=True
        )
        
        test_key = 'test_encryption_key_123'
        generated_hash = encryption.generate_key_hash(test_key)
        
        self.assertEqual(encryption.key_hash, generated_hash)
        self.assertEqual(len(generated_hash), 64)  # SHA256 hex length
    
    def test_encryption_metadata(self):
        """Test encryption metadata storage"""
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='ChaCha20-Poly1305',
            key_hash='sha256hash456',
            is_encrypted=True,
            salt='random_salt_123',
            iv='initialization_vector_456'
        )
        
        self.assertEqual(encryption.algorithm, 'ChaCha20-Poly1305')
        self.assertEqual(encryption.salt, 'random_salt_123')
        self.assertEqual(encryption.iv, 'initialization_vector_456')


class BackupAlertTest(TestCase):
    """Test BackupAlert model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
    
    def test_alert_creation(self):
        """Test backup alert creation"""
        alert = BackupAlert.objects.create(
            alert_type='failed',
            backup=self.backup,
            message='Backup failed during creation',
            severity='high'
        )
        
        self.assertEqual(str(alert), f"Backup Failed - Backup failed during creation")
        self.assertEqual(alert.alert_type, 'failed')
        self.assertEqual(alert.backup, self.backup)
        self.assertEqual(alert.message, 'Backup failed during creation')
        self.assertEqual(alert.severity, 'high')
        self.assertFalse(alert.is_resolved)
    
    def test_alert_factory_method(self):
        """Test alert factory method"""
        metadata = {
            'error_code': 'BACKUP_001',
            'error_details': 'Connection timeout'
        }
        
        alert = BackupAlert.create_alert(
            alert_type='verification_failed',
            message='Backup verification failed',
            backup=self.backup,
            severity='medium',
            metadata=metadata
        )
        
        self.assertEqual(alert.alert_type, 'verification_failed')
        self.assertEqual(alert.message, 'Backup verification failed')
        self.assertEqual(alert.backup, self.backup)
        self.assertEqual(alert.severity, 'medium')
        self.assertEqual(alert.metadata, metadata)
    
    def test_alert_resolution(self):
        """Test alert resolution"""
        alert = BackupAlert.objects.create(
            alert_type='schedule_missed',
            message='Scheduled backup missed',
            severity='medium'
        )
        
        # Test resolution
        alert.resolve(user=self.user)
        
        self.assertTrue(alert.is_resolved)
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(alert.resolved_by, self.user)
    
    def test_alert_types(self):
        """Test all alert types"""
        alert_types = [
            'failed', 'size_exceeded', 'schedule_missed', 'storage_full',
            'verification_failed', 'retention_expired', 'security'
        ]
        
        for alert_type in alert_types:
            alert = BackupAlert.objects.create(
                alert_type=alert_type,
                message=f'Test {alert_type} alert',
                severity='low'
            )
            self.assertEqual(alert.alert_type, alert_type)
    
    def test_alert_severity_levels(self):
        """Test alert severity levels"""
        severity_levels = ['low', 'medium', 'high', 'critical']
        
        for severity in severity_levels:
            alert = BackupAlert.objects.create(
                alert_type='failed',
                message=f'Test {severity} alert',
                severity=severity
            )
            self.assertEqual(alert.severity, severity)


class BackupModelRelationshipsTest(TestCase):
    """Test relationships between backup models"""
    
    def setUp(self):
        """Set up test data with relationships"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
    
    def test_backup_reverse_relationships(self):
        """Test reverse relationships from backup"""
        # Create related objects
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=True
        )
        
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='AES-256-GCM',
            is_encrypted=True
        )
        
        alert = BackupAlert.objects.create(
            backup=self.backup,
            alert_type='failed',
            message='Test alert',
            severity='medium'
        )
        
        # Test reverse relationships
        self.assertIn(verification, self.backup.verifications.all())
        self.assertEqual(self.backup.encryption_info, encryption)
        self.assertIn(alert, self.backup.alerts.all())
    
    def test_cascade_deletion(self):
        """Test cascade deletion behavior"""
        # Create related objects
        verification = BackupVerification.objects.create(
            backup=self.backup,
            verification_method='hash',
            is_valid=True
        )
        
        encryption = BackupEncryption.objects.create(
            backup=self.backup,
            algorithm='AES-256-GCM',
            is_encrypted=True
        )
        
        # Delete backup and verify cascade
        backup_id = str(self.backup.backup_id)
        self.backup.delete()
        
        # Verify related objects are deleted
        self.assertFalse(BackupVerification.objects.filter(backup_id=backup_id).exists())
        self.assertFalse(BackupEncryption.objects.filter(backup_id=backup_id).exists())


class BackupModelValidationTest(TestCase):
    """Test model validation and constraints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_backup_name_validation(self):
        """Test backup name validation"""
        # Test empty name
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='',
                backup_type='full',
                storage_type='local',
                database_name='test_db',
                created_by=self.user
            )
            backup.full_clean()
    
    def test_backup_type_validation(self):
        """Test backup type validation"""
        # Test invalid backup type
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type='invalid_type',
                storage_type='local',
                database_name='test_db',
                created_by=self.user
            )
            backup.full_clean()
    
    def test_file_size_validation(self):
        """Test file size validation"""
        # Test negative file size
        with self.assertRaises(ValidationError):
            backup = Backup(
                name='Test Backup',
                backup_type='full',
                storage_type='local',
                database_name='test_db',
                file_size=-1000,
                created_by=self.user
            )
            backup.full_clean()
    
    def test_model_string_representations(self):
        """Test model string representations"""
        backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
        
        self.assertEqual(str(backup), 'Test Backup')
        self.assertEqual(str(backup.backup_id), str(backup.backup_id))


class BackupModelQueryTest(TestCase):
    """Test model queries and filtering"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test backups
        self.backup1 = Backup.objects.create(
            name='Backup 1',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user,
            status='completed'
        )
        
        self.backup2 = Backup.objects.create(
            name='Backup 2',
            backup_type='incremental',
            storage_type='s3',
            database_name='test_db',
            created_by=self.user,
            status='failed'
        )
        
        self.backup3 = Backup.objects.create(
            name='Backup 3',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user,
            status='completed',
            expires_at=timezone.now() - timedelta(days=1),
            is_permanent=False
        )
    
    def test_filter_by_status(self):
        """Test filtering by status"""
        completed_backups = Backup.objects.filter(status='completed')
        failed_backups = Backup.objects.filter(status='failed')
        
        self.assertIn(self.backup1, completed_backups)
        self.assertIn(self.backup2, failed_backups)
        self.assertNotIn(self.backup2, completed_backups)
    
    def test_filter_by_backup_type(self):
        """Test filtering by backup type"""
        full_backups = Backup.objects.filter(backup_type='full')
        incremental_backups = Backup.objects.filter(backup_type='incremental')
        
        self.assertIn(self.backup1, full_backups)
        self.assertIn(self.backup3, full_backups)
        self.assertIn(self.backup2, incremental_backups)
        self.assertNotIn(self.backup1, incremental_backups)
    
    def test_filter_by_storage_type(self):
        """Test filtering by storage type"""
        local_backups = Backup.objects.filter(storage_type='local')
        s3_backups = Backup.objects.filter(storage_type='s3')
        
        self.assertIn(self.backup1, local_backups)
        self.assertIn(self.backup3, local_backups)
        self.assertIn(self.backup2, s3_backups)
        self.assertNotIn(self.backup1, s3_backups)
    
    def test_date_range_filtering(self):
        """Test date range filtering"""
        yesterday = timezone.now() - timedelta(days=1)
        recent_backups = Backup.objects.filter(created_at__gte=yesterday)
        
        self.assertIn(self.backup1, recent_backups)
        self.assertIn(self.backup2, recent_backups)
        self.assertIn(self.backup3, recent_backups)
    
    def test_ordering(self):
        """Test query ordering"""
        # Test ordering by creation date (newest first)
        backups = Backup.objects.all().order_by('-created_at')
        self.assertEqual(backups[0], self.backup3)  # Most recent
        self.assertEqual(backups[2], self.backup1)  # Oldest
        
        # Test ordering by creation date (oldest first)
        backups = Backup.objects.all().order_by('created_at')
        self.assertEqual(backups[0], self.backup1)  # Oldest
        self.assertEqual(backups[2], self.backup3)  # Most recent
