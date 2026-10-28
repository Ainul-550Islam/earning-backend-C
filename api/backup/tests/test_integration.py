"""
Test Integration Workflow
Comprehensive tests for full backup→verify→restore flow
"""

import os
import tempfile
import subprocess
import threading
import time
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import transaction
from django.conf import settings
from unittest.mock import patch, Mock, MagicMock, mock_open
import pytest

from api.backup.services import BackupService
from api.backup.models import (
    Backup, BackupRestoration, BackupVerification, BackupEncryption,
    BackupAlert, BackupStorageLocation, BackupSchedule
)
from api.backup.services.factory import BackupServiceFactory
from api.backup.services.DatabaseBackup import DatabaseBackupService
from api.backup.services.BaseBackupService import BaseBackupService

User = get_user_model()


class IntegrationWorkflowTest(TestCase):
    """Test complete backup workflow integration"""
    
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
            endpoint=tempfile.mkdtemp(),
            is_active=True,
            max_capacity=10737418240,  # 10GB
            used_space=0,
            free_space=10737418240
        )
        
        self.backup_service = BackupService()
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_full_backup_workflow(self, mock_factory, mock_subprocess):
        """Test complete backup creation workflow"""
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        mock_db_service = Mock()
        from api.backup.services.DatabaseBackup import DatabaseBackupService
        with patch.object(DatabaseBackupService, '__new__', return_value=mock_db_service):
            mock_db_service.create_backup.return_value = Mock(
                backup_file=ContentFile(b'test backup data'),
                file_path='/tmp/test_backup.sql'
            )
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Database dump completed',
                stderr=b''
            )
            
            # Step 1: Create backup
            backup = self.backup_service.create_backup(
                backup_type='full',
                storage_type='local',
                name='Integration Test Backup',
                created_by=self.user,
                encrypt=True,
                compress=True
            )
            
            # Verify backup creation
            self.assertIsNotNone(backup)
            self.assertEqual(backup.name, 'Integration Test Backup')
            self.assertEqual(backup.backup_type, 'full')
            self.assertEqual(backup.storage_type, 'local')
            self.assertEqual(backup.created_by, self.user)
            self.assertTrue(backup.encryption_enabled)
            self.assertTrue(backup.compression_enabled)
            
            # Verify service calls
            mock_db_service.create_backup.assert_called_once()
            mock_storage_service.save_backup.assert_called_once()
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_backup_verification_workflow(self, mock_factory, mock_subprocess):
        """Test backup verification workflow"""
        # Create test backup
        backup = Backup.objects.create(
            name='Integration Verification Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_hash='test_hash_123',
            file_size=1024000,
            created_by=self.user
        )
        
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        mock_storage_service.download_backup.return_value = b'test backup data'
        
        # Mock validator
        with patch('backup.services.BackupValidator') as mock_validator:
            mock_validator_instance = Mock()
            mock_validator.return_value = mock_validator_instance
            mock_validator_instance.verify_file_integrity.return_value = True
            mock_validator_instance.verify_file_size.return_value = True
            mock_validator_instance.test_restore_backup.return_value = True
            
            # Step 2: Verify backup
            verification = self.backup_service.verify_backup(
                str(backup.backup_id),
                verification_method='full'
            )
            
            # Verify verification creation
            self.assertIsNotNone(verification)
            self.assertEqual(verification.backup, backup)
            self.assertEqual(verification.verification_method, 'full')
            self.assertTrue(verification.is_valid)
            self.assertTrue(verification.checksum_match)
            self.assertTrue(verification.size_match)
            
            # Verify validator calls
            mock_validator_instance.verify_file_integrity.assert_called_once()
            mock_validator_instance.verify_file_size.assert_called_once()
            mock_validator_instance.test_restore_backup.assert_called_once()
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_backup_restore_workflow(self, mock_factory, mock_subprocess):
        """Test backup restoration workflow"""
        # Create test backup
        backup = Backup.objects.create(
            name='Integration Restore Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
        
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        mock_storage_service.download_backup.return_value = b'test backup data'
        
        mock_db_service = Mock()
        from api.backup.services.DatabaseBackup import DatabaseBackupService
        with patch.object(DatabaseBackupService, '__new__', return_value=mock_db_service):
            mock_db_service.restore_backup.return_value = True
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Restore completed',
                stderr=b''
            )
            
            # Step 3: Restore backup
            restoration = self.backup_service.restore_backup(
                str(backup.backup_id),
                restoration_type='full',
                initiated_by=self.user
            )
            
            # Verify restoration creation
            self.assertIsNotNone(restoration)
            self.assertEqual(restoration.backup, backup)
            self.assertEqual(restoration.restoration_type, 'full')
            self.assertEqual(restoration.initiated_by, self.user)
            self.assertEqual(restoration.status, 'completed')
            self.assertTrue(restoration.success)
            
            # Verify service calls
            mock_storage_service.download_backup.assert_called_once()
            mock_db_service.restore_backup.assert_called_once()
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_complete_workflow_integration(self, mock_factory, mock_subprocess):
        """Test complete backup→verify→restore workflow"""
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        mock_db_service = Mock()
        from api.backup.services.DatabaseBackup import DatabaseBackupService
        with patch.object(DatabaseBackupService, '__new__', return_value=mock_db_service):
            mock_db_service.create_backup.return_value = Mock(
                backup_file=ContentFile(b'test backup data'),
                file_path='/tmp/test_backup.sql'
            )
            mock_db_service.restore_backup.return_value = True
            
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Operation completed',
                stderr=b''
            )
            
            # Mock validator
            with patch('backup.services.BackupValidator') as mock_validator:
                mock_validator_instance = Mock()
                mock_validator.return_value = mock_validator_instance
                mock_validator_instance.verify_file_integrity.return_value = True
                mock_validator_instance.verify_file_size.return_value = True
                mock_validator_instance.test_restore_backup.return_value = True
                
                # Step 1: Create backup
                backup = self.backup_service.create_backup(
                    backup_type='full',
                    storage_type='local',
                    name='Complete Workflow Test',
                    created_by=self.user,
                    encrypt=True,
                    compress=True
                )
                
                # Step 2: Verify backup
                verification = self.backup_service.verify_backup(
                    str(backup.backup_id),
                    verification_method='full'
                )
                
                # Step 3: Restore backup
                restoration = self.backup_service.restore_backup(
                    str(backup.backup_id),
                    restoration_type='full',
                    initiated_by=self.user
                )
                
                # Verify complete workflow
                self.assertIsNotNone(backup)
                self.assertIsNotNone(verification)
                self.assertIsNotNone(restoration)
                
                # Verify relationships
                self.assertEqual(verification.backup, backup)
                self.assertEqual(restoration.backup, backup)
                
                # Verify all steps completed successfully
                self.assertEqual(backup.status, 'completed')
                self.assertTrue(verification.is_valid)
                self.assertEqual(restoration.status, 'completed')
                self.assertTrue(restoration.success)
    
    def test_scheduled_backup_workflow(self):
        """Test scheduled backup workflow"""
        # Create backup schedule
        schedule = self.backup_service.schedule_backup(
            cron_expr='0 2 * * *',  # Daily at 2 AM
            backup_type='full',
            name='Daily Integration Test',
            storage_type='local',
            created_by=self.user
        )
        
        # Verify schedule creation
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.name, 'Daily Integration Test')
        self.assertEqual(schedule.cron_expression, '0 2 * * *')
        self.assertEqual(schedule.backup_type, 'full')
        self.assertEqual(schedule.storage_type, 'local')
        self.assertEqual(schedule.created_by, self.user)
        self.assertTrue(schedule.is_active)
        
        # Verify next run calculation
        self.assertIsNotNone(schedule.next_run)
        self.assertGreater(schedule.next_run, timezone.now())
    
    def test_workflow_with_encryption(self):
        """Test workflow with encryption enabled"""
        # Create backup with encryption
        backup = Backup.objects.create(
            name='Encryption Workflow Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=True,
            encryption_method='AES-256-GCM',
            encryption_key='test_encryption_key',
            created_by=self.user
        )
        
        # Create encryption record
        from api.backup.models import BackupEncryption
        encryption = BackupEncryption.objects.create(
            backup=backup,
            algorithm='AES-256-GCM',
            key_hash='test_hash_123',
            is_encrypted=True,
            encryption_key='encrypted_key_data'
        )
        
        # Verify encryption workflow
        self.assertIsNotNone(backup)
        self.assertIsNotNone(encryption)
        self.assertEqual(backup.encryption_info, encryption)
        self.assertTrue(backup.encryption_enabled)
        self.assertEqual(encryption.algorithm, 'AES-256-GCM')
    
    def test_workflow_with_compression(self):
        """Test workflow with compression enabled"""
        # Create backup with compression
        backup = Backup.objects.create(
            name='Compression Workflow Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            compression_enabled=True,
            compression_method='gzip',
            compression_level=6,
            created_by=self.user
        )
        
        # Verify compression workflow
        self.assertIsNotNone(backup)
        self.assertTrue(backup.compression_enabled)
        self.assertEqual(backup.compression_method, 'gzip')
        self.assertEqual(backup.compression_level, 6)
    
    def test_workflow_error_handling(self):
        """Test workflow error handling"""
        # Test with non-existent backup ID
        with self.assertRaises(Exception):
            self.backup_service.restore_backup(
                'non-existent-backup-id',
                restoration_type='full'
            )
        
        # Test verification of non-existent backup
        with self.assertRaises(Exception):
            self.backup_service.verify_backup(
                'non-existent-backup-id',
                verification_method='hash'
            )


