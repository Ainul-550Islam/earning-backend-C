"""
test_fraud.py – Unit tests for postback-internal fraud detection.

Tests:
  • IP velocity check
  • Geo anomaly check
  • Device/OS sanity check
  • Blocked subnet check
  • FraudResult aggregation + scoring
  • Fail-open behaviour on cache errors
"""
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from api.postback.utils.fraud_detector import (
    FraudResult,
    FraudSignal,
    check_fraud,
    _check_blocked_subnet,
    _check_device_sanity,
    _check_geo_anomaly,
    _check_ip_velocity,
)


def _mock_network(network_key="test_net", metadata=None):
    config = MagicMock()
    config.network_key = network_key
    config.metadata = metadata or {}
    return config


class IPVelocityCheckTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_first_request_allowed(self):
        signal = _check_ip_velocity("1.2.3.4", "net1", limit=30, window=60)
        self.assertFalse(signal.triggered)

    def test_within_limit_allowed(self):
        for _ in range(25):
            _check_ip_velocity("1.2.3.5", "net1", limit=30, window=60)
        signal = _check_ip_velocity("1.2.3.5", "net1", limit=30, window=60)
        self.assertFalse(signal.triggered)

    def test_exceeds_limit_triggers(self):
        for _ in range(31):
            _check_ip_velocity("1.2.3.6", "net1", limit=30, window=60)
        signal = _check_ip_velocity("1.2.3.6", "net1", limit=30, window=60)
        self.assertTrue(signal.triggered)
        self.assertEqual(signal.score, 50)

    def test_empty_ip_never_triggers(self):
        signal = _check_ip_velocity(None, "net1", limit=5, window=60)
        self.assertFalse(signal.triggered)

    def test_different_ips_tracked_separately(self):
        for _ in range(35):
            _check_ip_velocity("9.9.9.9", "net1", limit=30, window=60)
        # Different IP should not be affected
        signal = _check_ip_velocity("8.8.8.8", "net1", limit=30, window=60)
        self.assertFalse(signal.triggered)

    @patch("api.postback.utils.fraud_detector.cache.add", side_effect=Exception("cache down"))
    def test_cache_failure_fails_open(self, mock_cache):
        signal = _check_ip_velocity("1.2.3.7", "net1", limit=5, window=60)
        self.assertFalse(signal.triggered)  # Fail open


class GeoAnomalyCheckTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_single_country_allowed(self):
        signal = _check_geo_anomaly("user1", "US", "net1", max_countries=3, window=3600)
        self.assertFalse(signal.triggered)

    def test_two_countries_allowed(self):
        _check_geo_anomaly("user2", "US", "net1", max_countries=3, window=3600)
        signal = _check_geo_anomaly("user2", "GB", "net1", max_countries=3, window=3600)
        self.assertFalse(signal.triggered)

    def test_exceeds_country_limit_triggers(self):
        cache.clear()
        for country in ["US", "GB", "DE", "FR"]:
            _check_geo_anomaly("user3", country, "net1", max_countries=3, window=3600)
        signal = _check_geo_anomaly("user3", "JP", "net1", max_countries=3, window=3600)
        self.assertTrue(signal.triggered)
        self.assertEqual(signal.score, 40)
        self.assertGreater(signal.score, 0)

    def test_same_country_repeated_not_anomaly(self):
        for _ in range(10):
            _check_geo_anomaly("user4", "US", "net1", max_countries=3, window=3600)
        signal = _check_geo_anomaly("user4", "US", "net1", max_countries=3, window=3600)
        self.assertFalse(signal.triggered)

    def test_empty_user_id_skips(self):
        # Empty user_id means we can't track — should not raise
        signal = _check_geo_anomaly("", "US", "net1", max_countries=3, window=3600)
        self.assertFalse(signal.triggered)


class DeviceSanityCheckTests(TestCase):

    def test_ios_windows_impossible(self):
        signal = _check_device_sanity("ios", "windows")
        self.assertTrue(signal.triggered)
        self.assertEqual(signal.score, 30)

    def test_ios_android_impossible(self):
        signal = _check_device_sanity("ios", "android")
        self.assertTrue(signal.triggered)

    def test_android_ios_impossible(self):
        signal = _check_device_sanity("android", "ios")
        self.assertTrue(signal.triggered)

    def test_android_macos_impossible(self):
        signal = _check_device_sanity("android", "macos")
        self.assertTrue(signal.triggered)

    def test_mobile_android_valid(self):
        signal = _check_device_sanity("mobile", "android")
        self.assertFalse(signal.triggered)

    def test_desktop_windows_valid(self):
        signal = _check_device_sanity("desktop", "windows")
        self.assertFalse(signal.triggered)

    def test_empty_values_no_trigger(self):
        signal = _check_device_sanity("", "")
        self.assertFalse(signal.triggered)


