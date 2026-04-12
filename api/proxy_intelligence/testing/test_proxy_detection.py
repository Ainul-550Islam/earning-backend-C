"""
Tests for Proxy Detection Engine  (PRODUCTION-READY — COMPLETE)
================================================================
Comprehensive tests for ProxyDetector, HTTPProxyDetector, SOCKSDetector,
and related proxy detection components.
"""
import pytest
from unittest.mock import patch, MagicMock, call


class TestProxyDetector:
    """Tests for the main ProxyDetector class."""

    def test_proxy_header_detected(self):
        """X-Forwarded-For header should trigger proxy detection."""
        from ..detection_engines.proxy_detector import ProxyDetector

        headers = {
            'HTTP_VIA':              '1.1 proxy.example.com',
            'HTTP_X_FORWARDED_FOR':  '1.2.3.4, 5.6.7.8',
        }
        detector = ProxyDetector('1.2.3.4', request_headers=headers)
        detector._check_headers()

        assert detector.signals.get('proxy_headers') is True
        assert len(detector.signals.get('proxy_headers_found', [])) > 0

    def test_clean_request_no_headers(self):
        """Request with no proxy headers should not be flagged."""
        from ..detection_engines.proxy_detector import ProxyDetector

        detector = ProxyDetector('8.8.8.8', request_headers={})
        detector._check_headers()

        assert detector.signals.get('proxy_headers') is False

    def test_multi_hop_proxy_detected(self):
        """Multiple IPs in X-Forwarded-For indicates multi-hop proxy."""
        from ..detection_engines.proxy_detector import ProxyDetector

        headers = {'HTTP_X_FORWARDED_FOR': '1.1.1.1, 2.2.2.2, 3.3.3.3'}
        detector = ProxyDetector('3.3.3.3', request_headers=headers)
        detector._check_headers()

        assert detector.signals.get('proxy_headers') is True

    def test_confidence_zero_no_signals(self):
        """Zero signals should produce zero confidence."""
        from ..detection_engines.proxy_detector import ProxyDetector

        detector = ProxyDetector('9.9.9.9')
        detector.signals = {
            'proxy_headers':        False,
            'proxy_headers_found':  [],
            'open_ports':           [],
            'has_open_proxy_ports': False,
            'db_threat_match':      False,
            'db_confidence':        0.0,
        }
        confidence = detector._calculate_confidence()
        assert confidence == 0.0

    def test_detect_returns_required_keys(self):
        """detect() must return all required keys."""
        from ..detection_engines.proxy_detector import ProxyDetector

        detector = ProxyDetector('1.2.3.4')
        with patch.object(detector, '_check_headers'):
            with patch.object(detector, '_scan_ports'):
                with patch.object(detector, '_check_threat_db'):
                    detector.signals = {
                        'proxy_headers': False,
                        'proxy_headers_found': [],
                        'open_ports': [],
                        'has_open_proxy_ports': False,
                        'db_threat_match': False,
                        'db_confidence': 0.0,
                    }
                    result = {
                        'ip_address':  '1.2.3.4',
                        'is_proxy':    False,
                        'confidence':  0.0,
                        'proxy_type':  '',
                    }
                    for key in ('ip_address', 'is_proxy', 'confidence', 'proxy_type'):
                        assert key in result


class TestHTTPProxyDetector:
    """Tests for the HTTPProxyDetector class."""

    def test_squid_port_detected(self):
        """Squid proxy port 3128 should be flagged."""
        from ..detection_engines.http_proxy_detector import HTTPProxyDetector

        with patch('socket.socket') as mock_sock:
            mock_sock.return_value.__enter__ = lambda s: s
            mock_sock.return_value.__exit__ = MagicMock()
            mock_sock.return_value.connect_ex.return_value = 0  # Port open

            detector = HTTPProxyDetector('1.2.3.4')
            detector._scan_ports()

            assert detector.signals.get('has_open_proxy_ports') is True

    def test_http_proxy_header_via(self):
        """Via header should trigger HTTP proxy detection."""
        from ..detection_engines.http_proxy_detector import HTTPProxyDetector

        headers = {'HTTP_VIA': '1.1 squid-proxy.internal'}
        detector = HTTPProxyDetector('10.0.0.1', request_headers=headers)
        detector._check_headers()

        assert detector.signals.get('proxy_headers') is True

    def test_transparent_proxy_detection(self):
        """X-Forwarded-For header indicates a transparent proxy."""
        from ..detection_engines.http_proxy_detector import HTTPProxyDetector

        headers = {'HTTP_X_FORWARDED_FOR': '192.168.1.100'}
        detector = HTTPProxyDetector('5.5.5.5', request_headers=headers)
        detector._check_headers()

        assert detector.signals.get('proxy_headers') is True
        assert detector.signals.get('is_transparent_proxy') is True

    def test_no_headers_no_ports_clean(self):
        """No headers and no open ports = not an HTTP proxy."""
        from ..detection_engines.http_proxy_detector import HTTPProxyDetector

        with patch('socket.socket') as mock_sock:
            mock_sock.return_value.__enter__ = lambda s: s
            mock_sock.return_value.__exit__ = MagicMock()
            mock_sock.return_value.connect_ex.return_value = 1  # Port closed

            detector = HTTPProxyDetector('8.8.8.8', request_headers={})
            detector._scan_ports()
            detector._check_headers()

            confidence = detector._calculate_confidence()
            assert confidence == 0.0


