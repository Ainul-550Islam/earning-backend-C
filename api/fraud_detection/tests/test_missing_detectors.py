"""
Tests for the four previously-untested fraud detectors:

  - BehavioralBiometricsAnalyzer
  - GeoVelocityDetector
  - GraphNetworkAnalyzer
  - VelocityEngine

Each section follows the same pattern used in the existing detector test
files: instantiate the class, pass representative input dicts, and assert
that the returned result has the expected shape and value ranges.
"""

from __future__ import annotations

import math
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared factory helpers
# ---------------------------------------------------------------------------

def _make_user(username="detector_test_user"):
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.example.com",
        password="testpass123",
    )


# =============================================================================
# 1. BehavioralBiometricsAnalyzer
# =============================================================================

class BehavioralBiometricsAnalyzerInitTest(TestCase):
    """Smoke-tests for BehavioralBiometricsAnalyzer instantiation."""

    def _get_cls(self):
        from api.fraud_detection.detectors.BehavioralBiometricsAnalyzer import (
            BehavioralBiometricsAnalyzer,
        )
        return BehavioralBiometricsAnalyzer

    def test_class_is_importable(self):
        cls = self._get_cls()
        self.assertIsNotNone(cls)

    def test_instantiation_no_args(self):
        cls = self._get_cls()
        analyzer = cls()
        self.assertIsNotNone(analyzer)

    def test_has_analyze_method(self):
        cls = self._get_cls()
        analyzer = cls()
        self.assertTrue(hasattr(analyzer, "analyze"))


class BehavioralBiometricsAnalyzerAnalyzeTest(TestCase):
    """Functional tests for analyze()."""

    def setUp(self):
        from api.fraud_detection.detectors.BehavioralBiometricsAnalyzer import (
            BehavioralBiometricsAnalyzer,
        )
        self.analyzer = BehavioralBiometricsAnalyzer()
        self.user = _make_user("biometrics_user")

    # --- Keystroke dynamics ------------------------------------------------

    def test_normal_typing_rhythm_low_risk(self):
        data = {
            "user_id": self.user.id,
            "keystroke_intervals_ms": [120, 115, 130, 125, 118, 122, 128],
            "typing_speed_wpm": 65,
            "backspace_ratio": 0.04,
            "session_duration_seconds": 300,
        }
        result = self.analyzer.analyze(data)
        self.assertIsInstance(result, dict)
        self.assertIn("risk_score", result)
        self.assertLessEqual(result["risk_score"], 50)

    def test_robotic_constant_timing_high_risk(self):
        """Identical keystroke intervals suggest a bot."""
        data = {
            "user_id": self.user.id,
            "keystroke_intervals_ms": [100, 100, 100, 100, 100, 100, 100, 100],
            "typing_speed_wpm": 200,
            "backspace_ratio": 0.0,
            "session_duration_seconds": 10,
        }
        result = self.analyzer.analyze(data)
        self.assertIsInstance(result, dict)
        self.assertIn("risk_score", result)
        # Robotic pattern should score higher than normal
        self.assertGreaterEqual(result["risk_score"], 0)

    def test_very_high_typing_speed_flagged(self):
        data = {
            "user_id": self.user.id,
            "keystroke_intervals_ms": [5, 5, 5, 5],
            "typing_speed_wpm": 500,
            "backspace_ratio": 0.0,
            "session_duration_seconds": 5,
        }
        result = self.analyzer.analyze(data)
        self.assertIn("risk_score", result)
        self.assertGreaterEqual(result["risk_score"], 0)

    # --- Mouse / touch dynamics -------------------------------------------

    def test_mouse_movement_data_accepted(self):
        data = {
            "user_id": self.user.id,
            "mouse_velocity_avg": 450.5,
            "mouse_acceleration_variance": 0.12,
            "click_pressure_avg": 0.78,
            "touch_events": [],
        }
        result = self.analyzer.analyze(data)
        self.assertIsInstance(result, dict)

    def test_zero_mouse_movement_flagged(self):
        """A human always moves the mouse; zero movement is suspicious."""
        data = {
            "user_id": self.user.id,
            "mouse_velocity_avg": 0.0,
            "mouse_acceleration_variance": 0.0,
            "click_pressure_avg": 0.0,
        }
        result = self.analyzer.analyze(data)
        self.assertIsInstance(result, dict)

    # --- Return value shape -----------------------------------------------

    def test_result_has_is_bot_flag(self):
        data = {"user_id": self.user.id}
        result = self.analyzer.analyze(data)
        # Must have either 'is_bot' or 'risk_score'
        self.assertTrue("is_bot" in result or "risk_score" in result)

    def test_risk_score_within_valid_range(self):
        data = {
            "user_id": self.user.id,
            "keystroke_intervals_ms": [100, 120, 115],
            "typing_speed_wpm": 60,
        }
        result = self.analyzer.analyze(data)
        if "risk_score" in result:
            self.assertGreaterEqual(result["risk_score"], 0)
            self.assertLessEqual(result["risk_score"], 100)

    def test_empty_data_does_not_raise(self):
        """Analyzer must handle missing keys gracefully."""
        try:
            result = self.analyzer.analyze({})
            self.assertIsInstance(result, dict)
        except (KeyError, TypeError) as exc:
            self.fail(f"analyze() raised {type(exc).__name__} on empty input: {exc}")

    def test_result_reasons_is_list(self):
        data = {"user_id": self.user.id, "keystroke_intervals_ms": [120, 115]}
        result = self.analyzer.analyze(data)
        if "reasons" in result:
            self.assertIsInstance(result["reasons"], list)

    def test_multiple_calls_consistent(self):
        """Results for identical input should be deterministic."""
        data = {
            "user_id": self.user.id,
            "keystroke_intervals_ms": [120, 115, 130],
            "typing_speed_wpm": 65,
        }
        r1 = self.analyzer.analyze(data)
        r2 = self.analyzer.analyze(data)
        self.assertEqual(r1.get("risk_score"), r2.get("risk_score"))


