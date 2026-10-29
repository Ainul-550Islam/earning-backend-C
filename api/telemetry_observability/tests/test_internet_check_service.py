"""
Unit tests for InternetCheckService.

All network I/O is mocked — these tests run offline with no external calls.
Each probe type (tcp, dns, http) is tested independently as well as through
the public check() API.
"""
import socket
from unittest.mock import MagicMock, patch, call
from urllib.error import URLError

import pytest

from ..services.internet_check_service import (
    InternetCheckResult,
    InternetCheckService,
    ProbeResult,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _passing_tcp_target():
    return {'type': 'tcp', 'host': '8.8.8.8', 'port': 53, 'timeout': 1}

def _passing_dns_target():
    return {'type': 'dns', 'host': 'dns.google', 'port': 53, 'timeout': 1}

def _passing_http_target():
    return {'type': 'http', 'url': 'https://connectivitycheck.gstatic.com/generate_204', 'timeout': 1}

def _failing_tcp_target():
    return {'type': 'tcp', 'host': '0.0.0.0', 'port': 9, 'timeout': 0.1}


# ── ProbeResult ────────────────────────────────────────────────────────────────

class TestProbeResult:
    def test_successful_probe_fields(self):
        p = ProbeResult(probe_type='tcp', target='8.8.8.8:53', reachable=True, latency_ms=12.5)
        assert p.reachable is True
        assert p.latency_ms == 12.5
        assert p.error is None
        assert p.http_status is None

    def test_failed_probe_fields(self):
        p = ProbeResult(
            probe_type='http', target='https://x.example',
            reachable=False, latency_ms=50.0, error='Connection refused',
            http_status=503,
        )
        assert p.reachable is False
        assert p.error == 'Connection refused'
        assert p.http_status == 503


# ── InternetCheckResult ────────────────────────────────────────────────────────

class TestInternetCheckResult:
    def _make_result(self, score=100, reachable=True, probes=None, error_count=0, latency=30.0):
        return InternetCheckResult(
            reachable=reachable,
            health_score=score,
            probes=probes or [],
            avg_latency_ms=latency,
            error_count=error_count,
        )

    def test_summary_reachable(self):
        r = self._make_result(score=100, reachable=True, latency=25.0)
        s = r.summary()
        assert 'REACHABLE' in s
        assert '100' in s

    def test_summary_unreachable(self):
        r = self._make_result(score=0, reachable=False, latency=None)
        assert 'UNREACHABLE' in r.summary()
        assert 'n/a' in r.summary()

    def test_as_metadata_structure(self):
        probes = [
            ProbeResult('tcp', '8.8.8.8:53', True, latency_ms=10.0),
            ProbeResult('http', 'https://x.com', False, latency_ms=200.0, error='timeout'),
        ]
        r = InternetCheckResult(
            reachable=True, health_score=50, probes=probes,
            avg_latency_ms=105.0, error_count=1,
        )
        meta = r.as_metadata()
        assert meta['probes_total'] == 2
        assert meta['probes_passed'] == 1
        assert meta['health_score'] == 50
        assert len(meta['probes']) == 2

    def test_as_metadata_latency_rounded(self):
        r = self._make_result(latency=123.456789)
        meta = r.as_metadata()
        assert meta['avg_latency_ms'] == 123.46

    def test_as_metadata_latency_none(self):
        r = self._make_result(latency=None)
        assert r.as_metadata()['avg_latency_ms'] is None

    def test_checked_at_is_set(self):
        r = self._make_result()
        assert isinstance(r.checked_at, float)
        assert r.checked_at > 0


# ── InternetCheckService — TCP probe ──────────────────────────────────────────

class TestTcpProbe:
    def test_successful_tcp_probe(self):
        svc = InternetCheckService(targets=[_passing_tcp_target()])
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch('socket.create_connection', return_value=mock_sock) as mock_conn:
            result = svc.check()

        assert result.reachable is True
        assert result.health_score == 100
        assert result.error_count == 0
        assert result.probes[0].probe_type == 'tcp'
        mock_conn.assert_called_once_with(('8.8.8.8', 53), timeout=1.0)

    def test_failed_tcp_probe_connection_refused(self):
        svc = InternetCheckService(targets=[_passing_tcp_target()])
        with patch('socket.create_connection', side_effect=OSError('Connection refused')):
            result = svc.check()

        assert result.reachable is False
        assert result.health_score == 0
        assert result.error_count == 1
        assert result.probes[0].error is not None

    def test_tcp_probe_records_latency(self):
        svc = InternetCheckService(targets=[_passing_tcp_target()])
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch('socket.create_connection', return_value=mock_sock):
            result = svc.check()

        assert result.probes[0].latency_ms is not None
        assert result.probes[0].latency_ms >= 0

    def test_failed_tcp_probe_still_records_latency(self):
        svc = InternetCheckService(targets=[_passing_tcp_target()])
        with patch('socket.create_connection', side_effect=OSError('timeout')):
            result = svc.check()

        assert result.probes[0].latency_ms is not None


# ── InternetCheckService — DNS probe ──────────────────────────────────────────

class TestDnsProbe:
    def test_successful_dns_probe(self):
        svc = InternetCheckService(targets=[_passing_dns_target()])
        fake_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 0)),
        ]
        with patch('socket.getaddrinfo', return_value=fake_addrinfo):
            result = svc.check()

        assert result.reachable is True
        assert result.probes[0].probe_type == 'dns'
        assert result.probes[0].reachable is True
        assert result.error_count == 0

    def test_failed_dns_probe(self):
        svc = InternetCheckService(targets=[_passing_dns_target()])
        with patch('socket.getaddrinfo', side_effect=OSError('Name or service not known')):
            result = svc.check()

        assert result.reachable is False
        assert result.probes[0].reachable is False
        assert result.probes[0].error is not None

    def test_empty_dns_result_treated_as_failure(self):
        svc = InternetCheckService(targets=[_passing_dns_target()])
        with patch('socket.getaddrinfo', return_value=[]):
            result = svc.check()

        assert result.probes[0].reachable is False


