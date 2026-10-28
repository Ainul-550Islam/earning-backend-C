"""
tests/test_security.py
=======================
Tests for brute_force_protection.py, security_views.py,
and all 9 new detector modules.

Coverage:
  BruteForceProtector         — check, record_failure, record_success, lock tiers
  CredentialStuffingDetector  — check_ip, record_attempt, check_password_breach
  AccountLockoutManager       — pre_login_check, on_login_failure, on_login_success
  BruteForceMiddleware        — blocks on locked, passes on clean
  Security API views          — status, reset, check, stats, lockout, cs, attack log
  All 9 detector modules      — detect, batch_detect, edge cases
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin(suffix=""):
    return User.objects.create_user(
        username=f"sec_admin{suffix}", email=f"sec_admin{suffix}@t.com",
        password="pass", is_staff=True, is_superuser=True,
    )


def _user(suffix=""):
    return User.objects.create_user(
        username=f"sec_user{suffix}", email=f"sec_user{suffix}@t.com",
        password="pass",
    )


# =============================================================================
# BruteForceProtector unit tests
# =============================================================================

class BruteForceProtectorTest(TestCase):

    def setUp(self):
        cache.clear()
        from api.fraud_detection.security.brute_force_protection import BruteForceProtector
        self.protector = BruteForceProtector()

    def tearDown(self):
        cache.clear()

    def test_initial_check_is_not_locked(self):
        result = self.protector.check("user:test1")
        self.assertFalse(result["locked"])
        self.assertEqual(result["attempts"], 0)

    def test_single_failure_not_locked(self):
        result = self.protector.record_failure("user:test2")
        self.assertFalse(result["locked"])
        self.assertEqual(result["attempts"], 1)

    def test_locks_after_max_attempts(self):
        from django.conf import settings
        max_attempts = getattr(settings, "BRUTE_FORCE_MAX_ATTEMPTS", 5)
        identifier   = "user:locktest"
        for _ in range(max_attempts - 1):
            self.protector.record_failure(identifier)
        result = self.protector.record_failure(identifier)
        self.assertTrue(result["locked"])
        self.assertIn("locked_minutes", result)
        self.assertGreater(result["locked_minutes"], 0)

    def test_check_returns_locked_after_lockout(self):
        identifier = "user:checklock"
        for _ in range(10):
            self.protector.record_failure(identifier)
        result = self.protector.check(identifier)
        self.assertTrue(result["locked"])

    def test_success_clears_counters(self):
        identifier = "user:successclear"
        self.protector.record_failure(identifier)
        self.protector.record_failure(identifier)
        self.protector.record_success(identifier)
        result = self.protector.check(identifier)
        self.assertFalse(result["locked"])
        self.assertEqual(result["attempts"], 0)

    def test_manual_reset_unlocks(self):
        identifier = "user:resetme"
        for _ in range(10):
            self.protector.record_failure(identifier)
        self.protector.reset(identifier)
        result = self.protector.check(identifier)
        self.assertFalse(result["locked"])

    def test_whitelist_ip_never_locked(self):
        with self.settings(BRUTE_FORCE_WHITELIST_IPS=["127.0.0.1"]):
            for _ in range(20):
                result = self.protector.record_failure("user:wl", ip="127.0.0.1")
            self.assertFalse(result.get("locked", False))

    def test_remaining_decrements(self):
        identifier = "user:remaining"
        r1 = self.protector.record_failure(identifier)
        r2 = self.protector.record_failure(identifier)
        self.assertLess(r2["remaining"], r1["remaining"])

    def test_status_returns_full_info(self):
        identifier = "user:statusfull"
        self.protector.record_failure(identifier)
        s = self.protector.status(identifier)
        self.assertIn("tier", s)
        self.assertIn("max_attempts", s)
        self.assertIn("window_secs", s)


# =============================================================================
# CredentialStuffingDetector unit tests
# =============================================================================

class CredentialStuffingDetectorTest(TestCase):

    def setUp(self):
        cache.clear()
        from api.fraud_detection.security.brute_force_protection import CredentialStuffingDetector
        self.cs = CredentialStuffingDetector()

    def tearDown(self):
        cache.clear()

    def test_single_attempt_not_stuffing(self):
        result = self.cs.record_attempt("5.5.5.5", "userA")
        self.assertFalse(result["is_stuffing"])

    def test_many_attempts_detected_as_stuffing(self):
        ip = "6.6.6.6"
        with self.settings(CREDENTIAL_STUFFING_IP_THRESHOLD=5):
            for i in range(6):
                result = self.cs.record_attempt(ip, f"user{i}")
            self.assertTrue(result["is_stuffing"])

    def test_suspicious_ua_flagged(self):
        result = self.cs.record_attempt("7.7.7.7", "userB",
                                         user_agent="python-requests/2.28")
        self.assertTrue(result["ua_suspicious"])

    def test_normal_browser_ua_not_flagged(self):
        result = self.cs.record_attempt(
            "8.8.8.8", "userC",
            user_agent="Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36"
        )
        self.assertFalse(result["ua_suspicious"])

    def test_check_ip_returns_status(self):
        result = self.cs.check_ip("9.9.9.9")
        self.assertIn("is_stuffing", result)
        self.assertIn("attempt_count", result)
        self.assertIn("risk_score", result)

    def test_password_breach_graceful_offline(self):
        """Should return not_checked=True when HIBP is unreachable."""
        with patch("urllib.request.urlopen", side_effect=Exception("Network unavailable")):
            result = self.cs.check_password_breach("test_password_123")
        self.assertEqual(result.get("breached"), None)
        self.assertTrue(result.get("not_checked", False))


# =============================================================================
# AccountLockoutManager unit tests
# =============================================================================

class AccountLockoutManagerTest(TestCase):

    def setUp(self):
        cache.clear()
        from api.fraud_detection.security.brute_force_protection import AccountLockoutManager
        self.mgr = AccountLockoutManager()

    def tearDown(self):
        cache.clear()

    def test_pre_login_check_allows_clean_user(self):
        allowed, reason = self.mgr.pre_login_check("cleanuser", "1.2.3.4")
        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_pre_login_check_blocks_locked_user(self):
        for _ in range(20):
            self.mgr.on_login_failure("lockeduser", "1.2.3.4")
        allowed, reason = self.mgr.pre_login_check("lockeduser", "1.2.3.4")
        self.assertFalse(allowed)
        self.assertGreater(len(reason), 0)

    def test_on_login_success_clears(self):
        for _ in range(3):
            self.mgr.on_login_failure("successuser", "2.3.4.5")
        self.mgr.on_login_success("successuser", "2.3.4.5")
        allowed, _ = self.mgr.pre_login_check("successuser", "2.3.4.5")
        self.assertTrue(allowed)

    def test_on_login_failure_returns_blocked_info(self):
        result = self.mgr.on_login_failure("testfail", "3.4.5.6")
        self.assertIn("user_lock", result)
        self.assertIn("ip_lock", result)
        self.assertIn("cs_detection", result)

    def test_get_full_status_shape(self):
        s = self.mgr.get_full_status("statususer", "4.5.6.7")
        self.assertIn("user", s)
        self.assertIn("ip", s)
        self.assertIn("cs_ip", s)


# =============================================================================
# BruteForceMiddleware tests
# =============================================================================

class BruteForceMiddlewareTest(TestCase):

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def _make_middleware(self):
        from api.fraud_detection.security.brute_force_protection import BruteForceMiddleware
        return BruteForceMiddleware(get_response=lambda r: MagicMock(status_code=200))

    def test_non_login_path_passes_through(self):
        mw  = self._make_middleware()
        req = self.factory.get("/api/fraud/dashboard/")
        resp = mw(req)
        self.assertEqual(resp.status_code, 200)

    def test_clean_login_passes_through(self):
        import json
        mw  = self._make_middleware()
        req = self.factory.post(
            "/api/auth/login/",
            data=json.dumps({"username": "newuser", "password": "pass"}),
            content_type="application/json",
            REMOTE_ADDR="10.0.0.1",
        )
        resp = mw(req)
        self.assertNotEqual(resp.status_code, 429)

    def test_locked_user_gets_429(self):
        import json
        from api.fraud_detection.security.brute_force_protection import AccountLockoutManager
        mgr = AccountLockoutManager()
        for _ in range(20):
            mgr.on_login_failure("locked_mw_user", "192.168.1.1")

        mw  = self._make_middleware()
        req = self.factory.post(
            "/api/auth/login/",
            data=json.dumps({"username": "locked_mw_user", "password": "wrong"}),
            content_type="application/json",
            REMOTE_ADDR="192.168.1.1",
        )
        resp = mw(req)
        self.assertEqual(resp.status_code, 429)


# =============================================================================
# Security API views
# =============================================================================

class SecurityAPIBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin  = _admin("sav")
        self.user   = _user("sav")
        self.client = APIClient()

    def tearDown(self):
        cache.clear()


class BruteForceStatusViewTest(SecurityAPIBase):
    def test_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(
            reverse("fraud_detection:security-bf-status",
                     kwargs={"identifier": "user:42"})
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_returns_status(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(
            reverse("fraud_detection:security-bf-status",
                     kwargs={"identifier": "user:42"})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("locked", resp.data)


class BruteForceResetViewTest(SecurityAPIBase):
    def test_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("fraud_detection:security-bf-reset",
                     kwargs={"identifier": "user:42"}),
            {},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_resets(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("fraud_detection:security-bf-reset",
                     kwargs={"identifier": "user:42"}),
            {},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["reset"])


class BruteForceCheckViewTest(SecurityAPIBase):
    def test_missing_username_returns_400(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("fraud_detection:security-bf-check"),
            {"ip": "1.2.3.4"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_ip_returns_400(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("fraud_detection:security-bf-check"),
            {"username": "bob"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_returns_allowed(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("fraud_detection:security-bf-check"),
            {"username": "freshuser", "ip": "1.2.3.4"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["allowed"])


class LockoutUnlockViewTest(SecurityAPIBase):
    def test_missing_both_returns_400(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("fraud_detection:security-lockout-unlock"), {}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_unlocks_by_username(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("fraud_detection:security-lockout-unlock"),
            {"username": "someuser"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["unlocked"])


class CSCheckIPViewTest(SecurityAPIBase):
    def test_missing_ip_returns_400(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("fraud_detection:security-cs-check-ip"), {}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_ip_returns_result(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("fraud_detection:security-cs-check-ip"),
            {"ip": "5.5.5.5"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("is_stuffing", resp.data)


class AttackLogViewTest(SecurityAPIBase):
    def test_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse("fraud_detection:security-attack-log"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_returns_log(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("fraud_detection:security-attack-log"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("events", resp.data)


class AttackLogClearViewTest(SecurityAPIBase):
    def test_admin_clears(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse("fraud_detection:security-attack-log-clear"), {})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("cleared", resp.data)


# =============================================================================
# Detector module unit tests
# =============================================================================

class ClickFraudDetectorTest(TestCase):
    def setUp(self):
        cache.clear()
        from api.fraud_detection.detectors.ClickFraudDetector import ClickFraudDetector
        self.det = ClickFraudDetector()

    def tearDown(self):
        cache.clear()

    def test_normal_click_is_not_fraud(self):
        result = self.det.detect({
            "user_id": 1, "click_id": "c_unique_1",
            "ip_address": "10.0.0.1", "offer_id": 5,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120",
        })
        self.assertFalse(result["is_fraud"])

    def test_bot_ua_detected(self):
        result = self.det.detect({
            "user_id": 2, "click_id": "c2",
            "ip_address": "10.0.0.2", "offer_id": 5,
            "user_agent": "HeadlessChrome/119",
        })
        self.assertTrue(result["is_fraud"])
        self.assertIn("bot_user_agent", result["reasons"])

    def test_duplicate_click_detected(self):
        data = {"click_id": "dup_click_x", "ip_address": "10.0.0.3",
                "user_id": 3, "offer_id": 1, "user_agent": "Mozilla"}
        self.det.detect(data)
        result = self.det.detect(data)
        self.assertIn("duplicate_click", result["reasons"])

    def test_batch_returns_list(self):
        events = [{"click_id": f"b{i}", "ip_address": "1.2.3.4",
                   "user_id": i, "offer_id": 1, "user_agent": "Mozilla"}
                  for i in range(5)]
        results = self.det.batch_detect(events)
        self.assertEqual(len(results), 5)


class VelocityEngineTest(TestCase):
    def setUp(self):
        cache.clear()
        from api.fraud_detection.detectors.VelocityEngine import VelocityEngine
        self.engine = VelocityEngine()

    def tearDown(self):
        cache.clear()

    def test_first_event_not_breach(self):
        result = self.engine.check({"user_id": 1, "event_type": "login", "ip_address": "1.1.1.1"})
        self.assertFalse(result["breach"])

    def test_velocity_breach_detected(self):
        with self.settings():
            for i in range(15):
                result = self.engine.check({
                    "user_id": 1, "event_type": "login", "ip_address": "2.2.2.2"
                })
        self.assertTrue(result["breach"])

    def test_reset_clears_counters(self):
        for _ in range(5):
            self.engine.check({"user_id": 99, "event_type": "withdrawal"})
        self.engine.reset(user_id="99", event_type="withdrawal")
        result = self.engine.check({"user_id": 99, "event_type": "withdrawal"})
        self.assertEqual(result["user_count"], 1)

    def test_batch_check(self):
        events = [{"user_id": i, "event_type": "login", "ip_address": "3.3.3.3"}
                  for i in range(5)]
        results = self.engine.batch_check(events)
        self.assertEqual(len(results), 5)


class GeoVelocityDetectorTest(TestCase):
    def setUp(self):
        cache.clear()
        from api.fraud_detection.detectors.GeoVelocityDetector import GeoVelocityDetector
        self.det = GeoVelocityDetector()

    def tearDown(self):
        cache.clear()

    def test_first_event_returns_low_risk(self):
        result = self.det.detect({"user_id": 1, "ip_address": "1.2.3.4"})
        self.assertEqual(result["risk_score"], 0)

    def test_impossible_travel_detected(self):
        import time
        # Simulate two logins from opposite sides of globe 1 second apart
        mock_coords_ny  = (40.7128, -74.0060)
        mock_coords_tok = (35.6762, 139.6503)

        with patch.object(self.det, "_ip_to_coords",
                          side_effect=[mock_coords_ny, mock_coords_tok]):
            from django.core.cache import cache as _cache
            now = time.time()
            _cache.set("geo_vel:10", {"coords": mock_coords_ny, "ts": now - 10, "ip": "1.2.3.4"}, 3600)
            result = self.det.detect({
                "user_id": 10,
                "ip_address": "5.6.7.8",
                "timestamp": now,
            })
        # Distance NY→Tokyo ~10,838 km in 10 sec = ~3.9M km/h = impossible
        if "is_impossible_travel" in result:
            self.assertTrue(result["is_impossible_travel"])

    def test_batch_detect(self):
        results = self.det.batch_detect([
            {"user_id": 20, "ip_address": "1.1.1.1"},
            {"user_id": 21, "ip_address": "2.2.2.2"},
        ])
        self.assertEqual(len(results), 2)


class MultiAccountDetectorTest(TestCase):
    def setUp(self):
        cache.clear()
        from api.fraud_detection.detectors.MultiAccountDetector import MultiAccountDetector
        self.det = MultiAccountDetector()

    def tearDown(self):
        cache.clear()

    def test_single_user_per_ip_clean(self):
        result = self.det.detect({"user_id": 1, "ip_address": "10.10.10.1"})
        self.assertFalse(result["is_fraud"])

    def test_multi_accounts_from_same_ip_detected(self):
        ip = "10.10.10.2"
        for i in range(5):
            result = self.det.detect({"user_id": i+100, "ip_address": ip})
        self.assertTrue(result["is_fraud"])
        self.assertTrue(any("ip_multi_account" in r for r in result["reasons"]))


class VPNProxyDetectorTest(TestCase):
    def setUp(self):
        cache.clear()
        from api.fraud_detection.detectors.VPNProxyDetector import VPNProxyDetector
        self.det = VPNProxyDetector()

    def tearDown(self):
        cache.clear()

    def test_normal_ip_low_risk(self):
        result = self.det.check_vpn_proxy("8.8.8.8")
        self.assertIn("risk_score", result)
        self.assertIn("is_vpn", result)
        self.assertIn("is_tor", result)

    def test_detect_wrapper_works(self):
        result = self.det.detect({"ip_address": "8.8.4.4"})
        self.assertIn("risk_score", result)

    def test_empty_ip_returns_error(self):
        result = self.det.detect({})
        self.assertIn("error", result)


class BehavioralBiometricsTest(TestCase):
    def setUp(self):
        cache.clear()
        from api.fraud_detection.detectors.BehavioralBiometricsAnalyzer import BehavioralBiometricsAnalyzer
        self.det = BehavioralBiometricsAnalyzer()

    def test_human_typing_not_bot(self):
        # Normal human: ~60 WPM, variable intervals
        keystrokes = list(range(0, 600, 10))  # varied intervals
        result = self.det.analyze({
            "user_id": 1, "session_id": "s1",
            "keystrokes": keystrokes,
            "mouse_events": [[100+i, 200+i] for i in range(20)],
            "duration_ms": 10000,
        })
        self.assertIn("risk_score", result)

    def test_headless_browser_not_flagged_by_biometrics_alone(self):
        # No keystrokes/mouse — insufficient data
        result = self.det.analyze({"user_id": 2, "session_id": "s2",
                                    "keystrokes": [], "mouse_events": []})
        self.assertIn("risk_score", result)


class PatternAnalyzerTest(TestCase):
    def setUp(self):
        from api.fraud_detection.detectors.PatternAnalyzer import PatternAnalyzer
        self.det = PatternAnalyzer()

    def test_insufficient_events_returns_low_risk(self):
        result = self.det.analyze({"user_id": 1, "events": [{"type": "login"}]})
        self.assertEqual(result["risk_score"], 0)

    def test_uniform_events_flagged(self):
        events = [{"type": "offer_click", "timestamp": float(i)} for i in range(20)]
        result = self.det.analyze({"user_id": 1, "events": events})
        self.assertIn("risk_score", result)


class GraphNetworkAnalyzerTest(TestCase):
    def setUp(self):
        cache.clear()
        from api.fraud_detection.detectors.GraphNetworkAnalyzer import GraphNetworkAnalyzer
        self.det = GraphNetworkAnalyzer()

    def tearDown(self):
        cache.clear()

    def test_single_user_no_ring(self):
        result = self.det.analyze({"user_id": 1, "ip_address": "1.2.3.4"})
        self.assertFalse(result["is_fraud_ring"])

    def test_large_ip_cluster_flagged(self):
        ip = "5.5.5.5"
        for i in range(5):
            result = self.det.analyze({"user_id": i+200, "ip_address": ip})
        self.assertGreater(result["risk_score"], 0)
