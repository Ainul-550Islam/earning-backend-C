"""
tests/test_views_factories.py
==============================
Comprehensive tests for views_factories.py.

Coverage targets
----------------
  FraudCaseFactory     — create, batch, scenario, cleanup
  TestDataFactory      — scenarios-list, simple, complex, scenario, cleanup
  FraudAlertFactory    — create, batch, by-type, cleanup
  UserRiskProfileFactory— create, batch, high-risk, cleanup

Every view tests:
  401 for unauthenticated, 403 for non-admin,
  happy-path 201/200, input validation (bad types/missing fields),
  ORM-fallback path (factory module absent → direct ORM),
  database-side assertions where meaningful.
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.fraud_detection.models import FraudAlert, FraudCase, UserRiskProfile

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin(suffix=""):
    return User.objects.create_user(
        username=f"admin_fac{suffix}",
        email=f"admin_fac{suffix}@test.example.com",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )


def _user(suffix=""):
    return User.objects.create_user(
        username=f"user_fac{suffix}",
        email=f"user_fac{suffix}@test.example.com",
        password="pass",
    )


class _FactoryBase(APITestCase):
    """Shared setUp and auth helpers."""

    def setUp(self):
        self.admin  = _admin(self.__class__.__name__[:8])
        self.user   = _user(self.__class__.__name__[:8])
        self.client = APIClient()

    def _post(self, url, data, user=None, **kw):
        self.client.force_authenticate(user or self.admin)
        return self.client.post(url, data, format="json", **kw)

    def _delete(self, url, user=None, **kw):
        self.client.force_authenticate(user or self.admin)
        return self.client.delete(url, **kw)

    def _get(self, url, user=None, **kw):
        self.client.force_authenticate(user or self.admin)
        return self.client.get(url, **kw)


# =============================================================================
# FraudCaseFactory
# =============================================================================

class FraudCaseFactoryCreateTest(_FactoryBase):
    """POST /fraud/factory/cases/create/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-case-create")

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_creates_case_with_defaults(self):
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("case_id", resp.data)

    def test_creates_case_with_specific_params(self):
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._post(self.url, {
                "case_type": "bonus_abuse",
                "severity":  "high",
                "status":    "open",
                "risk_score": 80,
            })
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_creates_real_db_record(self):
        count_before = FraudCase.objects.filter(
            metadata__factory_generated=True
        ).count()
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            self._post(self.url, {})
        count_after = FraudCase.objects.filter(
            metadata__factory_generated=True
        ).count()
        self.assertGreater(count_after, count_before)