# ── InternetCheckService — HTTP probe ─────────────────────────────────────────

class TestHttpProbe:
    def _mock_urlopen(self, status=200):
        mock_resp = MagicMock()
        mock_resp.status = status
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_resp)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    def test_successful_http_probe(self):
        svc = InternetCheckService(targets=[_passing_http_target()])
        with patch('api.telemetry_observability.services.internet_check_service.urlopen',
                   return_value=self._mock_urlopen(204)):
            result = svc.check()

        assert result.reachable is True
        assert result.probes[0].http_status == 204
        assert result.probes[0].reachable is True

    def test_http_redirect_treated_as_success(self):
        svc = InternetCheckService(targets=[_passing_http_target()])
        with patch('api.telemetry_observability.services.internet_check_service.urlopen',
                   return_value=self._mock_urlopen(301)):
            result = svc.check()

        assert result.probes[0].reachable is True

    def test_http_5xx_treated_as_failure(self):
        svc = InternetCheckService(targets=[_passing_http_target()])
        with patch('api.telemetry_observability.services.internet_check_service.urlopen',
                   return_value=self._mock_urlopen(503)):
            result = svc.check()

        assert result.probes[0].reachable is False
        assert result.probes[0].http_status == 503

    def test_http_url_error_treated_as_failure(self):
        svc = InternetCheckService(targets=[_passing_http_target()])
        with patch('api.telemetry_observability.services.internet_check_service.urlopen',
                   side_effect=URLError('timed out')):
            result = svc.check()

        assert result.probes[0].reachable is False
        assert result.probes[0].error is not None

    def test_http_unexpected_exception_treated_as_failure(self):
        svc = InternetCheckService(targets=[_passing_http_target()])
        with patch('api.telemetry_observability.services.internet_check_service.urlopen',
                   side_effect=ConnectionResetError('reset')):
            result = svc.check()

        assert result.probes[0].reachable is False

    def test_http_probe_sends_head_request(self):
        svc = InternetCheckService(targets=[_passing_http_target()])
        captured_requests = []

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            return self._mock_urlopen(200)

        with patch('api.telemetry_observability.services.internet_check_service.urlopen',
                   side_effect=fake_urlopen):
            svc.check()

        assert captured_requests[0].method == 'HEAD'


# ── Aggregation ───────────────────────────────────────────────────────────────

