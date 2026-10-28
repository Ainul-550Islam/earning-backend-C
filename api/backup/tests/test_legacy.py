# tests.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta
import json
import uuid

from .models import (
    Backup, BackupSchedule, BackupLog, BackupStorageLocation,
    BackupRestoration, BackupNotificationConfig, RetentionPolicy,
    DeltaBackupTracker
)
from .tasks import (
    backup_database_task, restore_backup_task, cleanup_old_backups_task,
    perform_delta_backup, execute_gfs_retention_policy
)

User = get_user_model()


class BaseBackupTestCase(TestCase):
    """Base test case for backup system"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create storage location
        self.storage_location = BackupStorageLocation.objects.create(
            name='Test Storage',
            storage_type='local',
            is_active=True,
            is_connected=True,
            max_capacity=10737418240,  # 10GB
            used_capacity=5368709120,   # 5GB
            config={'path': '/tmp/backups'}
        )
        
        # Create backup schedule
        self.schedule = BackupSchedule.objects.create(
            name='Test Schedule',
            is_active=True,
            frequency='daily',
            hour=2,
            minute=0,
            backup_type='full',
            storage_type='local',
            created_by=self.user
        )
        
        # Create backup
        self.backup = Backup.objects.create(
            name='Test Backup',
            backup_type='full',
            storage_type='local',
            status='completed',
            file_size=104857600,  # 100MB
            file_hash='abc123',
            database_engine='PostgreSQL',
            database_name='test_db',
            table_count=10,
            row_count=1000,
            duration=300,  # 5 minutes
            created_by=self.user,
            retention_days=30,
            expires_at=timezone.now() + timedelta(days=30),
            is_verified=True,
            is_healthy=True,
            health_score=95
        )
        
        # Create backup log
        self.backup_log = BackupLog.objects.create(
            backup=self.backup,
            level='info',
            message='Test log message',
            details={'test': 'data'}
        )
        
        # Create notification config
        self.notification_config = BackupNotificationConfig.objects.create(
            name='Test Notifications',
            is_active=True,
            channels=['email', 'slack'],
            channel_config={
                'email': {'smtp_server': 'smtp.example.com'},
                'slack': {'webhook_url': 'https://hooks.slack.com/test'}
            },
            notification_types=['success', 'failure'],
            recipients=['admin@example.com'],
            created_by=self.user
        )
        
        # Create retention policy
        self.retention_policy = RetentionPolicy.objects.create(
            name='Test GFS Policy',
            policy_type='gfs',
            is_active=True,
            daily_keep_days=7,
            weekly_keep_weeks=4,
            monthly_keep_months=12,
            yearly_keep_years=3,
            auto_cleanup=True,
            created_by=self.user
        )
        
        # Setup test client
        self.client = Client()
        self.api_client = APIClient()


class BackupModelTests(BaseBackupTestCase):
    """Test backup models"""
    
    def test_backup_creation(self):
        """Test backup creation"""
        self.assertEqual(self.backup.name, 'Test Backup')
        self.assertEqual(self.backup.status, 'completed')
        self.assertEqual(self.backup.backup_type, 'full')
        self.assertTrue(self.backup.is_verified)
        self.assertTrue(self.backup.is_healthy)
        self.assertEqual(self.backup.health_score, 95)
    
    def test_backup_file_size_human(self):
        """Test file size human readable format"""
        human_size = self.backup.file_size_human
        self.assertIn('MB', human_size)
    
    def test_backup_duration_human(self):
        """Test duration human readable format"""
        self.backup.duration = 3665  # 1 hour, 1 minute, 5 seconds
        self.backup.save()
        self.assertIn('1h', self.backup.duration_human)
    
    def test_backup_expiry(self):
        """Test backup expiry"""
        expired_backup = Backup.objects.create(
            name='Expired Backup',
            backup_type='full',
            status='completed',
            expires_at=timezone.now() - timedelta(days=1),
            is_permanent=False
        )
        self.assertTrue(expired_backup.is_expired)
        self.assertFalse(self.backup.is_expired)
    
    def test_backup_health_check(self):
        """Test backup health check method"""
        initial_check_count = self.backup.health_check_count
        self.backup.check_health()
        self.backup.refresh_from_db()
        self.assertEqual(self.backup.health_check_count, initial_check_count + 1)
    
    def test_backup_redundancy(self):
        """Test backup redundancy"""
        redundant_backup = Backup.objects.create(
            name='Redundant Backup',
            backup_type='full',
            storage_type='redundant',
            redundancy_level=2,
            storage_locations=[self.storage_location.id],
            status='completed'
        )
        
        copies = redundant_backup.get_redundant_copies()
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0]['name'], 'Test Storage')
    
    def test_backup_retention_calculation(self):
        """Test backup retention calculation"""
        gfs_backup = Backup.objects.create(
            name='GFS Backup',
            backup_type='full',
            retention_policy='gfs',
            gfs_category='son',
            start_time=timezone.now()
        )
        
        expiry = gfs_backup.calculate_retention_expiry()
        expected_expiry = gfs_backup.start_time + timedelta(days=7)
        self.assertEqual(expiry.date(), expected_expiry.date())
    
    def test_schedule_creation(self):
        """Test schedule creation"""
        self.assertEqual(self.schedule.name, 'Test Schedule')
        self.assertTrue(self.schedule.is_active)
        self.assertEqual(self.schedule.frequency, 'daily')
        self.assertEqual(self.schedule.backup_type, 'full')
    
    def test_storage_location_capacity(self):
        """Test storage location capacity calculations"""
        self.assertEqual(self.storage_location.available_capacity, 5368709120)  # 5GB
        self.assertEqual(self.storage_location.usage_percentage, 50.0)
    
    def test_notification_config_quiet_hours(self):
        """Test notification config quiet hours"""
        config = BackupNotificationConfig.objects.create(
            name='Test Quiet Hours',
            is_active=True,
            channels=['email'],
            quiet_hours_start='22:00',
            quiet_hours_end='06:00'
        )
        
        # Test should_notify_now logic (simplified)
        self.assertIsNotNone(config.should_notify_now)
    
    def test_retention_policy_cleanup(self):
        """Test retention policy cleanup"""
        backups = self.retention_policy.get_backups_to_cleanup()
        self.assertIsInstance(backups, list)
        
        result = self.retention_policy.execute_cleanup(dry_run=True)
        self.assertEqual(result['action'], 'dry_run')
    
    def test_delta_tracker_stats(self):
        """Test delta tracker statistics"""
        base_backup = Backup.objects.create(
            name='Base Backup',
            backup_type='full',
            status='completed'
        )
        
        tracker = DeltaBackupTracker.objects.create(
            base_backup=base_backup
        )
        
        # Create delta backups
        for i in range(3):
            Backup.objects.create(
                name=f'Delta Backup {i}',
                backup_type='delta',
                delta_base=base_backup,
                status='completed',
                file_size=10485760 * (i + 1)  # 10MB, 20MB, 30MB
            )
        
        tracker.calculate_chain_stats()
        tracker.refresh_from_db()
        
        self.assertEqual(tracker.chain_length, 4)  # Base + 3 deltas
        self.assertEqual(tracker.avg_delta_size, 20971520)  # Average 20MB


class BackupAPITests(APITestCase, BaseBackupTestCase):
    """Test backup API endpoints"""
    
    def setUp(self):
        """Set up API tests"""
        super().setUp()
        self.api_client.force_authenticate(user=self.admin_user)
    
    def test_backup_list_api(self):
        """Test backup list API"""
        url = reverse('backup-list')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
    
    def test_backup_detail_api(self):
        """Test backup detail API"""
        url = reverse('backup-detail', args=[self.backup.id])
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Backup')
    
    def test_backup_create_api(self):
        """Test backup creation API"""
        url = reverse('backup-list')
        data = {
            'name': 'API Created Backup',
            'backup_type': 'full',
            'storage_type': 'local',
            'status': 'pending',
            'database_engine': 'PostgreSQL',
            'database_name': 'test_db'
        }
        response = self.api_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'API Created Backup')
    
    def test_backup_update_api(self):
        """Test backup update API"""
        url = reverse('backup-detail', args=[self.backup.id])
        data = {'description': 'Updated description'}
        response = self.api_client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.backup.refresh_from_db()
        self.assertEqual(self.backup.description, 'Updated description')
    
    def test_backup_delete_api(self):
        """Test backup delete API"""
        backup = Backup.objects.create(
            name='To Delete',
            backup_type='full',
            status='completed'
        )
        
        url = reverse('backup-detail', args=[backup.id])
        response = self.api_client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Backup.objects.filter(id=backup.id).exists())
    
    def test_backup_verify_api(self):
        """Test backup verification API"""
        url = reverse('backup-verify', args=[self.backup.id])
        response = self.api_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_backup_health_check_api(self):
        """Test backup health check API"""
        url = reverse('backup-health-check', args=[self.backup.id])
        response = self.api_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_start_backup_api(self):
        """Test start backup API"""
        url = reverse('start-backup')
        data = {
            'type': 'full',
            'storage': 'local',
            'tables': ['users', 'products']
        }
        response = self.api_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_cancel_backup_api(self):
        """Test cancel backup API"""
        running_backup = Backup.objects.create(
            name='Running Backup',
            backup_type='full',
            status='running'
        )
        
        url = reverse('cancel-backup', args=[running_backup.id])
        response = self.api_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        running_backup.refresh_from_db()
        self.assertEqual(running_backup.status, 'cancelled')
    
    def test_maintenance_mode_api(self):
        """Test maintenance mode API"""
        url = reverse('maintenance-mode')
        
        # Enable maintenance mode
        data = {'enable': True, 'reason': 'Testing'}
        response = self.api_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['maintenance_mode'])
        
        # Disable maintenance mode
        data = {'enable': False}
        response = self.api_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['maintenance_mode'])
    
    def test_backup_progress_api(self):
        """Test backup progress API"""
        url = reverse('backup-progress', args=[self.backup.id])
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
    
    def test_backup_status_api(self):
        """Test backup status API"""
        url = reverse('backup-status')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('running', response.data)
        self.assertIn('pending', response.data)
        self.assertIn('failed_24h', response.data)
    
    def test_schedule_list_api(self):
        """Test schedule list API"""
        url = reverse('schedule-list')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_storage_location_list_api(self):
        """Test storage location list API"""
        url = reverse('storage-location-list')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_notification_config_api(self):
        """Test notification config API"""
        url = reverse('notification-config-list')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retention_policy_api(self):
        """Test retention policy API"""
        url = reverse('retention-policy-list')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_backup_logs_api(self):
        """Test backup logs API"""
        url = reverse('backup-logs', args=[self.backup.id])
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_backup_download_api(self):
        """Test backup download API"""
        url = reverse('backup-download', args=[self.backup.id])
        response = self.api_client.get(url)
        # This will redirect or return file, depends on implementation
        self.assertIn(response.status_code, [200, 302, 404])
    
    def test_create_redundant_copy_api(self):
        """Test create redundant copy API"""
        url = reverse('create-redundant', args=[self.backup.id])
        response = self.api_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cleanup_old_backups_api(self):
        """Test cleanup old backups API"""
        url = reverse('cleanup-old-backups')
        response = self.api_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_send_test_notification_api(self):
        """Test send test notification API"""
        url = reverse('test-notification', args=[self.backup.id])
        response = self.api_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BackupTaskTests(BaseBackupTestCase):
    """Test backup tasks"""
    
    def test_backup_database_task(self):
        """Test backup database task"""
        result = backup_database_task(
            backup_id=str(self.backup.id),
            backup_type='full',
            tables=['users', 'products'],
            user_id=str(self.user.id)
        )
        self.assertTrue(result['success'])
    
    def test_restore_backup_task(self):
        """Test restore backup task"""
        result = restore_backup_task(
            backup_id=str(self.backup.id),
            restore_type='full',
            user_id=str(self.user.id)
        )
        self.assertTrue(result['success'])
    
    def test_cleanup_old_backups_task(self):
        """Test cleanup old backups task"""
        result = cleanup_old_backups_task(user_id=str(self.user.id))
        self.assertTrue(result['success'])
    
    def test_perform_delta_backup(self):
        """Test delta backup task"""
        base_backup = Backup.objects.create(
            name='Base Backup',
            backup_type='full',
            status='completed'
        )
        
        result = perform_delta_backup(
            backup_id=str(self.backup.id),
            base_backup_id=str(base_backup.id)
        )
        self.assertTrue(result['success'])
    
    def test_execute_gfs_retention_policy(self):
        """Test GFS retention policy task"""
        result = execute_gfs_retention_policy(policy_id=str(self.retention_policy.id))
        self.assertTrue(result['success'])


class BackupAdminTests(BaseBackupTestCase):
    """Test backup admin views"""
    
    def setUp(self):
        """Set up admin tests"""
        super().setUp()
        self.client.login(username='admin', password='adminpass123')
    
    def test_backup_dashboard_view(self):
        """Test backup dashboard view"""
        url = reverse('backup_admin:backup_dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Backup & Recovery Dashboard')
    
    def test_backup_analytics_view(self):
        """Test backup analytics view"""
        url = reverse('backup_admin:backup_analytics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Backup Analytics')
    
    def test_storage_management_view(self):
        """Test storage management view"""
        url = reverse('backup_admin:storage_management')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Storage Management')
    
    def test_run_backup_view(self):
        """Test run backup view"""
        url = reverse('backup_admin:run_backup')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Run Backup')
    
    def test_restore_backup_view(self):
        """Test restore backup view"""
        url = reverse('backup_admin:restore_backup')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Restore Backup')
    
    def test_backup_monitoring_view(self):
        """Test backup monitoring view"""
        url = reverse('backup_admin:backup_monitoring')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Backup Monitoring')
    
    def test_schedule_manager_view(self):
        """Test schedule manager view"""
        url = reverse('backup_admin:schedule_manager')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schedule Manager')
    
    def test_backup_download_view(self):
        """Test backup download view"""
        url = reverse('backup_admin:backup_download', args=[self.backup.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect or file download
    
    def test_backup_verify_view(self):
        """Test backup verify view"""
        url = reverse('backup_admin:backup_verify', args=[self.backup.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect back
    
    def test_backup_clone_view(self):
        """Test backup clone view"""
        url = reverse('backup_admin:backup_clone', args=[self.backup.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to edit clone


class BackupIntegrationTests(BaseBackupTestCase):
    """Integration tests for backup system"""
    
    def test_complete_backup_flow(self):
        """Test complete backup flow"""
        # 1. Create a backup
        backup = Backup.objects.create(
            name='Integration Test Backup',
            backup_type='full',
            storage_type='local',
            status='pending',
            database_engine='PostgreSQL',
            database_name='integration_test',
            created_by=self.user
        )
        
        # 2. Start backup task
        result = backup_database_task(
            backup_id=str(backup.id),
            backup_type='full',
            tables=['*'],
            user_id=str(self.user.id)
        )
        self.assertTrue(result['success'])
        
        # 3. Verify backup
        backup.refresh_from_db()
        backup.is_verified = True
        backup.verified_by = self.admin_user
        backup.verified_at = timezone.now()
        backup.save()
        
        # 4. Perform health check
        backup.check_health()
        backup.refresh_from_db()
        self.assertTrue(backup.is_healthy)
        
        # 5. Create redundant copies
        backup.storage_type = 'redundant'
        backup.redundancy_level = 2
        backup.storage_locations = [self.storage_location.id]
        backup.save()
        
        # 6. Create restoration record
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',
            status='completed',
            restore_point=timezone.now(),
            initiated_by=self.user,
            success=True,
            verification_passed=True
        )
        
        # 7. Verify all components
        self.assertEqual(backup.status, 'completed')
        self.assertTrue(backup.is_verified)
        self.assertTrue(backup.is_healthy)
        self.assertEqual(backup.storage_type, 'redundant')
        self.assertTrue(restoration.success)
        self.assertTrue(restoration.verification_passed)
    
    def test_error_handling(self):
        """Test error handling in backup system"""
        # Create a backup that will fail
        backup = Backup.objects.create(
            name='Failing Backup',
            backup_type='full',
            status='pending'
        )
        
        # Simulate a failure
        backup.status = 'failed'
        backup.last_error = 'Test error'
        backup.error_traceback = 'Traceback...'
        backup.save()
        
        # Test retry logic
        self.assertEqual(backup.retry_count, 0)
        
        # Create a new backup for retry
        new_backup = Backup.objects.create(
            name='Retry: Failing Backup',
            backup_type=backup.backup_type,
            storage_type=backup.storage_type,
            status='pending',
            parent_backup=backup
        )
        
        self.assertEqual(new_backup.parent_backup, backup)
    
    def test_performance_metrics(self):
        """Test performance metrics calculation"""
        backup = Backup.objects.create(
            name='Performance Test Backup',
            backup_type='full',
            status='completed',
            start_time=timezone.now() - timedelta(minutes=5),
            end_time=timezone.now(),
            original_size=1073741824,  # 1GB
            compressed_size=536870912,  # 500MB
            file_size=536870912
        )
        
        # Save to trigger calculations
        backup.save()
        
        # Check calculated fields
        self.assertIsNotNone(backup.duration)
        self.assertGreater(backup.duration, 0)
        self.assertEqual(backup.compression_ratio, 50.0)
        self.assertGreater(backup.backup_speed, 0)
        self.assertGreater(backup.upload_speed, 0)
    
    def test_backup_chain_integrity(self):
        """Test backup chain integrity"""
        # Create base backup
        base_backup = Backup.objects.create(
            name='Base Backup',
            backup_type='full',
            status='completed'
        )
        
        # Create delta chain
        delta1 = Backup.objects.create(
            name='Delta 1',
            backup_type='delta',
            delta_base=base_backup,
            status='completed'
        )
        
        delta2 = Backup.objects.create(
            name='Delta 2',
            backup_type='delta',
            delta_base=delta1,
            status='completed'
        )
        
        # Verify chain
        self.assertEqual(delta1.delta_base, base_backup)
        self.assertEqual(delta2.delta_base, delta1)
        
        # Test tracker
        tracker = DeltaBackupTracker.objects.create(base_backup=base_backup)
        tracker.calculate_chain_stats()
        
        self.assertEqual(tracker.chain_length, 3)  # Base + 2 deltas


class BackupSecurityTests(BaseBackupTestCase):
    """Security tests for backup system"""
    
    def test_unauthenticated_access(self):
        """Test unauthenticated access to APIs"""
        self.api_client.logout()
        
        # Try to access protected endpoints
        urls = [
            reverse('backup-list'),
            reverse('start-backup'),
            reverse('maintenance-mode'),
        ]
        
        for url in urls:
            response = self.api_client.get(url) if 'list' in url else self.api_client.post(url, {})
            self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
    
    def test_unauthorized_user_access(self):
        """Test unauthorized user access"""
        regular_user = User.objects.create_user(
            username='regular',
            password='regularpass'
        )
        self.api_client.force_authenticate(user=regular_user)
        
        # Regular users shouldn't be able to access admin endpoints
        url = reverse('maintenance-mode')
        response = self.api_client.post(url, {'enable': True})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_csrf_protection(self):
        """Test CSRF protection"""
        client = Client(enforce_csrf_checks=True)
        client.login(username='admin', password='adminpass123')
        
        # Try to post without CSRF token
        url = reverse('backup_admin:run_backup')
        response = client.post(url, {})
        self.assertEqual(response.status_code, 403)  # CSRF failure
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        malicious_input = "'; DROP TABLE backup_backup; --"
        
        # Try to create backup with malicious input
        url = reverse('backup-list')
        data = {
            'name': malicious_input,
            'backup_type': 'full',
            'storage_type': 'local'
        }
        
        response = self.api_client.post(url, data, format='json')
        
        # Should either reject or sanitize input
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED])
        
        if response.status_code == 201:
            # Input should be sanitized, not executed
            backup = Backup.objects.get(id=response.data['id'])
            self.assertEqual(backup.name, malicious_input)  # Stored as is, but not executed
    
    def test_file_path_traversal(self):
        """Test file path traversal prevention"""
        malicious_path = '../../../etc/passwd'
        
        backup = Backup.objects.create(
            name='Path Traversal Test',
            backup_type='full',
            file_path=malicious_path
        )
        
        # File path should be stored as is, but access should be restricted
        self.assertEqual(backup.file_path, malicious_path)
        
        # Try to download (would be blocked by Django's security)
        url = reverse('backup-download', args=[backup.id])
        response = self.api_client.get(url)
        self.assertIn(response.status_code, [404, 403])  # Should not allow traversal


class BackupConcurrencyTests(BaseBackupTestCase):
    """Concurrency tests for backup system"""
    
    def test_concurrent_backup_creation(self):
        """Test concurrent backup creation"""
        import threading
        
        backup_ids = []
        errors = []
        
        def create_backup(index):
            try:
                backup = Backup.objects.create(
                    name=f'Concurrent Backup {index}',
                    backup_type='full',
                    status='pending'
                )
                backup_ids.append(backup.id)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple backups concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_backup, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no errors and all backups created
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(backup_ids), 10)
        self.assertEqual(Backup.objects.filter(name__startswith='Concurrent Backup').count(), 10)
    
    def test_concurrent_backup_updates(self):
        """Test concurrent backup updates"""
        import threading
        from django.db import transaction
        
        backup = Backup.objects.create(
            name='Concurrent Update Test',
            backup_type='full',
            status='pending',
            retry_count=0
        )
        
        update_count = {'success': 0, 'failed': 0}
        
        def update_backup():
            try:
                with transaction.atomic():
                    b = Backup.objects.select_for_update().get(id=backup.id)
                    b.retry_count += 1
                    b.save()
                    update_count['success'] += 1
            except Exception:
                update_count['failed'] += 1
        
        # Update concurrently
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=update_backup)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify results
        backup.refresh_from_db()
        self.assertEqual(backup.retry_count, 20)
        self.assertEqual(update_count['success'], 20)
        self.assertEqual(update_count['failed'], 0)


class BackupEdgeCaseTests(BaseBackupTestCase):
    """Edge case tests for backup system"""
    
    def test_empty_backup(self):
        """Test backup with no data"""
        backup = Backup.objects.create(
            name='Empty Backup',
            backup_type='full',
            status='completed',
            file_size=0,
            table_count=0,
            row_count=0
        )
        
        self.assertEqual(backup.file_size, 0)
        self.assertEqual(backup.table_count, 0)
        self.assertEqual(backup.row_count, 0)
        self.assertEqual(backup.file_size_human, '0 bytes')
    
    def test_very_large_backup(self):
        """Test backup with very large size"""
        large_size = 10 * 1024 * 1024 * 1024  # 10GB
        
        backup = Backup.objects.create(
            name='Large Backup',
            backup_type='full',
            status='completed',
            file_size=large_size
        )
        
        human_size = backup.file_size_human
        self.assertIn('GB', human_size)
    
    def test_backup_with_special_characters(self):
        """Test backup with special characters in name"""
        special_name = "Backup with 'quotes', & ampersands, <tags> and emoji [START]"
        
        backup = Backup.objects.create(
            name=special_name,
            backup_type='full',
            status='pending'
        )
        
        self.assertEqual(backup.name, special_name)
    
    def test_backup_with_json_fields(self):
        """Test backup with complex JSON fields"""
        complex_json = {
            'metadata': {
                'version': '1.0',
                'features': ['encryption', 'compression', 'verification'],
                'settings': {
                    'chunk_size': 1048576,
                    'parallel_workers': 4,
                    'timeout': 3600
                }
            },
            'tags': ['production', 'critical', 'database'],
            'custom_fields': {
                'department': 'IT',
                'project': 'Earning Platform',
                'owner': 'admin@example.com'
            }
        }
        
        backup = Backup.objects.create(
            name='JSON Test Backup',
            backup_type='full',
            status='completed',
            metadata=complex_json,
            tags=complex_json['tags']
        )
        
        self.assertIsInstance(backup.metadata, dict)
        self.assertIn('metadata', backup.metadata)
        self.assertIn('tags', backup.metadata)
        self.assertEqual(len(backup.tags), 3)
    
    def test_backup_with_invalid_data(self):
        """Test backup creation with invalid data"""
        # Test with invalid backup type
        with self.assertRaises(Exception):
            Backup.objects.create(
                name='Invalid Backup',
                backup_type='invalid_type',
                status='pending'
            )
        
        # Test with negative file size
        backup = Backup.objects.create(
            name='Negative Size Backup',
            backup_type='full',
            status='completed',
            file_size=-100
        )
        
        # Should allow negative but handle in business logic
        self.assertEqual(backup.file_size, -100)
    
    def test_backup_cleanup_edge_cases(self):
        """Test backup cleanup edge cases"""
        # Create permanent backup that shouldn't be cleaned up
        permanent_backup = Backup.objects.create(
            name='Permanent Backup',
            backup_type='full',
            status='completed',
            is_permanent=True,
            expires_at=timezone.now() - timedelta(days=365)  # Expired long ago
        )
        
        self.assertTrue(permanent_backup.is_expired)
        self.assertTrue(permanent_backup.is_permanent)
        
        # Create backup with auto-cleanup disabled
        no_cleanup_backup = Backup.objects.create(
            name='No Cleanup Backup',
            backup_type='full',
            status='completed',
            auto_cleanup_enabled=False,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertTrue(no_cleanup_backup.is_expired)
        self.assertFalse(no_cleanup_backup.auto_cleanup_enabled)
        self.assertFalse(no_cleanup_backup.should_auto_cleanup)


# Run tests with: python manage.py test backup.tests