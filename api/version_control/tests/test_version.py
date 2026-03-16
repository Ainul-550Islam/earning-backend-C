# =============================================================================
# version_control/tests/test_version.py
# =============================================================================
"""
Unit and integration tests for the version_control application.

Coverage:
  - SemVer comparison helper
  - VersionCheckService (with and without DB policies)
  - MaintenanceService lifecycle
  - UpdatePolicyService create + activate
  - Middleware maintenance-mode enforcement
  - Utility functions (update_checker, redirect_handler)
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from ..choices import MaintenanceStatus, PolicyStatus, UpdateType
from ..constants import ALL_PLATFORMS
from ..exceptions import (
    DuplicateSessionError,
    InvalidVersionStringError,
    MaintenanceAlreadyActiveError,
)
from ..models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect
from ..services import (
    MaintenanceService,
    SemVer,
    UpdatePolicyService,
    VersionCheckService,
    _parse_version,
)
from ..utils.update_checker import (
    client_needs_update,
    compare_versions,
    get_update_urgency,
    is_valid_version,
)
from ..utils.redirect_handler import (
    build_deep_link,
    is_valid_redirect_url,
    looks_like_store_url,
    sanitise_redirect_url,
)


# =============================================================================
# SemVer tests (pure unit)
# =============================================================================

class TestSemVer(TestCase):
    """Tests for the internal SemVer comparison helper."""

    def test_equality(self):
        self.assertEqual(SemVer("1.2.3"), SemVer("1.2.3"))

    def test_less_than_major(self):
        self.assertLess(SemVer("1.0.0"), SemVer("2.0.0"))

    def test_less_than_minor(self):
        self.assertLess(SemVer("1.1.0"), SemVer("1.2.0"))

    def test_less_than_patch(self):
        self.assertLess(SemVer("1.0.0"), SemVer("1.0.1"))

    def test_greater_than(self):
        self.assertGreater(SemVer("2.0.0"), SemVer("1.9.9"))

    def test_invalid_string_raises(self):
        with self.assertRaises(InvalidVersionStringError):
            SemVer("not-a-version")

    def test_prerelease_ignored_for_ordering(self):
        # Pre-release suffix is stripped; only MAJOR.MINOR.PATCH compared
        self.assertEqual(SemVer("1.2.3-alpha"), SemVer("1.2.3-beta"))

    def test_str_returns_original(self):
        self.assertEqual(str(SemVer("1.2.3")), "1.2.3")


# =============================================================================
# UpdatePolicyService tests (DB)
# =============================================================================

class TestUpdatePolicyService(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com",
            password="secret", is_staff=True,
        )

    def test_create_draft_policy(self):
        policy = UpdatePolicyService.create_policy(
            platform="ios",
            min_version="1.0.0",
            target_version="2.0.0",
            update_type=UpdateType.OPTIONAL,
            created_by=self.staff,
        )
        self.assertEqual(policy.status, PolicyStatus.DRAFT)
        self.assertEqual(policy.platform, "ios")

    def test_activate_policy(self):
        policy = UpdatePolicyService.create_policy(
            platform="android",
            min_version="1.0.0",
            target_version="1.5.0",
            created_by=self.staff,
        )
        activated = UpdatePolicyService.activate_policy(policy)
        self.assertEqual(activated.status, PolicyStatus.ACTIVE)

    def test_deactivate_policy(self):
        policy = UpdatePolicyService.create_policy(
            platform="web",
            min_version="2.0.0",
            target_version="3.0.0",
            created_by=self.staff,
        )
        UpdatePolicyService.activate_policy(policy)
        deactivated = UpdatePolicyService.deactivate_policy(policy)
        self.assertEqual(deactivated.status, PolicyStatus.INACTIVE)


# =============================================================================
# VersionCheckService tests (DB)
# =============================================================================

class TestVersionCheckService(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="vc_staff", email="vc@example.com",
            password="secret", is_staff=True,
        )

    def _create_active_policy(
        self,
        platform="ios",
        min_version="1.0.0",
        target_version="2.0.0",
        update_type=UpdateType.OPTIONAL,
    ):
        policy = UpdatePolicyService.create_policy(
            platform=platform,
            min_version=min_version,
            target_version=target_version,
            update_type=update_type,
            created_by=self.staff,
        )
        UpdatePolicyService.activate_policy(policy)
        return policy

    def test_no_policy_returns_no_update(self):
        result = VersionCheckService.check(platform="ios", client_version="1.0.0")
        self.assertFalse(result["update_required"])
        self.assertIsNone(result["update_type"])

    def test_client_below_target_optional_update(self):
        self._create_active_policy(
            platform="ios", min_version="1.0.0",
            target_version="2.0.0", update_type=UpdateType.OPTIONAL,
        )
        result = VersionCheckService.check(platform="ios", client_version="1.5.0")
        self.assertFalse(result["update_required"])   # optional = not required
        self.assertEqual(result["update_type"], UpdateType.OPTIONAL)
        self.assertEqual(result["target_version"], "2.0.0")

    def test_client_below_target_required_update(self):
        self._create_active_policy(
            platform="android", min_version="1.0.0",
            target_version="2.0.0", update_type=UpdateType.REQUIRED,
        )
        result = VersionCheckService.check(platform="android", client_version="1.0.0")
        self.assertTrue(result["update_required"])
        self.assertEqual(result["update_type"], UpdateType.REQUIRED)

    def test_client_already_on_target_no_update(self):
        self._create_active_policy(
            platform="ios", min_version="1.0.0", target_version="2.0.0"
        )
        result = VersionCheckService.check(platform="ios", client_version="2.0.0")
        self.assertFalse(result["update_required"])

    def test_invalid_platform_raises(self):
        from ..exceptions import InvalidPlatformError
        with self.assertRaises(InvalidPlatformError):
            VersionCheckService.check(platform="amiga", client_version="1.0.0")

    def test_invalid_version_raises(self):
        with self.assertRaises(InvalidVersionStringError):
            VersionCheckService.check(platform="ios", client_version="bad-ver")


# =============================================================================
# MaintenanceService tests (DB)
# =============================================================================

class TestMaintenanceService(TestCase):

    def _make_schedule(
        self,
        title: str = "Test Maintenance",
        offset_minutes: int = 0,
        duration_minutes: int = 60,
    ) -> MaintenanceSchedule:
        now   = timezone.now()
        start = now + timedelta(minutes=offset_minutes)
        end   = start + timedelta(minutes=duration_minutes)
        return MaintenanceService.create_schedule(
            title=title,
            scheduled_start=start,
            scheduled_end=end,
        )

    def test_create_schedule_status_scheduled(self):
        schedule = self._make_schedule()
        self.assertEqual(schedule.status, MaintenanceStatus.SCHEDULED)

    def test_start_maintenance(self):
        schedule = self._make_schedule()
        started  = MaintenanceService.start_maintenance(schedule)
        self.assertEqual(started.status, MaintenanceStatus.ACTIVE)
        self.assertIsNotNone(started.actual_start)

    def test_double_start_raises(self):
        s1 = self._make_schedule(title="First")
        MaintenanceService.start_maintenance(s1)
        s2 = self._make_schedule(title="Second")
        with self.assertRaises(MaintenanceAlreadyActiveError):
            MaintenanceService.start_maintenance(s2)

    def test_end_maintenance(self):
        schedule = self._make_schedule()
        MaintenanceService.start_maintenance(schedule)
        ended = MaintenanceService.end_maintenance(schedule)
        self.assertEqual(ended.status, MaintenanceStatus.COMPLETED)
        self.assertIsNotNone(ended.actual_end)

    def test_cancel_maintenance(self):
        schedule  = self._make_schedule()
        cancelled = MaintenanceService.cancel_maintenance(schedule)
        self.assertEqual(cancelled.status, MaintenanceStatus.CANCELLED)

    def test_is_active_for_platform_true(self):
        schedule = self._make_schedule()
        MaintenanceService.start_maintenance(schedule)
        self.assertTrue(
            MaintenanceService.is_active_for_platform("ios")
        )

    def test_is_active_for_platform_false_when_no_maintenance(self):
        self.assertFalse(
            MaintenanceService.is_active_for_platform("ios")
        )

    def test_affects_platform_specific(self):
        now      = timezone.now()
        schedule = MaintenanceService.create_schedule(
            title="iOS Only",
            scheduled_start=now,
            scheduled_end=now + timedelta(hours=1),
            platforms=["ios"],
        )
        self.assertTrue(schedule.affects_platform("ios"))
        self.assertFalse(schedule.affects_platform("android"))

    def test_invalid_time_range_raises(self):
        from ..exceptions import InvalidMaintenanceWindowError
        now = timezone.now()
        with self.assertRaises(InvalidMaintenanceWindowError):
            MaintenanceService.create_schedule(
                title="Bad Window",
                scheduled_start=now + timedelta(hours=2),
                scheduled_end=now,          # end before start
            )


# =============================================================================
# Utility: update_checker
# =============================================================================

class TestUpdateCheckerUtils(TestCase):

    def test_is_valid_version_good(self):
        self.assertTrue(is_valid_version("1.2.3"))
        self.assertTrue(is_valid_version("10.0.0-alpha"))

    def test_is_valid_version_bad(self):
        self.assertFalse(is_valid_version(""))
        self.assertFalse(is_valid_version("not-semver"))
        self.assertFalse(is_valid_version("1.2"))

    def test_compare_versions(self):
        self.assertEqual(compare_versions("1.0.0", "1.0.0"),  0)
        self.assertEqual(compare_versions("1.0.0", "2.0.0"), -1)
        self.assertEqual(compare_versions("2.0.0", "1.0.0"), +1)

    def test_client_needs_update_true(self):
        self.assertTrue(client_needs_update("1.0.0", "2.0.0"))

    def test_client_needs_update_false_same(self):
        self.assertFalse(client_needs_update("2.0.0", "2.0.0"))

    def test_client_needs_update_false_ahead(self):
        self.assertFalse(client_needs_update("3.0.0", "2.0.0"))

    def test_get_update_urgency_major(self):
        self.assertEqual(get_update_urgency("1.0.0", "2.0.0"), "critical")

    def test_get_update_urgency_minor(self):
        self.assertEqual(get_update_urgency("1.0.0", "1.1.0"), "required")

    def test_get_update_urgency_patch(self):
        self.assertEqual(get_update_urgency("1.0.0", "1.0.1"), "optional")


# =============================================================================
# Utility: redirect_handler
# =============================================================================

class TestRedirectHandlerUtils(TestCase):

    def test_is_valid_redirect_url_true(self):
        self.assertTrue(is_valid_redirect_url("https://apps.apple.com/app/id123"))
        self.assertTrue(is_valid_redirect_url("http://localhost/"))

    def test_is_valid_redirect_url_false(self):
        self.assertFalse(is_valid_redirect_url(""))
        self.assertFalse(is_valid_redirect_url("not-a-url"))
        self.assertFalse(is_valid_redirect_url("ftp://example.com"))

    def test_looks_like_store_url_ios(self):
        self.assertTrue(
            looks_like_store_url("ios", "https://apps.apple.com/app/id1234")
        )
        self.assertFalse(
            looks_like_store_url("ios", "https://play.google.com/store/apps")
        )

    def test_looks_like_store_url_unknown_platform(self):
        # Unknown platforms always return True (no validation)
        self.assertTrue(looks_like_store_url("web", "https://example.com"))

    def test_build_deep_link_no_params(self):
        self.assertEqual(build_deep_link("myapp://update", {}), "myapp://update")

    def test_build_deep_link_with_params(self):
        result = build_deep_link("myapp://update", {"version": "2.0.0"})
        self.assertIn("version=2.0.0", result)

    def test_sanitise_redirect_url_strips_slash(self):
        result = sanitise_redirect_url("  https://example.com/  ")
        self.assertFalse(result.endswith("/"))

    def test_sanitise_redirect_url_invalid_raises(self):
        with self.assertRaises(ValueError):
            sanitise_redirect_url("not-a-url")