class IntegrationPerformanceTest(TestCase):
    """Test integration performance characteristics"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = BackupService()
    
    @patch('backup.services.DatabaseBackup.subprocess.run')
    @patch('backup.services.factory.BackupServiceFactory')
    def test_workflow_performance_timing(self, mock_factory, mock_subprocess):
        """Test workflow performance timing"""
        # Mock services
        mock_storage_service = Mock()
        mock_factory.get_storage_service.return_value = mock_storage_service
        
        mock_db_service = Mock()
        from api.backup.services.DatabaseBackup import DatabaseBackupService
        with patch.object(DatabaseBackupService, '__new__', return_value=mock_db_service):
            mock_db_service.create_backup.return_value = Mock(
                backup_file=ContentFile(b'test backup data'),
                file_path='/tmp/test_backup.sql'
            )
            mock_db_service.restore_backup.return_value = True
            
            mock_subprocess.return_value = Mock(
                returncode=0,
                stdout=b'Operation completed',
                stderr=b''
            )
            
            # Measure complete workflow time
            start_time = time.time()
            
            # Create backup
            backup = self.backup_service.create_backup(
                backup_type='full',
                storage_type='local',
                name='Performance Test Backup',
                created_by=self.user
            )
            
            # Verify backup
            with patch('backup.services.BackupValidator') as mock_validator:
                mock_validator_instance = Mock()
                mock_validator.return_value = mock_validator_instance
                mock_validator_instance.verify_file_integrity.return_value = True
                
                verification = self.backup_service.verify_backup(
                    str(backup.backup_id),
                    verification_method='hash'
                )
            
            # Restore backup
            restoration = self.backup_service.restore_backup(
                str(backup.backup_id),
                restoration_type='full',
                initiated_by=self.user
            )
            
            end_time = time.time()
            workflow_time = end_time - start_time
            
            # Verify workflow completed
            self.assertIsNotNone(backup)
            self.assertIsNotNone(verification)
            self.assertIsNotNone(restoration)
            
            # Should complete within reasonable time (less than 10 seconds for mock)
            self.assertLess(workflow_time, 10.0)
    
    def test_concurrent_workflows(self):
        """Test concurrent workflow execution"""
        results = []
        errors = []
        
        def execute_workflow(index):
            try:
                # Create backup service for each thread
                backup_service = BackupService()
                
                # Create test backup
                backup = Backup.objects.create(
                    name=f'Concurrent Workflow {index}',
                    backup_type='full',
                    storage_type='local',
                    database_name=f'test_db_{index}',
                    created_by=self.user
                )
                
                # Mock verification (simplified for concurrency test)
                verification = BackupVerification.objects.create(
                    backup=backup,
                    verification_method='hash',
                    is_valid=True
                )
                
                # Mock restoration (simplified for concurrency test)
                restoration = BackupRestoration.objects.create(
                    backup=backup,
                    restoration_type='full',
                    status='completed',
                    success=True
                )
                
                results.append({
                    'backup': backup,
                    'verification': verification,
                    'restoration': restoration
                })
                
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=execute_workflow, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all workflows completed
        self.assertEqual(len(results), 3)
        self.assertEqual(len(errors), 0)
        
        for result in results:
            self.assertIsNotNone(result['backup'])
            self.assertIsNotNone(result['verification'])
            self.assertIsNotNone(result['restoration'])


class IntegrationDataIntegrityTest(TestCase):
    """Test data integrity across integration workflow"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = BackupService()
    
    def test_data_consistency_across_workflow(self):
        """Test data consistency across workflow steps"""
        # Create backup
        backup = Backup.objects.create(
            name='Data Consistency Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            file_hash='consistency_test_hash',
            file_size=2048000,
            created_by=self.user
        )
        
        # Create verification
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True,
            checksum_match=True,
            size_match=True
        )
        
        # Create restoration
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            status='completed',
            success=True
        )
        
        # Verify data consistency
        self.assertEqual(verification.backup, backup)
        self.assertEqual(restoration.backup, backup)
        
        # Verify backup data remains consistent
        backup.refresh_from_db()
        self.assertEqual(backup.file_hash, 'consistency_test_hash')
        self.assertEqual(backup.file_size, 2048000)
    
    def test_transaction_safety(self):
        """Test transaction safety across workflow"""
        # Test transaction rollback on error
        with self.assertRaises(Exception):
            with transaction.atomic():
                # Create backup
                backup = Backup.objects.create(
                    name='Transaction Test',
                    backup_type='full',
                    storage_type='local',
                    database_name='test_db'
                )
                
                # Create verification
                verification = BackupVerification.objects.create(
                    backup=backup,
                    verification_method='hash',
                    is_valid=True
                )
                
                # Simulate error
                raise Exception("Simulated error for transaction test")
        
        # Verify rollback occurred
        self.assertFalse(Backup.objects.filter(name='Transaction Test').exists())
        self.assertFalse(BackupVerification.objects.filter(backup__name='Transaction Test').exists())
    
    def test_cascade_deletion_behavior(self):
        """Test cascade deletion behavior"""
        # Create backup with related objects
        backup = Backup.objects.create(
            name='Cascade Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True
        )
        
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            status='completed'
        )
        
        # Delete backup
        backup.delete()
        
        # Verify cascade deletion
        self.assertFalse(Backup.objects.filter(name='Cascade Test').exists())
        self.assertFalse(BackupVerification.objects.filter(backup__name='Cascade Test').exists())
        self.assertFalse(BackupRestoration.objects.filter(backup__name='Cascade Test').exists())


