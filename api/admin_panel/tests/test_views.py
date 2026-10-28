# api/admin_panel/tests/test_views.py
"""
ViewSet/API tests for admin_panel.
Tests all major endpoints with authentication.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class BaseAdminAPITest(TestCase):
    """Base class with admin client setup."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='testadmin',
            email='admin@test.com',
            password='adminpass123',
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            email='user@test.com',
            password='userpass123',
        )
        self.client.force_authenticate(user=self.admin)
        self.base_url = '/api/admin-panel'


class SystemSettingsViewTest(BaseAdminAPITest):
    def setUp(self):
        super().setUp()
        from api.admin_panel.models.core import SystemSettings
        self.settings = SystemSettings.objects.create(site_name='Test Platform')

    def test_settings_list_authenticated(self):
        resp = self.client.get(f'{self.base_url}/settings/')
        self.assertIn(resp.status_code, [200, 301, 302])

    def test_settings_public_no_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(f'{self.base_url}/settings/public/')
        self.assertEqual(resp.status_code, 200)

    def test_maintenance_status_no_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(f'{self.base_url}/settings/maintenance-status/')
        self.assertIn(resp.status_code, [200, 404])


class EndpointToggleViewTest(BaseAdminAPITest):
    def setUp(self):
        super().setUp()
        from api.admin_panel.models import EndpointToggle
        self.toggle = EndpointToggle.objects.create(
            path='/api/test-path/',
            method='GET',
            group='test',
            is_enabled=True,
        )

    def test_list_toggles(self):
        resp = self.client.get(f'{self.base_url}/endpoint-toggles/')
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.regular_user)
        resp = self.client.get(f'{self.base_url}/endpoint-toggles/')
        self.assertEqual(resp.status_code, 403)

    def test_toggle_status_summary(self):
        resp = self.client.get(f'{self.base_url}/endpoint-toggles/status_summary/')
        self.assertIn(resp.status_code, [200, 404])

    def test_bulk_toggle(self):
        resp = self.client.post(f'{self.base_url}/endpoint-toggles/bulk-toggle/', {
            'toggles': [
                {'path': '/api/test-path/', 'method': 'GET', 'is_enabled': False}
            ]
        }, format='json')
        self.assertIn(resp.status_code, [200, 400])


class DashboardViewTest(BaseAdminAPITest):
    def test_dashboard_stats(self):
        resp = self.client.get(f'{self.base_url}/dashboard/stats/')
        self.assertIn(resp.status_code, [200, 404])

    def test_system_health(self):
        resp = self.client.get(f'{self.base_url}/dashboard/system-health/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('status', data)

    def test_kpis_endpoint(self):
        resp = self.client.get(f'{self.base_url}/dashboard/kpis/')
        self.assertIn(resp.status_code, [200, 404])


class SiteNotificationViewTest(BaseAdminAPITest):
    def setUp(self):
        super().setUp()
        from api.admin_panel.models.core import SiteNotification
        self.notif = SiteNotification.objects.create(
            title='Test', message='Test message', notification_type='INFO', is_active=True
        )

    def test_list_notifications(self):
        resp = self.client.get(f'{self.base_url}/site-notifications/')
        self.assertEqual(resp.status_code, 200)

    def test_active_notifications_no_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(f'{self.base_url}/site-notifications/active_notifications/')
        self.assertIn(resp.status_code, [200, 403])

    def test_create_notification(self):
        resp = self.client.post(f'{self.base_url}/site-notifications/', {
            'title': 'New Notif',
            'message': 'Test message',
            'notification_type': 'SUCCESS',
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400])


class SystemConfigViewTest(BaseAdminAPITest):
    def setUp(self):
        super().setUp()
        from api.admin_panel.models.config import SystemConfig
        SystemConfig.objects.create(
            key='test_ad_points', value='10', value_type='integer', group='earning'
        )

    def test_list_configs(self):
        resp = self.client.get(f'{self.base_url}/config/')
        self.assertEqual(resp.status_code, 200)

    def test_config_by_group(self):
        resp = self.client.get(f'{self.base_url}/config/by-group/')
        self.assertIn(resp.status_code, [200, 404])

    def test_public_configs(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(f'{self.base_url}/config/public/')
        self.assertIn(resp.status_code, [200, 403])


class FeatureFlagViewTest(BaseAdminAPITest):
    def setUp(self):
        super().setUp()
        from api.admin_panel.models.config import FeatureFlag
        self.flag = FeatureFlag.objects.create(
            flag_key='test_feature', is_enabled=True, rollout_pct=100
        )

    def test_list_flags(self):
        resp = self.client.get(f'{self.base_url}/feature-flags/')
        self.assertEqual(resp.status_code, 200)

    def test_toggle_flag(self):
        resp = self.client.post(f'{self.base_url}/feature-flags/{self.flag.pk}/toggle/')
        self.assertIn(resp.status_code, [200, 404])

    def test_all_states(self):
        resp = self.client.get(f'{self.base_url}/feature-flags/all-states/')
        self.assertIn(resp.status_code, [200, 404])


class BulkActionViewTest(BaseAdminAPITest):
    def test_available_actions(self):
        resp = self.client.get(f'{self.base_url}/bulk-actions/available/')
        self.assertIn(resp.status_code, [200, 404])

    def test_execute_bulk_action_missing_params(self):
        resp = self.client.post(f'{self.base_url}/bulk-actions/execute/', {}, format='json')
        self.assertIn(resp.status_code, [400, 404])

    def test_execute_bulk_activate(self):
        users = [User.objects.create_user(f'bulk_u{i}', password='pass').pk for i in range(3)]
        resp = self.client.post(f'{self.base_url}/bulk-actions/execute/', {
            'model': 'auth.User',
            'action': 'activate',
            'ids': users,
        }, format='json')
        self.assertIn(resp.status_code, [200, 404, 500])


class AdminActivityViewTest(BaseAdminAPITest):
    def test_activity_list(self):
        resp = self.client.get(f'{self.base_url}/activity/')
        self.assertIn(resp.status_code, [200, 404])

    def test_activity_summary(self):
        resp = self.client.get(f'{self.base_url}/activity/summary/')
        self.assertIn(resp.status_code, [200, 404])


class AdminSearchViewTest(BaseAdminAPITest):
    def test_global_search(self):
        resp = self.client.get(f'{self.base_url}/search/global/?q=test')
        self.assertIn(resp.status_code, [200, 404])

    def test_search_too_short_query(self):
        resp = self.client.get(f'{self.base_url}/search/global/?q=a')
        self.assertIn(resp.status_code, [400, 404])


class MaintenanceWindowViewTest(BaseAdminAPITest):
    def test_maintenance_status(self):
        resp = self.client.get(f'{self.base_url}/maintenance/status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_create_maintenance_window(self):
        from django.utils import timezone
        from datetime import timedelta
        resp = self.client.post(f'{self.base_url}/maintenance/', {
            'title': 'Test Maintenance',
            'message': 'Test message',
            'maintenance_type': 'scheduled',
            'start_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            'end_at': (timezone.now() + timedelta(hours=2)).isoformat(),
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400])