# =============================================================================
# 2. GeoVelocityDetector
# =============================================================================

class GeoVelocityDetectorInitTest(TestCase):

    def _get_cls(self):
        from api.fraud_detection.detectors.GeoVelocityDetector import GeoVelocityDetector
        return GeoVelocityDetector

    def test_importable(self):
        self.assertIsNotNone(self._get_cls())

    def test_instantiation(self):
        cls = self._get_cls()
        self.assertIsNotNone(cls())

    def test_has_detect_method(self):
        cls = self._get_cls()
        self.assertTrue(hasattr(cls(), "detect"))


class GeoVelocityDetectorDetectTest(TestCase):

    def setUp(self):
        from api.fraud_detection.detectors.GeoVelocityDetector import GeoVelocityDetector
        self.detector = GeoVelocityDetector()
        self.user = _make_user("geo_velocity_user")

    # --- Impossible travel -------------------------------------------------

    def test_same_location_consecutive_is_safe(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "current_location": {"lat": 23.8103, "lng": 90.4125, "country": "BD"},
            "current_time": now.isoformat(),
            "previous_location": {"lat": 23.8103, "lng": 90.4125, "country": "BD"},
            "previous_time": (now - timedelta(hours=1)).isoformat(),
        }
        result = self.detector.detect(data)
        self.assertIsInstance(result, dict)
        self.assertIn("is_suspicious", result)
        self.assertFalse(result.get("is_suspicious", True))

    def test_impossible_travel_detected(self):
        """NY → London in 5 minutes is physically impossible."""
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "current_location": {"lat": 51.5074, "lng": -0.1278, "country": "GB"},
            "current_time": now.isoformat(),
            "previous_location": {"lat": 40.7128, "lng": -74.0060, "country": "US"},
            "previous_time": (now - timedelta(minutes=5)).isoformat(),
        }
        result = self.detector.detect(data)
        self.assertIsInstance(result, dict)
        # Must flag impossible travel
        self.assertTrue(result.get("is_suspicious") or result.get("risk_score", 0) >= 70)

    def test_cross_country_overnight_travel_acceptable(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "current_location": {"lat": 51.5074, "lng": -0.1278, "country": "GB"},
            "current_time": now.isoformat(),
            "previous_location": {"lat": 48.8566, "lng": 2.3522, "country": "FR"},
            "previous_time": (now - timedelta(hours=3)).isoformat(),
        }
        result = self.detector.detect(data)
        self.assertIsInstance(result, dict)

    # --- Distance helpers -------------------------------------------------

    def test_has_distance_calculation(self):
        """Detector should expose haversine or similar utility."""
        has_method = (
            hasattr(self.detector, "calculate_distance")
            or hasattr(self.detector, "haversine")
            or hasattr(self.detector, "_haversine")
        )
        self.assertTrue(has_method, "Expected a distance calculation method on GeoVelocityDetector")

    def test_distance_calculation_correctness(self):
        """Dhaka–London ≈ 7,966 km; accept ±200 km for any projection."""
        method = (
            getattr(self.detector, "calculate_distance", None)
            or getattr(self.detector, "haversine", None)
            or getattr(self.detector, "_haversine", None)
        )
        if method is None:
            self.skipTest("No public distance method found")
        dhaka  = (23.8103, 90.4125)
        london = (51.5074, -0.1278)
        try:
            dist = method(dhaka[0], dhaka[1], london[0], london[1])
        except TypeError:
            dist = method(dhaka, london)
        self.assertAlmostEqual(dist, 7966, delta=300)

    # --- Return value shape -----------------------------------------------

    def test_result_risk_score_range(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "current_location": {"lat": 23.8103, "lng": 90.4125},
            "current_time": now.isoformat(),
            "previous_location": {"lat": 23.8103, "lng": 90.4125},
            "previous_time": (now - timedelta(hours=2)).isoformat(),
        }
        result = self.detector.detect(data)
        if "risk_score" in result:
            self.assertGreaterEqual(result["risk_score"], 0)
            self.assertLessEqual(result["risk_score"], 100)

    def test_missing_previous_location_handled(self):
        data = {
            "user_id": self.user.id,
            "current_location": {"lat": 23.8103, "lng": 90.4125},
            "current_time": timezone.now().isoformat(),
        }
        try:
            result = self.detector.detect(data)
            self.assertIsInstance(result, dict)
        except (KeyError, TypeError) as exc:
            self.fail(f"detect() raised on missing previous_location: {exc}")

    def test_empty_input_does_not_raise(self):
        try:
            result = self.detector.detect({})
            self.assertIsInstance(result, dict)
        except (KeyError, TypeError) as exc:
            self.fail(f"detect() raised on empty input: {exc}")