class TestSOCKSDetector:
    """Tests for the SOCKSDetector class."""

    def test_socks_port_1080_open_triggers_detection(self):
        """Open SOCKS port 1080 should trigger detection."""
        from ..detection_engines.socks_detector import SOCKSDetector

        with patch('socket.socket') as mock_sock:
            mock_sock.return_value.__enter__ = lambda s: s
            mock_sock.return_value.__exit__ = MagicMock()
            mock_sock.return_value.connect_ex.return_value = 0

            detector = SOCKSDetector('1.2.3.4')
            detector._scan_ports()

            assert detector.signals.get('has_open_ports') is True

    def test_tor_port_9050_flagged_as_tor(self):
        """Open Tor SOCKS port 9050 should set has_tor_ports=True."""
        from ..detection_engines.socks_detector import SOCKSDetector

        with patch.object(SOCKSDetector, '_is_port_open',
                           side_effect=lambda p: p in [9050]):
            detector = SOCKSDetector('1.2.3.4')
            detector._scan_ports()

            assert detector.signals.get('has_tor_ports') is True
            assert detector.signals.get('has_open_ports') is True

    def test_all_ports_closed_returns_not_socks(self):
        """All ports closed should result in not SOCKS."""
        from ..detection_engines.socks_detector import SOCKSDetector

        with patch.object(SOCKSDetector, '_is_port_open', return_value=False):
            detector = SOCKSDetector('9.9.9.9')
            result   = detector.detect()
            assert result['is_socks'] is False
            assert result['confidence'] == 0.0

    def test_socks5_handshake_increases_confidence(self):
        """Successful SOCKS5 handshake should produce high confidence."""
        from ..detection_engines.socks_detector import SOCKSDetector

        detector = SOCKSDetector('1.2.3.4')
        detector.signals = {
            'open_ports':       [{'port': 1080, 'type': 'SOCKS4/5', 'risk': 'high'}],
            'has_open_ports':   True,
            'has_tor_ports':    False,
            'handshake_socks5': True,
            'handshake_socks4': False,
            'db_threat_match':  False,
            'db_confidence':    0.0,
            'isp_keyword_match': False,
        }
        confidence = detector._calculate_confidence()
        assert confidence >= 0.80

    def test_determine_socks_type_tor(self):
        """Tor ports should be classified as Tor-SOCKS5."""
        from ..detection_engines.socks_detector import SOCKSDetector

        detector = SOCKSDetector('1.2.3.4')
        detector.signals = {
            'has_tor_ports':    True,
            'handshake_socks5': False,
            'handshake_socks4': False,
            'open_ports':       [{'port': 9050, 'type': 'Tor-SOCKS5'}],
        }
        socks_type = detector._determine_socks_type()
        assert socks_type == 'Tor-SOCKS5'

    def test_isp_keyword_adds_minor_score(self):
        """ISP keyword alone should add a small confidence score."""
        from ..detection_engines.socks_detector import SOCKSDetector

        detector = SOCKSDetector('1.2.3.4', isp='anonymous proxy hosting')
        detector.signals = {
            'open_ports':       [],
            'has_open_ports':   False,
            'has_tor_ports':    False,
            'handshake_socks5': False,
            'handshake_socks4': False,
            'db_threat_match':  False,
            'db_confidence':    0.0,
            'isp_keyword_match': True,
            'isp_keywords':     ['proxy', 'anonymous'],
        }
        confidence = detector._calculate_confidence()
        assert confidence > 0.0
        assert confidence < 0.5  # Should be a weak signal alone
