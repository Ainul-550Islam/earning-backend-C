"""
tests/test_views_notification_signals.py
=========================================
Tests for views_notification_service.py,
views_signals_monitor.py, and the three new
serializers added to serializers.py.

Coverage targets
----------------
NotificationService (7 views):
  create-alert, create-and-send-alert,
  create-case, create-and-send-case,
  channels, extended-stats, test

SignalsMonitor (12 views):
  status, handlers, activity, stats,
  trigger/fraud-attempt, trigger/ip-change,
  trigger/device-update, trigger/risk-recalc,
  trigger/alert-handler, trigger/whitelist-sync,
  middleware/status, middleware/stats

Serializers (3 new classes):
  FraudAlertCreateSerializer,
  FraudRuleCreateSerializer,
  FraudRuleUpdateSerializer
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
    FraudNotification,
    FraudRule,
    FraudWhitelist,
    IPReputation,
    UserRiskProfile,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin(suffix=""):
    return User.objects.create_user(
        username=f"admin_ns{suffix}",
        email=f"admin_ns{suffix}@test.example.com",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )


def _user(suffix=""):
    return User.objects.create_user(
        username=f"user_ns{suffix}",
        email=f"user_ns{suffix}@test.example.com",
        password="pass",
    )


def _alert(user, **kw):
    defaults = dict(
        alert_type="suspicious_activity", priority="high",
        title="Test", description="Test", is_resolved=False, data={},
    )
    defaults.update(kw)
    return FraudAlert.objects.create(user=user, **defaults)


def _case(user, **kw):
    defaults = dict(
        case_type="account_takeover", severity="high",
        status="open", risk_score=75,
        title="Test Case", description="Test", metadata={},
    )
    defaults.update(kw)
    return FraudCase.objects.create(user=user, **defaults)


def _rule(**kw):
    defaults = dict(
        name="Signal Test Rule", rule_type="velocity",
        severity="medium", condition={}, weight=0.5,
        threshold=10, is_active=True,
    )
    defaults.update(kw)
    return FraudRule.objects.create(**defaults)


class _NSBase(APITestCase):
    def setUp(self):
        self.admin  = _admin(self.__class__.__name__[:6])
        self.user   = _user(self.__class__.__name__[:6])
        self.client = APIClient()

    def _post(self, url, data, user=None, **kw):
        self.client.force_authenticate(user or self.admin)
        return self.client.post(url, data, format="json", **kw)

    def _get(self, url, user=None):
        self.client.force_authenticate(user or self.user)
        return self.client.get(url)


# =============================================================================
# NotificationService views
# =============================================================================

class NotifServiceCreateAlertNotifTest(_NSBase):
    """POST /fraud/notifications/service/alert/<id>/create/"""

    def setUp(self):
        super().setUp()
        self.alert = _alert(self.admin)
        self.url   = reverse("fraud_detection:notif-service-alert-create",
                              kwargs={"alert_id": self.alert.pk})

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_alert_returns_404(self):
        resp = self._post(
            reverse("fraud_detection:notif-service-alert-create",
                     kwargs={"alert_id": 999999}),
            {},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_creates_notification_record(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertTrue(resp.data["created"])

    def test_service_method_called_when_available(self):
        mock_svc = MagicMock()
        mock_svc.create_alert_notification.return_value = True
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=mock_svc):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        mock_svc.create_alert_notification.assert_called_once_with(self.alert.pk)


class NotifServiceCreateAndSendAlertTest(_NSBase):
    """POST /fraud/notifications/service/alert/<id>/create-and-send/"""

    def setUp(self):
        super().setUp()
        self.alert = _alert(self.admin)
        self.url   = reverse("fraud_detection:notif-service-alert-create-send",
                              kwargs={"alert_id": self.alert.pk})

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_alert_returns_404(self):
        resp = self._post(
            reverse("fraud_detection:notif-service-alert-create-send",
                     kwargs={"alert_id": 999999}),
            {},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_creates_and_marks_sent(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertIn("sent", resp.data)

    def test_response_has_both_created_and_sent_keys(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn("created", resp.data)
        self.assertIn("sent", resp.data)
        self.assertIn("alert_id", resp.data)


class NotifServiceCreateCaseNotifTest(_NSBase):
    """POST /fraud/notifications/service/case/<id>/create/"""

    def setUp(self):
        super().setUp()
        self.case = _case(self.admin)
        self.url  = reverse("fraud_detection:notif-service-case-create",
                             kwargs={"case_id": self.case.pk})

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"notification_type": "case_created"},
                          user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_notification_type_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_notification_type_returns_400(self):
        resp = self._post(self.url, {"notification_type": "invalid_type_xyz"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_types_all_accepted(self):
        valid = ["case_created", "case_updated", "case_escalated",
                 "case_resolved", "case_closed", "evidence_added",
                 "action_taken", "investigator_assigned"]
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            for t in valid:
                resp = self._post(self.url, {"notification_type": t})
                self.assertIn(
                    resp.status_code,
                    [status.HTTP_201_CREATED, status.HTTP_200_OK],
                    msg=f"Type '{t}' failed with {resp.status_code}",
                )

    def test_nonexistent_case_returns_404(self):
        resp = self._post(
            reverse("fraud_detection:notif-service-case-create",
                     kwargs={"case_id": 999999}),
            {"notification_type": "case_created"},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_creates_notification_in_db(self):
        count_before = FraudNotification.objects.count()
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            self._post(self.url, {"notification_type": "case_created"})
        self.assertGreater(FraudNotification.objects.count(), count_before)


class NotifServiceChannelsTest(_NSBase):
    """GET /fraud/notifications/service/channels/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:notif-service-channels")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_all_5_channels(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 5)

    def test_channel_names_correct(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._get(self.url)
        channel_names = {c["channel"] for c in resp.data["channels"]}
        self.assertEqual(channel_names, {"email", "sms", "push", "webhook", "dashboard"})


class NotifServiceExtendedStatsTest(_NSBase):
    """GET /fraud/notifications/service/stats/extended/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:notif-service-stats-extended")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_stats_shape(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)
        self.assertIn("sent", resp.data)
        self.assertIn("delivery_rate", resp.data)

    def test_days_param_accepted(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._get(self.url + "?days=7")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["days"], 7)


class NotifServiceTestEndpointTest(_NSBase):
    """POST /fraud/notifications/service/test/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:notif-service-test")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_channel_returns_400(self):
        resp = self._post(self.url, {"channel": "fax"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_channel_is_dashboard(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertEqual(resp.data["channel"], "dashboard")

    def test_all_channels_accepted(self):
        for ch in ["email", "sms", "push", "webhook", "dashboard"]:
            with patch("api.fraud_detection.views_notification_service._svc",
                       return_value=None):
                resp = self._post(self.url, {"channel": ch})
            self.assertIn(
                resp.status_code,
                [status.HTTP_200_OK, status.HTTP_201_CREATED],
                msg=f"Channel '{ch}' failed",
            )

    def test_response_contains_test_flag(self):
        with patch("api.fraud_detection.views_notification_service._svc",
                   return_value=None):
            resp = self._post(self.url, {})
        self.assertTrue(resp.data["test"])


# =============================================================================
# Signal Monitor views
# =============================================================================

class SignalStatusViewTest(_NSBase):
    """GET /fraud/signals/status/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-status")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_all_13_handlers(self):
        with patch("api.fraud_detection.views_signals_monitor.cache") as mc:
            mc.get.return_value = {}
            resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 13)

    def test_each_handler_has_required_fields(self):
        with patch("api.fraud_detection.views_signals_monitor.cache") as mc:
            mc.get.return_value = {}
            resp = self._get(self.url)
        for h in resp.data["handlers"]:
            self.assertIn("name", h)
            self.assertIn("sender", h)
            self.assertIn("can_trigger", h)


class SignalHandlerListViewTest(_NSBase):
    """GET /fraud/signals/handlers/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-handlers")

    def test_returns_senders_map(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("senders", resp.data)
        self.assertIn("handler_count", resp.data)
        self.assertGreater(resp.data["handler_count"], 0)


class SignalActivityViewTest(_NSBase):
    """GET /fraud/signals/activity/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-activity")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_activity_returns_ok(self):
        with patch("api.fraud_detection.views_signals_monitor.cache") as mc:
            mc.get.return_value = []
            resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["activity"], [])

    def test_signal_filter(self):
        entries = [
            {"signal": "handle_fraud_alert", "event": "auto"},
            {"signal": "handle_whitelist_changes", "event": "auto"},
        ]
        with patch("api.fraud_detection.views_signals_monitor.cache") as mc:
            mc.get.return_value = entries
            resp = self._get(self.url + "?signal=handle_fraud_alert")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for entry in resp.data["activity"]:
            self.assertEqual(entry["signal"], "handle_fraud_alert")

    def test_limit_param(self):
        entries = [{"signal": f"s{i}", "event": "e"} for i in range(100)]
        with patch("api.fraud_detection.views_signals_monitor.cache") as mc:
            mc.get.return_value = entries
            resp = self._get(self.url + "?limit=5")
        self.assertLessEqual(len(resp.data["activity"]), 5)


class SignalStatsViewTest(_NSBase):
    """GET /fraud/signals/stats/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-stats")

    def test_returns_stats(self):
        with patch("api.fraud_detection.views_signals_monitor.cache") as mc:
            mc.get.return_value = {"handle_fraud_alert": 10, "handle_whitelist_changes": 3}
            resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_fires", resp.data)
        self.assertEqual(resp.data["total_fires"], 13)


class SignalTriggerFraudAttemptTest(_NSBase):
    """POST /fraud/signals/trigger/fraud-attempt/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-trigger-fraud-attempt")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_attempt_id_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_attempt_returns_404(self):
        resp = self._post(self.url, {"attempt_id": "00000000-0000-0000-0000-000000000000"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class SignalTriggerIPChangeTest(_NSBase):
    """POST /fraud/signals/trigger/ip-change/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-trigger-ip-change")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"ip_id": 1}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_ip_id_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_ip_returns_404(self):
        resp = self._post(self.url, {"ip_id": 999999})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_existing_ip_triggers_handler(self):
        ip = IPReputation.objects.create(
            ip_address="100.200.100.200",
            fraud_score=60,
            is_blacklisted=False,
        )
        with patch("api.fraud_detection.views_signals_monitor.handle_ip_reputation_changes"):
            with patch("api.fraud_detection.views_signals_monitor._record_activity"):
                resp = self._post(self.url, {"ip_id": ip.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["triggered"])


class SignalTriggerDeviceUpdateTest(_NSBase):
    """POST /fraud/signals/trigger/device-update/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-trigger-device-update")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"device_id": 1}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_device_id_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_device_returns_404(self):
        resp = self._post(self.url, {"device_id": 999999})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class SignalTriggerAlertHandlerTest(_NSBase):
    """POST /fraud/signals/trigger/alert-handler/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-trigger-alert")

    def test_non_admin_returns_403(self):
        resp = self._post(self.url, {"alert_id": 1}, user=self.user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_alert_id_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_alert_returns_404(self):
        resp = self._post(self.url, {"alert_id": 999999})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_existing_alert_triggers_handler(self):
        alert = _alert(self.admin)
        with patch("api.fraud_detection.views_signals_monitor.handle_fraud_alert"):
            with patch("api.fraud_detection.views_signals_monitor._record_activity"):
                resp = self._post(self.url, {"alert_id": alert.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["triggered"])


class SignalTriggerWhitelistSyncTest(_NSBase):
    """POST /fraud/signals/trigger/whitelist-sync/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:signal-trigger-whitelist")

    def test_missing_whitelist_id_returns_400(self):
        resp = self._post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_whitelist_returns_404(self):
        resp = self._post(self.url, {"whitelist_id": 999999})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class MiddlewareStatusViewTest(_NSBase):
    """GET /fraud/signals/middleware/status/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:middleware-status")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_middleware_config(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("middleware", resp.data)
        self.assertIn("installed", resp.data)
        self.assertIn("config", resp.data)
        self.assertEqual(resp.data["middleware"], "FraudDetectionMiddleware")


class MiddlewareStatsViewTest(_NSBase):
    """GET /fraud/signals/middleware/stats/"""

    def setUp(self):
        super().setUp()
        self.url = reverse("fraud_detection:middleware-stats")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_stats_shape(self):
        with patch("api.fraud_detection.views_signals_monitor.cache") as mc:
            mc.get.return_value = {
                "total_requests": 1000,
                "total_blocked": 50,
                "total_flagged": 30,
            }
            resp = self._get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_requests", resp.data)
        self.assertIn("block_rate", resp.data)
        self.assertEqual(resp.data["block_rate"], 5.0)


# =============================================================================
# New serializer tests
# =============================================================================

class FraudAlertCreateSerializerTest(APITestCase):
    """Unit tests for FraudAlertCreateSerializer."""

    def _get_ser(self, data):
        from api.fraud_detection.serializers import FraudAlertCreateSerializer
        return FraudAlertCreateSerializer(data=data)

    def test_valid_data_passes(self):
        admin = User.objects.create_user(
            username="ser_admin_a", email="s@e.com", password="p"
        )
        ser = self._get_ser({
            "alert_type": "geo_anomaly",
            "priority":   "high",
            "title":      "Test",
            "description":"Test alert",
            "user":       admin.pk,
        })
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_priority_fails(self):
        admin = User.objects.create_user(
            username="ser_admin_b", email="sb@e.com", password="p"
        )
        ser = self._get_ser({
            "alert_type": "geo_anomaly",
            "priority":   "ultra",
            "title":      "Test",
            "user":       admin.pk,
        })
        self.assertFalse(ser.is_valid())
        self.assertIn("priority", ser.errors)

    def test_missing_alert_type_fails(self):
        admin = User.objects.create_user(
            username="ser_admin_c", email="sc@e.com", password="p"
        )
        ser = self._get_ser({"priority": "high", "title": "T", "user": admin.pk})
        self.assertFalse(ser.is_valid())
        self.assertIn("alert_type", ser.errors)


class FraudRuleCreateSerializerTest(APITestCase):
    """Unit tests for FraudRuleCreateSerializer."""

    def _get_ser(self, data):
        from api.fraud_detection.serializers import FraudRuleCreateSerializer
        return FraudRuleCreateSerializer(data=data)

    def test_valid_data_passes(self):
        ser = self._get_ser({
            "name":      "Test Rule",
            "rule_type": "velocity",
            "severity":  "medium",
            "condition": {},
            "weight":    0.5,
            "threshold": 10,
            "is_active": True,
        })
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_weight_above_1_fails(self):
        ser = self._get_ser({
            "name": "Bad Weight", "rule_type": "velocity",
            "severity": "low", "condition": {},
            "weight": 1.5, "threshold": 5,
        })
        self.assertFalse(ser.is_valid())
        self.assertIn("weight", ser.errors)

    def test_weight_below_0_fails(self):
        ser = self._get_ser({
            "name": "Neg Weight", "rule_type": "velocity",
            "severity": "low", "condition": {},
            "weight": -0.1, "threshold": 5,
        })
        self.assertFalse(ser.is_valid())
        self.assertIn("weight", ser.errors)

    def test_weight_boundary_0_and_1_pass(self):
        for w in [0.0, 1.0]:
            ser = self._get_ser({
                "name": f"Rule w={w}", "rule_type": "velocity",
                "severity": "low", "condition": {},
                "weight": w, "threshold": 5,
            })
            self.assertTrue(ser.is_valid(), f"weight={w} should be valid: {ser.errors}")


class FraudRuleUpdateSerializerTest(APITestCase):
    """Unit tests for FraudRuleUpdateSerializer."""

    def _get_ser(self, data, partial=True):
        from api.fraud_detection.serializers import FraudRuleUpdateSerializer
        rule = _rule(name="UpdateSerRule")
        return FraudRuleUpdateSerializer(rule, data=data, partial=partial)

    def test_partial_update_single_field(self):
        ser = self._get_ser({"severity": "critical"}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_weight_in_update_fails(self):
        ser = self._get_ser({"weight": 5.0}, partial=True)
        self.assertFalse(ser.is_valid())
        self.assertIn("weight", ser.errors)

    def test_full_update_without_name_still_valid(self):
        """rule_type excluded from update serializer — should not be required."""
        ser = self._get_ser({
            "severity": "high", "condition": {}, "weight": 0.7,
            "threshold": 15, "is_active": True,
        }, partial=False)
        self.assertTrue(ser.is_valid(), ser.errors)
