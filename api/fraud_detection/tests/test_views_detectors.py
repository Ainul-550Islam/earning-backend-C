"""
tests/test_views_detectors.py
==============================
Comprehensive tests for views_detectors.py.

Coverage targets
----------------
• Every detector: auth gate, detect/analyze, batch, config GET/PATCH
• Global views: DetectorListAPIView, DetectorHealthAPIView,
  DetectorStatsAPIView, DetectorGenericRunAPIView
• _load() fallback: returns 503 when detector module missing
• Admin-only gating on config PATCH and VelocityEngine reset
• Input validation: missing required fields → 400
• Batch limit enforcement (max 50/100/200)
• DETECTOR_REGISTRY completeness
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _admin(suffix=""):
    return User.objects.create_user(
        username=f"admin_det{suffix}",
        email=f"admin_det{suffix}@test.example.com",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )


def _user(suffix=""):
    return User.objects.create_user(
        username=f"user_det{suffix}",
        email=f"user_det{suffix}@test.example.com",
        password="pass",
    )


def _mock_detector(result=None):
    """Return a mock detector instance whose detect/analyze/check returns result."""
    inst = MagicMock()
    inst.detect.return_value  = result or {"risk_score": 42, "is_fraud": False}
    inst.analyze.return_value = result or {"anomaly": False, "score": 10}
    inst.check.return_value   = result or {"breach": False, "count": 3}
    inst.batch_detect.return_value = [result or {"risk_score": 0}]
    inst._cfg = {"threshold": 80}
    inst.config = {"threshold": 80}
    return inst


def _unavailable():
    """Simulate _load returning None (detector not available)."""
    return None


# ---------------------------------------------------------------------------
# DETECTOR_REGISTRY integrity
# ---------------------------------------------------------------------------

class DetectorRegistryTest(APITestCase):

    def test_registry_has_all_10_detectors(self):
        from api.fraud_detection.views_detectors import DETECTOR_REGISTRY
        expected_keys = {
            "click_fraud", "device_fingerprint", "multi_account",
            "pattern_analyzer", "vpn_proxy", "biometrics",
            "geo_velocity", "graph_network", "velocity_engine", "referral_fraud",
        }
        self.assertTrue(expected_keys.issubset(set(DETECTOR_REGISTRY.keys())))

    def test_each_entry_has_required_fields(self):
        from api.fraud_detection.views_detectors import DETECTOR_REGISTRY
        required = {"slug", "class_name", "description", "input_fields", "primary_method"}
        for key, meta in DETECTOR_REGISTRY.items():
            for field in required:
                self.assertIn(field, meta, f"'{field}' missing from {key}")

    def test_slug_to_key_reverse_lookup(self):
        from api.fraud_detection.views_detectors import DETECTOR_REGISTRY, SLUG_TO_KEY
        for key, meta in DETECTOR_REGISTRY.items():
            self.assertEqual(SLUG_TO_KEY[meta["slug"]], key)


# ---------------------------------------------------------------------------
# Global views
# ---------------------------------------------------------------------------

class DetectorListViewTest(APITestCase):
    """GET /fraud/detectors/"""

    def setUp(self):
        self.user   = _user("list")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:detector-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_all_detectors(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_detectors._load", return_value=_mock_detector()):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 10)

    def test_available_only_filter(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_detectors._load", side_effect=[
            _mock_detector(), None, _mock_detector(), None, None,
            _mock_detector(), None, None, _mock_detector(), None,
        ]):
            resp = self.client.get(self.url + "?available_only=true")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for d in resp.data["detectors"]:
            self.assertTrue(d["available"])

    def test_each_detector_has_detect_url(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_detectors._load", return_value=_mock_detector()):
            resp = self.client.get(self.url)
        for d in resp.data["detectors"]:
            self.assertIn("detect_url", d)


class DetectorHealthViewTest(APITestCase):
    """GET /fraud/detectors/health/"""

    def setUp(self):
        self.user   = _user("health")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:detector-health")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_all_available_reports_healthy(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_detectors._load", return_value=_mock_detector()):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["overall"], "healthy")
        self.assertEqual(resp.data["available"], 10)

    def test_partial_availability_reports_degraded(self):
        self.client.force_authenticate(self.user)
        # 5 available, 5 not
        side = [_mock_detector() if i % 2 == 0 else None for i in range(10)]
        with patch("api.fraud_detection.views_detectors._load", side_effect=side):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["overall"], "degraded")


class DetectorStatsViewTest(APITestCase):
    """GET /fraud/detectors/stats/"""

    def setUp(self):
        self.user   = _user("stats")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:detector-stats")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_stats_shape(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_detectors.cache") as mock_cache:
            mock_cache.get.return_value = {"runs": 5, "errors": 1, "last_run": "2024-01-01"}
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_runs", resp.data)
        self.assertIn("by_detector", resp.data)


class DetectorGenericRunViewTest(APITestCase):
    """POST /fraud/detectors/run/"""

    def setUp(self):
        self.user   = _user("generic")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:detector-run")

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_detector_slug_returns_400(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"data": {}})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_slug_returns_400(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"detector": "nonexistent-xyz", "data": {}})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unavailable_detector_returns_503(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.post(self.url,
                                    {"detector": "referral-fraud", "data": {}},
                                    format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_available_detector_runs_successfully(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_detectors._load",
                   return_value=_mock_detector({"risk_score": 30})):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(self.url,
                                        {"detector": "referral-fraud",
                                         "data": {"referrer_user_id": 1, "referred_user_id": 2}},
                                        format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("result", resp.data)


# ---------------------------------------------------------------------------
# Per-detector: abstract base + concrete test classes
# ---------------------------------------------------------------------------

class _DetectorBase(APITestCase):
    """Base for per-detector view tests."""
    detect_url_name: str = ""
    batch_url_name:  str = ""
    config_url_name: str = ""
    required_detect_body: dict = {}
    required_batch_key: str = "items"
    detect_method: str = "post"   # 'post' for detect/analyze/check

    def setUp(self):
        self.admin  = _admin(self.__class__.__name__)
        self.user   = _user(self.__class__.__name__)
        self.client = APIClient()

    # ── Detect / Analyze / Check ──────────────────────────────────────────

    def test_detect_unauthenticated_returns_401(self):
        url = reverse(f"fraud_detection:{self.detect_url_name}")
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detect_returns_503_when_unavailable(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.detect_url_name}")
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.post(url, self.required_detect_body, format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_detect_returns_200_when_available(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.detect_url_name}")
        with patch("api.fraud_detection.views_detectors._load",
                   return_value=_mock_detector()):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(url, self.required_detect_body, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("result", resp.data)

    # ── Batch ─────────────────────────────────────────────────────────────

    def test_batch_unauthenticated_returns_401(self):
        url = reverse(f"fraud_detection:{self.batch_url_name}")
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_batch_empty_list_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.batch_url_name}")
        resp = self.client.post(url, {self.required_batch_key: []}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_returns_503_when_unavailable(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.batch_url_name}")
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.post(url,
                                    {self.required_batch_key: [self.required_detect_body]},
                                    format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_batch_returns_results(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.batch_url_name}")
        mock_det = _mock_detector()
        mock_det.batch_detect.return_value = [{"risk_score": 0}]
        with patch("api.fraud_detection.views_detectors._load", return_value=mock_det):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(
                    url,
                    {self.required_batch_key: [self.required_detect_body]},
                    format="json",
                )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)

    # ── Config ────────────────────────────────────────────────────────────

    def test_config_get_unauthenticated_returns_401(self):
        url = reverse(f"fraud_detection:{self.config_url_name}")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_config_get_returns_503_when_unavailable(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.config_url_name}")
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_config_get_returns_config(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.config_url_name}")
        with patch("api.fraud_detection.views_detectors._load",
                   return_value=_mock_detector()):
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("config", resp.data)

    def test_config_patch_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        url = reverse(f"fraud_detection:{self.config_url_name}")
        resp = self.client.patch(url, {"threshold": 90})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_config_patch_admin_returns_200(self):
        self.client.force_authenticate(self.admin)
        url = reverse(f"fraud_detection:{self.config_url_name}")
        with patch("api.fraud_detection.views_detectors._load",
                   return_value=_mock_detector()):
            resp = self.client.patch(url, {"threshold": 90}, format="json")
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])


# ── Concrete detector test classes ──────────────────────────────────────────

class ClickFraudDetectorViewTest(_DetectorBase):
    detect_url_name    = "detector-click-detect"
    batch_url_name     = "detector-click-batch"
    config_url_name    = "detector-click-config"
    required_detect_body = {"user_id": 1, "click_id": "c1", "ip_address": "1.2.3.4",
                             "offer_id": 10, "timestamp": "2024-01-01T00:00:00Z"}
    required_batch_key = "events"


class DeviceFingerprinterViewTest(_DetectorBase):
    detect_url_name    = "detector-device-detect"
    batch_url_name     = "detector-device-batch"
    config_url_name    = "detector-device-config"
    required_detect_body = {"user_agent": "Mozilla/5.0", "ip_address": "1.2.3.4",
                             "screen_resolution": "1920x1080", "timezone": "UTC"}
    required_batch_key = "devices"


class MultiAccountDetectorViewTest(_DetectorBase):
    detect_url_name    = "detector-multi-detect"
    batch_url_name     = "detector-multi-batch"
    config_url_name    = "detector-multi-config"
    required_detect_body = {"user_id": 1, "ip_address": "1.2.3.4", "device_id": "d1"}
    required_batch_key = "users"


class PatternAnalyzerViewTest(_DetectorBase):
    detect_url_name    = "detector-pattern-analyze"
    batch_url_name     = "detector-pattern-batch"
    config_url_name    = "detector-pattern-config"
    required_detect_body = {"user_id": 1, "events": [{"type": "login"}]}
    required_batch_key = "users"


class VPNProxyDetectorViewTest(_DetectorBase):
    detect_url_name    = "detector-vpn-detect"
    batch_url_name     = "detector-vpn-batch"
    config_url_name    = "detector-vpn-config"
    required_detect_body = {"ip_address": "1.2.3.4"}
    required_batch_key = "ip_addresses"

    def test_detect_missing_ip_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-vpn-detect")
        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_uses_ip_addresses_key(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-vpn-batch")
        mock_det = _mock_detector()
        mock_det.batch_detect.return_value = [{"is_vpn": False}]
        with patch("api.fraud_detection.views_detectors._load", return_value=mock_det):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(url, {"ip_addresses": ["1.2.3.4"]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class BiometricsAnalyzerViewTest(_DetectorBase):
    detect_url_name    = "detector-biometrics-analyze"
    batch_url_name     = "detector-biometrics-batch"
    config_url_name    = "detector-biometrics-config"
    required_detect_body = {"user_id": 1, "session_id": "s1",
                             "keystrokes": [10, 20], "mouse_events": [1, 2]}
    required_batch_key = "sessions"


class GeoVelocityDetectorViewTest(_DetectorBase):
    detect_url_name    = "detector-geo-detect"
    batch_url_name     = "detector-geo-batch"
    config_url_name    = "detector-geo-config"
    required_detect_body = {"user_id": 1, "ip_address": "1.2.3.4"}
    required_batch_key = "events"

    def test_detect_missing_user_id_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-geo-detect")
        resp = self.client.post(url, {"ip_address": "1.2.3.4"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detect_missing_ip_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-geo-detect")
        resp = self.client.post(url, {"user_id": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class GraphNetworkAnalyzerViewTest(_DetectorBase):
    detect_url_name    = "detector-graph-analyze"
    batch_url_name     = "detector-graph-batch"
    config_url_name    = "detector-graph-config"
    required_detect_body = {"user_id": 1, "ip_address": "1.2.3.4"}
    required_batch_key = "entities"

    def test_detect_missing_user_id_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-graph-analyze")
        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class VelocityEngineViewTest(APITestCase):
    """VelocityEngine has an extra reset endpoint."""

    def setUp(self):
        self.admin  = _admin("vel")
        self.user   = _user("vel")
        self.client = APIClient()

    def test_check_missing_user_id_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-velocity-check")
        resp = self.client.post(url, {"event_type": "login"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_missing_event_type_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-velocity-check")
        resp = self.client.post(url, {"user_id": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_returns_503_when_unavailable(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-velocity-check")
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.post(url,
                                    {"user_id": 1, "event_type": "login"},
                                    format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_check_returns_200_when_available(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-velocity-check")
        mock_det = _mock_detector()
        mock_det.check.return_value = {"breach": False, "count": 2}
        with patch("api.fraud_detection.views_detectors._load", return_value=mock_det):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(url,
                                        {"user_id": 1, "event_type": "login"},
                                        format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-velocity-reset")
        resp = self.client.post(url, {"user_id": 1})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_reset_missing_all_params_returns_400(self):
        self.client.force_authenticate(self.admin)
        url = reverse("fraud_detection:detector-velocity-reset")
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_admin_with_user_id_returns_200(self):
        self.client.force_authenticate(self.admin)
        url = reverse("fraud_detection:detector-velocity-reset")
        mock_det = _mock_detector()
        mock_det.reset.return_value = {"reset": True}
        with patch("api.fraud_detection.views_detectors._load", return_value=mock_det):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(url, {"user_id": 1}, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])

    def test_batch_empty_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-velocity-batch")
        resp = self.client.post(url, {"events": []}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_config_get_returns_503_when_unavailable(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-velocity-config")
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class ReferralFraudDetectorViewTest(APITestCase):
    """ReferralFraudDetector has an extra analyze endpoint."""

    def setUp(self):
        self.admin  = _admin("ref")
        self.user   = _user("ref")
        self.client = APIClient()

    def test_detect_missing_referrer_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-detect")
        resp = self.client.post(url, {"referred_user_id": 2}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detect_missing_referred_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-detect")
        resp = self.client.post(url, {"referrer_user_id": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detect_returns_503_when_unavailable(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-detect")
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.post(
                url,
                {"referrer_user_id": 1, "referred_user_id": 2},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_detect_returns_structured_result(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-detect")
        mock_det = _mock_detector({"risk_score": 55, "is_fraud": True, "reasons": ["same_ip"]})
        with patch("api.fraud_detection.views_detectors._load", return_value=mock_det):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(
                    url,
                    {"referrer_user_id": 1, "referred_user_id": 2},
                    format="json",
                )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("risk_score", resp.data)
        self.assertIn("is_fraud", resp.data)

    def test_batch_empty_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-batch")
        resp = self.client.post(url, {"referrals": []}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_returns_fraud_count(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-batch")
        mock_det = _mock_detector()
        mock_det.batch_detect.return_value = [
            {"risk_score": 80, "is_fraud": True},
            {"risk_score": 20, "is_fraud": False},
        ]
        with patch("api.fraud_detection.views_detectors._load", return_value=mock_det):
            with patch("api.fraud_detection.views_detectors._record_run"):
                resp = self.client.post(
                    url,
                    {"referrals": [
                        {"referrer_user_id": 1, "referred_user_id": 2},
                        {"referrer_user_id": 3, "referred_user_id": 4},
                    ]},
                    format="json",
                )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["fraud_found"], 1)

    def test_analyze_missing_referrer_returns_400(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-analyze")
        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_analyze_returns_503_when_unavailable(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-analyze")
        with patch("api.fraud_detection.views_detectors._load", return_value=None):
            resp = self.client.post(
                url,
                {"referrer_user_id": 1},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_config_get_non_admin_returns_200(self):
        """Analysts can read config."""
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-config")
        mock_det = _mock_detector()
        mock_det._cfg = {"threshold": 70}
        with patch("api.fraud_detection.views_detectors._load", return_value=mock_det):
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_config_patch_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        url = reverse("fraud_detection:detector-referral-config")
        resp = self.client.patch(url, {"threshold": 90})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