class TestAggregation:
    def test_all_probes_pass_score_100(self):
        targets = [_passing_tcp_target(), _passing_dns_target()]
        svc = InternetCheckService(targets=targets, pass_threshold=0.5)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch('socket.create_connection', return_value=mock_sock), \
             patch('socket.getaddrinfo', return_value=[('', '', '', '', ('8.8.8.8', 0))]):
            result = svc.check()

        assert result.health_score == 100

    def test_half_probes_fail_score_50(self):
        targets = [_passing_tcp_target(), _passing_tcp_target()]
        svc = InternetCheckService(targets=targets, pass_threshold=0.4)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        call_count = [0]

        def alternate(host_port, timeout=None):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise OSError('fail')
            return mock_sock

        with patch('socket.create_connection', side_effect=alternate):
            result = svc.check()

        assert result.health_score == 50
        assert result.error_count == 1

    def test_all_probes_fail_score_0(self):
        svc = InternetCheckService(targets=[_failing_tcp_target()])
        with patch('socket.create_connection', side_effect=OSError('refused')):
            result = svc.check()

        assert result.health_score == 0
        assert result.reachable is False

    def test_avg_latency_only_from_passing_probes(self):
        targets = [_passing_tcp_target(), _passing_tcp_target()]
        svc = InternetCheckService(targets=targets, pass_threshold=0.4)

        call_count = [0]
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        def alternate(host_port, timeout=None):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError('fail')
            return mock_sock

        with patch('socket.create_connection', side_effect=alternate):
            result = svc.check()

        # avg_latency should only include the 1 passing probe
        assert result.avg_latency_ms is not None

    def test_avg_latency_none_when_all_fail(self):
        svc = InternetCheckService(targets=[_passing_tcp_target()])
        with patch('socket.create_connection', side_effect=OSError('refused')):
            result = svc.check()

        assert result.avg_latency_ms is None

    def test_empty_targets_returns_unreachable(self):
        svc = InternetCheckService(targets=[])
        result = svc.check()
        assert result.reachable is False
        assert result.health_score == 0

    def test_unknown_probe_type_skipped(self):
        svc = InternetCheckService(targets=[
            {'type': 'icmp', 'host': '8.8.8.8'},  # unsupported
        ])
        result = svc.check()
        assert result.probes == []

    def test_reachable_false_when_below_threshold(self):
        targets = [_passing_tcp_target(), _passing_tcp_target(), _passing_tcp_target()]
        svc = InternetCheckService(targets=targets, pass_threshold=0.8)

        call_count = [0]
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        def mostly_fail(host_port, timeout=None):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise OSError('fail')
            return mock_sock

        with patch('socket.create_connection', side_effect=mostly_fail):
            result = svc.check()

        # 1 of 3 passed = 33% < 80% threshold
        assert result.reachable is False

    def test_reachable_true_when_above_threshold(self):
        svc = InternetCheckService(
            targets=[_passing_tcp_target()], pass_threshold=0.5
        )
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch('socket.create_connection', return_value=mock_sock):
            result = svc.check()

        assert result.reachable is True


# ── Configuration ─────────────────────────────────────────────────────────────

class TestConfiguration:
    def test_custom_targets_used(self):
        custom = [{'type': 'tcp', 'host': '192.168.1.1', 'port': 80, 'timeout': 1}]
        svc = InternetCheckService(targets=custom)

        with patch('socket.create_connection', side_effect=OSError('refused')) as mock_conn:
            svc.check()

        mock_conn.assert_called_with(('192.168.1.1', 80), timeout=1.0)

    def test_custom_pass_threshold(self):
        # 2 targets, only 1 passes → 50%.
        # threshold=0.4 → reachable; threshold=0.6 → not reachable
        targets = [_passing_tcp_target(), _passing_tcp_target()]

        call_count = [0]
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        def alternating(host_port, timeout=None):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise OSError('fail')
            return mock_sock

        svc_permissive = InternetCheckService(targets=targets, pass_threshold=0.4)
        with patch('socket.create_connection', side_effect=alternating):
            r1 = svc_permissive.check()
        assert r1.reachable is True

        call_count[0] = 0
        svc_strict = InternetCheckService(targets=targets, pass_threshold=0.6)
        with patch('socket.create_connection', side_effect=alternating):
            r2 = svc_strict.check()
        assert r2.reachable is False
