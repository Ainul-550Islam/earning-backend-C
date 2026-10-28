from ...exceptions import WebhookHealthCheckError
"""Webhook Health Monitor Service

This service monitors webhook endpoint health and performance.
Tracks availability, response times, and automatically suspends unhealthy endpoints.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone

from ...models import WebhookEndpoint, WebhookHealthLog
from ...choices import WebhookStatus

logger = logging.getLogger(__name__)


class HealthMonitorService:
    """
    Service for monitoring webhook endpoint health.
    Performs periodic health checks and manages endpoint status.
    """
    
    def __init__(self):
        """Initialize health monitor service."""
        self.logger = logger
    
    def check_endpoint_health(self, endpoint: WebhookEndpoint, timeout_seconds: int = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Perform health check on a webhook endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            timeout_seconds: optional request timeout override (defaults to
                settings.WEBHOOKS['DEFAULT_TIMEOUT'] or 10)
            headers: optional extra headers to merge into the request
            
        Returns:
            Dict: Health check results
        """
        import requests
        from django.conf import settings

        default_timeout = getattr(settings, 'WEBHOOKS', {}).get('DEFAULT_TIMEOUT', 10) if hasattr(settings, 'WEBHOOKS') else 10
        request_headers = {'User-Agent': 'Webhooks-Health-Check/1.0'}
        if headers:
            request_headers.update(headers)

        try:
            response = requests.get(
                endpoint.target_url,
                timeout=timeout_seconds or default_timeout,
                headers=request_headers,
                verify=endpoint.verify_ssl,
            )

            response_time_ms = int(response.elapsed.total_seconds() * 1000)
            is_healthy = response.status_code == 200

            health_log = WebhookHealthLog.objects.create(
                endpoint=endpoint,
                is_healthy=is_healthy,
                response_time_ms=response_time_ms,
                status_code=response.status_code,
                error=None,
            )

            if not is_healthy and endpoint.status == WebhookStatus.ACTIVE:
                self._auto_suspend_endpoint(endpoint, "Health check failed")

            self.logger.info(
                f"Health check for {endpoint.target_url}: {'Healthy' if is_healthy else 'Unhealthy'} "
                f"({response_time_ms}ms, {response.status_code})"
            )

            return {
                'endpoint_id': endpoint.id,
                'url': endpoint.target_url,
                'is_healthy': is_healthy,
                'response_time_ms': response_time_ms,
                'status_code': response.status_code,
                'error': None,
                'checked_at': health_log.checked_at,
            }

        except Exception as e:
            self.logger.error(f"Health check error for {endpoint.target_url}: {e}")

            health_log = WebhookHealthLog.objects.create(
                endpoint=endpoint,
                is_healthy=False,
                response_time_ms=None,
                status_code=None,
                error=str(e),
            )

            if endpoint.status == WebhookStatus.ACTIVE:
                self._auto_suspend_endpoint(endpoint, "Health check failed")

            return {
                'endpoint_id': endpoint.id,
                'url': endpoint.target_url,
                'is_healthy': False,
                'response_time_ms': None,
                'status_code': None,
                'error': str(e),
                'checked_at': health_log.checked_at,
            }
    
    def check_all_endpoints(self, timeout_seconds: int = None) -> List[Dict[str, Any]]:
        """
        Perform health checks on all active endpoints.

        Args:
            timeout_seconds: optional request timeout override, forwarded
                to check_endpoint_health() for each endpoint (defaults to
                settings.WEBHOOKS['DEFAULT_TIMEOUT'] or 10 if not given)

        Returns:
            List[Dict]: Health check results for all endpoints
        """
        results = []
        
        active_endpoints = WebhookEndpoint.objects.filter(
            status=WebhookStatus.ACTIVE
        )
        
        for endpoint in active_endpoints:
            result = self.check_endpoint_health(endpoint, timeout_seconds=timeout_seconds)
            results.append(result)
        
        return results
    
    def get_endpoint_health_summary(self, endpoint: WebhookEndpoint, hours: int = 24) -> Dict[str, Any]:
        """
        Get health summary for an endpoint over specified period.
        
        Args:
            endpoint: WebhookEndpoint instance
            hours: Number of hours to look back
            
        Returns:
            Dict: Health summary
        """
        try:
            since = timezone.now() - timedelta(hours=hours)
            
            health_logs = WebhookHealthLog.objects.filter(
                endpoint=endpoint,
                checked_at__gte=since
            ).order_by('-checked_at')
            
            total_checks = health_logs.count()
            healthy_checks = health_logs.filter(is_healthy=True).count()
            unhealthy_checks = health_logs.filter(is_healthy=False).count()
            
            # Calculate average response time
            response_times = [
                log.response_time_ms for log in health_logs 
                if log.response_time_ms is not None
            ]
            avg_response_time = (sum(response_times) / len(response_times)) if response_times else None
            
            # Calculate uptime percentage
            uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
            
            last_log = health_logs.first()
            last_check_status = None
            if last_log is not None:
                last_check_status = 'healthy' if last_log.is_healthy else 'unhealthy'
            
            return {
                'endpoint_id': endpoint.id,
                'url': endpoint.target_url,
                'period_hours': hours,
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': unhealthy_checks,
                'uptime_percentage': round(uptime_percentage, 2),
                'avg_response_time_ms': round(avg_response_time, 2) if avg_response_time is not None else None,
                'last_check_status': last_check_status,
                'current_status': endpoint.status,
                'last_check': last_log.checked_at if last_log else None,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get health summary: {e}")
            return {}

    def get_endpoint_health_metrics(self, endpoint: WebhookEndpoint, hours: int = 1) -> Dict[str, Any]:
        """
        Response-time percentile breakdown for an endpoint over a window.

        Args:
            endpoint: WebhookEndpoint instance
            hours: lookback window

        Returns:
            {'min_response_time_ms', 'max_response_time_ms',
            'avg_response_time_ms', 'median_response_time_ms',
            'p95_response_time_ms', 'p99_response_time_ms'} - all None if
            there's no data in the window.
        """
        import statistics

        since = timezone.now() - timedelta(hours=hours)
        response_times = sorted(
            WebhookHealthLog.objects.filter(endpoint=endpoint, checked_at__gte=since, response_time_ms__isnull=False)
            .values_list('response_time_ms', flat=True)
        )

        if not response_times:
            return {
                'min_response_time_ms': None,
                'max_response_time_ms': None,
                'avg_response_time_ms': None,
                'median_response_time_ms': None,
                'p95_response_time_ms': None,
                'p99_response_time_ms': None,
            }

        def percentile(sorted_values, pct):
            n = len(sorted_values)
            if n == 1:
                return sorted_values[0]
            pos = (pct / 100) * n  # 1-indexed, possibly fractional
            lower_rank = max(1, min(n, int(pos // 1) or 1))
            upper_rank = max(1, min(n, -(-pos // 1)))  # ceil
            fraction = pos - (pos // 1)
            lower_val = sorted_values[lower_rank - 1]
            upper_val = sorted_values[upper_rank - 1]
            return lower_val + fraction * (upper_val - lower_val)

        return {
            'min_response_time_ms': response_times[0],
            'max_response_time_ms': response_times[-1],
            'avg_response_time_ms': round(sum(response_times) / len(response_times), 2),
            'median_response_time_ms': statistics.median(response_times),
            'p95_response_time_ms': round(percentile(response_times, 95)),
            'p99_response_time_ms': round(percentile(response_times, 99)),
        }

    def get_endpoint_health_score(self, endpoint: WebhookEndpoint, hours: int = 1) -> Optional[float]:
        """
        Single 0-100 health score for an endpoint (percentage of checks in
        the window that were healthy). None if there's no data.

        Args:
            endpoint: WebhookEndpoint instance
            hours: lookback window
        """
        since = timezone.now() - timedelta(hours=hours)
        logs = WebhookHealthLog.objects.filter(endpoint=endpoint, checked_at__gte=since)
        total = logs.count()
        if total == 0:
            return None
        healthy = logs.filter(is_healthy=True).count()
        return round((healthy / total) * 100, 2)
    
    # FIX: removed _make_health_request() and _generate_health_signature()
    # (dead code - confirmed zero callers anywhere in the codebase, not even
    # within this class). Both were also broken if ever invoked: they read
    # endpoint.secret, which doesn't exist on WebhookEndpoint (the real field
    # is secret_key), so _generate_health_signature would have raised
    # AttributeError immediately. _make_health_request also hardcoded
    # verify=False unconditionally - silently ignoring endpoint.verify_ssl -
    # unlike check_endpoint_health() above, the real/live method, which
    # correctly does verify=endpoint.verify_ssl and persists a
    # WebhookHealthLog row (this dead pair didn't persist anything at all).
    # Left in place this was a landmine for a future session to wire up by
    # mistake, believing it the real health-ping path.

    def _auto_suspend_endpoint(self, endpoint: WebhookEndpoint, reason: str) -> bool:
        """
        Automatically suspend an unhealthy endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            reason: Reason for suspension
            
        Returns:
            bool: True if successful
        """
        try:
            with transaction.atomic():
                endpoint.status = WebhookStatus.SUSPENDED
                endpoint.save()
                
                self.logger.warning(
                    f"Auto-suspended endpoint {endpoint.target_url}: {reason}"
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to auto-suspend endpoint: {e}")
            return False
    
    def get_unhealthy_endpoints(self, hours: int = 1) -> List[WebhookEndpoint]:
        """
        Get endpoints that have been unhealthy.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List[WebhookEndpoint]: Unhealthy endpoints
        """
        try:
            since = timezone.now() - timedelta(hours=hours)
            
            # Get endpoints with recent failed health checks
            unhealthy_endpoints = []
            
            for endpoint in WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE):
                recent_fails = WebhookHealthLog.objects.filter(
                    endpoint=endpoint,
                    is_healthy=False,
                    checked_at__gte=since
                ).count()
                
                if recent_fails >= 3:  # 3+ failed checks in specified period
                    unhealthy_endpoints.append(endpoint)
            
            return unhealthy_endpoints
            
        except Exception as e:
            self.logger.error(f"Failed to get unhealthy endpoints: {e}")
            return []
    
    def resume_suspended_endpoint(self, endpoint: WebhookEndpoint) -> bool:
        """
        Resume a suspended endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            
        Returns:
            bool: True if successful
        """
        try:
            with transaction.atomic():
                endpoint.status = WebhookStatus.ACTIVE
                endpoint.save()
                
                self.logger.info(f"Resumed endpoint {endpoint.target_url}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to resume endpoint: {e}")
            return False

    def auto_suspend_unhealthy_endpoint(self, endpoint: WebhookEndpoint, consecutive_failures: int = 3, force: bool = False) -> Dict[str, Any]:
        """
        Suspend an endpoint if its most recent `consecutive_failures` health
        checks were all unhealthy.

        Args:
            endpoint: WebhookEndpoint instance
            consecutive_failures: how many most-recent checks must all be
                unhealthy to trigger suspension
            force: if True, still evaluate (and re-apply if warranted) even
                when the endpoint is already suspended. Does NOT bypass the
                consecutive-failures evidence check below - it only affects
                the already-suspended short-circuit, matching the narrower
                scope suggested by suspend_unhealthy.py's own --force help
                text ("force suspension even if endpoint is already
                suspended", not "suspend regardless of health").

        Returns:
            {'suspended': bool, 'reason': str}
        """
        # BUG FIX: this used to return early unconditionally whenever the
        # endpoint was already suspended, with no way to override it. The
        # caller (suspend_unhealthy.py) has its own --force flag
        # documented as overriding exactly this case, but had no way to
        # actually signal that through - force was silently swallowed,
        # so --force never did anything for an already-suspended endpoint.
        if endpoint.status == WebhookStatus.SUSPENDED and not force:
            return {'suspended': False, 'reason': 'endpoint is already suspended'}

        recent_logs = list(
            WebhookHealthLog.objects.filter(endpoint=endpoint)
            .order_by('-checked_at')[:consecutive_failures]
        )

        if len(recent_logs) < consecutive_failures or not all(not log.is_healthy for log in recent_logs):
            return {'suspended': False, 'reason': 'not enough consecutive failures'}

        reason = f"{consecutive_failures} consecutive failed health checks"
        self._auto_suspend_endpoint(endpoint, reason)
        return {'suspended': True, 'reason': reason}

    def get_endpoint_health_alerts(self, endpoint: WebhookEndpoint, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Build a list of active alerts for an endpoint based on recent health
        logs: consecutive failures and/or high response times.

        Args:
            endpoint: WebhookEndpoint instance
            hours: lookback window

        Returns:
            List of {'type': str, ...} alert dicts
        """
        since = timezone.now() - timedelta(hours=hours)
        recent_logs = list(
            WebhookHealthLog.objects.filter(endpoint=endpoint, checked_at__gte=since)
            .order_by('-checked_at')
        )

        alerts = []
        unhealthy_count = sum(1 for log in recent_logs if not log.is_healthy)
        if unhealthy_count >= 2:
            alerts.append({
                'type': 'consecutive_failures',
                'severity': 'critical' if unhealthy_count >= 5 else 'warning',
                'count': unhealthy_count,
                'message': f"{unhealthy_count} failed health checks in the last {hours} hour(s)",
            })

        slow_logs = [log for log in recent_logs if (log.response_time_ms or 0) > 3000]
        if slow_logs:
            max_response = max(log.response_time_ms for log in slow_logs)
            alerts.append({
                'type': 'high_response_time',
                'severity': 'warning',
                'max_response_time_ms': max_response,
                'message': f"Response time as high as {max_response}ms in the last {hours} hour(s)",
            })

        return alerts

    def get_endpoint_health_trends(self, endpoint: WebhookEndpoint, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Build hourly trend buckets, oldest to newest, each showing
        cumulative healthy/unhealthy counts and uptime percentage from the
        start of the window through that hour.

        Args:
            endpoint: WebhookEndpoint instance
            hours: how many hourly buckets to produce

        Returns:
            List of `hours` dicts: {'hour': int, 'healthy_checks': int,
            'unhealthy_checks': int, 'uptime_percentage': float}
        """
        now = timezone.now()
        window_start = now - timedelta(hours=hours)
        logs = list(
            WebhookHealthLog.objects.filter(endpoint=endpoint, checked_at__gte=window_start)
            .order_by('checked_at')
        )

        trends = []
        cumulative_healthy = 0
        cumulative_unhealthy = 0
        for i in range(hours):
            bucket_end = window_start + timedelta(hours=i + 1)
            while logs and logs[0].checked_at < bucket_end:
                log = logs.pop(0)
                if log.is_healthy:
                    cumulative_healthy += 1
                else:
                    cumulative_unhealthy += 1
            total = cumulative_healthy + cumulative_unhealthy
            uptime_pct = round((cumulative_healthy / total) * 100, 2) if total else 0.0
            trends.append({
                'hour': i,
                'healthy_checks': cumulative_healthy,
                'unhealthy_checks': cumulative_unhealthy,
                'uptime_percentage': uptime_pct,
            })

        return trends

    def update_endpoint_health_status(self, endpoint: WebhookEndpoint) -> None:
        """
        Sync endpoint.status to its most recent health check result:
        unhealthy -> SUSPENDED, healthy -> ACTIVE.

        Args:
            endpoint: WebhookEndpoint instance
        """
        latest = WebhookHealthLog.objects.filter(endpoint=endpoint).order_by('-checked_at').first()
        if latest is None:
            return

        new_status = WebhookStatus.SUSPENDED if not latest.is_healthy else WebhookStatus.ACTIVE
        if endpoint.status != new_status:
            endpoint.status = new_status
            endpoint.save()

    def cleanup_old_health_logs(self, days: int = 90) -> Dict[str, Any]:
        """
        Delete health logs older than `days`.

        Args:
            days: retention window

        Returns:
            {'cleaned_count': int}
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = WebhookHealthLog.objects.filter(checked_at__lt=cutoff).delete()
        return {'cleaned_count': deleted_count}

    def get_health_check_recommendations(self, endpoint: WebhookEndpoint, hours: int = 1) -> List[str]:
        """
        Produce a list of recommendation identifiers based on recent health
        check patterns for an endpoint.

        Args:
            endpoint: WebhookEndpoint instance
            hours: lookback window

        Returns:
            List of recommendation strings, e.g. ['consecutive_failures',
            'high_failure_rate', 'slow_response_times']
        """
        since = timezone.now() - timedelta(hours=hours)
        recent_logs = list(WebhookHealthLog.objects.filter(endpoint=endpoint, checked_at__gte=since))

        if not recent_logs:
            return []

        recommendations = []
        unhealthy_count = sum(1 for log in recent_logs if not log.is_healthy)
        total = len(recent_logs)

        if unhealthy_count >= 2:
            recommendations.append('consecutive_failures')
        if total and (unhealthy_count / total) > 0.5:
            recommendations.append('high_failure_rate')
        slow_count = sum(1 for log in recent_logs if (log.response_time_ms or 0) > 3000)
        if slow_count and (slow_count / total) > 0.5:
            recommendations.append('slow_response_times')

        return recommendations

    def get_system_health_overview(self) -> Dict[str, Any]:
        """
        System-wide health snapshot across all endpoints.

        Returns:
            {'total_endpoints', 'active_endpoints', 'healthy_endpoints',
            'unhealthy_endpoints', 'overall_uptime_percentage',
            'avg_response_time_ms'}
        """
        total_endpoints = WebhookEndpoint.objects.count()
        active_endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE).count()

        # Most recent health log per endpoint determines healthy/unhealthy
        healthy_endpoints = 0
        unhealthy_endpoints = 0
        response_times = []
        for endpoint in WebhookEndpoint.objects.all():
            latest = WebhookHealthLog.objects.filter(endpoint=endpoint).order_by('-checked_at').first()
            if latest is None:
                continue
            if latest.is_healthy:
                healthy_endpoints += 1
            else:
                unhealthy_endpoints += 1
            if latest.response_time_ms is not None:
                response_times.append(latest.response_time_ms)

        checked_total = healthy_endpoints + unhealthy_endpoints
        overall_uptime = round((healthy_endpoints / checked_total) * 100, 2) if checked_total else 0.0
        avg_response_time = round(sum(response_times) / len(response_times), 2) if response_times else 0.0

        return {
            'total_endpoints': total_endpoints,
            'active_endpoints': active_endpoints,
            'healthy_endpoints': healthy_endpoints,
            'unhealthy_endpoints': unhealthy_endpoints,
            'overall_uptime_percentage': overall_uptime,
            'avg_response_time_ms': avg_response_time,
        }
    def schedule_health_check(self, endpoint: WebhookEndpoint, interval_minutes: int = 5) -> Dict[str, Any]:
        """
        Dispatch (synchronously invoke) the schedule_health_check task for
        an endpoint.

        Args:
            endpoint: WebhookEndpoint instance
            interval_minutes: informational recurrence hint (see task docstring)

        Returns:
            {'scheduled': bool, 'task_id': str or None}
        """
        from ...tasks import health_check_tasks
        task_result = health_check_tasks.schedule_health_check(endpoint.id, interval_minutes)
        return {
            'scheduled': True,
            'task_id': getattr(task_result, 'id', None),
        }

    def cancel_health_check(self, endpoint: WebhookEndpoint, task_id: str = None) -> Dict[str, Any]:
        """
        Cancel a scheduled health check for an endpoint.

        Args:
            endpoint: WebhookEndpoint instance
            task_id: optional task identifier to cancel

        Returns:
            {'cancelled': bool}
        """
        from ...tasks import health_check_tasks
        result = health_check_tasks.cancel_health_check(endpoint.id, task_id=task_id)
        return {'cancelled': bool(result)}
