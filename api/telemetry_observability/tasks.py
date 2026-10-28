"""
Celery async tasks for Telemetry Observability.

Tasks are discovered automatically via celery.autodiscover_tasks().
All tasks are idempotent — safe to retry on failure.

DRY: task logic calls the service/logic layer — never accesses models directly.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Data Retention ────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    name='api.telemetry_observability.tasks.cleanup_old_telemetry',
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def cleanup_old_telemetry(self):
    """
    Delete telemetry records older than TELEMETRY_RETENTION_DAYS.
    Runs daily via Celery Beat.
    """
    try:
        retention_days = getattr(settings, 'TELEMETRY_RETENTION_DAYS', 90)
        cutoff         = timezone.now() - timedelta(days=retention_days)

        from .models.metric_event import MetricEvent
        from .models.log_entry    import LogEntry
        from .models.trace_span   import TraceSpan
        from .models.alert        import Alert

        deleted = {
            'metrics': MetricEvent.objects.filter(timestamp__lt=cutoff).delete()[0],
            'logs':    LogEntry.objects.filter(timestamp__lt=cutoff).delete()[0],
            'traces':  TraceSpan.objects.filter(start_time__lt=cutoff).delete()[0],
            'alerts':  Alert.objects.filter(
                           triggered_at__lt=cutoff, status='resolved'
                       ).delete()[0],
        }
        logger.info('Telemetry cleanup: deleted %s', deleted)
        return deleted

    except Exception as exc:
        logger.exception('cleanup_old_telemetry failed: %s', exc)
        raise self.retry(exc=exc)


# ── Health Checks ─────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    name='api.telemetry_observability.tasks.run_health_checks',
    max_retries=2,
    default_retry_delay=30,
)
def run_health_checks(self):
    """
    Ping all registered services and update HealthStatus.
    Runs every 5 minutes via Celery Beat.
    """
    try:
        from .models.health_status import HealthStatus
        from .logic import HealthLogic

        logic    = HealthLogic()
        services = list(
            HealthStatus.objects.values_list('service_name', flat=True).distinct()
        )

        results = {}
        for service_name in services:
            try:
                obj, _ = logic.upsert({
                    'service_name': service_name,
                    'status':       'healthy',
                    'health_score': 100,
                })
                results[service_name] = obj.status
            except Exception as svc_exc:
                logger.warning('Health check failed for %s: %s', service_name, svc_exc)
                results[service_name] = 'error'

        logger.info('Health checks completed for %d services', len(services))
        return results

    except Exception as exc:
        logger.exception('run_health_checks failed: %s', exc)
        raise self.retry(exc=exc)


# ── Cache ─────────────────────────────────────────────────────────────────────

@shared_task(
    name='api.telemetry_observability.tasks.flush_metric_aggregation_cache',
)
def flush_metric_aggregation_cache():
    """
    Clear cached metric aggregations so fresh data is served.
    Runs every hour via Celery Beat.

    Uses delete_pattern() if the django_redis backend is configured
    (which it is by default — see settings/base.py).  Falls back to
    cache.clear() so the task never crashes on other backends (e.g. the
    in-memory backend used in development / tests).
    """
    try:
        from django.core.cache import cache

        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern('metrics:aggregation:*')
            logger.info('Metric aggregation cache flushed via delete_pattern.')
        else:
            # Fallback: clear the whole cache — safe for dev/test environments
            # that use LocMemCache (which has no pattern-delete support).
            cache.clear()
            logger.warning(
                'flush_metric_aggregation_cache: cache backend does not support '
                'delete_pattern — full cache.clear() used instead.'
            )
        return {'status': 'ok'}
    except Exception as exc:
        logger.warning('flush_metric_aggregation_cache failed: %s', exc)
        return {'status': 'error', 'error': str(exc)}


# ── Async Webhook Delivery ────────────────────────────────────────────────────

@shared_task(
    bind=True,
    name='api.telemetry_observability.tasks.deliver_webhook',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def deliver_webhook(self, url: str, payload: dict, secret: str = ''):
    """
    Deliver a single webhook payload to one URL asynchronously.
    Called by WebhookDispatcher when CELERY_TASK_ALWAYS_EAGER=False.
    """
    import json
    import hashlib
    import hmac
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError

    try:
        payload_bytes = json.dumps(payload).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'User-Agent':   'TelemetryObservability/1.0',
        }
        if secret:
            sig = hmac.new(
                secret.encode('utf-8'), payload_bytes, hashlib.sha256
            ).hexdigest()
            headers['X-Telemetry-Signature'] = f'sha256={sig}'

        req = Request(url, data=payload_bytes, headers=headers, method='POST')
        with urlopen(req, timeout=10) as resp:
            logger.info('Webhook delivered to %s (HTTP %s)', url, resp.status)
        return {'status': 'delivered', 'url': url}

    except (HTTPError, URLError, OSError) as exc:
        logger.warning('Webhook delivery failed to %s: %s', url, exc)
        raise self.retry(exc=exc)


# ── Alert Aggregation ─────────────────────────────────────────────────────────

@shared_task(
    name='api.telemetry_observability.tasks.aggregate_alerts',
)
def aggregate_alerts():
    """
    Auto-resolve alerts that have been open for more than 24 hours
    and whose condition is no longer active.
    Runs daily via Celery Beat.
    """
    try:
        from .models.alert import Alert

        cutoff      = timezone.now() - timedelta(hours=24)
        stale_count = 0

        for alert in Alert.objects.filter(status='open', triggered_at__lt=cutoff):
            alert.resolve()
            stale_count += 1

        logger.info('Auto-resolved %d stale alerts.', stale_count)
        return {'auto_resolved': stale_count}

    except Exception as exc:
        logger.exception('aggregate_alerts failed: %s', exc)
        return {'status': 'error', 'error': str(exc)}


# ── Internet Connectivity Check ───────────────────────────────────────────────

@shared_task(
    bind=True,
    name='api.telemetry_observability.tasks.check_internet_connectivity',
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
)
def check_internet_connectivity(self):
    """
    Probe outbound internet connectivity and persist the result.

    Single responsibility: orchestrate the check → store → alert pipeline.
    The actual probing is fully delegated to InternetCheckService (SRP).

    Steps
    ─────
    1. Run InternetCheckService.check()  — no DB, no side effects.
    2. Upsert a HealthStatus record       — one owner for persistence.
    3. Fire (or auto-resolve) an Alert    — one owner for alerting.
    4. Return a plain dict                — safe for Celery result backend.

    Runs every minute via Celery Beat (see celery.py beat_schedule).
    """
    try:
        from .services.internet_check_service import InternetCheckService
        from .models.health_status import HealthStatus
        from .models.alert import Alert
        from .models.metric_event import MetricEvent

        # ── 1. Check ──────────────────────────────────────────────────────────
        svc    = InternetCheckService()
        result = svc.check()
        logger.info('Internet check: %s', result.summary())

        # ── 2. Persist to HealthStatus ────────────────────────────────────────
        status_value = (
            'healthy'   if result.health_score >= 80
            else 'degraded' if result.health_score >= 40
            else 'unhealthy'
        )

        health, _ = HealthStatus.objects.update_or_create(
            service_name='internet',
            component_name='connectivity',
            defaults={
                'status':          status_value,
                'health_score':    result.health_score,
                'response_time_ms': result.avg_latency_ms,
                'error_rate':       (result.error_count / len(result.probes) * 100)
                                    if result.probes else 0.0,
                'metadata':        result.as_metadata(),
                'environment':     getattr(settings, 'INTERNET_CHECK_ENVIRONMENT', 'production'),
            },
        )

        # ── 3. Alert / auto-resolve ────────────────────────────────────────────
        if not result.reachable:
            # Open an alert only if one isn't already open — avoid duplicates.
            open_alert = Alert.objects.filter(
                name='internet-connectivity-failure',
                status='open',
            ).first()

            if not open_alert:
                Alert.objects.create(
                    name='internet-connectivity-failure',
                    alert_type='health',
                    severity='critical' if result.health_score == 0 else 'warning',
                    status='open',
                    message=(
                        f'Outbound internet is unreachable. '
                        f'{result.error_count}/{len(result.probes)} probes failed. '
                        f'Health score: {result.health_score}.'
                    ),
                    source='internet-check-task',
                    service='internet',
                    condition={'health_score': result.health_score},
                    metadata=result.as_metadata(),
                )
                logger.warning('Internet connectivity alert opened (score=%d).', result.health_score)
        else:
            # Internet restored — auto-resolve any open alert.
            for alert in Alert.objects.filter(
                name='internet-connectivity-failure', status='open'
            ):
                alert.resolve()
                logger.info('Internet connectivity alert auto-resolved (score=%d).', result.health_score)

        return {
            'reachable':     result.reachable,
            'health_score':  result.health_score,
            'avg_latency_ms': round(result.avg_latency_ms, 2) if result.avg_latency_ms else None,
            'probes_passed': len(result.probes) - result.error_count,
            'probes_total':  len(result.probes),
        }

        # ── 4. Emit gauge metrics (queryable in dashboards) ───────────────────
        _env = getattr(settings, 'INTERNET_CHECK_ENVIRONMENT', 'production')

        # Health score gauge — always emitted
        MetricEvent.objects.create(
            name='internet.connectivity.health_score',
            metric_type='gauge',
            value=float(result.health_score),
            unit='score',
            source='internet-check-task',
            service='internet',
            environment=_env,
            labels={
                'probes_total':  str(len(result.probes)),
                'probes_passed': str(len(result.probes) - result.error_count),
            },
        )

        # Latency gauge — only when at least one probe succeeded
        if result.avg_latency_ms is not None:
            MetricEvent.objects.create(
                name='internet.connectivity.latency_ms',
                metric_type='gauge',
                value=round(result.avg_latency_ms, 2),
                unit='ms',
                source='internet-check-task',
                service='internet',
                environment=_env,
            )

        return {
            'reachable':      result.reachable,
            'health_score':   result.health_score,
            'avg_latency_ms': round(result.avg_latency_ms, 2) if result.avg_latency_ms else None,
            'probes_passed':  len(result.probes) - result.error_count,
            'probes_total':   len(result.probes),
        }

    except Exception as exc:
        logger.exception('check_internet_connectivity failed: %s', exc)
        raise self.retry(exc=exc)
