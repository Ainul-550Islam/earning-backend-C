# api/tests/test_backup.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class BackupTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_backup_creation(self):
        from api.backup.models import Backup
        backup = Backup.objects.create(
            name=f'Backup_{uid()}',          # ✅ unique required
            backup_type='manual',
            status='pending',
            database_name='earning_db',      # ✅ required field
        )
        self.assertEqual(backup.backup_type, 'manual')
        self.assertEqual(backup.status, 'pending')

    def test_backup_storage_location(self):
        from api.backup.models import BackupStorageLocation
        location = BackupStorageLocation.objects.create(
            name=f'Storage_{uid()}',         # ✅ unique required
            storage_type='local',            # ✅ choices field
            base_path='/backups/',
        )
        self.assertTrue(location.is_active)  # ✅ property - status=='active'

    def test_backup_schedule(self):
        from api.backup.models import BackupSchedule
        from datetime import time
        schedule = BackupSchedule.objects.create(
            name=f'Schedule_{uid()}',        # ✅ unique required
            frequency='daily',               # ✅ required
            backup_type='full',
            daily_time=time(2, 0),           # ✅ required - 02:00 AM
            scheduled_time=time(2, 0),       # ✅ NOT NULL field
            is_active=True,
        )
        self.assertTrue(schedule.is_active)
        self.assertEqual(schedule.frequency, 'daily')

    def test_backup_log(self):
        from api.backup.models import Backup, BackupLog
        backup = Backup.objects.create(
            name=f'Backup_{uid()}',
            backup_type='manual',
            status='completed',
            database_name='earning_db',
        )
        log = BackupLog.objects.create(
            backup=backup,
            level='info',                    # ✅ LOG_LEVEL_INFO
            category='backup',               # ✅ LOG_CATEGORY_BACKUP
            action='complete',               # ✅ ACTION_COMPLETE
            source='system',                 # ✅ SOURCE_SYSTEM
            message='Backup completed successfully',
        )
        self.assertEqual(log.level, 'info')
        self.assertFalse(log.requires_attention)

    def test_retention_policy(self):
        from api.backup.models import RetentionPolicy
        policy = RetentionPolicy.objects.create(
            name=f'Policy_{uid()}',          # ✅ required
            keep_weekly=True,
            keep_monthly=True,
        )
        self.assertTrue(policy.keep_weekly)

    def test_backup_notification_config(self):
        from api.backup.models import BackupNotificationConfig
        config = BackupNotificationConfig.objects.create(
            name=f'Config_{uid()}',          # ✅ required
            notify_on_failure=True,
        )
        self.assertTrue(config.notify_on_failure)

    def test_backup_restoration(self):
        from api.backup.models import Backup, BackupRestoration
        backup = Backup.objects.create(
            name=f'Backup_{uid()}',
            backup_type='full',
            status='completed',
            database_name='earning_db',
        )
        restoration = BackupRestoration.objects.create(
            backup=backup,
            restoration_type='full',         # ✅ required
            restore_point=timezone.now(),    # ✅ NOT NULL
            initiated_by=self.user,
        )
        self.assertEqual(restoration.status, 'pending')

    def test_delta_backup_tracker(self):
        from api.backup.models import Backup, DeltaBackupTracker
        parent = Backup.objects.create(
            name=f'Parent_{uid()}',
            backup_type='full',
            status='completed',
            database_name='earning_db',
        )
        child = Backup.objects.create(
            name=f'Child_{uid()}',
            backup_type='incremental',
            status='completed',
            database_name='earning_db',
        )
        tracker = DeltaBackupTracker.objects.create(
            parent_backup=parent,
            child_backup=child,
            changed_row_count=500,
        )
        self.assertEqual(tracker.changed_row_count, 500)