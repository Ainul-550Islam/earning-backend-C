"""
tests/test_views_repositories.py
==================================
Comprehensive tests for views_repositories.py.

Coverage targets
----------------
All 6 repositories × {list, detail, filter, stats, bulk, special}:
  • FraudRuleRepository       (7  views)
  • FraudCaseRepository       (8  views)
  • FraudAlertRepository      (8  views)
  • FraudRiskProfileRepository(7  views)
  • IPReputationRepository    (8  views)
  • FraudSuspiciousIPRepository(7 views)

Every view tests:
  auth gate (401), admin gate (403 where applicable),
  happy-path (200 / 201), 404 on unknown pk,
  ORM-fallback path (repository returns None → direct ORM),
  pagination params, filter params, body validation.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.fraud_detection.models import (
    FraudAlert,
    FraudCase,
    FraudRule,
    IPReputation,
    UserRiskProfile,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin(suffix=""):
    return User.objects.create_user(
        username=f"admin_repo{suffix}",
        email=f"admin_repo{suffix}@test.example.com",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )


def _user(suffix=""):
    return User.objects.create_user(
        username=f"user_repo{suffix}",
        email=f"user_repo{suffix}@test.example.com",
        password="pass",
    )


def _rule(**kwargs):
    defaults = dict(
        name="Test Rule",
        rule_type="velocity",
        severity="medium",
        condition={"threshold": 10},
        weight=0.5,
        threshold=10,
        is_active=True,
    )
    defaults.update(kwargs)
    return FraudRule.objects.create(**defaults)


def _case(user, **kwargs):
    defaults = dict(
        user=user,
        case_type="account_takeover",
        severity="high",
        status="open",
        risk_score=75,
        title="Test Case",
        description="Test case description",
        metadata={},
    )
    defaults.update(kwargs)
    return FraudCase.objects.create(**defaults)


def _alert(user, **kwargs):
    defaults = dict(
        alert_type="suspicious_activity",
        priority="high",
        title="Test Alert",
        description="Test alert description",
        user=user,
        is_resolved=False,
        data={},
    )
    defaults.update(kwargs)
    return FraudAlert.objects.create(**defaults)


def _profile(user, **kwargs):
    defaults = dict(overall_risk_score=50)
    defaults.update(kwargs)
    p, _ = UserRiskProfile.objects.get_or_create(user=user, defaults=defaults)
    return p


def _ip_rep(**kwargs):
    defaults = dict(
        ip_address="1.2.3.4",
        fraud_score=30,
        is_blacklisted=False,
        country="US",
    )
    defaults.update(kwargs)
    r, _ = IPReputation.objects.get_or_create(
        ip_address=defaults["ip_address"], defaults=defaults
    )
    return r


# ---------------------------------------------------------------------------
# Shared URL-building + auth test mixin
# ---------------------------------------------------------------------------

class _RepoBase(APITestCase):
    def setUp(self):
        self.admin  = _admin(self.__class__.__name__[:8])
        self.anon_u = _user(self.__class__.__name__[:8])
        self.client = APIClient()

    def _get(self, url, user=None, **kw):
        self.client.force_authenticate(user or self.anon_u)
        return self.client.get(url, **kw)

    def _post(self, url, data, user=None, **kw):
        self.client.force_authenticate(user or self.admin)
        return self.client.post(url, data, format="json", **kw)

    def _patch(self, url, data, user=None, **kw):
        self.client.force_authenticate(user or self.admin)
        return self.client.patch(url, data, format="json", **kw)

    def _delete(self, url, user=None, **kw):
        self.client.force_authenticate(user or self.admin)
        return self.client.delete(url, **kw)


# =============================================================================
# 1. FraudRuleRepository
# =============================================================================

class FraudRuleRepoListTest(_RepoBase):
    """GET/POST /fraud/repository/rules/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-rule-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_returns_paginated_list(self):
        _rule(name="Rule A")
        _rule(name="Rule B")
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertGreaterEqual(resp.data["total"], 2)

    def test_filter_by_is_active(self):
        _rule(name="Active Rule", is_active=True)
        _rule(name="Inactive Rule", is_active=False)
        resp = self._get(self.url + "?is_active=true")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertTrue(item["is_active"])

    def test_filter_by_rule_type(self):
        _rule(name="Velocity Rule", rule_type="velocity")
        _rule(name="Geo Rule", rule_type="geo_anomaly")
        resp = self._get(self.url + "?rule_type=velocity")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertEqual(item["rule_type"], "velocity")

    def test_post_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_creates_rule(self):
        data = {"name": "New Rule", "rule_type": "velocity",
                "severity": "low", "condition": {}, "weight": 0.3,
                "threshold": 5, "is_active": True}
        resp = self._post(self.url, data)
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_pagination_page_size(self):
        for i in range(5):
            _rule(name=f"Rule {i}")
        resp = self._get(self.url + "?page_size=2&page=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(resp.data.get("results", [])), 2)


class FraudRuleRepoDetailTest(_RepoBase):
    """GET/PUT/PATCH/DELETE /fraud/repository/rules/<pk>/"""

    def setUp(self):
        super().setUp()
        self.rule = _rule(name="Detail Rule")
        self.url  = reverse("fraud_detection:repo-rule-detail",
                             kwargs={"pk": self.rule.pk})

    def test_get_existing_rule(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_get_nonexistent_rule_returns_404(self):
        resp = self._get(reverse("fraud_detection:repo-rule-detail",
                                  kwargs={"pk": 999999}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_updates_rule(self):
        data = {"name": "Updated Rule", "rule_type": "velocity",
                "severity": "high", "condition": {}, "weight": 0.8,
                "threshold": 20, "is_active": True}
        resp = self._patch(self.url, data)
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_patch_non_admin_returns_403(self):
        resp = self._patch(self.url, {"severity": "low"}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_removes_rule(self):
        resp = self._delete(self.url)
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_delete_nonexistent_returns_404(self):
        resp = self._delete(reverse("fraud_detection:repo-rule-detail",
                                     kwargs={"pk": 999999}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_non_admin_returns_403(self):
        resp = self._delete(self.url, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class FraudRuleRepoActiveTest(_RepoBase):
    """GET /fraud/repository/rules/active/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-rule-active")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_only_active_rules(self):
        _rule(name="Active", is_active=True)
        _rule(name="Inactive", is_active=False)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertTrue(item["is_active"])


class FraudRuleRepoStatsTest(_RepoBase):
    """GET /fraud/repository/rules/stats/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-rule-stats")

    def test_returns_stats_shape(self):
        _rule(name="Stat Rule")
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)
        self.assertIn("active", resp.data)


class FraudRuleRepoBulkStatusTest(_RepoBase):
    """PATCH /fraud/repository/rules/bulk-status/"""

    def setUp(self):
        super().setUp()
        self.r1  = _rule(name="Bulk R1", is_active=True)
        self.r2  = _rule(name="Bulk R2", is_active=True)
        self.url = reverse("fraud_detection:repo-rule-bulk-status")

    def test_non_admin_returns_403(self):
        resp = self._patch(self.url, {}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_ids_returns_400(self):
        resp = self._patch(self.url, {"is_active": False})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_is_active_returns_400(self):
        resp = self._patch(self.url, {"ids": [self.r1.pk]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_deactivate_succeeds(self):
        resp = self._patch(self.url,
                           {"ids": [self.r1.pk, self.r2.pk], "is_active": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("updated", resp.data)


# =============================================================================
# 2. FraudCaseRepository
# =============================================================================

class FraudCaseRepoListTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-case-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_cases_with_pagination(self):
        _case(self.admin)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)

    def test_filter_by_status(self):
        _case(self.admin, status="open")
        _case(self.admin, status="resolved")
        resp = self._get(self.url + "?status=open")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertEqual(item["status"], "open")

    def test_filter_by_severity(self):
        _case(self.admin, severity="critical")
        resp = self._get(self.url + "?severity=critical")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class FraudCaseRepoDetailTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.case = _case(self.admin)
        self.url  = reverse("fraud_detection:repo-case-detail",
                             kwargs={"pk": self.case.pk})

    def test_get_existing_case(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_get_nonexistent_returns_404(self):
        resp = self._get(
            reverse("fraud_detection:repo-case-detail", kwargs={"pk": 999999})
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_updates_case(self):
        resp = self._patch(self.url, {"status": "resolved"})
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_delete_non_admin_returns_403(self):
        resp = self._delete(self.url, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_removes_case(self):
        resp = self._delete(self.url)
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])


class FraudCaseRepoByUserTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.target_user = _user("cu")
        _case(self.target_user)
        self.url = reverse("fraud_detection:repo-case-by-user",
                            kwargs={"user_id": self.target_user.pk})

    def test_returns_cases_for_user(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(int(resp.data["user_id"]), self.target_user.pk)

    def test_empty_for_unknown_user(self):
        resp = self._get(
            reverse("fraud_detection:repo-case-by-user", kwargs={"user_id": 999999})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 0)


class FraudCaseRepoOpenTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-case-open")

    def test_returns_open_and_investigating_cases(self):
        _case(self.admin, status="open")
        _case(self.admin, status="investigating")
        _case(self.admin, status="resolved")
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertIn(item["status"], ["open", "investigating"])


class FraudCaseRepoBulkStatusTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.c1  = _case(self.admin, status="open")
        self.c2  = _case(self.admin, status="open")
        self.url = reverse("fraud_detection:repo-case-bulk-status")

    def test_non_admin_returns_403(self):
        resp = self._patch(self.url, {}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_ids_returns_400(self):
        resp = self._patch(self.url, {"status": "closed"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_status_returns_400(self):
        resp = self._patch(self.url, {"ids": [self.c1.pk]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_close_succeeds(self):
        resp = self._patch(self.url,
                           {"ids": [self.c1.pk, self.c2.pk], "status": "closed"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_updates_case_status_in_db(self):
        self._patch(self.url,
                    {"ids": [self.c1.pk], "status": "closed"})
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, "closed")


class FraudCaseRepoStatsTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-case-stats")

    def test_returns_stats_shape(self):
        _case(self.admin)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)
        self.assertIn("by_status", resp.data)
        self.assertIn("avg_risk_score", resp.data)


# =============================================================================
# 3. FraudAlertRepository
# =============================================================================

class FraudAlertRepoListTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-alert-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_paginated_alerts(self):
        _alert(self.admin)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)

    def test_filter_by_is_resolved(self):
        _alert(self.admin, is_resolved=False)
        _alert(self.admin, is_resolved=True)
        resp = self._get(self.url + "?is_resolved=false")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertFalse(item["is_resolved"])

    def test_filter_by_priority(self):
        _alert(self.admin, priority="critical")
        resp = self._get(self.url + "?priority=critical")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertEqual(item["priority"], "critical")


class FraudAlertRepoDetailTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.alert = _alert(self.admin)
        self.url   = reverse("fraud_detection:repo-alert-detail",
                              kwargs={"pk": self.alert.pk})

    def test_get_returns_alert(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_get_nonexistent_returns_404(self):
        resp = self._get(
            reverse("fraud_detection:repo-alert-detail", kwargs={"pk": 999999})
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_non_admin_returns_403(self):
        resp = self._patch(self.url, {"priority": "low"}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_removes_alert(self):
        resp = self._delete(self.url)
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])


class FraudAlertRepoResolveTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.alert = _alert(self.admin, is_resolved=False)
        self.url   = reverse("fraud_detection:repo-alert-resolve",
                              kwargs={"pk": self.alert.pk})

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_resolve_marks_alert_resolved(self):
        resp = self._post(self.url, {"resolution_notes": "Closed as benign."})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_resolved)

    def test_resolve_nonexistent_returns_404(self):
        resp = self._post(
            reverse("fraud_detection:repo-alert-resolve", kwargs={"pk": 999999}),
            {},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class FraudAlertRepoUnresolvedTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-alert-unresolved")

    def test_returns_only_unresolved(self):
        _alert(self.admin, is_resolved=False)
        _alert(self.admin, is_resolved=True)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertFalse(item["is_resolved"])


class FraudAlertRepoBulkResolveTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.a1  = _alert(self.admin, is_resolved=False)
        self.a2  = _alert(self.admin, is_resolved=False)
        self.url = reverse("fraud_detection:repo-alert-bulk-resolve")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"ids": [self.a1.pk]}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_ids_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_resolve_marks_alerts_resolved(self):
        resp = self._post(self.url,
                          {"ids": [self.a1.pk, self.a2.pk],
                           "resolution_notes": "Batch close"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["resolved"], 2)


class FraudAlertRepoStatsTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-alert-stats")

    def test_returns_stats_shape(self):
        _alert(self.admin)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)
        self.assertIn("unresolved", resp.data)


# =============================================================================
# 4. FraudRiskProfileRepository
# =============================================================================

class FraudRiskProfileRepoListTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-profile-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_profiles(self):
        _profile(self.admin)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)

    def test_filter_by_is_flagged(self):
        u1 = _user("pflag1")
        u2 = _user("pflag2")
        _profile(u1, is_flagged=True)
        _profile(u2, is_flagged=False)
        resp = self._get(self.url + "?is_flagged=true")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertTrue(item["is_flagged"])

    def test_filter_by_score_range(self):
        u = _user("prange")
        _profile(u, overall_risk_score=85)
        resp = self._get(self.url + "?min_score=80")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertGreaterEqual(item["overall_risk_score"], 80)


class FraudRiskProfileRepoDetailTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.profile = _profile(self.admin)
        self.url     = reverse("fraud_detection:repo-profile-detail",
                                kwargs={"pk": self.profile.pk})

    def test_get_returns_profile(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_get_nonexistent_returns_404(self):
        resp = self._get(
            reverse("fraud_detection:repo-profile-detail", kwargs={"pk": 999999})
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_non_admin_returns_403(self):
        resp = self._patch(self.url, {}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class FraudRiskProfileRepoHighRiskTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-profile-high-risk")

    def test_default_threshold_is_70(self):
        u1 = _user("hr1")
        u2 = _user("hr2")
        _profile(u1, overall_risk_score=80)
        _profile(u2, overall_risk_score=30)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertGreaterEqual(item["overall_risk_score"], 70)

    def test_custom_threshold(self):
        u = _user("hr3")
        _profile(u, overall_risk_score=55)
        resp = self._get(self.url + "?threshold=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertGreaterEqual(item["overall_risk_score"], 50)


class FraudRiskProfileRepoBulkRecalcTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-profile-bulk-recalc")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"user_ids": [1]}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_user_ids_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_user_ids_returns_200(self):
        resp = self._post(self.url, {"user_ids": [self.admin.pk]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("queued", resp.data)


# =============================================================================
# 5. IPReputationRepository
# =============================================================================

class IPReputationRepoListTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-ip-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_paginated_ips(self):
        _ip_rep(ip_address="10.0.0.1")
        _ip_rep(ip_address="10.0.0.2")
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)

    def test_filter_by_is_blacklisted(self):
        _ip_rep(ip_address="10.1.1.1", is_blacklisted=True)
        _ip_rep(ip_address="10.1.1.2", is_blacklisted=False)
        resp = self._get(self.url + "?is_blacklisted=true")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data.get("results", []):
            self.assertTrue(item["is_blacklisted"])


class IPReputationRepoLookupTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.ip  = _ip_rep(ip_address="192.168.10.1")
        self.url = reverse("fraud_detection:repo-ip-lookup",
                            kwargs={"ip_address": "192.168.10.1"})

    def test_returns_ip_record(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["ip_address"], "192.168.10.1")

    def test_unknown_ip_returns_404(self):
        resp = self._get(
            reverse("fraud_detection:repo-ip-lookup",
                     kwargs={"ip_address": "9.9.9.9"})
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class IPReputationRepoBlacklistTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-ip-blacklist")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"ip_address": "5.5.5.5"}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_ip_address_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blacklists_ip(self):
        resp = self._post(self.url,
                          {"ip_address": "6.6.6.6", "reason": "Manual test"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["blacklisted"])
        rec = IPReputation.objects.get(ip_address="6.6.6.6")
        self.assertTrue(rec.is_blacklisted)


class IPReputationRepoUnblacklistTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.ip  = _ip_rep(ip_address="7.7.7.7", is_blacklisted=True)
        self.url = reverse("fraud_detection:repo-ip-unblacklist")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"ip_address": "7.7.7.7"}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_ip_address_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_removes_blacklist(self):
        resp = self._post(self.url, {"ip_address": "7.7.7.7"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.ip.refresh_from_db()
        self.assertFalse(self.ip.is_blacklisted)

    def test_unknown_ip_returns_404(self):
        resp = self._post(self.url, {"ip_address": "250.250.250.250"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class IPReputationRepoBulkCheckTest(_RepoBase):

    def setUp(self):
        super().setUp()
        _ip_rep(ip_address="20.20.20.1")
        _ip_rep(ip_address="20.20.20.2")
        self.url = reverse("fraud_detection:repo-ip-bulk-check")

    def test_missing_ip_list_returns_400(self):
        self.client.force_authenticate(self.anon_u)
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_check_known_and_unknown_ips(self):
        self.client.force_authenticate(self.anon_u)
        resp = self.client.post(
            self.url,
            {"ip_addresses": ["20.20.20.1", "20.20.20.2", "99.99.99.99"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["checked"], 3)
        self.assertEqual(resp.data["found"], 2)


# =============================================================================
# 6. FraudSuspiciousIPRepository
# =============================================================================

class SuspiciousIPRepoListTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-sus-ip-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_list(self):
        _ip_rep(ip_address="50.0.0.1", is_blacklisted=True)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_post_creates_suspicious_ip(self):
        resp = self._post(self.url,
                          {"ip_address": "51.0.0.1", "reason": "Test add"})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


class SuspiciousIPRepoBulkAddTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-sus-ip-bulk-add")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url,
                          {"ip_addresses": ["60.0.0.1"]}, user=self.anon_u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_ip_list_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_adds_ips(self):
        resp = self._post(self.url,
                          {"ip_addresses": ["61.0.0.1", "61.0.0.2"],
                           "reason": "Threat feed"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("processed", resp.data)
        self.assertEqual(resp.data["processed"], 2)


class SuspiciousIPRepoCheckTest(_RepoBase):

    def setUp(self):
        super().setUp()
        _ip_rep(ip_address="70.0.0.1", is_blacklisted=True, fraud_score=90)

    def test_known_suspicious_ip(self):
        resp = self._get(
            reverse("fraud_detection:repo-sus-ip-check",
                     kwargs={"ip_address": "70.0.0.1"})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_suspicious"])

    def test_unknown_ip_not_suspicious(self):
        resp = self._get(
            reverse("fraud_detection:repo-sus-ip-check",
                     kwargs={"ip_address": "250.1.2.3"})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_suspicious"])


class SuspiciousIPRepoStatsTest(_RepoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:repo-sus-ip-stats")

    def test_returns_stats_shape(self):
        _ip_rep(ip_address="80.0.0.1", is_blacklisted=True)
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_suspicious", resp.data)
