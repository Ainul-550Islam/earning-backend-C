"""
Proxy Intelligence Celery Tasks
================================
Asynchronous tasks for background processing.
Register in celery_schedule.py or add to CELERY_BEAT_SCHEDULE.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='proxy_intelligence.sync_tor_exit_nodes', bind=True, max_retries=3)
def sync_tor_exit_nodes(self):
    """Sync Tor exit node list from the Tor Project (runs every 6 hours)."""
    try:
        from .detection_engines.tor_detector import TorDetector
        count = TorDetector.sync_exit_nodes()
        logger.info(f"[Task] Tor exit nodes synced: {count} nodes.")
        return {'status': 'success', 'count': count}
    except Exception as exc:
        logger.error(f"[Task] Tor sync failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='proxy_intelligence.send_daily_summary')
def send_daily_risk_summary():
    """Send daily risk summary email to admins."""
    try:
        from .analytics_reporting.daily_risk_summary import DailyRiskSummary
        from django.conf import settings
        recipients = getattr(settings, 'PROXY_INTELLIGENCE_ADMIN_EMAILS', [])
        if not recipients:
            logger.warning("[Task] No admin emails configured for daily summary.")
            return {'status': 'skipped', 'reason': 'no_recipients'}
        DailyRiskSummary().send_email(recipients)
        return {'status': 'sent', 'recipients': len(recipients)}
    except Exception as e:
        logger.error(f"[Task] Daily summary failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='proxy_intelligence.cleanup_old_logs')
def cleanup_old_logs():
    """Remove API request logs older than retention period."""
    try:
        from .models import APIRequestLog, PerformanceMetric
        from .constants import API_LOG_RETENTION_DAYS, PERFORMANCE_METRIC_RETENTION_DAYS
        from datetime import timedelta

        cutoff_api = timezone.now() - timedelta(days=API_LOG_RETENTION_DAYS)
        cutoff_perf = timezone.now() - timedelta(days=PERFORMANCE_METRIC_RETENTION_DAYS)

        deleted_api, _ = APIRequestLog.objects.filter(created_at__lt=cutoff_api).delete()
        deleted_perf, _ = PerformanceMetric.objects.filter(recorded_at__lt=cutoff_perf).delete()

        logger.info(f"[Task] Cleanup: {deleted_api} API logs, {deleted_perf} metrics deleted.")
        return {'api_logs_deleted': deleted_api, 'metrics_deleted': deleted_perf}
    except Exception as e:
        logger.error(f"[Task] Cleanup failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='proxy_intelligence.sync_threat_feeds')
def sync_threat_feeds():
    """Sync all active threat feeds."""
    try:
        from .threat_intelligence.threat_feed_integrator import ThreatFeedIntegrator
        results = ThreatFeedIntegrator().sync_all_feeds()
        logger.info(f"[Task] Threat feeds synced: {results}")
        return {'status': 'success', 'results': results}
    except Exception as e:
        logger.error(f"[Task] Threat feed sync failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='proxy_intelligence.expire_blacklist_entries')
def expire_blacklist_entries():
    """Deactivate expired blacklist entries."""
    try:
        from .models import IPBlacklist
        from .cache import PICache

        now = timezone.now()
        expired = IPBlacklist.objects.filter(
            is_active=True,
            is_permanent=False,
            expires_at__lt=now
        )
        count = expired.count()
        ips = list(expired.values_list('ip_address', flat=True))
        expired.update(is_active=False)

        # Invalidate cache for expired IPs
        for ip in ips:
            PICache.invalidate_blacklist(ip)

        logger.info(f"[Task] Expired {count} blacklist entries.")
        return {'expired': count}
    except Exception as e:
        logger.error(f"[Task] Blacklist expiry failed: {e}")
        return {'status': 'error', 'error': str(e)}
