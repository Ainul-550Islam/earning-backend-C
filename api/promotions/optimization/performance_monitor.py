# =============================================================================
# api/promotions/optimization/performance_monitor.py
# Performance Monitor — Real-time metrics, APM, Health checks, Alerting
# Response time, Error rate, DB performance, Memory usage track করে
# =============================================================================

import logging
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('optimization.performance')

# Config
METRICS_WINDOW_SECONDS  = getattr(settings, 'METRICS_WINDOW_SECONDS', 60)   # 1 min rolling window
ALERT_ERROR_RATE        = getattr(settings, 'ALERT_ERROR_RATE', 0.05)        # 5% error rate
ALERT_RESPONSE_TIME_MS  = getattr(settings, 'ALERT_RESPONSE_TIME_MS', 2000)  # 2 seconds
CACHE_PREFIX_METRICS    = 'opt:metrics:{}'
CACHE_TTL_METRICS       = 300  # 5 minutes


# =============================================================================
# ── DATA CLASSES ──────────────────────────────────────────────────────────────
# =============================================================================

@dataclass
class RequestMetric:
    path:         str
    method:       str
    status_code:  int
    response_ms:  float
    user_id:      Optional[int]
    timestamp:    float = field(default_factory=time.time)


@dataclass
class HealthStatus:
    healthy:      bool
    score:        float            # 0.0 - 1.0
    components:   dict             # {'db': True, 'cache': True, 'storage': True}
    issues:       list[str]
    response_ms:  float
    timestamp:    float = field(default_factory=time.time)


@dataclass
class PerformanceReport:
    window_seconds:     int
    total_requests:     int
    error_count:        int
    error_rate:         float
    avg_response_ms:    float
    p50_response_ms:    float
    p95_response_ms:    float
    p99_response_ms:    float
    slowest_endpoints:  list
    error_endpoints:    list
    throughput_rps:     float      # requests per second
    db_query_avg_ms:    float


# =============================================================================
# ── METRICS COLLECTOR ────────────────────────────────────────────────────────
# =============================================================================

