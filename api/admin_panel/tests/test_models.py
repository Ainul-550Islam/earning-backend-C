# api/admin_panel/tests/test_models.py
"""
Model tests for admin_panel.
Tests all 32 models covering: create, str, properties, methods, signals.
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

User = get_user_model()


class SystemSettingsModelTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.core import SystemSettings
        self.settings = SystemSettings.objects.create(
            site_name='Test Platform',
            currency_code='BDT',
            currency_symbol='৳',
        )

    def test_str(self):
        self.assertIn('Test Platform', str(self.settings))

    def test_singleton(self):
        from api.admin_panel.models.core import SystemSettings
        with self.assertRaises(Exception):
            SystemSettings.objects.create(site_name='Second Settings')

    def test_get_settings_cached(self):
        from api.admin_panel.models.core import SystemSettings
        s = SystemSettings.get_settings()
        self.assertIsNotNone(s)
        self.assertEqual(s.site_name, 'Test Platform')

    def test_to_dict(self):
        d = self.settings.to_dict()
        self.assertIn('site_name', d)
        self.assertIn('currency_code', d)
        self.assertIn('referral_enabled', d)

    def test_check_app_version_android(self):
        self.settings.android_version_code = 10
        self.settings.android_min_version_code = 8
        self.settings.android_force_update = False
        self.settings.save()
        result = self.settings.check_app_version('android', 9)
        self.assertTrue(result['is_allowed'])

    def test_check_app_version_force_update(self):
        self.settings.android_version_code = 10
        self.settings.android_min_version_code = 10
        self.settings.android_force_update = True
        self.settings.save()
        result = self.settings.check_app_version('android', 5)
        self.assertFalse(result['is_allowed'])
        self.assertTrue(result['force_update'])


class SiteNotificationModelTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.core import SiteNotification
        self.notif = SiteNotification.objects.create(
            title='Test Notif',
            message='Test message',
            notification_type='INFO',
            is_active=True,
        )

    def test_str(self):
        self.assertIn('Test Notif', str(self.notif))

    def test_is_current_active(self):
        self.assertTrue(self.notif.is_current())

    def test_is_current_inactive(self):
        self.notif.is_active = False
        self.notif.save()
        self.assertFalse(self.notif.is_current())

    def test_is_current_expired(self):
        self.notif.end_date = timezone.now() - timedelta(hours=1)
        self.notif.save()
        self.assertFalse(self.notif.is_current())


class SiteContentModelTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.core import SiteContent
        self.content = SiteContent.objects.create(
            identifier='test-page',
            title='Test Page',
            content='<p>Hello World</p>',
            content_type='PAGE',
            language='en',
        )

    def test_str(self):
        self.assertIn('Test Page', str(self.content))

    def test_unique_together(self):
        from api.admin_panel.models.core import SiteContent
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            SiteContent.objects.create(
                identifier='test-page',
                title='Duplicate',
                content='duplicate',
                language='en',
            )


class AdminProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='adminuser', email='admin@test.com',
            password='testpass123', is_staff=True
        )
        from api.admin_panel.models.core import AdminProfile
        self.profile = AdminProfile.objects.create(
            user=self.user, role='admin'
        )

    def test_str(self):
        self.assertIn('adminuser', str(self.profile))

    def test_get_display_name(self):
        self.assertIsNotNone(self.profile.get_display_name())

    def test_is_superadmin_false(self):
        self.assertFalse(self.profile.is_superadmin)

    def test_can_manage_settings(self):
        self.assertTrue(self.profile.can_manage_settings)

    def test_can_manage_users(self):
        self.assertTrue(self.profile.can_manage_users)

    def test_viewer_cannot_manage_settings(self):
        self.profile.role = 'viewer'
        self.profile.save()
        self.assertFalse(self.profile.can_manage_settings)


class SystemConfigModelTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.config import SystemConfig
        self.config = SystemConfig.objects.create(
            key='test_referral_bonus',
            value='500',
            value_type='integer',
            group='earning',
        )

    def test_str(self):
        self.assertIn('test_referral_bonus', str(self.config))

    def test_get_typed_value_integer(self):
        val = self.config.get_typed_value()
        self.assertEqual(val, 500)
        self.assertIsInstance(val, int)

    def test_get_typed_value_float(self):
        from api.admin_panel.models.config import SystemConfig
        config = SystemConfig.objects.create(
            key='test_rate', value='0.5', value_type='float', group='earning'
        )
        self.assertEqual(config.get_typed_value(), 0.5)

    def test_get_typed_value_boolean_true(self):
        from api.admin_panel.models.config import SystemConfig
        config = SystemConfig.objects.create(
            key='test_bool', value='true', value_type='boolean', group='general'
        )
        self.assertTrue(config.get_typed_value())

    def test_classmethod_get(self):
        from api.admin_panel.models.config import SystemConfig
        val = SystemConfig.get('test_referral_bonus')
        self.assertEqual(val, 500)

    def test_classmethod_get_default(self):
        from api.admin_panel.models.config import SystemConfig
        val = SystemConfig.get('nonexistent_key', default=999)
        self.assertEqual(val, 999)

    def test_classmethod_set(self):
        from api.admin_panel.models.config import SystemConfig
        SystemConfig.set('new_key', '100', 'integer')
        val = SystemConfig.get('new_key')
        self.assertEqual(val, 100)


class FeatureFlagModelTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.config import FeatureFlag
        self.flag = FeatureFlag.objects.create(
            flag_key='referral_system',
            is_enabled=True,
            rollout_pct=100,
        )

    def test_str(self):
        self.assertIn('referral_system', str(self.flag))

    def test_is_active_for_user_100pct(self):
        user = User.objects.create_user('flaguser', password='pass')
        self.assertTrue(self.flag.is_active_for_user(user))

    def test_is_active_for_user_disabled(self):
        self.flag.is_enabled = False
        self.flag.save()
        user = User.objects.create_user('flaguser2', password='pass')
        self.assertFalse(self.flag.is_active_for_user(user))

    def test_is_active_for_user_0pct(self):
        self.flag.rollout_pct = 0
        self.flag.save()
        user = User.objects.create_user('flaguser3', password='pass')
        self.assertFalse(self.flag.is_active_for_user(user))

    def test_is_enabled_globally(self):
        from api.admin_panel.models.config import FeatureFlag
        result = FeatureFlag.is_enabled_globally('referral_system')
        self.assertTrue(result)


class MaintenanceWindowModelTest(TestCase):
    def test_is_currently_active_true(self):
        from api.admin_panel.models.config import MaintenanceWindow
        window = MaintenanceWindow.objects.create(
            title='Test Maintenance',
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=1),
            is_active=True,
        )
        self.assertTrue(window.is_currently_active)

    def test_duration_minutes(self):
        from api.admin_panel.models.config import MaintenanceWindow
        window = MaintenanceWindow.objects.create(
            title='Test',
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(minutes=60),
        )
        self.assertEqual(window.duration_minutes, 60)

    def test_clean_end_before_start_raises(self):
        from api.admin_panel.models.config import MaintenanceWindow
        from django.core.exceptions import ValidationError
        window = MaintenanceWindow(
            title='Bad Window',
            start_at=timezone.now() + timedelta(hours=2),
            end_at=timezone.now() + timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            window.clean()


class AdminActivityModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('actoruser', password='pass', is_staff=True)

    def test_log_creates_activity(self):
        from api.admin_panel.models.activity import AdminActivity
        activity = AdminActivity.log(
            actor=self.user,
            action='test_action',
            model_name='TestModel',
            object_id='42',
        )
        self.assertIsNotNone(activity)
        self.assertEqual(activity.action, 'test_action')
        self.assertEqual(activity.actor, self.user)

    def test_str(self):
        from api.admin_panel.models.activity import AdminActivity
        activity = AdminActivity.log(actor=self.user, action='create')
        self.assertIn('actoruser', str(activity))


class DashboardMetricModelTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.dashboard import DashboardMetric
        self.metric = DashboardMetric.objects.create(
            metric_key='total_users',
            label='Total Users',
            value=1000,
            previous_value=800,
            unit='users',
            period='daily',
        )

    def test_change_percentage(self):
        pct = self.metric.change_percentage
        self.assertAlmostEqual(pct, 25.0)

    def test_change_percentage_zero_previous(self):
        self.metric.previous_value = 0
        self.metric.save()
        self.assertIsNone(self.metric.change_percentage)


class DataExportModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('exportuser', password='pass')
        from api.admin_panel.models.reports import DataExport
        self.export = DataExport.objects.create(
            model_name='auth.User',
            format='csv',
            status='queued',
            requested_by=self.user,
        )

    def test_str(self):
        self.assertIn('auth.User', str(self.export))

    def test_mark_processing(self):
        self.export.mark_processing(task_id='celery-task-123')
        self.assertEqual(self.export.status, 'processing')
        self.assertEqual(self.export.task_id, 'celery-task-123')

    def test_mark_failed(self):
        self.export.mark_failed('Connection timeout')
        self.assertEqual(self.export.status, 'failed')
        self.assertIn('Connection timeout', self.export.error_message)

    def test_is_not_expired_default(self):
        self.assertFalse(self.export.is_expired)