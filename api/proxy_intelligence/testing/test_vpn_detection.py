"""Tests for VPN Detection Engine."""
import pytest
from unittest.mock import patch, MagicMock
from ..detection_engines.vpn_detector import VPNDetector


class TestVPNDetector:
    def test_known_vpn_asn_detected(self):
        with patch("..detection_engines.vpn_detector.VPNDetector._check_open_ports"):
            with patch("..detection_engines.vpn_detector.VPNDetector._check_hostname"):
                detector = VPNDetector("192.168.1.1")
                detector.signals = {
                    "asn_match": True,
                    "asn_provider": "NordVPN",
                    "asn": "AS44814",
                    "isp_keyword": True,
                    "isp_keywords_matched": ["nordvpn"],
                    "hostname_keyword": False,
                    "hostname_keywords_matched": [],
                    "proxy_headers": False,
                    "proxy_headers_found": [],
                    "open_vpn_ports": False,
                    "open_ports": [],
                    "db_malicious": False,
                    "db_confidence": 0.0,
                    "datacenter_asn": False,
                }
                confidence = detector._calculate_confidence()
                assert confidence >= 0.65, f"Expected >=0.65, got {confidence}"

    def test_clean_ip_not_flagged(self):
        detector = VPNDetector("8.8.8.8")
        detector.signals = {
            "asn_match": False, "isp_keyword": False,
            "hostname_keyword": False, "proxy_headers": False,
            "open_vpn_ports": False, "db_malicious": False,
            "datacenter_asn": False, "db_confidence": 0.0,
        }
        confidence = detector._calculate_confidence()
        assert confidence == 0.0

    def test_tor_hostname_detected(self):
        detector = VPNDetector("10.0.0.1")
        detector.signals = {
            "asn_match": False, "isp_keyword": False,
            "hostname_keyword": True, "hostname_keywords_matched": ["tor"],
            "proxy_headers": False, "open_vpn_ports": False,
            "db_malicious": False, "db_confidence": 0.0,
            "datacenter_asn": False,
        }
        confidence = detector._calculate_confidence()
        assert confidence > 0.0

    def test_detection_methods_listed(self):
        detector = VPNDetector("1.2.3.4")
        detector.signals = {
            "asn_match": True, "isp_keyword": True,
            "hostname_keyword": False, "proxy_headers": False,
            "open_vpn_ports": False, "db_malicious": False, "datacenter_asn": False,
        }
        methods = detector._triggered_methods()
        assert "asn_database" in methods
        assert "isp_keyword_analysis" in methods

    def test_proxy_header_increases_confidence(self):
        detector = VPNDetector("5.5.5.5")
        detector.signals = {
            "asn_match": False, "isp_keyword": False,
            "hostname_keyword": False, "proxy_headers": True,
            "proxy_headers_found": [{"header": "X_FORWARDED_FOR", "value": "1.2.3.4"}],
            "open_vpn_ports": False, "db_malicious": False,
            "db_confidence": 0.0, "datacenter_asn": False,
        }
        confidence = detector._calculate_confidence()
        assert confidence >= 0.10