class BlockedSubnetCheckTests(TestCase):

    def test_ip_in_blocked_cidr_triggers(self):
        signal = _check_blocked_subnet("192.168.1.50", ["192.168.1.0/24"])
        self.assertTrue(signal.triggered)
        self.assertEqual(signal.score, 80)

    def test_ip_outside_blocked_cidr_clean(self):
        signal = _check_blocked_subnet("10.0.0.1", ["192.168.1.0/24"])
        self.assertFalse(signal.triggered)

    def test_exact_ip_match_in_blocklist(self):
        signal = _check_blocked_subnet("8.8.8.8", ["8.8.8.8/32"])
        self.assertTrue(signal.triggered)

    def test_multiple_subnets_one_matches(self):
        signal = _check_blocked_subnet("172.16.0.5", [
            "192.168.0.0/24",
            "172.16.0.0/16",
            "10.0.0.0/8",
        ])
        self.assertTrue(signal.triggered)

    def test_malformed_cidr_skipped_gracefully(self):
        signal = _check_blocked_subnet("1.2.3.4", ["not_a_cidr", "1.2.3.4/32"])
        self.assertTrue(signal.triggered)  # Valid CIDR still matched

    def test_invalid_ip_returns_clean(self):
        signal = _check_blocked_subnet("not_an_ip", ["192.168.0.0/24"])
        self.assertFalse(signal.triggered)


class FraudResultAggregationTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_clean_payload_not_fraudulent(self):
        config = _mock_network()
        result = check_fraud(
            adapted_payload={"lead_id": "L1", "user_id": "U1"},
            source_ip="1.2.3.4",
            network_config=config,
        )
        self.assertIsInstance(result, FraudResult)
        self.assertFalse(result.is_fraudulent)

    def test_blocked_subnet_marks_fraudulent(self):
        config = _mock_network(metadata={"fraud_blocked_subnets": ["5.5.5.0/24"]})
        result = check_fraud(
            adapted_payload={"lead_id": "L1", "user_id": "U1"},
            source_ip="5.5.5.100",
            network_config=config,
        )
        self.assertTrue(result.is_fraudulent)
        self.assertGreaterEqual(result.total_score, 80)

    def test_impossible_device_os_adds_score(self):
        config = _mock_network()
        result = check_fraud(
            adapted_payload={
                "lead_id": "L1", "user_id": "U1",
                "device": "ios", "os": "windows",
            },
            source_ip="1.2.3.4",
            network_config=config,
            fraud_threshold=25,
        )
        self.assertTrue(result.is_fraudulent)

    def test_custom_threshold_respected(self):
        config = _mock_network(metadata={"fraud_score_threshold": 200})
        result = check_fraud(
            adapted_payload={"lead_id": "L1"},
            source_ip="5.5.5.100",
            network_config=_mock_network(metadata={
                "fraud_blocked_subnets": ["5.5.5.0/24"],
                "fraud_score_threshold": 200,
            }),
            fraud_threshold=200,
        )
        # Score would be 80 from blocked subnet, threshold is 200, so NOT fraudulent
        self.assertFalse(result.is_fraudulent)

    def test_exception_fails_open(self):
        """check_fraud never raises — always returns FraudResult."""
        result = check_fraud(
            adapted_payload=None,  # type: ignore
            source_ip=None,
            network_config=None,  # type: ignore
        )
        self.assertIsInstance(result, FraudResult)
        self.assertFalse(result.is_fraudulent)

    def test_reasons_populated_when_triggered(self):
        config = _mock_network(metadata={"fraud_blocked_subnets": ["9.9.9.0/24"]})
        result = check_fraud(
            adapted_payload={"lead_id": "L1"},
            source_ip="9.9.9.9",
            network_config=config,
        )
        self.assertTrue(len(result.reasons) > 0)
        self.assertIn("9.9.9.9", result.reasons[0])