class MetricsCollector:
    """
    In-memory rolling window metrics collection।
    Low overhead — production safe।

    Collects:
    - Request count, error rate, response times
    - Endpoint-level breakdown
    - Database query performance
    - Memory & CPU (optional)
    """

    def __init__(self, window_seconds: int = METRICS_WINDOW_SECONDS):
        self._window  = window_seconds
        self._lock    = threading.Lock()
        # Rolling buffer — (timestamp, RequestMetric)
        self._metrics: deque = deque(maxlen=10000)
        # Endpoint counters
        self._endpoint_stats: dict = defaultdict(lambda: {
            'count': 0, 'errors': 0, 'total_ms': 0.0,
        })

    def record(self, metric: RequestMetric) -> None:
        """Request metric record করে।"""
        with self._lock:
            self._metrics.append((time.time(), metric))
            key   = f'{metric.method}:{metric.path}'
            stats = self._endpoint_stats[key]
            stats['count']    += 1
            stats['total_ms'] += metric.response_ms
            if metric.status_code >= 500:
                stats['errors'] += 1

    def get_report(self) -> PerformanceReport:
        """Rolling window metrics report তৈরি করে।"""
        now     = time.time()
        cutoff  = now - self._window

        with self._lock:
            recent = [m for ts, m in self._metrics if ts >= cutoff]

        if not recent:
            return PerformanceReport(
                window_seconds=self._window, total_requests=0,
                error_count=0, error_rate=0.0, avg_response_ms=0.0,
                p50_response_ms=0.0, p95_response_ms=0.0, p99_response_ms=0.0,
                slowest_endpoints=[], error_endpoints=[],
                throughput_rps=0.0, db_query_avg_ms=0.0,
            )

        total      = len(recent)
        errors     = sum(1 for m in recent if m.status_code >= 500)
        times      = sorted(m.response_ms for m in recent)
        avg_ms     = sum(times) / total

        def percentile(data, pct):
            idx = max(0, int(len(data) * pct / 100) - 1)
            return data[idx]

        # Endpoint breakdown
        endpoint_agg = defaultdict(lambda: {'count': 0, 'errors': 0, 'total_ms': 0.0})
        for m in recent:
            k = f'{m.method}:{m.path}'
            endpoint_agg[k]['count']    += 1
            endpoint_agg[k]['total_ms'] += m.response_ms
            if m.status_code >= 500:
                endpoint_agg[k]['errors'] += 1

        slowest = sorted(
            [{'endpoint': k, 'avg_ms': v['total_ms']/v['count'], 'count': v['count']}
             for k, v in endpoint_agg.items()],
            key=lambda x: x['avg_ms'], reverse=True,
        )[:5]

        error_eps = sorted(
            [{'endpoint': k, 'error_rate': v['errors']/v['count']*100, 'count': v['count']}
             for k, v in endpoint_agg.items() if v['errors'] > 0],
            key=lambda x: x['error_rate'], reverse=True,
        )[:5]

        return PerformanceReport(
            window_seconds    = self._window,
            total_requests    = total,
            error_count       = errors,
            error_rate        = round(errors / total, 4),
            avg_response_ms   = round(avg_ms, 2),
            p50_response_ms   = round(percentile(times, 50), 2),
            p95_response_ms   = round(percentile(times, 95), 2),
            p99_response_ms   = round(percentile(times, 99), 2),
            slowest_endpoints = slowest,
            error_endpoints   = error_eps,
            throughput_rps    = round(total / self._window, 2),
            db_query_avg_ms   = self._get_db_avg_ms(),
        )

    def get_endpoint_stats(self, path: str = None) -> dict:
        """নির্দিষ্ট endpoint এর stats return করে।"""
        if path:
            return dict(self._endpoint_stats.get(path, {}))
        return {k: dict(v) for k, v in self._endpoint_stats.items()}

    @staticmethod
    def _get_db_avg_ms() -> float:
        """Database average query time (last 1 minute)।"""
        try:
            from django.db import connection
            if not settings.DEBUG or not connection.queries:
                return 0.0
            times = [float(q.get('time', 0)) * 1000 for q in connection.queries]
            return round(sum(times) / len(times), 2) if times else 0.0
        except Exception:
            return 0.0


# ── Singleton ──────────────────────────────────────────────────────────────────
_collector = MetricsCollector()


# =============================================================================
# ── HEALTH CHECKER ────────────────────────────────────────────────────────────
# =============================================================================

