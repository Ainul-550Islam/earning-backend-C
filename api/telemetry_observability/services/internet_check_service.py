"""
InternetCheckService — single responsibility: check internet connectivity.

SRP contract
────────────
  This service does exactly ONE thing: probe whether outbound internet access
  is working and report the result as a plain data object.

  It NEVER:
    - writes to the database             (that's the Celery task's job)
    - fires alerts                       (that's AlertService's job)
    - changes HealthStatus records       (that's the task's job)
    - logs to the structured log store   (caller decides what to log)

Usage
─────
    from telemetry_observability.services.internet_check_service import (
        InternetCheckService, InternetCheckResult,
    )

    svc    = InternetCheckService()
    result = svc.check()

    if not result.reachable:
        # handle degraded connectivity
        print(result.summary())

Configuration (settings.py)
────────────────────────────
    INTERNET_CHECK_TARGETS = [
        {'type': 'tcp',  'host': '8.8.8.8',                                    'port': 53,  'timeout': 3},
        {'type': 'tcp',  'host': '1.1.1.1',                                    'port': 53,  'timeout': 3},
        {'type': 'dns',  'host': 'dns.google',                                 'port': 53,  'timeout': 3},
        {'type': 'http', 'url': 'https://connectivitycheck.gstatic.com/generate_204', 'timeout': 5},
        {'type': 'http', 'url': 'https://cloudflare.com/cdn-cgi/trace',               'timeout': 5},
    ]
    INTERNET_CHECK_TIMEOUT         = 5    # per-probe default timeout (seconds)
    INTERNET_CHECK_PASS_THRESHOLD  = 0.5  # fraction of probes that must pass (0.0–1.0)
"""
from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    """Result of a single connectivity probe."""
    probe_type:   str            # 'tcp' | 'dns' | 'http'
    target:       str            # host, URL, or "host:port"
    reachable:    bool
    latency_ms:   Optional[float] = None
    error:        Optional[str]   = None
    http_status:  Optional[int]   = None   # HTTP probes only


@dataclass
class InternetCheckResult:
    """
    Aggregated result from all probes run by InternetCheckService.check().

    Fields
    ──────
    reachable   — True when enough probes passed (≥ INTERNET_CHECK_PASS_THRESHOLD).
    health_score — 0–100 integer suitable for HealthStatus.health_score.
    probes      — Individual ProbeResult objects for every target checked.
    avg_latency_ms — Mean latency across successful probes (None if all failed).
    error_count — Number of probes that failed.
    checked_at  — Unix timestamp (float) when the check ran.
    """
    reachable:       bool
    health_score:    int
    probes:          List[ProbeResult]
    avg_latency_ms:  Optional[float]
    error_count:     int
    checked_at:      float = field(default_factory=time.time)

    def summary(self) -> str:
        """One-line human-readable summary, safe to log."""
        passed  = len(self.probes) - self.error_count
        total   = len(self.probes)
        latency = f'{self.avg_latency_ms:.1f} ms' if self.avg_latency_ms is not None else 'n/a'
        status  = 'REACHABLE' if self.reachable else 'UNREACHABLE'
        return (
            f'Internet {status} | probes: {passed}/{total} passed | '
            f'avg latency: {latency} | score: {self.health_score}'
        )

    def as_metadata(self) -> Dict:
        """Serialisable dict for HealthStatus.metadata storage."""
        return {
            'health_score':   self.health_score,
            'avg_latency_ms': round(self.avg_latency_ms, 2) if self.avg_latency_ms else None,
            'probes_passed':  len(self.probes) - self.error_count,
            'probes_total':   len(self.probes),
            'probes': [
                {
                    'type':        p.probe_type,
                    'target':      p.target,
                    'reachable':   p.reachable,
                    'latency_ms':  round(p.latency_ms, 2) if p.latency_ms else None,
                    'http_status': p.http_status,
                    'error':       p.error,
                }
                for p in self.probes
            ],
        }


# ── Default targets ───────────────────────────────────────────────────────────