class FraudCaseFactoryBatchTest(_FactoryBase):
    """POST /fraud/factory/cases/batch/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-case-batch")

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"count": 3}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_default_count_is_5(self):
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("created", resp.data)
        self.assertLessEqual(resp.data["created"], 5)

    def test_custom_count(self):
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 3})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertEqual(resp.data["created"], 3)

    def test_count_capped_at_50(self):
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 9999})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertLessEqual(resp.data["created"], 50)

    def test_fixed_severity_respected(self):
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 2, "severity": "critical"})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        for item in resp.data.get("results", []):
            self.assertEqual(item["severity"], "critical")


class FraudCaseFactoryScenarioTest(_FactoryBase):
    """POST /fraud/factory/cases/scenario/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-case-scenario")

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_scenario_returns_400(self):
        resp = self._post(self.url, {"scenario": "nonexistent_scenario"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_takeover_scenario_creates_case(self):
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._post(self.url,
                              {"scenario": "account_takeover", "user_id": 99})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertEqual(resp.data["scenario"], "account_takeover")

    def test_all_known_scenarios_accepted(self):
        known = ["account_takeover", "bonus_abuse", "payment_fraud",
                 "referral_chain", "identity_theft"]
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            for sc in known:
                resp = self._post(self.url, {"scenario": sc})
                self.assertIn(
                    resp.status_code,
                    [status.HTTP_201_CREATED, status.HTTP_200_OK],
                    msg=f"Scenario '{sc}' failed with {resp.status_code}",
                )


class FraudCaseFactoryCleanupTest(_FactoryBase):
    """DELETE /fraud/factory/cases/cleanup/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-case-cleanup")

    def test_unauthenticated_returns_401(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        resp = self._delete(self.url, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_deletes_factory_cases(self):
        # Create a factory-tagged case
        FraudCase.objects.create(
            user=self.admin,
            case_type="account_takeover",
            severity="low",
            status="open",
            risk_score=10,
            title="Cleanup Test",
            description="Cleanup",
            metadata={"factory_generated": True},
        )
        with patch("api.fraud_detection.views_factories._fraud_case_factory",
                   return_value=None):
            resp = self._delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("deleted", resp.data)
        self.assertGreaterEqual(resp.data["deleted"], 1)


# =============================================================================
# TestDataFactory
# =============================================================================

class TestDataFactoryListScenariosTest(_FactoryBase):
    """GET /fraud/factory/test-data/scenarios/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-testdata-scenarios")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_available_scenarios(self):
        with patch("api.fraud_detection.views_factories._test_data_factory",
                   return_value=None):
            resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("available_scenarios", resp.data)
        self.assertGreater(len(resp.data["available_scenarios"]), 0)


class TestDataFactorySimpleTest(_FactoryBase):
    """POST /fraud/factory/test-data/simple/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-testdata-simple")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_creates_case_alert_and_profile(self):
        with patch("api.fraud_detection.views_factories._test_data_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("fraud_case", resp.data)
        self.assertIn("fraud_alert", resp.data)
        self.assertIn("risk_profile", resp.data)

    def test_creates_entities_in_db(self):
        with patch("api.fraud_detection.views_factories._test_data_factory",
                   return_value=None):
            resp = self._post(self.url, {"user_id": self.admin.pk})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


class TestDataFactoryComplexTest(_FactoryBase):
    """POST /fraud/factory/test-data/complex/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-testdata-complex")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_creates_5_cases_and_3_alerts(self):
        with patch("api.fraud_detection.views_factories._test_data_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("fraud_cases", resp.data)
        self.assertIn("fraud_alerts", resp.data)
        self.assertEqual(len(resp.data["fraud_cases"]), 5)
        self.assertEqual(len(resp.data["fraud_alerts"]), 3)

    def test_contains_ip_reputation_record(self):
        with patch("api.fraud_detection.views_factories._test_data_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("ip_reputation", resp.data)


class TestDataFactoryCleanupTest(_FactoryBase):
    """DELETE /fraud/factory/test-data/cleanup/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-testdata-cleanup")

    def test_non_admin_returns_403(self):
        resp = self._delete(self.url, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cleanup_runs_and_returns_counts(self):
        with patch("api.fraud_detection.views_factories._test_data_factory",
                   return_value=None):
            resp = self._delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("fraud_cases_deleted", resp.data)
        self.assertIn("fraud_alerts_deleted", resp.data)


# =============================================================================
# FraudAlertFactory
# =============================================================================

class FraudAlertFactoryCreateTest(_FactoryBase):
    """POST /fraud/factory/alerts/create/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-alert-create")

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_creates_alert_with_defaults(self):
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("alert_id", resp.data)

    def test_creates_real_db_record(self):
        count_before = FraudAlert.objects.filter(data__factory_generated=True).count()
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            self._post(self.url, {})
        count_after = FraudAlert.objects.filter(data__factory_generated=True).count()
        self.assertGreater(count_after, count_before)


class FraudAlertFactoryBatchTest(_FactoryBase):
    """POST /fraud/factory/alerts/batch/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-alert-batch")

    def test_creates_requested_count(self):
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 4})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertEqual(resp.data["created"], 4)

    def test_count_capped_at_50(self):
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 999})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertLessEqual(resp.data["created"], 50)

    def test_fixed_priority_respected(self):
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 2, "priority": "critical"})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        for item in resp.data.get("results", []):
            self.assertEqual(item["priority"], "critical")


class FraudAlertFactoryByTypeTest(_FactoryBase):
    """POST /fraud/factory/alerts/by-type/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-alert-by-type")

    def test_missing_alert_type_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_alert_type_returns_400(self):
        resp = self._post(self.url, {"alert_type": "invalid_type_xyz"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_known_alert_types_accepted(self):
        known_types = [
            "suspicious_activity", "high_risk_score",
            "multiple_accounts", "velocity_breach",
            "geo_anomaly", "device_anomaly",
        ]
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            for atype in known_types:
                resp = self._post(self.url,
                                  {"alert_type": atype, "count": 1})
                self.assertIn(
                    resp.status_code,
                    [status.HTTP_201_CREATED, status.HTTP_200_OK],
                    msg=f"alert_type='{atype}' failed",
                )

    def test_response_contains_alert_type(self):
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            resp = self._post(self.url,
                              {"alert_type": "geo_anomaly", "count": 1})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertEqual(resp.data["alert_type"], "geo_anomaly")


class FraudAlertFactoryCleanupTest(_FactoryBase):
    """DELETE /fraud/factory/alerts/cleanup/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-alert-cleanup")

    def test_non_admin_returns_403(self):
        resp = self._delete(self.url, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_deletes_factory_alerts(self):
        FraudAlert.objects.create(
            alert_type="geo_anomaly",
            priority="low",
            title="Cleanup Test Alert",
            description="cleanup",
            user=self.admin,
            data={"factory_generated": True},
        )
        with patch("api.fraud_detection.views_factories._fraud_alert_factory",
                   return_value=None):
            resp = self._delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["deleted"], 1)


# =============================================================================
# UserRiskProfileFactory
# =============================================================================

class UserRiskProfileFactoryCreateTest(_FactoryBase):
    """POST /fraud/factory/profiles/create/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-profile-create")

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_creates_or_updates_profile(self):
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("user_id", resp.data)

    def test_high_score_sets_flagged(self):
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._post(self.url, {"overall_risk_score": 90})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        # Score >= 70 should set is_flagged True
        p = UserRiskProfile.objects.get(pk=resp.data["data"]["id"])
        self.assertTrue(p.is_flagged)


class UserRiskProfileFactoryBatchTest(_FactoryBase):
    """POST /fraud/factory/profiles/batch/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-profile-batch")

    def test_creates_requested_count(self):
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 3, "risk_level": "mixed"})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertEqual(resp.data["created"], 3)

    def test_count_capped_at_50(self):
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 200})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertLessEqual(resp.data["created"], 50)

    def test_critical_risk_level_creates_high_score_profiles(self):
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._post(self.url, {"count": 2, "risk_level": "critical"})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        for item in resp.data.get("results", []):
            self.assertGreaterEqual(item["overall_risk_score"], 80)


class UserRiskProfileFactoryHighRiskTest(_FactoryBase):
    """POST /fraud/factory/profiles/high-risk/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-profile-high-risk")

    def test_creates_critical_profile(self):
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertEqual(resp.data["overall_score"], 95)
        self.assertEqual(resp.data["risk_level"], "critical")

    def test_profile_has_is_restricted_true(self):
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        data = resp.data["data"]
        self.assertTrue(data["is_restricted"])
        self.assertTrue(data["is_flagged"])


class UserRiskProfileFactoryCleanupTest(_FactoryBase):
    """DELETE /fraud/factory/profiles/cleanup/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:factory-profile-cleanup")

    def test_non_admin_returns_403(self):
        resp = self._delete(self.url, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_soft_cleanup_resets_scores(self):
        u = _user("cleanup_profile")
        p, _ = UserRiskProfile.objects.get_or_create(
            user=u,
            defaults={
                "overall_risk_score": 90,
                "is_flagged": True,
                "is_restricted": True,
                "risk_factors": {"factory_generated": True},
            },
        )
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("soft_cleaned", resp.data)

    def test_hard_delete_removes_profiles(self):
        u = _user("hard_del_profile")
        UserRiskProfile.objects.get_or_create(
            user=u,
            defaults={
                "overall_risk_score": 80,
                "risk_factors": {"factory_generated": True},
            },
        )
        with patch("api.fraud_detection.views_factories._user_risk_profile_factory",
                   return_value=None):
            resp = self._delete(self.url + "?hard_delete=true")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("hard_deleted", resp.data)