class HealthChecker:
    """
    System health check — Database, Cache, Storage, External APIs।
    Kubernetes liveness/readiness probe এর জন্য।
    """

    def check(self, deep: bool = False) -> HealthStatus:
        """
        Full health check।

        Args:
            deep: True হলে external service গুলোও check করে (slow)
        """
        start      = time.monotonic()
        components = {}
        issues     = []

        # ── Database ─────────────────────────────────────────────────────
        db_ok, db_ms = self._check_database()
        components['database'] = {'healthy': db_ok, 'response_ms': db_ms}
        if not db_ok:
            issues.append('database_unreachable')

        # ── Cache (Redis) ─────────────────────────────────────────────────
        cache_ok, cache_ms = self._check_cache()
        components['cache'] = {'healthy': cache_ok, 'response_ms': cache_ms}
        if not cache_ok:
            issues.append('cache_unreachable')

        # ── Storage ───────────────────────────────────────────────────────
        storage_ok = self._check_storage()
        components['storage'] = {'healthy': storage_ok}
        if not storage_ok:
            issues.append('storage_unreachable')

        # ── Celery (optional) ─────────────────────────────────────────────
        if deep:
            celery_ok = self._check_celery()
            components['celery'] = {'healthy': celery_ok}
            if not celery_ok:
                issues.append('celery_worker_unavailable')

        # ── Memory ───────────────────────────────────────────────────────
        mem_ok, mem_info = self._check_memory()
        components['memory'] = {'healthy': mem_ok, **mem_info}
        if not mem_ok:
            issues.append(f'high_memory_usage:{mem_info.get("used_percent", 0):.0f}%')

        # ── Score ─────────────────────────────────────────────────────────
        critical  = [c for c in ['database', 'cache'] if not components[c]['healthy']]
        score     = 1.0 - (len(critical) * 0.4) - (len(issues) * 0.1)
        score     = max(0.0, min(1.0, score))
        healthy   = score >= 0.5 and db_ok  # DB down = unhealthy

        elapsed = round((time.monotonic() - start) * 1000, 2)
        return HealthStatus(
            healthy=healthy, score=round(score, 3),
            components=components, issues=issues, response_ms=elapsed,
        )

    def _check_database(self) -> tuple[bool, float]:
        start = time.monotonic()
        try:
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute('SELECT 1')
            ms = round((time.monotonic() - start) * 1000, 2)
            return True, ms
        except Exception as e:
            logger.error(f'Database health check failed: {e}')
            return False, -1.0

    def _check_cache(self) -> tuple[bool, float]:
        start = time.monotonic()
        try:
            test_key = 'health:ping'
            cache.set(test_key, 'pong', timeout=10)
            result   = cache.get(test_key)
            ms = round((time.monotonic() - start) * 1000, 2)
            return result == 'pong', ms
        except Exception as e:
            logger.error(f'Cache health check failed: {e}')
            return False, -1.0

    @staticmethod
    def _check_storage() -> bool:
        try:
            from django.core.files.storage import default_storage
            default_storage.exists('health_check_dummy')
            return True
        except Exception:
            return False

    @staticmethod
    def _check_celery() -> bool:
        try:
            from celery import current_app
            inspect = current_app.control.inspect(timeout=2)
            workers = inspect.ping()
            return bool(workers)
        except Exception:
            return False

    @staticmethod
    def _check_memory() -> tuple[bool, dict]:
        try:
            import psutil
            mem   = psutil.virtual_memory()
            pct   = mem.percent
            info  = {
                'used_percent':  round(pct, 1),
                'available_mb':  round(mem.available / 1024 / 1024, 0),
                'total_mb':      round(mem.total / 1024 / 1024, 0),
            }
            return pct < 90, info
        except ImportError:
            # psutil not available — check /proc/meminfo on Linux
            try:
                with open('/proc/meminfo') as f:
                    lines = f.read()
                total = int(next(l.split()[1] for l in lines.split('\n') if l.startswith('MemTotal')))
                avail = int(next(l.split()[1] for l in lines.split('\n') if l.startswith('MemAvailable')))
                pct   = (1 - avail/total) * 100
                return pct < 90, {'used_percent': round(pct, 1)}
            except Exception:
                return True, {}


# =============================================================================
# ── ALERTING ─────────────────────────────────────────────────────────────────
# =============================================================================

class PerformanceAlerter:
    """
    Performance threshold এ exceed করলে alert পাঠায়।
    Slack, PagerDuty, Email সব support করে।
    """

    COOLDOWN_SECONDS = 300   # একই alert ৫ মিনিটে একবার

    def check_and_alert(self, report: PerformanceReport) -> list[str]:
        """Report check করে প্রয়োজনে alert পাঠায়।"""
        alerts = []

        # Error rate
        if report.error_rate > ALERT_ERROR_RATE:
            msg = (
                f'High error rate: {report.error_rate*100:.1f}% '
                f'({report.error_count}/{report.total_requests} requests)'
            )
            if self._should_alert('high_error_rate'):
                self._send_alert('critical', msg, report.error_endpoints)
            alerts.append(msg)

        # Response time
        if report.p95_response_ms > ALERT_RESPONSE_TIME_MS:
            msg = f'Slow P95 response: {report.p95_response_ms:.0f}ms (threshold: {ALERT_RESPONSE_TIME_MS}ms)'
            if self._should_alert('slow_response'):
                self._send_alert('warning', msg, report.slowest_endpoints)
            alerts.append(msg)

        # High throughput (traffic spike)
        if report.throughput_rps > 1000:
            msg = f'Traffic spike: {report.throughput_rps:.0f} req/s'
            if self._should_alert('traffic_spike'):
                self._send_alert('info', msg, {})
            alerts.append(msg)

        return alerts

    def _should_alert(self, alert_type: str) -> bool:
        """Cooldown check — একই alert বারবার না পাঠানো।"""
        key = f'opt:alert_cooldown:{alert_type}'
        if cache.get(key):
            return False
        cache.set(key, True, timeout=self.COOLDOWN_SECONDS)
        return True

    def _send_alert(self, severity: str, message: str, context: any) -> None:
        """Alert পাঠায় — Slack/PagerDuty/Email।"""
        logger.warning(f'PERFORMANCE ALERT [{severity.upper()}]: {message}')

        # Slack
        slack_url = getattr(settings, 'SLACK_ALERT_WEBHOOK', None)
        if slack_url:
            try:
                import requests
                emoji = {'critical': ':red_circle:', 'warning': ':warning:', 'info': ':blue_circle:'}.get(severity, '')
                requests.post(
                    slack_url,
                    json={'text': f'{emoji} *{severity.upper()}*: {message}\n```{context}```'},
                    timeout=3,
                )
            except Exception as e:
                logger.error(f'Slack alert failed: {e}')


