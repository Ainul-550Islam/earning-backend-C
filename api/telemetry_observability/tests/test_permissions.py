"""
Tests for permissions.py — all permission classes.
"""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import User, AnonymousUser

from ..permissions import (
    TelemetryBasePermission, ReadOnlyOrAuthenticated,
    IsAdminOrReadOnly, IsServiceAccount,
    CanViewMetrics, CanCreateMetrics, CanViewLogs,
    CanManageAlerts, CanManageDashboards,
)


def make_request(method='GET', user=None, authenticated=True):
    factory = APIRequestFactory()
    req_map = {
        'GET': factory.get, 'POST': factory.post,
        'PUT': factory.put, 'PATCH': factory.patch,
        'DELETE': factory.delete,
    }
    request = req_map[method]('/test/')
    if user is None and authenticated:
        user = MagicMock(spec=User)
        user.is_authenticated = True
        user.is_active        = True
        user.is_staff         = False
        user.is_superuser     = False
        user.has_perm         = MagicMock(return_value=False)
        user.groups           = MagicMock()
        user.groups.filter    = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=False)))
    elif not authenticated:
        user = AnonymousUser()
    request.user = user
    return request


class TestTelemetryBasePermission:
    perm = TelemetryBasePermission()

    def test_authenticated_active_user_allowed(self):
        req = make_request()
        assert self.perm.has_permission(req, None) is True

    def test_unauthenticated_denied(self):
        req = make_request(authenticated=False)
        assert self.perm.has_permission(req, None) is False

    def test_inactive_user_denied(self):
        user = MagicMock(spec=User)
        user.is_authenticated = True
        user.is_active        = False
        req = make_request()
        req.user = user
        assert self.perm.has_permission(req, None) is False


class TestReadOnlyOrAuthenticated:
    perm = ReadOnlyOrAuthenticated()

    def test_get_allowed_authenticated(self):
        req = make_request('GET')
        assert self.perm.has_permission(req, None) is True

    def test_post_requires_write_perm(self):
        req = make_request('POST')
        req.user.has_perm = MagicMock(return_value=False)
        assert self.perm.has_permission(req, None) is False

    def test_post_allowed_with_write_perm(self):
        req = make_request('POST')
        req.user.has_perm = MagicMock(return_value=True)
        assert self.perm.has_permission(req, None) is True

    def test_unauthenticated_denied(self):
        req = make_request('GET', authenticated=False)
        assert self.perm.has_permission(req, None) is False


class TestIsAdminOrReadOnly:
    perm = IsAdminOrReadOnly()

    def test_staff_can_post(self):
        req         = make_request('POST')
        req.user.is_staff = True
        assert self.perm.has_permission(req, None) is True

    def test_superuser_can_delete(self):
        req             = make_request('DELETE')
        req.user.is_superuser = True
        assert self.perm.has_permission(req, None) is True

    def test_regular_user_can_get(self):
        req = make_request('GET')
        assert self.perm.has_permission(req, None) is True

    def test_regular_user_cannot_post(self):
        req = make_request('POST')
        assert self.perm.has_permission(req, None) is False


class TestIsServiceAccount:
    perm = IsServiceAccount()

    def test_service_account_flag_allowed(self):
        req = make_request('POST')
        req.user.is_service_account = True
        assert self.perm.has_permission(req, None) is True

    def test_service_accounts_group_allowed(self):
        req = make_request('POST')
        req.user.is_service_account = False
        req.user.groups.filter = MagicMock(
            return_value=MagicMock(exists=MagicMock(return_value=True))
        )
        assert self.perm.has_permission(req, None) is True

    def test_regular_user_denied(self):
        req = make_request('POST')
        req.user.is_service_account = False
        assert self.perm.has_permission(req, None) is False


class TestCanManageAlerts:
    perm = CanManageAlerts()

    def test_view_perm_allows_get(self):
        req = make_request('GET')
        def has_perm(p): return 'view_alert' in p
        req.user.has_perm = has_perm
        assert self.perm.has_permission(req, None) is True

    def test_change_perm_allows_post(self):
        req = make_request('POST')
        def has_perm(p): return 'change_alert' in p
        req.user.has_perm = has_perm
        assert self.perm.has_permission(req, None) is True

    def test_no_change_perm_denies_post(self):
        req = make_request('POST')
        req.user.has_perm = MagicMock(return_value=False)
        assert self.perm.has_permission(req, None) is False

    def test_unauthenticated_denied(self):
        req = make_request('GET', authenticated=False)
        assert self.perm.has_permission(req, None) is False


class TestCanManageDashboards:
    perm = CanManageDashboards()

    def test_view_perm_allows_get(self):
        req = make_request('GET')
        def has_perm(p): return 'view_dashboardwidget' in p
        req.user.has_perm = has_perm
        assert self.perm.has_permission(req, None) is True

    def test_change_perm_allows_patch(self):
        req = make_request('PATCH')
        def has_perm(p): return 'change_dashboardwidget' in p
        req.user.has_perm = has_perm
        assert self.perm.has_permission(req, None) is True