_DEFAULT_TARGETS: List[Dict] = [
    # TCP — Cloudflare DNS (port 53 is open without DNS query overhead)
    {'type': 'tcp', 'host': '1.1.1.1', 'port': 53, 'timeout': 3},
    # TCP — Google DNS
    {'type': 'tcp', 'host': '8.8.8.8', 'port': 53, 'timeout': 3},
    # DNS — resolve a well-known hostname (tests DNS resolution separately)
    {'type': 'dns', 'host': 'dns.google', 'port': 53, 'timeout': 3},
    # HTTP — Google's connectivity check endpoint (returns HTTP 204, tiny payload)
    {'type': 'http', 'url': 'https://connectivitycheck.gstatic.com/generate_204', 'timeout': 5},
    # HTTP — Cloudflare trace endpoint (returns HTTP 200, tiny text payload)
    {'type': 'http', 'url': 'https://cloudflare.com/cdn-cgi/trace', 'timeout': 5},
]


# ── Service ───────────────────────────────────────────────────────────────────

class InternetCheckService:
    """
    Probe outbound internet connectivity.

    Single responsibility: run the configured probes, aggregate the results,
    return an InternetCheckResult.  Nothing else.

    All probe types are isolated in private methods so they can be tested
    independently and swapped without touching the aggregation logic.
    """

    def __init__(
        self,
        targets: Optional[List[Dict]]  = None,
        pass_threshold: Optional[float] = None,
    ) -> None:
        """
        Args:
            targets:        List of probe target dicts.  Defaults to
                            settings.INTERNET_CHECK_TARGETS or the built-in
                            defaults if the setting is absent.
            pass_threshold: Fraction of probes that must pass for
                            ``reachable`` to be True.  Defaults to
                            settings.INTERNET_CHECK_PASS_THRESHOLD (0.5).
        """
        self._targets: List[Dict] = (
            targets
            if targets is not None
            else getattr(settings, 'INTERNET_CHECK_TARGETS', _DEFAULT_TARGETS)
        )
        self._pass_threshold: float = (
            pass_threshold
            if pass_threshold is not None
            else float(getattr(settings, 'INTERNET_CHECK_PASS_THRESHOLD', 0.5))
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self) -> InternetCheckResult:
        """
        Run all configured probes and return an aggregated result.

        Returns:
            InternetCheckResult — never raises; probe failures are captured
            as ProbeResult.error strings.
        """
        probes: List[ProbeResult] = []

        for target in self._targets:
            probe_type = target.get('type', 'tcp')
            if probe_type == 'tcp':
                probes.append(self._probe_tcp(target))
            elif probe_type == 'dns':
                probes.append(self._probe_dns(target))
            elif probe_type == 'http':
                probes.append(self._probe_http(target))
            else:
                logger.warning(
                    'InternetCheckService: unknown probe type %r — skipped.', probe_type
                )

        return self._aggregate(probes)

    # ── Private probes ────────────────────────────────────────────────────────

    def _probe_tcp(self, target: Dict) -> ProbeResult:
        """
        Open a raw TCP socket to host:port.

        Fastest possible connectivity probe — no DNS overhead (IPs preferred),
        no HTTP handshake, no TLS.  A successful connect proves the route is up.
        """
        host    = target['host']
        port    = int(target.get('port', 53))
        timeout = float(target.get(
            'timeout',
            getattr(settings, 'INTERNET_CHECK_TIMEOUT', 5),
        ))
        label   = f'{host}:{port}'

        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                pass
            latency = (time.perf_counter() - t0) * 1000
            return ProbeResult(
                probe_type='tcp', target=label, reachable=True, latency_ms=latency
            )
        except OSError as exc:
            latency = (time.perf_counter() - t0) * 1000
            logger.debug('TCP probe %s failed: %s', label, exc)
            return ProbeResult(
                probe_type='tcp', target=label, reachable=False,
                latency_ms=latency, error=str(exc),
            )

    def _probe_dns(self, target: Dict) -> ProbeResult:
        """
        Attempt to resolve a hostname via the system resolver.

        Tests that DNS is reachable independently of raw IP connectivity.
        A TCP probe to an IP can succeed even when DNS is broken; this catches
        DNS-specific failures (bad /etc/resolv.conf, DNS server down, etc.).
        """
        host    = target['host']
        port    = int(target.get('port', 53))
        timeout = float(target.get(
            'timeout',
            getattr(settings, 'INTERNET_CHECK_TIMEOUT', 5),
        ))
        label   = f'dns://{host}'

        t0 = time.perf_counter()
        try:
            # socket.getaddrinfo does not support a timeout natively; wrap in
            # a non-blocking approach using settimeout on a throwaway socket.
            socket.setdefaulttimeout(timeout)
            results = socket.getaddrinfo(host, port)
            socket.setdefaulttimeout(None)

            latency = (time.perf_counter() - t0) * 1000
            resolved_ips = [r[4][0] for r in results]
            return ProbeResult(
                probe_type='dns', target=label, reachable=bool(results),
                latency_ms=latency,
                error=None if results else 'empty getaddrinfo result',
            )
        except OSError as exc:
            socket.setdefaulttimeout(None)
            latency = (time.perf_counter() - t0) * 1000
            logger.debug('DNS probe %s failed: %s', label, exc)
            return ProbeResult(
                probe_type='dns', target=label, reachable=False,
                latency_ms=latency, error=str(exc),
            )

    def _probe_http(self, target: Dict) -> ProbeResult:
        """
        Send an HTTP HEAD (or GET) request and verify a successful response.

        Tests end-to-end connectivity including TLS and application-layer
        routing.  Connectivity check URLs (generate_204, /cdn-cgi/trace) are
        preferred because they return minimal payloads quickly.
        """
        url     = target['url']
        timeout = float(target.get(
            'timeout',
            getattr(settings, 'INTERNET_CHECK_TIMEOUT', 5),
        ))

        t0 = time.perf_counter()
        try:
            req = Request(
                url,
                method='HEAD',
                headers={'User-Agent': 'TelemetryObservability/InternetCheck 1.0'},
            )
            with urlopen(req, timeout=timeout) as resp:
                http_status = resp.status
            latency = (time.perf_counter() - t0) * 1000
            reachable = 200 <= http_status < 400
            return ProbeResult(
                probe_type='http', target=url, reachable=reachable,
                latency_ms=latency, http_status=http_status,
                error=None if reachable else f'HTTP {http_status}',
            )
        except URLError as exc:
            latency = (time.perf_counter() - t0) * 1000
            logger.debug('HTTP probe %s failed: %s', url, exc)
            return ProbeResult(
                probe_type='http', target=url, reachable=False,
                latency_ms=latency, error=str(exc.reason),
            )
        except Exception as exc:  # timeout, SSL error, etc.
            latency = (time.perf_counter() - t0) * 1000
            logger.debug('HTTP probe %s error: %s', url, exc)
            return ProbeResult(
                probe_type='http', target=url, reachable=False,
                latency_ms=latency, error=str(exc),
            )

    # ── Aggregation ───────────────────────────────────────────────────────────

    def _aggregate(self, probes: List[ProbeResult]) -> InternetCheckResult:
        """
        Collapse individual probe results into a single InternetCheckResult.

        Score formula
        ─────────────
          100  — all probes passed
           80  — ≥ 80 % passed
           60  — ≥ 60 % passed (degraded, threshold met)
           40  — ≥ 40 % passed (below threshold — unreachable)
            0  — no probes passed at all
        """
        if not probes:
            return InternetCheckResult(
                reachable=False, health_score=0, probes=[],
                avg_latency_ms=None, error_count=0,
            )

        passed      = [p for p in probes if p.reachable]
        failed      = [p for p in probes if not p.reachable]
        pass_ratio  = len(passed) / len(probes)
        reachable   = pass_ratio >= self._pass_threshold

        # Health score: proportional to pass ratio, rounded to nearest 10
        raw_score   = pass_ratio * 100
        health_score = max(0, min(100, round(raw_score / 10) * 10))

        # Average latency only over successful probes
        latencies = [p.latency_ms for p in passed if p.latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        return InternetCheckResult(
            reachable=reachable,
            health_score=health_score,
            probes=probes,
            avg_latency_ms=avg_latency,
            error_count=len(failed),
        )