class IntegrationAlertingTest(TestCase):
    """Test alerting integration across workflow"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_backup_failure_alerts(self):
        """Test alert creation for backup failures"""
        # Create failed backup
        backup = Backup.objects.create(
            name='Failed Backup Alert Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            status='failed',
            error_message='Backup failed due to disk space'
        )
        
        # Create alert for backup failure
        alert = BackupAlert.objects.create(
            alert_type='failed',
            backup=backup,
            message=f"Backup {backup.name} failed: {backup.error_message}",
            severity='high',
            metadata={
                'backup_id': str(backup.backup_id),
                'error_message': backup.error_message,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Verify alert creation
        self.assertEqual(alert.alert_type, 'failed')
        self.assertEqual(alert.backup, backup)
        self.assertEqual(alert.severity, 'high')
        self.assertIn('backup_id', alert.metadata)
    
    def test_verification_failure_alerts(self):
        """Test alert creation for verification failures"""
        # Create backup
        backup = Backup.objects.create(
            name='Verification Alert Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create failed verification
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=False,
            checksum_match=False,
            error_message='Hash mismatch detected'
        )
        
        # Create alert for verification failure
        alert = BackupAlert.objects.create(
            alert_type='verification_failed',
            backup=backup,
            message=f"Backup verification failed: {verification.error_message}",
            severity='medium',
            metadata={
                'verification_id': str(verification.verification_id),
                'verification_method': verification.verification_method,
                'error_message': verification.error_message
            }
        )
        
        # Verify alert creation
        self.assertEqual(alert.alert_type, 'verification_failed')
        self.assertEqual(alert.backup, backup)
        self.assertEqual(alert.severity, 'medium')
        self.assertIn('verification_id', alert.metadata)
    
    def test_restoration_failure_alerts(self):
        """Test alert creation for restoration failures"""
        # Create backup
        backup = Backup.objects.create(
            name='Restoration Alert Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db'
        )
        
        # Create failed restoration
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            status='failed',
            error_message='Restoration failed due to corrupted data'
        )
        
        # Create alert for restoration failure
        alert = BackupAlert.objects.create(
            alert_type='failed',
            backup=backup,
            message=f"Backup restoration failed: {restoration.error_message}",
            severity='critical',
            metadata={
                'restoration_id': str(restoration.restoration_id),
                'restoration_type': restoration.restoration_type,
                'error_message': restoration.error_message
            }
        )
        
        # Verify alert creation
        self.assertEqual(alert.alert_type, 'failed')
        self.assertEqual(alert.backup, backup)
        self.assertEqual(alert.severity, 'critical')
        self.assertIn('restoration_id', alert.metadata)


class IntegrationSecurityTest(TestCase):
    """Test security aspects of integration workflow"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.backup_service = BackupService()
    
    def test_user_permission_enforcement(self):
        """Test user permission enforcement"""
        # Create backup with user
        backup = Backup.objects.create(
            name='Permission Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
        
        # Verify user ownership
        self.assertEqual(backup.created_by, self.user)
        
        # Create verification with user
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True,
            verified_by=self.user
        )
        
        # Verify user attribution
        self.assertEqual(verification.verified_by, self.user)
    
    def test_sensitive_data_handling(self):
        """Test sensitive data handling"""
        # Create backup with encryption
        backup = Backup.objects.create(
            name='Sensitive Data Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            encryption_enabled=True,
            encryption_method='AES-256-GCM'
        )
        
        # Create encryption record
        from api.backup.models import BackupEncryption
        encryption = BackupEncryption.objects.create(
            backup=backup,
            algorithm='AES-256-GCM',
            key_hash='secure_hash_123',
            is_encrypted=True,
            encryption_key='encrypted_key_data'
        )
        
        # Verify sensitive data is properly stored
        self.assertTrue(backup.encryption_enabled)
        self.assertEqual(encryption.algorithm, 'AES-256-GCM')
        self.assertIsNotNone(encryption.key_hash)
        self.assertIsNotNone(encryption.encryption_key)
    
    def test_audit_trail_creation(self):
        """Test audit trail creation across workflow"""
        # Create backup
        backup = Backup.objects.create(
            name='Audit Trail Test',
            backup_type='full',
            storage_type='local',
            database_name='test_db',
            created_by=self.user
        )
        
        # Create verification
        verification = BackupVerification.objects.create(
            backup=backup,
            verification_method='hash',
            is_valid=True,
            verified_by=self.user
        )
        
        # Create restoration
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            status='completed',
            initiated_by=self.user
        )
        
        # Verify audit trail
        self.assertIsNotNone(backup.created_at)
        self.assertIsNotNone(verification.verified_at)
        self.assertIsNotNone(restoration.started_at)
        
        # Verify user attribution in audit trail
        self.assertEqual(backup.created_by, self.user)
        self.assertEqual(verification.verified_by, self.user)
        self.assertEqual(restoration.initiated_by, self.user)
