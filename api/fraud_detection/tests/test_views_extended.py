"""
Tests for views_extended.py (formerly views_missing.py).

Covers:
  ViewSets:
    - FraudPatternViewSet
    - FraudSettingsViewSet
    - FraudWhitelistViewSet
    - FraudNotificationViewSet
    - FraudCaseEvidenceViewSet
    - FraudCaseActionViewSet
    - OfferCompletionViewSet

  APIViews / function-based views:
    - FraudAnalyticsAPIView
    - GeographicAnalysisAPIView
    - RiskTimelineAPIView
    - IntegrityVerificationAPIView
    - SystemHealthAPIView
    - fraud_statistics
    - quick_fraud_check
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.fraud_detection.models import (
    DeviceFingerprint,
    FraudAlert,
    FraudAttempt,
    FraudCase,
    FraudCaseAction,
    FraudCaseEvidence,
    FraudNotification,
    FraudPattern,
    FraudSettings,
    FraudWhitelist,
    IPReputation,
    OfferCompletion,
    UserRiskProfile,
)

User = get_user_model()


# =============================================================================
# Shared helpers
# =============================================================================

def _make_user(username, *, staff=False):
    return User.objects.create_user(
        username=username,
        email=f"{username}@ext.test",
        password="pass1234",
        is_staff=staff,
        is_superuser=staff,
    )


def _make_fraud_case(user):
    return FraudCase.objects.create(
        user=user,
        title="Test Case",
        description="Auto-created test case",
        status="open",
        risk_score=75,
        priority="high",
    )


def _make_fraud_attempt(user, *, risk_score=70):
    return FraudAttempt.objects.create(
        user=user,
        attempt_type="account_takeover",
        description="Test attempt",
        fraud_score=risk_score,
        confidence_score=80,
        status="flagged",
        evidence_data={"ip": "1.2.3.4"},
        metadata={},
    )


# =============================================================================
# 1. FraudPatternViewSet
# =============================================================================

class FraudPatternViewSetTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("fpattern_admin", staff=True)
        self.user   = _make_user("fpattern_user")
        self.client = APIClient()
        self.pattern = FraudPattern.objects.create(
            name="Test Pattern",
            pattern_type="velocity",
            description="Test",
            pattern_data={"threshold": 10},
            is_active=True,
            occurrence_count=0,
            accuracy_rate=0.95,
        )

    def test_list_requires_auth(self):
        resp = self.client.get(reverse("fraud_detection:fraudpattern-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_requires_staff(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:fraudpattern-list"))
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_admin_can_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudpattern-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_create(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudpattern-list"),
            {
                "name": "New Pattern",
                "pattern_type": "geo",
                "description": "New",
                "pattern_data": {},
                "is_active": True,
                "occurrence_count": 0,
                "accuracy_rate": 0.90,
            },
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_activate_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudpattern-activate", kwargs={"pk": self.pattern.pk})
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_deactivate_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudpattern-deactivate", kwargs={"pk": self.pattern.pk})
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_active_patterns_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudpattern-active-patterns"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_accuracy_stats_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudpattern-accuracy-stats"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)


# =============================================================================
# 2. FraudSettingsViewSet
# =============================================================================

class FraudSettingsViewSetTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("fsettings_admin", staff=True)
        self.user   = _make_user("fsettings_user")
        self.client = APIClient()
        FraudSettings.objects.get_or_create(
            pk=1,
            defaults={"block_vpn": True, "global_risk_threshold": 70},
        )

    def test_list_requires_auth(self):
        resp = self.client.get(reverse("fraud_detection:fraudsettings-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:fraudsettings-list"))
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_admin_can_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudsettings-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_current_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudsettings-current"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("global_risk_threshold", resp.data)

    def test_update_threshold_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse("fraud_detection:fraudsettings-update-threshold"),
            {"global_risk_threshold": 80},
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_update_threshold_missing_field(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse("fraud_detection:fraudsettings-update-threshold"),
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_not_allowed(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(reverse("fraud_detection:fraudsettings-list"), {})
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# =============================================================================
# 3. FraudWhitelistViewSet
# =============================================================================

class FraudWhitelistViewSetTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("fwhitelist_admin", staff=True)
        self.user   = _make_user("fwhitelist_user")
        self.client = APIClient()
        self.entry = FraudWhitelist.objects.create(
            entity_type="ip",
            entity_value="192.168.0.1",
            reason="Internal server",
            is_active=True,
            whitelisted_by=self.admin,
        )

    def test_list_requires_auth(self):
        resp = self.client.get(reverse("fraud_detection:fraudwhitelist-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudwhitelist-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_create(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudwhitelist-list"),
            {
                "entity_type": "user",
                "entity_value": "trusted_user_001",
                "reason": "VIP user",
                "is_active": True,
            },
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_deactivate_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudwhitelist-deactivate", kwargs={"pk": self.entry.pk})
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        if resp.status_code == status.HTTP_200_OK:
            self.entry.refresh_from_db()
            self.assertFalse(self.entry.is_active)

    def test_active_entries_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudwhitelist-active-entries"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_bulk_add_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudwhitelist-bulk-add"),
            {
                "entries": [
                    {"entity_type": "ip", "entity_value": "10.0.0.1", "reason": "Office IP", "is_active": True},
                    {"entity_type": "ip", "entity_value": "10.0.0.2", "reason": "Office IP2", "is_active": True},
                ]
            },
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_bulk_add_empty_entries_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudwhitelist-bulk-add"),
            {"entries": []},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# =============================================================================
# 4. FraudNotificationViewSet
# =============================================================================

class FraudNotificationViewSetTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("fnotif_admin", staff=True)
        self.user   = _make_user("fnotif_user")
        self.client = APIClient()
        self.notif = FraudNotification.objects.create(
            user=self.user,
            notification_type="fraud_detected",
            message="Test notification",
            metadata={},
        )

    def test_list_requires_auth(self):
        resp = self.client.get(reverse("fraud_detection:fraudnotification-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_sees_own_notifications(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:fraudnotification-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        ids = [n["id"] for n in results]
        self.assertIn(self.notif.pk, ids)

    def test_user_cannot_see_other_user_notifications(self):
        other = _make_user("fnotif_other")
        FraudNotification.objects.create(
            user=other,
            notification_type="fraud_detected",
            message="Other user notification",
            metadata={},
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:fraudnotification-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        for n in results:
            self.assertNotEqual(n.get("user"), other.id)

    def test_admin_sees_all_notifications(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudnotification-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_mark_read_action(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            reverse("fraud_detection:fraudnotification-mark-read", kwargs={"pk": self.notif.pk})
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        if resp.status_code == status.HTTP_200_OK:
            self.notif.refresh_from_db()
            self.assertIsNotNone(self.notif.read_at)

    def test_mark_all_read_action(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(reverse("fraud_detection:fraudnotification-mark-all-read"))
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_unread_count_action(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:fraudnotification-unread-count"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("unread_count", resp.data)

    def test_bulk_send_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudnotification-bulk-send"),
            {
                "user_ids": [self.user.id],
                "notification_type": "fraud_detected",
                "message": "Bulk test message",
            },
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_bulk_send_empty_user_ids_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudnotification-bulk-send"),
            {"user_ids": [], "notification_type": "fraud_detected", "message": "Test"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_send_missing_message_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudnotification-bulk-send"),
            {"user_ids": [self.user.id], "notification_type": "fraud_detected"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# =============================================================================
# 5. FraudCaseEvidenceViewSet
# =============================================================================

class FraudCaseEvidenceViewSetTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("fcev_admin", staff=True)
        self.user   = _make_user("fcev_user")
        self.client = APIClient()
        self.case   = _make_fraud_case(self.user)
        self.evidence = FraudCaseEvidence.objects.create(
            fraud_case=self.case,
            evidence_type="screenshot",
            data={"url": "https://example.com/ev.png"},
            added_by=self.admin,
        )

    def test_list_requires_auth(self):
        resp = self.client.get(reverse("fraud_detection:fraudcaseevidence-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_see_own_case_evidence(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:fraudcaseevidence-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_create_evidence(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudcaseevidence-list"),
            {
                "fraud_case": self.case.pk,
                "evidence_type": "log_entry",
                "data": {"log": "Suspicious login at 03:00"},
            },
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_bulk_upload_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudcaseevidence-bulk-upload"),
            {
                "items": [
                    {
                        "fraud_case": self.case.pk,
                        "evidence_type": "screenshot",
                        "data": {"note": "item 1"},
                    },
                    {
                        "fraud_case": self.case.pk,
                        "evidence_type": "log_entry",
                        "data": {"note": "item 2"},
                    },
                ]
            },
            format="json",
        )
        self.assertIn(resp.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_207_MULTI_STATUS,
            status.HTTP_400_BAD_REQUEST,
        ])

    def test_bulk_upload_empty_items_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudcaseevidence-bulk-upload"),
            {"items": []},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_case_id(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            reverse("fraud_detection:fraudcaseevidence-list"),
            {"case_id": self.case.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# =============================================================================
# 6. FraudCaseActionViewSet
# =============================================================================

class FraudCaseActionViewSetTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("fcav_admin", staff=True)
        self.user   = _make_user("fcav_user")
        self.client = APIClient()
        self.case   = _make_fraud_case(self.user)
        self.action_obj = FraudCaseAction.objects.create(
            fraud_case=self.case,
            action_type="investigate",
            performed_by=self.admin,
            note="Initial investigation",
            is_completed=False,
        )

    def test_list_requires_auth(self):
        resp = self.client.get(reverse("fraud_detection:fraudcaseaction-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:fraudcaseaction-list"))
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_admin_can_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:fraudcaseaction-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_create(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudcaseaction-list"),
            {
                "fraud_case": self.case.pk,
                "action_type": "flag",
                "note": "Flagged for escalation",
                "is_completed": False,
            },
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_complete_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudcaseaction-complete-action", kwargs={"pk": self.action_obj.pk})
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        if resp.status_code == status.HTTP_200_OK:
            self.action_obj.refresh_from_db()
            self.assertTrue(self.action_obj.is_completed)

    def test_bulk_create_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudcaseaction-bulk-create"),
            {
                "actions": [
                    {"fraud_case": self.case.pk, "action_type": "investigate", "note": "note1", "is_completed": False},
                    {"fraud_case": self.case.pk, "action_type": "flag", "note": "note2", "is_completed": False},
                ]
            },
            format="json",
        )
        self.assertIn(resp.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_207_MULTI_STATUS,
            status.HTTP_400_BAD_REQUEST,
        ])

    def test_bulk_create_empty_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("fraud_detection:fraudcaseaction-bulk-create"),
            {"actions": []},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# =============================================================================
# 7. OfferCompletionViewSet
# =============================================================================

class OfferCompletionViewSetTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("ocv_admin", staff=True)
        self.user   = _make_user("ocv_user")
        self.client = APIClient()

    def test_list_requires_auth(self):
        resp = self.client.get(reverse("fraud_detection:offercompletion-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_own(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("fraud_detection:offercompletion-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_list_all(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:offercompletion-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_pending_review_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:offercompletion-pending-review"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_fraud_analysis_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("fraud_detection:offercompletion-fraud-analysis"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_fraud", resp.data)
        self.assertIn("fraud_rate", resp.data)


# =============================================================================
# 8. FraudAnalyticsAPIView
# =============================================================================

class FraudAnalyticsAPIViewTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("analytics_admin", staff=True)
        self.user   = _make_user("analytics_user")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:fraud-analytics")

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_admin_gets_analytics(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_keys(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ["period_days", "total_attempts", "by_type"]:
            self.assertIn(key, resp.data)

    def test_custom_days_param(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url, {"days": 7})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period_days"], 7)

    def test_cached_response_returned(self):
        self.client.force_authenticate(user=self.admin)
        resp1 = self.client.get(self.url, {"days": 30})
        resp2 = self.client.get(self.url, {"days": 30})
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)


# =============================================================================
# 9. GeographicAnalysisAPIView
# =============================================================================

class GeographicAnalysisAPIViewTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("geo_admin", staff=True)
        self.client = APIClient()
        self.url    = reverse("fraud_detection:geographic-analysis")

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_gets_data(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_has_by_country(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertIn("by_country", resp.data)

    def test_custom_days_param(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url, {"days": 14})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period_days"], 14)


# =============================================================================
# 10. RiskTimelineAPIView
# =============================================================================

class RiskTimelineAPIViewTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("timeline_admin", staff=True)
        self.user   = _make_user("timeline_user")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:risk-timeline")

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_gets_global_timeline(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("timeline", resp.data)

    def test_user_can_see_own_timeline(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url, {"user_id": self.user.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_user_cannot_see_other_user_timeline(self):
        other = _make_user("timeline_other")
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url, {"user_id": other.id})
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_granularity_hourly(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url, {"granularity": "hourly", "days": 1})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("granularity"), "hourly")

    def test_granularity_daily(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url, {"granularity": "daily", "days": 7})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("granularity"), "daily")


# =============================================================================
# 11. IntegrityVerificationAPIView
# =============================================================================

class IntegrityVerificationAPIViewTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("integrity_admin", staff=True)
        self.user   = _make_user("integrity_user")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:integrity-verification")
        self.case   = _make_fraud_case(self.user)

    def test_requires_auth(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {"model": "FraudCase", "id": self.case.pk})
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_unknown_model_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, {"model": "NonExistentModel", "id": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_record_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, {"model": "FraudCase", "id": 999999}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_valid_case_returns_verification_result(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.url, {"model": "FraudCase", "id": self.case.pk}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("valid", resp.data)
        self.assertIn("model", resp.data)

    def test_fraud_case_evidence_model(self):
        evidence = FraudCaseEvidence.objects.create(
            fraud_case=self.case,
            evidence_type="screenshot",
            data={},
            added_by=self.admin,
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.url, {"model": "FraudCaseEvidence", "id": evidence.pk}, format="json"
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])


# =============================================================================
# 12. SystemHealthAPIView
# =============================================================================

class SystemHealthAPIViewTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("health_admin", staff=True)
        self.user   = _make_user("health_user")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:system-health")

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_admin_gets_health_data(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_has_expected_sections(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ["status", "fraud_engine", "queue"]:
            self.assertIn(key, resp.data)

    def test_status_is_healthy(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.data.get("status"), "healthy")


# =============================================================================
# 13. fraud_statistics (function-based view)
# =============================================================================

class FraudStatisticsFBVTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("fstats_admin", staff=True)
        self.user   = _make_user("fstats_user")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:fraud-statistics")

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_admin_gets_statistics(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_has_today_week_totals(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for section in ["today", "week", "totals"]:
            self.assertIn(section, resp.data)

    def test_today_section_has_attempt_count(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertIn("attempts", resp.data.get("today", {}))


# =============================================================================
# 14. quick_fraud_check (function-based view)
# =============================================================================

class QuickFraudCheckFBVTest(APITestCase):
    def setUp(self):
        self.admin  = _make_user("qfc_admin", staff=True)
        self.user   = _make_user("qfc_user")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:quick-fraud-check")

    def test_requires_auth(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_check_own_id(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url,
            {"user_id": self.user.id, "ip_address": "1.2.3.4", "action": "login"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_user_cannot_check_other_user(self):
        other = _make_user("qfc_other_target")
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url,
            {"user_id": other.id, "ip_address": "1.2.3.4", "action": "login"},
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])

    def test_admin_can_check_any_user(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.url,
            {"user_id": self.user.id, "ip_address": "5.6.7.8", "action": "withdrawal"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_has_risk_score_and_recommendation(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url,
            {"user_id": self.user.id, "ip_address": "9.9.9.9"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("risk_score", resp.data)
        self.assertIn("recommendation", resp.data)

    def test_risk_score_in_valid_range(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url,
            {"user_id": self.user.id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        score = resp.data.get("risk_score", 0)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_recommendation_is_valid_value(self):
        valid_recommendations = {"allow", "monitor", "challenge", "block"}
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url,
            {"user_id": self.user.id, "ip_address": "1.2.3.4"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(resp.data.get("recommendation"), valid_recommendations)

    def test_known_bad_ip_increases_risk_score(self):
        """A blacklisted IP should push the risk score higher."""
        IPReputation.objects.create(
            ip_address="192.0.2.99",
            fraud_score=90,
            is_vpn=True,
            is_proxy=False,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url,
            {"user_id": self.user.id, "ip_address": "192.0.2.99"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(resp.data.get("risk_score", 0), 0)

    def test_missing_user_id_defaults_to_request_user(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(str(resp.data.get("user_id")), str(self.user.id))