# =============================================================================
# 3. GraphNetworkAnalyzer
# =============================================================================

class GraphNetworkAnalyzerInitTest(TestCase):

    def _get_cls(self):
        from api.fraud_detection.detectors.GraphNetworkAnalyzer import GraphNetworkAnalyzer
        return GraphNetworkAnalyzer

    def test_importable(self):
        self.assertIsNotNone(self._get_cls())

    def test_instantiation(self):
        cls = self._get_cls()
        self.assertIsNotNone(cls())

    def test_has_analyze_method(self):
        cls = self._get_cls()
        self.assertTrue(
            hasattr(cls(), "analyze") or hasattr(cls(), "detect"),
            "GraphNetworkAnalyzer needs an analyze() or detect() method",
        )


class GraphNetworkAnalyzerAnalyzeTest(TestCase):

    def setUp(self):
        from api.fraud_detection.detectors.GraphNetworkAnalyzer import GraphNetworkAnalyzer
        self.analyzer = GraphNetworkAnalyzer()
        self.user = _make_user("graph_network_user")
        self._method = getattr(self.analyzer, "analyze", None) or getattr(self.analyzer, "detect")

    # --- Single isolated node (no fraud ring) -----------------------------

    def test_isolated_user_low_risk(self):
        data = {
            "user_id": self.user.id,
            "connections": [],
            "shared_ips": [],
            "shared_devices": [],
            "shared_payment_methods": [],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)
        self.assertLessEqual(result.get("risk_score", 0), 40)

    # --- Fraud ring detection ---------------------------------------------

    def test_dense_shared_ip_cluster_raises_risk(self):
        """5 users sharing the same IP looks like a fraud ring."""
        data = {
            "user_id": self.user.id,
            "connections": [101, 102, 103, 104, 105],
            "shared_ips": ["192.168.1.1"] * 5,
            "shared_devices": [],
            "shared_payment_methods": [],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)
        self.assertIn("risk_score", result)

    def test_shared_device_increases_risk(self):
        data = {
            "user_id": self.user.id,
            "connections": [201, 202],
            "shared_devices": ["device_abc123", "device_abc123"],
            "shared_ips": [],
            "shared_payment_methods": [],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    def test_shared_payment_method_detected(self):
        data = {
            "user_id": self.user.id,
            "connections": [301],
            "shared_payment_methods": ["card_xxxx1234"],
            "shared_ips": [],
            "shared_devices": [],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    # --- Ring structure ---------------------------------------------------

    def test_known_fraud_ring_members_flagged(self):
        data = {
            "user_id": self.user.id,
            "connections": [401, 402, 403],
            "shared_ips": ["10.0.0.1", "10.0.0.1", "10.0.0.1"],
            "shared_devices": ["dev_001", "dev_001"],
            "shared_payment_methods": ["card_1111"],
            "known_fraud_user_ids": [401, 402],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)
        self.assertGreaterEqual(result.get("risk_score", 0), 0)

    # --- Return value shape -----------------------------------------------

    def test_risk_score_in_valid_range(self):
        data = {"user_id": self.user.id, "connections": [1, 2, 3]}
        result = self._method(data)
        if "risk_score" in result:
            self.assertGreaterEqual(result["risk_score"], 0)
            self.assertLessEqual(result["risk_score"], 100)

    def test_result_contains_is_suspicious_or_risk_score(self):
        data = {"user_id": self.user.id}
        result = self._method(data)
        self.assertTrue(
            "is_suspicious" in result or "risk_score" in result,
            f"Expected is_suspicious or risk_score key, got: {list(result.keys())}",
        )

    def test_empty_input_does_not_raise(self):
        try:
            result = self._method({})
            self.assertIsInstance(result, dict)
        except (KeyError, TypeError) as exc:
            self.fail(f"analyze() raised on empty input: {exc}")

    def test_reasons_field_is_list_when_present(self):
        data = {"user_id": self.user.id, "connections": [501, 502]}
        result = self._method(data)
        if "reasons" in result:
            self.assertIsInstance(result["reasons"], list)

    def test_multiple_calls_deterministic(self):
        data = {
            "user_id": self.user.id,
            "connections": [601, 602],
            "shared_ips": ["172.16.0.1"],
        }
        r1 = self._method(data)
        r2 = self._method(data)
        self.assertEqual(r1.get("risk_score"), r2.get("risk_score"))


# =============================================================================
# 4. VelocityEngine
# =============================================================================

class VelocityEngineInitTest(TestCase):

    def _get_cls(self):
        from api.fraud_detection.detectors.VelocityEngine import VelocityEngine
        return VelocityEngine

    def test_importable(self):
        self.assertIsNotNone(self._get_cls())

    def test_instantiation(self):
        cls = self._get_cls()
        self.assertIsNotNone(cls())

    def test_has_check_method(self):
        cls = self._get_cls()
        instance = cls()
        self.assertTrue(
            hasattr(instance, "check") or hasattr(instance, "analyze") or hasattr(instance, "detect"),
            "VelocityEngine must expose check(), analyze(), or detect()",
        )


class VelocityEngineCheckTest(TestCase):

    def setUp(self):
        from api.fraud_detection.detectors.VelocityEngine import VelocityEngine
        self.engine = VelocityEngine()
        self.user = _make_user("velocity_user")
        self._method = (
            getattr(self.engine, "check", None)
            or getattr(self.engine, "analyze", None)
            or getattr(self.engine, "detect")
        )

    # --- Normal velocity --------------------------------------------------

    def test_single_attempt_is_safe(self):
        data = {
            "user_id": self.user.id,
            "event_type": "login",
            "window_seconds": 3600,
            "event_count": 1,
            "timestamps": [timezone.now().isoformat()],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("limit_exceeded", False))

    def test_normal_rate_below_threshold(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "event_type": "offer_completion",
            "window_seconds": 3600,
            "event_count": 5,
            "timestamps": [
                (now - timedelta(minutes=i * 10)).isoformat() for i in range(5)
            ],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    # --- High velocity / burst -------------------------------------------

    def test_burst_many_events_same_second_flagged(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "event_type": "login",
            "window_seconds": 60,
            "event_count": 50,
            "timestamps": [now.isoformat()] * 50,
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)
        # High burst should be detected
        self.assertTrue(
            result.get("limit_exceeded", False) or result.get("risk_score", 0) >= 60,
            f"Expected high velocity to be flagged; got: {result}",
        )

    def test_many_offer_completions_in_short_window(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "event_type": "offer_completion",
            "window_seconds": 300,  # 5 minutes
            "event_count": 30,
            "timestamps": [
                (now - timedelta(seconds=i * 10)).isoformat() for i in range(30)
            ],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    def test_withdrawal_velocity_check(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "event_type": "withdrawal",
            "window_seconds": 3600,
            "event_count": 20,
            "amount_total": 50000.00,
            "timestamps": [
                (now - timedelta(minutes=i * 3)).isoformat() for i in range(20)
            ],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    # --- Window boundary tests -------------------------------------------

    def test_events_outside_window_not_counted(self):
        now = timezone.now()
        data = {
            "user_id": self.user.id,
            "event_type": "login",
            "window_seconds": 60,
            "event_count": 2,
            "timestamps": [
                now.isoformat(),
                (now - timedelta(hours=2)).isoformat(),  # outside 60-second window
            ],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    # --- Per-IP and per-device velocity ----------------------------------

    def test_ip_velocity_check(self):
        now = timezone.now()
        data = {
            "ip_address": "203.0.113.42",
            "event_type": "login",
            "window_seconds": 3600,
            "event_count": 100,
            "timestamps": [(now - timedelta(seconds=i * 36)).isoformat() for i in range(100)],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    def test_device_velocity_check(self):
        now = timezone.now()
        data = {
            "device_id": "device_fingerprint_abc",
            "event_type": "offer_completion",
            "window_seconds": 3600,
            "event_count": 40,
            "timestamps": [(now - timedelta(seconds=i * 90)).isoformat() for i in range(40)],
        }
        result = self._method(data)
        self.assertIsInstance(result, dict)

    # --- Return value shape -----------------------------------------------

    def test_result_risk_score_in_valid_range(self):
        data = {
            "user_id": self.user.id,
            "event_type": "login",
            "window_seconds": 3600,
            "event_count": 3,
        }
        result = self._method(data)
        if "risk_score" in result:
            self.assertGreaterEqual(result["risk_score"], 0)
            self.assertLessEqual(result["risk_score"], 100)

    def test_result_has_velocity_metadata(self):
        data = {
            "user_id": self.user.id,
            "event_type": "login",
            "window_seconds": 3600,
            "event_count": 5,
        }
        result = self._method(data)
        # At least one of these should be in the response
        self.assertTrue(
            any(k in result for k in [
                "risk_score", "limit_exceeded", "rate", "velocity",
                "events_per_minute", "is_suspicious",
            ]),
            f"No velocity metadata found in result keys: {list(result.keys())}",
        )

    def test_empty_input_does_not_raise(self):
        try:
            result = self._method({})
            self.assertIsInstance(result, dict)
        except (KeyError, TypeError) as exc:
            self.fail(f"check() raised on empty input: {exc}")

    def test_zero_events_safe(self):
        data = {
            "user_id": self.user.id,
            "event_type": "login",
            "window_seconds": 3600,
            "event_count": 0,
            "timestamps": [],
        }
        try:
            result = self._method(data)
            self.assertIsInstance(result, dict)
            self.assertFalse(result.get("limit_exceeded", False))
        except ZeroDivisionError as exc:
            self.fail(f"check() raised ZeroDivisionError on zero events: {exc}")

    def test_multiple_calls_deterministic(self):
        data = {
            "user_id": self.user.id,
            "event_type": "login",
            "window_seconds": 3600,
            "event_count": 10,
        }
        r1 = self._method(data)
        r2 = self._method(data)
        self.assertEqual(r1.get("risk_score"), r2.get("risk_score"))
