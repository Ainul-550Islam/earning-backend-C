"""Suspend Unhealthy Management Command

This management command manually triggers the auto-suspend functionality
for webhook endpoints that are experiencing health issues.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Avg

from ...models import WebhookEndpoint, WebhookHealthLog
from ...services.analytics import HealthMonitorService
from ...choices import WebhookStatus


class Command(BaseCommand):
    help = 'Manually trigger auto-suspend for unhealthy webhook endpoints'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--consecutive-failures',
            type=int,
            default=3,
            help='Number of consecutive failures to trigger suspension (default: 3)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Time window in hours to check for failures (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be suspended without actually suspending'
        )
        parser.add_argument(
            '--endpoint-id',
            type=str,
            help='Specific endpoint ID to check (optional)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force suspension even if endpoint is already suspended'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        consecutive_failures = options['consecutive_failures']
        hours = options['hours']
        dry_run = options['dry_run']
        endpoint_id = options.get('endpoint_id')
        force = options['force']
        verbose = options['verbose']
        
        health_monitor = HealthMonitorService()
        
        if verbose:
            self.stdout.write(f"Checking for unhealthy endpoints in the last {hours} hours")
            self.stdout.write(f"Suspension threshold: {consecutive_failures} consecutive failures")
        
        # Get time window
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        # Build base query
        query = WebhookHealthLog.objects.filter(
            checked_at__gte=since
        )
        
        if endpoint_id:
            query = query.filter(endpoint_id=endpoint_id)
            if verbose:
                self.stdout.write(f"Checking specific endpoint: {endpoint_id}")
        
        # Find endpoints with consecutive failures
        unhealthy_endpoints = []
        
        # Get all endpoints that have health logs in the time window
        endpoints_with_logs = query.values_list('endpoint_id', flat=True).distinct()
        
        for endpoint_id in endpoints_with_logs:
            # Get recent health logs for this endpoint
            recent_logs = WebhookHealthLog.objects.filter(
                endpoint_id=endpoint_id,
                checked_at__gte=since
            ).order_by('-checked_at')
            
            if recent_logs.count() >= consecutive_failures:
                # Check if the most recent logs are all failures
                recent_failure_count = 0
                for log in recent_logs:
                    if not log.is_healthy:
                        recent_failure_count += 1
                    else:
                        break  # Stop at first healthy check
                    
                    if recent_failure_count >= consecutive_failures:
                        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
                        unhealthy_endpoints.append({
                            'endpoint': endpoint,
                            'failure_count': recent_failure_count,
                            'last_check': recent_logs[0].checked_at,
                            'avg_response_time': recent_logs.aggregate(
                                avg=Avg('response_time_ms')
                            )['avg'] or 0
                        })
                        break
        
        if not unhealthy_endpoints:
            self.stdout.write(
                self.style.SUCCESS("No unhealthy endpoints found")
            )
            return
        
        # Display results
        self.stdout.write(
            self.style.WARNING(f"Found {len(unhealthy_endpoints)} unhealthy endpoint(s):")
        )
        
        for endpoint_info in unhealthy_endpoints:
            endpoint = endpoint_info['endpoint']
            self.stdout.write(
                f"  - {endpoint.url} ({endpoint.label or 'No label'}) "
                f"- {endpoint_info['failure_count']} consecutive failures "
                f"- Avg response time: {endpoint_info['avg_response_time']:.0f}ms"
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: No endpoints were suspended")
            )
            return
        
        # Suspend unhealthy endpoints
        suspended_count = 0
        for endpoint_info in unhealthy_endpoints:
            endpoint = endpoint_info['endpoint']
            
            # Skip if already suspended (unless force flag is used)
            if endpoint.status == WebhookStatus.SUSPENDED and not force:
                if verbose:
                    self.stdout.write(
                        f"Skipping {endpoint.url} - already suspended"
                    )
                continue
            
            # Suspend the endpoint
            result = health_monitor.auto_suspend_unhealthy_endpoint(
                endpoint,
                consecutive_failures=consecutive_failures
            )
            
            if result['suspended']:
                suspended_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Suspended endpoint: {endpoint.url} "
                        f"({endpoint.label or 'No label'})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to suspend endpoint: {endpoint.url} "
                        f"- {result.get('reason', 'Unknown error')}"
                    )
                )
        
        # Summary
        total_unhealthy = len(unhealthy_endpoints)
        self.stdout.write(
            self.style.SUCCESS(
                f"Suspended {suspended_count} out of {total_unhealthy} unhealthy endpoints"
            )
        )
        
        if suspended_count < total_unhealthy:
            self.stdout.write(
                self.style.WARNING(
                    f"{total_unhealthy - suspended_count} endpoints were not suspended"
                )
            )
    
    def _get_endpoint_health_summary(self, endpoint_id, hours):
        """Get detailed health summary for an endpoint."""
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        health_logs = WebhookHealthLog.objects.filter(
            endpoint_id=endpoint_id,
            checked_at__gte=since
        ).order_by('-checked_at')
        
        if not health_logs.exists():
            return None
        
        total_checks = health_logs.count()
        healthy_checks = health_logs.filter(is_healthy=True).count()
        unhealthy_checks = total_checks - healthy_checks
        uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
        
        avg_response_time = health_logs.aggregate(
            avg=Avg('response_time_ms')
        )['avg'] or 0
        
        return {
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': unhealthy_checks,
            'uptime_percentage': uptime_percentage,
            'avg_response_time': avg_response_time,
            'last_check': health_logs.first(),
            'last_healthy': health_logs.filter(is_healthy=True).first()
        }
    
    def _print_endpoint_health_details(self, endpoint_id, hours):
        """Print detailed health information for an endpoint."""
        summary = self._get_endpoint_health_summary(endpoint_id, hours)
        
        if not summary:
            self.stdout.write("No health data available for this endpoint")
            return
        
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        
        self.stdout.write(f"\nHealth Details for: {endpoint.url}")
        self.stdout.write(f"Label: {endpoint.label or 'No label'}")
        self.stdout.write(f"Status: {endpoint.status}")
        self.stdout.write(f"Total Checks: {summary['total_checks']}")
        self.stdout.write(f"Healthy Checks: {summary['healthy_checks']}")
        self.stdout.write(f"Unhealthy Checks: {summary['unhealthy_checks']}")
        self.stdout.write(f"Uptime: {summary['uptime_percentage']:.1f}%")
        self.stdout.write(f"Avg Response Time: {summary['avg_response_time']:.0f}ms")
        
        if summary['last_check']:
            self.stdout.write(
                f"Last Check: {summary['last_check'].checked_at.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({'Healthy' if summary['last_check'].is_healthy else 'Unhealthy'})"
            )
        
        if summary['last_healthy']:
            self.stdout.write(
                f"Last Healthy: {summary['last_healthy'].checked_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            self.stdout.write("Last Healthy: Never")
        
        # Show recent health logs
        recent_logs = WebhookHealthLog.objects.filter(
            endpoint_id=endpoint_id,
            checked_at__gte=timezone.now() - timezone.timedelta(hours=hours)
        ).order_by('-checked_at')[:10]
        
        if recent_logs.exists():
            self.stdout.write("\nRecent Health Checks:")
            for log in recent_logs:
                status = "Healthy" if log.is_healthy else "Unhealthy"
                response_time = f"{log.response_time_ms}ms" if log.response_time_ms else "N/A"
                self.stdout.write(
                    f"  {log.checked_at.strftime('%Y-%m-%d %H:%M:%S')} - "
                    f"{status} - {response_time} - "
                    f"{log.status_code or 'N/A'}"
                )