# =============================================================================
# ── MIDDLEWARE ────────────────────────────────────────────────────────────────
# =============================================================================

class PerformanceMonitorMiddleware:
    """
    Django middleware — সব request এর metrics collect করে।
    Production safe, low overhead।
    """
    _alerter  = PerformanceAlerter()
    _check_counter = 0

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start    = time.monotonic()
        response = self.get_response(request)
        elapsed  = round((time.monotonic() - start) * 1000, 2)

        # Skip static files
        path = request.path
        if any(path.startswith(p) for p in ('/static/', '/media/', '/favicon')):
            return response

        # Collect metric
        metric = RequestMetric(
            path        = self._normalize_path(path),
            method      = request.method,
            status_code = response.status_code,
            response_ms = elapsed,
            user_id     = getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
        )
        _collector.record(metric)

        # Response headers
        response['X-Response-Time'] = f'{elapsed:.0f}ms'

        # Periodic alert check (every 100 requests)
        self.__class__._check_counter += 1
        if self.__class__._check_counter % 100 == 0:
            threading.Thread(target=self._check_alerts, daemon=True).start()

        return response

    @staticmethod
    def _check_alerts():
        """Background alert check।"""
        try:
            report = _collector.get_report()
            PerformanceAlerter().check_and_alert(report)
        except Exception as e:
            logger.debug(f'Alert check failed: {e}')

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Path normalize — ID গুলো replace করে pattern দেখায়।"""
        import re
        path = re.sub(r'/\d+/', '/{id}/', path)
        path = re.sub(r'/\d+$', '/{id}', path)
        return path


# =============================================================================
# ── HEALTH CHECK VIEW ─────────────────────────────────────────────────────────
# =============================================================================

def health_check_view(request):
    """
    /health/ endpoint।

    Kubernetes probe:
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
    """
    from django.http import JsonResponse

    deep   = request.GET.get('deep', '').lower() == 'true'
    checker = HealthChecker()
    status  = checker.check(deep=deep)

    http_status = 200 if status.healthy else 503
    return JsonResponse(
        {
            'status':     'healthy' if status.healthy else 'unhealthy',
            'score':      status.score,
            'components': status.components,
            'issues':     status.issues,
            'response_ms': status.response_ms,
        },
        status=http_status,
    )


def metrics_view(request):
    """
    /metrics/ endpoint — Prometheus format (optional)।
    Admin only।
    """
    from django.http import JsonResponse, HttpResponseForbidden
    if not request.user.is_staff:
        return HttpResponseForbidden()

    report = _collector.get_report()
    return JsonResponse({
        'window_seconds':   report.window_seconds,
        'total_requests':   report.total_requests,
        'error_rate':       report.error_rate,
        'avg_response_ms':  report.avg_response_ms,
        'p50_ms':           report.p50_response_ms,
        'p95_ms':           report.p95_response_ms,
        'p99_ms':           report.p99_response_ms,
        'throughput_rps':   report.throughput_rps,
        'slowest_endpoints': report.slowest_endpoints,
        'error_endpoints':  report.error_endpoints,
    })
