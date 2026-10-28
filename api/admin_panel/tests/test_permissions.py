# api/admin_panel/tests/test_permissions.py
"""Tests for admin_panel permissions."""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

User = get_user_model()


class PermissionsTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.superuser = User.objects.create_superuser('super', 'su@t.com', 'pass')
        self.staff = User.objects.create_user('staff', 'staff@t.com', 'pass', is_staff=True)
        self.regular = User.objects.create_user('regular', 'reg@t.com', 'pass')

    def _make_request(self, user):
        request = self.factory.get('/')
        request.user = user
        return request

    def test_is_super_admin(self):
        from api.admin_panel.permissions import IsSuperAdmin
        perm = IsSuperAdmin()
        self.assertTrue(perm.has_permission(self._make_request(self.superuser), None))
        self.assertFalse(perm.has_permission(self._make_request(self.staff), None))
        self.assertFalse(perm.has_permission(self._make_request(self.regular), None))

    def test_system_admin_permission(self):
        from api.admin_panel.permissions import IsSystemAdmin
        perm = IsSystemAdmin()
        self.assertTrue(perm.has_permission(self._make_request(self.superuser), None))
        self.assertTrue(perm.has_permission(self._make_request(self.staff), None))
        self.assertFalse(perm.has_permission(self._make_request(self.regular), None))

    def test_can_manage_system_settings(self):
        from api.admin_panel.permissions import CanManageSystemSettings
        perm = CanManageSystemSettings()
        self.assertTrue(perm.has_permission(self._make_request(self.superuser), None))
        self.assertFalse(perm.has_permission(self._make_request(self.staff), None))

    def test_can_manage_notifications(self):
        from api.admin_panel.permissions import CanManageNotifications
        perm = CanManageNotifications()
        self.assertTrue(perm.has_permission(self._make_request(self.superuser), None))
        self.assertTrue(perm.has_permission(self._make_request(self.staff), None))
        self.assertFalse(perm.has_permission(self._make_request(self.regular), None))


# api/admin_panel/tests/test_filters.py
"""Tests for admin_panel filters (combined in this file)."""
from django.test import TestCase
from django.utils import timezone


class SiteNotificationFilterTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.core import SiteNotification
        SiteNotification.objects.create(
            title='Active Info', message='test', notification_type='INFO', is_active=True
        )
        SiteNotification.objects.create(
            title='Inactive Warning', message='test', notification_type='WARNING', is_active=False
        )

    def test_filter_by_type(self):
        from api.admin_panel.models.core import SiteNotification
        from api.admin_panel.filters import SiteNotificationFilter, get_filter_for_model
        BoundFilter = get_filter_for_model(SiteNotification, SiteNotificationFilter)
        f = BoundFilter({'notification_type': 'INFO'}, queryset=SiteNotification.objects.all())
        self.assertEqual(f.qs.count(), 1)

    def test_filter_active(self):
        from api.admin_panel.models.core import SiteNotification
        from api.admin_panel.filters import SiteNotificationFilter, get_filter_for_model
        BoundFilter = get_filter_for_model(SiteNotification, SiteNotificationFilter)
        f = BoundFilter({'is_active': True}, queryset=SiteNotification.objects.all())
        self.assertEqual(f.qs.count(), 1)


class FeatureFlagFilterTest(TestCase):
    def setUp(self):
        from api.admin_panel.models.config import FeatureFlag
        FeatureFlag.objects.create(flag_key='enabled_flag', is_enabled=True, rollout_pct=100)
        FeatureFlag.objects.create(flag_key='disabled_flag', is_enabled=False, rollout_pct=0)

    def test_filter_enabled_only(self):
        from api.admin_panel.models.config import FeatureFlag
        from api.admin_panel.filters import FeatureFlagFilter, get_filter_for_model
        BoundFilter = get_filter_for_model(FeatureFlag, FeatureFlagFilter)
        f = BoundFilter({'is_enabled': True}, queryset=FeatureFlag.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.first().flag_key, 'enabled_flag')