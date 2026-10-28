"""
payout_queue/tests/test_permissions.py  ← NEW FILE

Permissions had 0% test coverage.
Covers: IsStaffOrSuperuser (view + object level),
        IsOwner, IsOwnerOrStaff, IsTenantMember, IsStaffOrReadOnly.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from django.test import TestCase, RequestFactory

from ..permissions import (
    IsStaffOrSuperuser,
    IsOwner,
    IsOwnerOrStaff,
    IsTenantMember,
    IsStaffOrReadOnly,
)
from .factories import UserFactory, StaffUserFactory

def _mock_request(user, method="GET"):
    req = MagicMock()
    req.user = user
    req.method = method
    return req

def _user(*, staff=False, superuser=False, tenant_id=None, authenticated=True):
    u = MagicMock()
    u.is_authenticated = authenticated
    u.is_staff = staff
    u.is_superuser = superuser
    u.pk = 42
    u.tenant_id = tenant_id
    return u

# ---------------------------------------------------------------------------
# IsStaffOrSuperuser
# ---------------------------------------------------------------------------

class IsStaffOrSuperuserTest(TestCase):

    perm = IsStaffOrSuperuser()

    def test_staff_allowed(self):
        self.assertTrue(self.perm.has_permission(_mock_request(_user(staff=True)), None))

    def test_superuser_allowed(self):
        self.assertTrue(self.perm.has_permission(_mock_request(_user(superuser=True)), None))

    def test_regular_user_denied(self):
        self.assertFalse(self.perm.has_permission(_mock_request(_user()), None))

    def test_unauthenticated_denied(self):
        self.assertFalse(
            self.perm.has_permission(_mock_request(_user(authenticated=False)), None)
        )

    # FIX: object-level permission was missing
    def test_object_permission_staff_allowed(self):
        req = _mock_request(_user(staff=True))
        self.assertTrue(self.perm.has_object_permission(req, None, object()))

    def test_object_permission_regular_denied(self):
        req = _mock_request(_user())
        self.assertFalse(self.perm.has_object_permission(req, None, object()))

# ---------------------------------------------------------------------------
# IsOwner
# ---------------------------------------------------------------------------

class IsOwnerTest(TestCase):

    perm = IsOwner()

    def _obj(self, user_pk):
        obj = MagicMock()
        obj.user_id = user_pk
        obj.user = None
        return obj

    def test_owner_allowed(self):
        user = _user()
        user.pk = 7
        req = _mock_request(user)
        obj = self._obj(7)
        self.assertTrue(self.perm.has_object_permission(req, None, obj))

    def test_non_owner_denied(self):
        user = _user()
        user.pk = 7
        req = _mock_request(user)
        obj = self._obj(99)
        self.assertFalse(self.perm.has_object_permission(req, None, obj))

    def test_no_user_field_on_obj_allows(self):
        """Object with no user/user_id attr → no restriction."""
        obj = MagicMock(spec=[])  # no user attr
        req = _mock_request(_user())
        self.assertTrue(self.perm.has_object_permission(req, None, obj))

    def test_unauthenticated_denied_at_view_level(self):
        req = _mock_request(_user(authenticated=False))
        self.assertFalse(self.perm.has_permission(req, None))

# ---------------------------------------------------------------------------
# IsOwnerOrStaff
# ---------------------------------------------------------------------------

class IsOwnerOrStaffTest(TestCase):

    perm = IsOwnerOrStaff()

    def _obj(self, user_pk):
        obj = MagicMock()
        obj.user_id = user_pk
        obj.user = None
        return obj

    def test_owner_allowed(self):
        user = _user()
        user.pk = 5
        req = _mock_request(user)
        self.assertTrue(self.perm.has_object_permission(req, None, self._obj(5)))

    def test_non_owner_denied(self):
        user = _user()
        user.pk = 5
        req = _mock_request(user)
        self.assertFalse(self.perm.has_object_permission(req, None, self._obj(999)))

    def test_staff_allowed_regardless_of_ownership(self):
        user = _user(staff=True)
        user.pk = 1
        req = _mock_request(user)
        self.assertTrue(self.perm.has_object_permission(req, None, self._obj(999)))

    def test_superuser_allowed(self):
        user = _user(superuser=True)
        user.pk = 1
        req = _mock_request(user)
        self.assertTrue(self.perm.has_object_permission(req, None, self._obj(999)))

# ---------------------------------------------------------------------------
# IsTenantMember
# ---------------------------------------------------------------------------

class IsTenantMemberTest(TestCase):

    perm = IsTenantMember()

    def _obj(self, tenant_id):
        obj = MagicMock()
        obj.tenant_id = tenant_id
        return obj

    def test_same_tenant_allowed(self):
        user = _user(tenant_id="T1")
        req = _mock_request(user)
        self.assertTrue(self.perm.has_object_permission(req, None, self._obj("T1")))

    def test_different_tenant_denied(self):
        user = _user(tenant_id="T1")
        req = _mock_request(user)
        self.assertFalse(self.perm.has_object_permission(req, None, self._obj("T2")))

    def test_no_tenant_on_obj_allows(self):
        user = _user(tenant_id="T1")
        req = _mock_request(user)
        obj = MagicMock()
        obj.tenant_id = None
        self.assertTrue(self.perm.has_object_permission(req, None, obj))

    def test_superuser_bypasses_tenant_check(self):
        user = _user(superuser=True, tenant_id="T1")
        req = _mock_request(user)
        self.assertTrue(self.perm.has_object_permission(req, None, self._obj("T999")))

# ---------------------------------------------------------------------------
# IsStaffOrReadOnly
# ---------------------------------------------------------------------------

class IsStaffOrReadOnlyTest(TestCase):

    perm = IsStaffOrReadOnly()

    def test_get_allowed_for_authenticated(self):
        req = _mock_request(_user())
        self.assertTrue(self.perm.has_permission(req, None))

    def test_post_denied_for_regular_user(self):
        req = _mock_request(_user(), method="POST")
        self.assertFalse(self.perm.has_permission(req, None))

    def test_post_allowed_for_staff(self):
        req = _mock_request(_user(staff=True), method="POST")
        self.assertTrue(self.perm.has_permission(req, None))

    def test_delete_allowed_for_superuser(self):
        req = _mock_request(_user(superuser=True), method="DELETE")
        self.assertTrue(self.perm.has_permission(req, None))

    def test_unauthenticated_denied_even_for_get(self):
        req = _mock_request(_user(authenticated=False))
        self.assertFalse(self.perm.has_permission(req, None))

# ---------------------------------------------------------------------------
# Integration: DB-backed users
# ---------------------------------------------------------------------------

class PermissionIntegrationTest(TestCase):
    """Uses real DB users via factories."""

    def test_staff_factory_user_passes_is_staff_or_superuser(self):
        from rest_framework.test import APIClient
        client = APIClient()
        staff = StaffUserFactory()
        client.force_authenticate(user=staff)
        # Just verify the permission class works with a real user object
        perm = IsStaffOrSuperuser()
        req = MagicMock()
        req.user = staff
        self.assertTrue(perm.has_permission(req, None))

    def test_regular_user_fails_is_staff_or_superuser(self):
        perm = IsStaffOrSuperuser()
        user = UserFactory()
        req = MagicMock()
        req.user = user
        self.assertFalse(perm.has_permission(req, None))
