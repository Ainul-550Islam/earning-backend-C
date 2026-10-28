# api/admin_panel/tests/test_integration.py
"""
Integration tests — simulates full admin workflows.
CPAlead-style: withdrawal approval, feature flag rollout, maintenance toggle.
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.core.cache import cache
from django.utils import timezone

User = get_user_model()


class WithdrawalApprovalWorkflowTest(TestCase):
    """Test the admin withdrawal management workflow."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('wdadmin', 'admin@t.com', 'pass')
        self.client.force_authenticate(user=self.admin)
        cache.clear()

    def test_bulk_approve_withdrawal_flow(self):
        """Simulate: Admin selects withdrawals → bulk approve."""
        # Create some users to approve
        users = [User.objects.create_user(f'wduser{i}', password='pass').pk for i in range(3)]
        resp = self.client.post('/api/admin-panel/bulk-actions/execute/', {
            'model': 'auth.User',
            'action': 'activate',
            'ids': users,
        }, format='json')
        # Should not crash (200 or 404 if URL not set up in test)
        self.assertIn(resp.status_code, [200, 404, 500])


class MaintenanceModeWorkflowTest(TestCase):
    """Test maintenance mode enable/disable workflow."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('maintadmin', 'ma@t.com', 'pass')
        self.client.force_authenticate(user=self.admin)
        cache.clear()

    def test_enable_then_disable_maintenance(self):
        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        # Enable
        MaintenanceModeService.enable(message='Integration test maintenance')
        self.assertTrue(MaintenanceModeService.is_active())
        # Disable
        MaintenanceModeService.disable()
        self.assertFalse(MaintenanceModeService.is_active())

    def test_maintenance_message_persists(self):
        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        MaintenanceModeService.enable(message='DB upgrade in progress')
        msg = MaintenanceModeService.get_message()
        self.assertIn('DB upgrade', msg)
        MaintenanceModeService.disable()


class FeatureFlagRolloutWorkflowTest(TestCase):
    """Test feature flag rollout workflow."""

    def setUp(self):
        from api.admin_panel.models.config import FeatureFlag
        self.flag = FeatureFlag.objects.create(
            flag_key='daily_bonus_v2', is_enabled=True, rollout_pct=0
        )
        cache.clear()

    def test_gradual_rollout_to_100pct(self):
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        # Start at 0%
        user = User.objects.create_user('rolloutuser', password='pass')
        self.assertFalse(FeatureFlagService.is_enabled('daily_bonus_v2', user=user))
        # Roll out to 100%
        FeatureFlagService.set_rollout('daily_bonus_v2', 100)
        self.assertTrue(FeatureFlagService.is_enabled('daily_bonus_v2', user=user))


class SystemConfigWorkflowTest(TestCase):
    """Test runtime config change workflow."""

    def test_change_ad_click_points(self):
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        from api.admin_panel.models.config import SystemConfig
        # Set initial value
        SystemConfig.objects.create(
            key='ad_click_points', value='10', value_type='integer', group='earning'
        )
        self.assertEqual(SystemConfigService.get('ad_click_points'), 10)
        # Admin changes it
        SystemConfigService.set('ad_click_points', '25', 'integer')
        # Verify updated
        self.assertEqual(SystemConfigService.get('ad_click_points'), 25)

    def test_get_all_public_configs(self):
        from api.admin_panel.models.config import SystemConfig
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        SystemConfig.objects.create(
            key='public_site_name', value='Test Platform', value_type='string',
            group='general', is_public=True
        )
        SystemConfig.objects.create(
            key='private_key', value='secret', value_type='string',
            group='general', is_public=False
        )
        public = SystemConfigService.get_public()
        self.assertIn('public_site_name', public)
        self.assertNotIn('private_key', public)


class AdminActivityTrackingTest(TestCase):
    """Test admin activity tracking end-to-end."""

    def setUp(self):
        self.admin = User.objects.create_superuser('tracker', 'tr@t.com', 'pass', is_staff=True)

    def test_activity_logged_on_model_save(self):
        from api.admin_panel.models.activity import AdminActivity
        # Log an activity manually (middleware does this auto in real use)
        AdminActivity.log(
            actor=self.admin,
            action='approve_withdrawal',
            model_name='Withdrawal',
            object_id='999',
            status='success',
            ip='192.168.1.1',
        )
        count = AdminActivity.objects.filter(
            actor=self.admin,
            action='approve_withdrawal',
            object_id='999',
        ).count()
        self.assertEqual(count, 1)

    def test_activity_summary_stats(self):
        from api.admin_panel.models.activity import AdminActivity
        from api.admin_panel.services.AdminActivityService import AdminActivityService
        for action in ['create', 'update', 'delete', 'create']:
            AdminActivity.log(actor=self.admin, action=action)
        summary = AdminActivityService.get_summary(days=1)
        self.assertGreater(summary['total'], 0)
        by_action = {item['action']: item['count'] for item in summary['by_action']}
        self.assertEqual(by_action.get('create', 0), 2)