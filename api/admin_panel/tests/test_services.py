# api/admin_panel/tests/test_services.py
"""Tests for admin_panel services."""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemConfigServiceTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.config import SystemConfig
        SystemConfig.objects.create(
            key='ad_click_points', value='10', value_type='integer', group='earning'
        )

    def test_get_existing_key(self):
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        val = SystemConfigService.get('ad_click_points')
        self.assertEqual(val, 10)

    def test_get_missing_key_default(self):
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        val = SystemConfigService.get('nonexistent', default=42)
        self.assertEqual(val, 42)

    def test_set_creates_config(self):
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        from api.admin_panel.models.config import SystemConfig
        SystemConfigService.set('new_rate', '5.5', 'float')
        config = SystemConfig.objects.get(key='new_rate')
        self.assertEqual(config.get_typed_value(), 5.5)

    def test_get_all(self):
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        all_conf = SystemConfigService.get_all()
        self.assertIn('ad_click_points', all_conf)


class FeatureFlagServiceTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.config import FeatureFlag
        self.flag = FeatureFlag.objects.create(
            flag_key='referral_system', is_enabled=True, rollout_pct=100
        )

    def test_is_enabled_globally(self):
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        self.assertTrue(FeatureFlagService.is_enabled('referral_system'))

    def test_is_enabled_for_user(self):
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        user = User.objects.create_user('flaguser', password='pass')
        self.assertTrue(FeatureFlagService.is_enabled('referral_system', user=user))

    def test_disable_flag(self):
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        FeatureFlagService.disable('referral_system')
        self.assertFalse(FeatureFlagService.is_enabled('referral_system'))

    def test_enable_flag(self):
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        FeatureFlagService.disable('referral_system')
        FeatureFlagService.enable('referral_system')
        self.assertTrue(FeatureFlagService.is_enabled('referral_system'))

    def test_set_rollout(self):
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        from api.admin_panel.models.config import FeatureFlag
        FeatureFlagService.set_rollout('referral_system', 50)
        flag = FeatureFlag.objects.get(flag_key='referral_system')
        self.assertEqual(flag.rollout_pct, 50)


class MaintenanceModeServiceTest(TestCase):
    def test_enable_maintenance(self):
        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        result = MaintenanceModeService.enable(message='Test maintenance', duration_minutes=30)
        self.assertTrue(result)
        self.assertTrue(MaintenanceModeService.is_active())

    def test_disable_maintenance(self):
        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        MaintenanceModeService.enable(duration_minutes=30)
        MaintenanceModeService.disable()
        self.assertFalse(MaintenanceModeService.is_active())

    def test_get_message(self):
        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        MaintenanceModeService.enable(message='System upgrade in progress')
        msg = MaintenanceModeService.get_message()
        self.assertIn('System upgrade', msg)


class AdminActivityServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('actortest', password='pass', is_staff=True)

    def test_log_creates_record(self):
        from api.admin_panel.services.AdminActivityService import AdminActivityService
        from api.admin_panel.models.activity import AdminActivity
        AdminActivityService.log(
            actor=self.user,
            action='approve_withdrawal',
            model_name='Withdrawal',
            object_id='123',
        )
        count = AdminActivity.objects.filter(
            actor=self.user, action='approve_withdrawal'
        ).count()
        self.assertEqual(count, 1)

    def test_get_recent(self):
        from api.admin_panel.services.AdminActivityService import AdminActivityService
        activities = AdminActivityService.get_recent(days=7, actor=self.user)
        self.assertIsNotNone(activities)

    def test_get_summary(self):
        from api.admin_panel.services.AdminActivityService import AdminActivityService
        summary = AdminActivityService.get_summary(days=7)
        self.assertIn('total', summary)
        self.assertIn('by_action', summary)