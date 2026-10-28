# api/support/monitoring.py
"""
Support system monitoring and health checks.
Exposes metrics for Prometheus, Datadog, Railway metrics, etc.
"""
import logging
import time
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


class SupportMonitor:
    """Real-time support system health and metrics."""

    def get_health_status(self) -> dict:
        """
        Full health check — called by /api/support/health/ endpoint.
        Returns HTTP 200 if healthy, 503 if degraded.
        """
        checks = {}
        overall_healthy = True

        # Database
        try:
            from api.support.models import SupportTicket
            SupportTicket.objects.count()
            checks['database'] = {'healthy': True, 'message': 'OK'}
        except Exception as e:
            checks['database'] = {'healthy': False, 'message': str(e)[:100]}
            overall_healthy = False

        # Cache (Redis)
        try:
            from django.core.cache import cache
            cache.set('support:health:ping', 'pong', timeout=10)
            val = cache.get('support:health:ping')
            ok  = val == 'pong'
            checks['cache'] = {'healthy': ok, 'message': 'OK' if ok else 'Cache read failed'}
            if not ok:
                overall_healthy = False
        except Exception as e:
            checks['cache'] = {'healthy': False, 'message': str(e)[:100]}
            overall_healthy = False

        # Celery
        try:
            from celery import current_app
            inspect = current_app.control.inspect(timeout=2)
            ping    = inspect.ping()
            ok      = bool(ping)
            checks['celery'] = {'healthy': ok, 'message': 'Workers active' if ok else 'No workers'}
        except Exception:
            checks['celery'] = {'healthy': None, 'message': 'Not configured'}

        # Integration adapters
        try:
            from api.support.integrations.health_check import health_checker
            integ = health_checker.get_health_summary()
            checks['integrations'] = {
                'healthy': integ['status'] == 'healthy',
                'message': f"{len(integ['healthy'])} healthy, {len(integ['unhealthy'])} degraded",
                'detail':  integ,
            }
        except Exception as e:
            checks['integrations'] = {'healthy': None, 'message': str(e)[:100]}

        return {
            'status':    'healthy' if overall_healthy else 'degraded',
            'timestamp': timezone.now().isoformat(),
            'checks':    checks,
            'version':   self._get_version(),
        }

    def get_metrics(self, tenant=None) -> dict:
        """
        Get real-time support metrics.
        Suitable for dashboard widgets.
        """
        from api.support.cache import get_ticket_stats
        stats = get_ticket_stats(tenant=tenant)

        # Queue metrics
        try:
            from api.support.models import ChatSession
            queue_depth = ChatSession.objects.filter(status='waiting').count()
        except Exception:
            queue_depth = 0

        # Agent metrics
        try:
            from api.support.models import SupportAgent
            total_agents   = SupportAgent.objects.filter(is_active=True).count()
            online_agents  = SupportAgent.objects.filter(is_active=True, is_available=True).count()
        except Exception:
            total_agents = online_agents = 0

        # SLA metrics
        try:
            from api.support.models import TicketSLA
            from django.db.models import Q
            sla_breached = TicketSLA.objects.filter(
                Q(first_response_breached=True) | Q(resolution_breached=True)
            ).count()
        except Exception:
            sla_breached = 0

        return {
            'timestamp':     timezone.now().isoformat(),
            'tickets':       stats,
            'queue_depth':   queue_depth,
            'total_agents':  total_agents,
            'online_agents': online_agents,
            'sla_breached':  sla_breached,
        }

    def _get_version(self) -> str:
        try:
            from api.support.models import SupportSettings
            obj = SupportSettings.objects.filter(id=1).first()
            return obj.latest_version_name if obj else '1.0.0'
        except Exception:
            return '1.0.0'

    def track_response_time(self, start: float, endpoint: str) -> None:
        """Track API response time for monitoring."""
        elapsed_ms = round((time.time() - start) * 1000, 1)
        if elapsed_ms > 2000:
            logger.warning(f'Slow support endpoint: {endpoint} ({elapsed_ms}ms)')
        elif elapsed_ms > 500:
            logger.info(f'Support endpoint: {endpoint} ({elapsed_ms}ms)')

    def alert_on_high_queue(self, threshold: int = 20) -> bool:
        """Alert if ticket queue is too deep."""
        try:
            from api.support.models import SupportTicket
            open_count = SupportTicket.objects.filter(
                status='open', assigned_to__isnull=True
            ).count()
            if open_count >= threshold:
                logger.error(f'HIGH QUEUE ALERT: {open_count} unassigned tickets!')
                try:
                    from api.support.webhooks import webhook_sender
                    webhook_sender.send('slack_alert', 'queue_alert', {
                        'message': f'{open_count} unassigned tickets in queue!',
                        'count': open_count,
                    })
                except Exception:
                    pass
                return True
            return False
        except Exception:
            return False


monitor = SupportMonitor()