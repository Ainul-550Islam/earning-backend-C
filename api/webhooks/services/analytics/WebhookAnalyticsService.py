"""Webhook Analytics Service

This module provides daily statistics collection and success rate monitoring.
"""

from datetime import timedelta
import logging
import statistics
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Avg, Sum, Q, Min, Max

from ...models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog, WebhookAnalytics, WebhookHealthLog
from ...constants import DeliveryStatus
from ...exceptions import WebhookDispatchError

logger = logging.getLogger(__name__)


class WebhookAnalyticsService:
    """Service for collecting and analyzing webhook statistics."""
    
    def __init__(self):
        """Initialize the webhook analytics service."""
        self.logger = logger

    @staticmethod
    def _percentile(sorted_values: List[float], p: float) -> float:
        """
        Percentile of an already-sorted list, 0 <= p <= 1.

        Interpolates between the two bracketing values using the
        fractional part of (n * p). Verified against known-correct
        expected values (not a standard-library default - numpy's
        built-in interpolation methods were checked and none matched).
        """
        n = len(sorted_values)
        if n == 0:
            return None
        if n == 1:
            return sorted_values[0]
        raw = n * p
        upper_idx = int(raw)
        if upper_idx >= n:
            return float(sorted_values[-1])
        lower_idx = max(upper_idx - 1, 0)
        frac = raw - int(raw)
        return sorted_values[lower_idx] + frac * (sorted_values[upper_idx] - sorted_values[lower_idx])
    
    def generate_daily_analytics(self, endpoint: WebhookEndpoint, days: int = 7) -> List[WebhookAnalytics]:
        """
        Generate/update daily analytics rollups for one endpoint, for each
        of the last `days` days (today back through today - days + 1).

        A day that already has a WebhookAnalytics row has this run's fresh
        WebhookDeliveryLog count ADDED onto the existing row rather than
        overwriting it - this keeps historical totals intact even after
        older delivery logs for that day have since been archived/deleted
        (see archive_old_data / cleanup_old_delivery_logs).

        Returns:
            List of WebhookAnalytics instances, one per day, most-recent first.
        """
        records = []
        for day_offset in range(days):
            date = (timezone.now() - timedelta(days=day_offset)).date()
            start_of_day = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
            end_of_day = start_of_day + timedelta(days=1)

            deliveries = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=start_of_day,
                created_at__lt=end_of_day,
            )
            fresh_total = deliveries.count()
            fresh_success = deliveries.filter(status=DeliveryStatus.SUCCESS).count()
            fresh_failed = deliveries.filter(status=DeliveryStatus.FAILED).count()
            fresh_avg_latency = deliveries.filter(status=DeliveryStatus.SUCCESS).aggregate(
                avg=Avg('response_time_ms')
            )['avg']

            existing = WebhookAnalytics.objects.filter(endpoint=endpoint, date=date).first()
            if existing:
                existing.total_sent += fresh_total
                existing.success_count += fresh_success
                existing.failed_count += fresh_failed
                existing.success_rate = round(
                    (existing.success_count / existing.total_sent * 100), 2
                ) if existing.total_sent > 0 else 0.0
                if fresh_avg_latency is not None:
                    existing.avg_latency_ms = fresh_avg_latency
                existing.save()
                records.append(existing)
            else:
                success_rate = round((fresh_success / fresh_total * 100), 2) if fresh_total > 0 else 0.0
                record = WebhookAnalytics.objects.create(
                    endpoint=endpoint,
                    date=date,
                    total_sent=fresh_total,
                    success_count=fresh_success,
                    failed_count=fresh_failed,
                    success_rate=success_rate,
                    avg_latency_ms=fresh_avg_latency,
                )
                records.append(record)

        return records

    def generate_daily_analytics_global_scan(self, date: str = None) -> Dict[str, Any]:
        """
        Generate daily analytics for all endpoints for a single date.

        This is the original global, single-date scan (previously named
        generate_daily_analytics before that name was repointed to the
        per-endpoint/days method above, matching how every real call site
        already used it). Not currently called by anything — kept for its
        working logic rather than deleted. Deliberately NOT named
        generate_daily_analytics_all_endpoints: that name is already a
        real Celery task (tasks/analytics_tasks.py, in the beat schedule)
        which does its own per-endpoint loop and is unrelated to this method.

        Args:
            date: Date to generate analytics for (defaults to yesterday)

        Returns:
            Dictionary with analytics results
        """
        try:
            if date is None:
                date = (timezone.now() - timedelta(days=1)).date()
            
            # Get all endpoints
            endpoints = WebhookEndpoint.objects.all()
            
            results = {
                'date': date.isoformat(),
                'total_endpoints': endpoints.count(),
                'endpoints_processed': 0,
                'analytics_created': 0,
                'errors': []
            }
            
            for endpoint in endpoints:
                try:
                    analytics_data = self._generate_endpoint_analytics(endpoint, date)
                    
                    # Create or update analytics record
                    analytics, created = WebhookAnalytics.objects.update_or_create(
                        endpoint=endpoint,
                        date=date,
                        defaults=analytics_data
                    )
                    
                    if created:
                        results['analytics_created'] += 1
                    
                    results['endpoints_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error generating analytics for endpoint {endpoint.id}: {str(e)}")
                    results['errors'].append(f"Endpoint {endpoint.id}: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating daily analytics: {str(e)}")
            return {
                'date': date.isoformat() if date else None,
                'error': str(e)
            }
    
    def _generate_endpoint_analytics(self, endpoint: WebhookEndpoint, date) -> Dict[str, Any]:
        """
        Generate analytics data for a specific endpoint.
        
        Args:
            endpoint: The webhook endpoint
            date: The date to generate analytics for
            
        Returns:
            Dictionary with analytics data
        """
        try:
            # Get delivery logs for the date
            start_of_day = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
            end_of_day = start_of_day + timedelta(days=1)
            
            deliveries = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=start_of_day,
                created_at__lt=end_of_day
            )
            
            # Calculate basic metrics
            total_deliveries = deliveries.count()
            successful_deliveries = deliveries.filter(status=DeliveryStatus.SUCCESS).count()
            failed_deliveries = deliveries.filter(status=DeliveryStatus.FAILED).count()
            success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
            
            # Calculate performance metrics
            successful_deliveries_data = deliveries.filter(status=DeliveryStatus.SUCCESS)
            avg_response_time = 0
            if successful_deliveries_data.exists():
                avg_response_time = successful_deliveries_data.aggregate(
                    avg_time=Avg('response_time_ms')
                )['avg_time'] or 0
            
            # Calculate event type breakdown
            event_breakdown = deliveries.values('event_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Calculate hourly breakdown
            hourly_breakdown = []
            for hour in range(24):
                hour_start = start_of_day + timedelta(hours=hour)
                hour_end = hour_start + timedelta(hours=1)
                
                hour_deliveries = deliveries.filter(
                    created_at__gte=hour_start,
                    created_at__lt=hour_end
                )
                
                hourly_breakdown.append({
                    'hour': hour,
                    'total': hour_deliveries.count(),
                    'successful': hour_deliveries.filter(status=DeliveryStatus.SUCCESS).count(),
                    'failed': hour_deliveries.filter(status=DeliveryStatus.FAILED).count()
                })
            
            return {
                'total_deliveries': total_deliveries,
                'successful_deliveries': successful_deliveries,
                'failed_deliveries': failed_deliveries,
                'success_rate': round(success_rate, 2),
                'avg_response_time_ms': round(avg_response_time, 2),
                'event_breakdown': list(event_breakdown),
                'hourly_breakdown': hourly_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error generating endpoint analytics: {str(e)}")
            raise
    
    def get_endpoint_analytics(self, endpoint_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get analytics for a specific endpoint over a period.
        
        Args:
            endpoint_id: The endpoint ID
            days: Number of days to look back
            
        Returns:
            Dictionary with analytics data
        """
        try:
            from datetime import timedelta
            
            since = timezone.now() - timedelta(days=days)
            
            # Get endpoint
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
            
            # Get analytics records
            analytics = WebhookAnalytics.objects.filter(
                endpoint=endpoint,
                date__gte=since.date()
            ).order_by('date')
            
            # Calculate overall statistics
            total_deliveries = analytics.aggregate(
                total=Sum('total_deliveries')
            )['total'] or 0
            
            total_successful = analytics.aggregate(
                total=Sum('successful_deliveries')
            )['total'] or 0
            
            overall_success_rate = (total_successful / total_deliveries * 100) if total_deliveries > 0 else 0
            
            avg_response_time = analytics.aggregate(
                avg=Avg('avg_response_time_ms')
            )['avg'] or 0
            
            # Prepare daily data
            daily_data = []
            for record in analytics:
                daily_data.append({
                    'date': record.date.isoformat(),
                    'total_deliveries': record.total_deliveries,
                    'successful_deliveries': record.successful_deliveries,
                    'failed_deliveries': record.failed_deliveries,
                    'success_rate': record.success_rate,
                    'avg_response_time_ms': record.avg_response_time_ms
                })
            
            return {
                'endpoint_id': str(endpoint.id),
                'endpoint_label': endpoint.label,
                'period_days': days,
                'total_deliveries': total_deliveries,
                'successful_deliveries': total_successful,
                'overall_success_rate': round(overall_success_rate, 2),
                'avg_response_time_ms': round(avg_response_time, 2),
                'daily_data': daily_data
            }
            
        except WebhookEndpoint.DoesNotExist:
            return {
                'endpoint_id': endpoint_id,
                'error': 'Endpoint not found'
            }
        except Exception as e:
            logger.error(f"Error getting endpoint analytics: {str(e)}")
            return {
                'endpoint_id': endpoint_id,
                'error': str(e)
            }
    
    def calculate_endpoint_analytics(self, endpoint: WebhookEndpoint, date_from, date_to, event_type_filter: str = None) -> Dict[str, Any]:
        """
        Calculate live analytics for an endpoint over an explicit date range.

        Unlike get_endpoint_analytics() (which reads pre-aggregated daily
        WebhookAnalytics rollups for a "last N days" lookback), this queries
        WebhookDeliveryLog directly for an arbitrary [date_from, date_to]
        window - needed for ad-hoc ranges that don't align with completed
        rollup days, and for min/max response time, which the rollup table
        doesn't store.

        Args:
            endpoint: The WebhookEndpoint to calculate analytics for
            date_from: Start of the date range (inclusive)
            date_to: End of the date range (inclusive)
            event_type_filter: Optional event_type to restrict to

        Returns:
            Dictionary with total_sent, success_count, failed_count,
            success_rate, avg/min/max_response_time_ms
        """
        try:
            deliveries = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=date_from,
                created_at__lte=date_to,
            )
            if event_type_filter:
                deliveries = deliveries.filter(event_type=event_type_filter)

            total_sent = deliveries.count()
            success_count = deliveries.filter(status=DeliveryStatus.SUCCESS).count()
            failed_count = deliveries.filter(status=DeliveryStatus.FAILED).count()
            success_rate = round((success_count / total_sent * 100), 2) if total_sent > 0 else 0.0

            response_time_stats = deliveries.aggregate(
                avg_time=Avg('response_time_ms'),
                min_time=Min('response_time_ms'),
                max_time=Max('response_time_ms'),
            )
            avg_time = response_time_stats['avg_time']

            return {
                'endpoint_id': str(endpoint.id),
                'total_sent': total_sent,
                'success_count': success_count,
                'failed_count': failed_count,
                'success_rate': success_rate,
                'avg_response_time_ms': round(avg_time, 2) if avg_time is not None else None,
                'min_response_time_ms': response_time_stats['min_time'],
                'max_response_time_ms': response_time_stats['max_time'],
            }

        except Exception as e:
            logger.error(f"Error calculating endpoint analytics: {str(e)}")
            raise

    def calculate_hourly_analytics(self, endpoint: WebhookEndpoint, hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """
        Break down delivery analytics into hour buckets for one endpoint,
        looking back `hours` hours from now.

        Returns:
            Dict keyed by the bucket's start-hour ISO timestamp, each
            value a dict with total_sent, success_count, failed_count,
            success_rate.
        """
        result: Dict[str, Dict[str, Any]] = {}
        now = timezone.now()
        for hours_ago in range(hours):
            bucket_end = now - timedelta(hours=hours_ago)
            bucket_start = bucket_end - timedelta(hours=1)

            bucket_deliveries = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=bucket_start,
                created_at__lt=bucket_end,
            )
            total_sent = bucket_deliveries.count()
            success_count = bucket_deliveries.filter(status=DeliveryStatus.SUCCESS).count()
            failed_count = bucket_deliveries.filter(status=DeliveryStatus.FAILED).count()
            success_rate = round((success_count / total_sent * 100), 2) if total_sent > 0 else 0.0

            result[bucket_start.isoformat()] = {
                'total_sent': total_sent,
                'success_count': success_count,
                'failed_count': failed_count,
                'success_rate': success_rate,
            }

        return result

    def calculate_response_time_distribution(self, endpoint: WebhookEndpoint, date_from, date_to) -> Dict[str, Any]:
        """
        Response-time distribution (min/max/avg/median/p95/p99) for one
        endpoint's successful deliveries over an explicit date range.
        """
        response_times = list(
            WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=date_from,
                created_at__lte=date_to,
                status=DeliveryStatus.SUCCESS,
                response_time_ms__isnull=False,
            ).values_list('response_time_ms', flat=True)
        )

        if not response_times:
            return {
                'total_requests': 0,
                'min_response_time_ms': None,
                'max_response_time_ms': None,
                'avg_response_time_ms': None,
                'median_response_time_ms': None,
                'p95_response_time_ms': None,
                'p99_response_time_ms': None,
            }

        response_times.sort()
        n = len(response_times)

        return {
            'total_requests': n,
            'min_response_time_ms': response_times[0],
            'max_response_time_ms': response_times[-1],
            'avg_response_time_ms': round(sum(response_times) / n, 2),
            'median_response_time_ms': statistics.median(response_times),
            'p95_response_time_ms': round(self._percentile(response_times, 0.95)),
            'p99_response_time_ms': round(self._percentile(response_times, 0.99)),
        }

    def calculate_error_rate_analytics(self, endpoint: WebhookEndpoint, date_from, date_to) -> Dict[str, Any]:
        """
        Error-rate breakdown for one endpoint over an explicit date range,
        keyed by HTTP status code for non-2xx/non-success deliveries.
        """
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint,
            created_at__gte=date_from,
            created_at__lte=date_to,
        )
        total_requests = deliveries.count()
        success_count = deliveries.filter(status=DeliveryStatus.SUCCESS).count()
        error_count = total_requests - success_count
        error_rate = round((error_count / total_requests * 100), 2) if total_requests > 0 else 0.0

        error_breakdown: Dict[str, int] = {}
        code_counts = (
            deliveries.exclude(status=DeliveryStatus.SUCCESS)
            .values('http_status_code')
            .annotate(count=Count('id'))
        )
        for row in code_counts:
            code = row['http_status_code']
            if code is not None:
                error_breakdown[str(code)] = row['count']

        return {
            'total_requests': total_requests,
            'success_count': success_count,
            'error_count': error_count,
            'error_rate': error_rate,
            'error_breakdown': error_breakdown,
        }

    def calculate_throughput_analytics(self, endpoint: WebhookEndpoint, date_from, date_to) -> Dict[str, Any]:
        """
        Requests-per-hour throughput for one endpoint over an explicit
        date range, bucketed into whole hours between date_from and date_to.
        """
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint,
            created_at__gte=date_from,
            created_at__lte=date_to,
        )
        total_requests = deliveries.count()

        if total_requests == 0:
            return {
                'total_requests': 0,
                'avg_requests_per_hour': 0.0,
                'max_requests_per_hour': 0,
                'min_requests_per_hour': 0,
                'avg_requests_per_minute': 0.0,
            }

        total_hours = max(int((date_to - date_from).total_seconds() // 3600), 1)
        hourly_counts = []
        for hour_offset in range(total_hours):
            bucket_start = date_from + timedelta(hours=hour_offset)
            bucket_end = bucket_start + timedelta(hours=1)
            count = deliveries.filter(
                created_at__gte=bucket_start, created_at__lt=bucket_end
            ).count()
            hourly_counts.append(count)

        total_minutes = total_hours * 60

        return {
            'total_requests': total_requests,
            'avg_requests_per_hour': round(sum(hourly_counts) / len(hourly_counts), 2),
            'max_requests_per_hour': max(hourly_counts),
            'min_requests_per_hour': min(hourly_counts),
            'avg_requests_per_minute': total_requests / total_minutes,
        }

    def get_event_type_analytics(self, endpoint: WebhookEndpoint, date_from, date_to) -> Dict[str, Dict[str, Any]]:
        """
        Break down delivery analytics by event type for one endpoint over
        an explicit date range.

        Args:
            endpoint: The WebhookEndpoint to analyze
            date_from: Start of the date range (inclusive)
            date_to: End of the date range (inclusive)

        Returns:
            Dict keyed by event_type, each value a dict with total_sent,
            success_count, failed_count, success_rate. Empty dict if no
            deliveries exist in the range.
        """
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint,
            created_at__gte=date_from,
            created_at__lte=date_to,
        )

        result: Dict[str, Dict[str, Any]] = {}
        event_types = deliveries.values_list('event_type', flat=True).distinct()
        for event_type in event_types:
            type_deliveries = deliveries.filter(event_type=event_type)
            total_sent = type_deliveries.count()
            success_count = type_deliveries.filter(status=DeliveryStatus.SUCCESS).count()
            failed_count = type_deliveries.filter(status=DeliveryStatus.FAILED).count()
            success_rate = round((success_count / total_sent * 100), 2) if total_sent > 0 else 0.0
            result[event_type] = {
                'total_sent': total_sent,
                'success_count': success_count,
                'failed_count': failed_count,
                'success_rate': success_rate,
            }

        return result
    
    def get_global_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get global analytics across all endpoints.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with global analytics data
        """
        try:
            from datetime import timedelta
            
            since = timezone.now() - timedelta(days=days)
            
            # Get delivery logs
            deliveries = WebhookDeliveryLog.objects.filter(created_at__gte=since)
            
            # Calculate overall statistics
            total_deliveries = deliveries.count()
            successful_deliveries = deliveries.filter(status=DeliveryStatus.SUCCESS).count()
            failed_deliveries = deliveries.filter(status=DeliveryStatus.FAILED).count()
            success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
            
            # Get endpoint statistics
            endpoint_stats = deliveries.values(
                'endpoint__label'
            ).annotate(
                count=Count('id'),
                successful=Count('id', filter=Q(status=DeliveryStatus.SUCCESS))
            ).order_by('-count')[:10]
            
            # Get event type statistics
            event_stats = deliveries.values('event_type').annotate(
                count=Count('id'),
                successful=Count('id', filter=Q(status=DeliveryStatus.SUCCESS))
            ).order_by('-count')[:10]
            
            # Get daily breakdown
            daily_breakdown = []
            for day in range(days):
                date = (timezone.now() - timedelta(days=day)).date()
                
                day_deliveries = deliveries.filter(created_at__date=date)
                
                daily_breakdown.append({
                    'date': date.isoformat(),
                    'total': day_deliveries.count(),
                    'successful': day_deliveries.filter(status=DeliveryStatus.SUCCESS).count(),
                    'failed': day_deliveries.filter(status=DeliveryStatus.FAILED).count()
                })
            
            return {
                'period_days': days,
                'total_deliveries': total_deliveries,
                'successful_deliveries': successful_deliveries,
                'failed_deliveries': failed_deliveries,
                'success_rate': round(success_rate, 2),
                'endpoint_statistics': list(endpoint_stats),
                'event_type_statistics': list(event_stats),
                'daily_breakdown': daily_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error getting global analytics: {str(e)}")
            return {
                'error': str(e),
                'period_days': days
            }

    def calculate_endpoint_health_metrics(self, endpoint: WebhookEndpoint, hours: int = 24) -> Dict[str, Any]:
        """
        Health-check uptime metrics for one endpoint over the last `hours`
        hours, based on WebhookHealthLog rows.
        """
        since = timezone.now() - timedelta(hours=hours)
        checks = WebhookHealthLog.objects.filter(endpoint=endpoint, checked_at__gte=since)

        total_checks = checks.count()
        if total_checks == 0:
            return {
                'total_checks': 0,
                'healthy_checks': 0,
                'unhealthy_checks': 0,
                'uptime_percentage': 0.0,
                'avg_response_time_ms': None,
                'min_response_time_ms': None,
                'max_response_time_ms': None,
            }

        healthy_checks = checks.filter(is_healthy=True).count()
        unhealthy_checks = total_checks - healthy_checks
        uptime_percentage = round((healthy_checks / total_checks * 100), 2)

        response_time_stats = checks.aggregate(
            avg_time=Avg('response_time_ms'),
            min_time=Min('response_time_ms'),
            max_time=Max('response_time_ms'),
        )
        avg_time = response_time_stats['avg_time']

        return {
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': unhealthy_checks,
            'uptime_percentage': uptime_percentage,
            'avg_response_time_ms': round(avg_time, 2) if avg_time is not None else None,
            'min_response_time_ms': response_time_stats['min_time'],
            'max_response_time_ms': response_time_stats['max_time'],
        }

    def calculate_system_overview_analytics(self, date_from, date_to) -> Dict[str, Any]:
        """
        System-wide delivery analytics across every endpoint with activity
        in an explicit date range.

        total_endpoints counts distinct endpoints that actually have
        deliveries in the range, not every registered WebhookEndpoint.
        """
        deliveries = WebhookDeliveryLog.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to,
        )
        total_requests = deliveries.count()

        if total_requests == 0:
            return {
                'total_endpoints': 0,
                'total_requests': 0,
                'total_successes': 0,
                'total_failures': 0,
                'overall_success_rate': 0.0,
                'avg_response_time_ms': None,
            }

        total_endpoints = deliveries.values('endpoint_id').distinct().count()
        total_successes = deliveries.filter(status=DeliveryStatus.SUCCESS).count()
        total_failures = deliveries.filter(status=DeliveryStatus.FAILED).count()
        overall_success_rate = round((total_successes / total_requests * 100), 2)

        avg_response_time = deliveries.filter(status=DeliveryStatus.SUCCESS).aggregate(
            avg=Avg('response_time_ms')
        )['avg']

        return {
            'total_endpoints': total_endpoints,
            'total_requests': total_requests,
            'total_successes': total_successes,
            'total_failures': total_failures,
            'overall_success_rate': overall_success_rate,
            'avg_response_time_ms': round(avg_response_time, 2) if avg_response_time is not None else None,
        }

    def get_performance_metrics(self, endpoint: WebhookEndpoint, date_from, date_to) -> Dict[str, Any]:
        """
        Response-time performance metrics (including spread/percentiles)
        for one endpoint's successful deliveries over an explicit date range.
        """
        response_times = list(
            WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=date_from,
                created_at__lte=date_to,
                status=DeliveryStatus.SUCCESS,
                response_time_ms__isnull=False,
            ).values_list('response_time_ms', flat=True)
        )

        if not response_times:
            return {
                'min_response_time_ms': None,
                'max_response_time_ms': None,
                'avg_response_time_ms': None,
                'median_response_time_ms': None,
                'p95_response_time_ms': None,
                'p99_response_time_ms': None,
                'std_deviation': None,
            }

        response_times.sort()

        return {
            'min_response_time_ms': response_times[0],
            'max_response_time_ms': response_times[-1],
            'avg_response_time_ms': round(sum(response_times) / len(response_times), 2),
            'median_response_time_ms': statistics.median(response_times),
            'p95_response_time_ms': round(self._percentile(response_times, 0.95)),
            'p99_response_time_ms': round(self._percentile(response_times, 0.99)),
            'std_deviation': round(statistics.pstdev(response_times), 2) if len(response_times) > 1 else 0.0,
        }
    
    def get_error_analysis(self, endpoint_id: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get error analysis for webhook deliveries.
        
        Args:
            endpoint_id: Optional endpoint ID to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with error analysis
        """
        try:
            from datetime import timedelta
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for failed deliveries
            failed_deliveries = WebhookDeliveryLog.objects.filter(
                created_at__gte=since,
                status=DeliveryStatus.FAILED
            )
            
            if endpoint_id:
                failed_deliveries = failed_deliveries.filter(endpoint_id=endpoint_id)
            
            # Get error breakdown
            error_breakdown = failed_deliveries.values('error_message').annotate(
                count=Count('id')
            ).order_by('-count')[:20]
            
            # Get HTTP status code breakdown
            status_code_breakdown = failed_deliveries.values('http_status_code').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Get endpoint breakdown
            endpoint_breakdown = failed_deliveries.values(
                'endpoint__label'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            return {
                'endpoint_id': endpoint_id,
                'period_days': days,
                'total_failures': failed_deliveries.count(),
                'error_breakdown': list(error_breakdown),
                'status_code_breakdown': list(status_code_breakdown),
                'endpoint_breakdown': list(endpoint_breakdown)
            }
            
        except Exception as e:
            logger.error(f"Error getting error analysis: {str(e)}")
            return {
                'endpoint_id': endpoint_id,
                'error': str(e),
                'period_days': days
            }

    def calculate_trend_analytics(self, endpoint: WebhookEndpoint, days: int = 7):
        """
        Day-over-day request-volume trend for one endpoint, most recent
        day first. Each day is compared against the day before it.

        Returns:
            List of `days` dicts (each with total_sent, trend_direction,
            trend_percentage), or {} if there's no delivery activity at
            all across the whole window.
        """
        now = timezone.now()
        daily_totals = []
        for day_offset in range(days + 1):  # +1 so the oldest day in the
            # window has a prior day to compare against
            date = (now - timedelta(days=day_offset)).date()
            start_of_day = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
            end_of_day = start_of_day + timedelta(days=1)
            total = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=start_of_day,
                created_at__lt=end_of_day,
            ).count()
            daily_totals.append(total)

        if sum(daily_totals) == 0:
            return {}

        trends = []
        for day_offset in range(days):
            today_total = daily_totals[day_offset]
            prior_total = daily_totals[day_offset + 1]

            if prior_total == 0:
                trend_direction = 'up' if today_total > 0 else 'stable'
                trend_percentage = 100.0 if today_total > 0 else 0.0
            else:
                change = round(((today_total - prior_total) / prior_total) * 100, 2)
                trend_direction = 'up' if change > 0 else ('down' if change < 0 else 'stable')
                trend_percentage = change

            trends.append({
                'date': (now - timedelta(days=day_offset)).date().isoformat(),
                'total_sent': today_total,
                'trend_direction': trend_direction,
                'trend_percentage': trend_percentage,
            })

        return trends

    def export_analytics_data(self, endpoint: WebhookEndpoint, date_from, date_to, format: str = 'json') -> str:
        """
        Export one endpoint's analytics for an explicit date range as a
        JSON or CSV string (not a dict — the return value IS the file
        content, ready to write out or return as an HTTP attachment).
        """
        analytics = self.calculate_endpoint_analytics(endpoint=endpoint, date_from=date_from, date_to=date_to)
        summary = {
            'endpoint_id': str(endpoint.id),
            'total_requests': analytics['total_sent'],
            'success_count': analytics['success_count'],
            'failed_count': analytics['failed_count'],
            'success_rate': analytics['success_rate'],
            'avg_response_time_ms': analytics['avg_response_time_ms'],
        }

        if format == 'csv':
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Date', 'Total Requests', 'Success Rate', 'Avg Response Time (ms)'])
            writer.writerow([
                f"{date_from.date().isoformat()} to {date_to.date().isoformat()}",
                summary['total_requests'],
                summary['success_rate'],
                summary['avg_response_time_ms'],
            ])
            return output.getvalue()

        import json
        return json.dumps(summary)

    def generate_analytics_report(self, endpoint: WebhookEndpoint = None, endpoints: List[WebhookEndpoint] = None,
                                   date_from=None, date_to=None) -> Dict[str, Any]:
        """
        Composite analytics report for either one endpoint (full
        breakdown across every metric this service computes) or a list
        of endpoints (summary + per-endpoint analytics only).
        """
        if endpoint is not None:
            endpoint_analytics = self.calculate_endpoint_analytics(
                endpoint=endpoint, date_from=date_from, date_to=date_to
            )
            return {
                'summary': {
                    'total_requests': endpoint_analytics['total_sent'],
                    'success_rate': endpoint_analytics['success_rate'],
                    'avg_response_time_ms': endpoint_analytics['avg_response_time_ms'],
                },
                'endpoint_analytics': endpoint_analytics,
                'event_type_analytics': self.get_event_type_analytics(
                    endpoint=endpoint, date_from=date_from, date_to=date_to
                ),
                'hourly_analytics': self.calculate_hourly_analytics(endpoint=endpoint),
                'response_time_distribution': self.calculate_response_time_distribution(
                    endpoint=endpoint, date_from=date_from, date_to=date_to
                ),
                'error_rate_analytics': self.calculate_error_rate_analytics(
                    endpoint=endpoint, date_from=date_from, date_to=date_to
                ),
                'throughput_analytics': self.calculate_throughput_analytics(
                    endpoint=endpoint, date_from=date_from, date_to=date_to
                ),
                'health_metrics': self.calculate_endpoint_health_metrics(endpoint=endpoint),
            }

        endpoints = endpoints or []
        per_endpoint = [
            self.calculate_endpoint_analytics(endpoint=e, date_from=date_from, date_to=date_to)
            for e in endpoints
        ]
        total_requests = sum(a['total_sent'] for a in per_endpoint)
        total_success = sum(a['success_count'] for a in per_endpoint)
        success_rate = round((total_success / total_requests * 100), 2) if total_requests > 0 else 0.0

        return {
            'summary': {
                'total_requests': total_requests,
                'success_rate': success_rate,
            },
            'endpoint_analytics': per_endpoint,
        }

    def cleanup_old_analytics(self, days: int = 365) -> Dict[str, Any]:
        """
        Clean up old analytics records.
        
        Args:
            days: Number of days to keep analytics
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Delete old analytics
            old_analytics = WebhookAnalytics.objects.filter(date__lt=cutoff_date.date())
            deleted_count = old_analytics.count()
            old_analytics.delete()
            
            return {
                'deleted_records': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'days': days
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old analytics: {str(e)}")
            return {
                'error': str(e),
                'days': days
            }
    
    def export_analytics(self, endpoint_id: str = None, days: int = 30, format: str = 'json') -> Dict[str, Any]:
        """
        Export analytics data.
        
        Args:
            endpoint_id: Optional endpoint ID to filter by
            days: Number of days to export
            format: Export format (json or csv)
            
        Returns:
            Dictionary with export results
        """
        try:
            if endpoint_id:
                analytics_data = self.get_endpoint_analytics(endpoint_id, days)
            else:
                analytics_data = self.get_global_analytics(days)
            
            if format == 'csv':
                # Convert to CSV format
                import csv
                import io
                
                output = io.StringIO()
                
                if 'daily_data' in analytics_data:
                    writer = csv.writer(output)
                    writer.writerow(['date', 'total_deliveries', 'successful_deliveries', 'failed_deliveries', 'success_rate', 'avg_response_time_ms'])
                    
                    for day_data in analytics_data['daily_data']:
                        writer.writerow([
                            day_data['date'],
                            day_data['total_deliveries'],
                            day_data['successful_deliveries'],
                            day_data['failed_deliveries'],
                            day_data['success_rate'],
                            day_data['avg_response_time_ms']
                        ])
                
                return {
                    'format': 'csv',
                    'data': output.getvalue(),
                    'filename': f"webhook_analytics_{endpoint_id}_{days}d.csv"
                }
            else:
                return {
                    'format': 'json',
                    'data': analytics_data,
                    'filename': f"webhook_analytics_{endpoint_id}_{days}d.json"
                }
                
        except Exception as e:
            logger.error(f"Error exporting analytics: {str(e)}")
            return {
                'error': str(e)
            }
    
    def get_analytics_summary(self, endpoint_id: str = None) -> Dict[str, Any]:
        """
        Get a quick analytics summary.
        
        Args:
            endpoint_id: Optional endpoint ID to filter by
            
        Returns:
            Dictionary with summary statistics
        """
        try:
            # Get last 7 days and last 30 days
            last_7_days = self.get_global_analytics(7) if not endpoint_id else self.get_endpoint_analytics(endpoint_id, 7)
            last_30_days = self.get_global_analytics(30) if not endpoint_id else self.get_endpoint_analytics(endpoint_id, 30)
            
            # Calculate trends
            success_rate_trend = 0
            if last_30_days.get('success_rate', 0) > 0:
                success_rate_trend = ((last_7_days.get('success_rate', 0) - last_30_days.get('success_rate', 0)) / last_30_days.get('success_rate', 1)) * 100
            
            volume_trend = 0
            if last_30_days.get('total_deliveries', 0) > 0:
                volume_trend = ((last_7_days.get('total_deliveries', 0) - last_30_days.get('total_deliveries', 0)) / last_30_days.get('total_deliveries', 1)) * 100
            
            return {
                'endpoint_id': endpoint_id,
                'last_7_days': {
                    'total_deliveries': last_7_days.get('total_deliveries', 0),
                    'success_rate': last_7_days.get('success_rate', 0)
                },
                'last_30_days': {
                    'total_deliveries': last_30_days.get('total_deliveries', 0),
                    'success_rate': last_30_days.get('success_rate', 0)
                },
                'trends': {
                    'success_rate_trend': round(success_rate_trend, 2),
                    'volume_trend': round(volume_trend, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics summary: {str(e)}")
            return {
                'endpoint_id': endpoint_id,
                'error': str(e)
            }