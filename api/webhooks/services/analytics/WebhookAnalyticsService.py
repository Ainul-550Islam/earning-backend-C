"""Webhook Analytics Service

This module provides daily statistics collection and success rate monitoring.
"""

import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Avg, Sum, Q

from ...models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog, WebhookAnalytics
from ...constants import DeliveryStatus

logger = logging.getLogger(__name__)


class WebhookAnalyticsService:
    """Service for collecting and analyzing webhook statistics."""
    
    def __init__(self):
        """Initialize the webhook analytics service."""
        self.logger = logger
    
    def generate_daily_analytics(self, date: str = None) -> Dict[str, Any]:
        """
        Generate daily analytics for all endpoints.
        
        Args:
            date: Date to generate analytics for (defaults to yesterday)
            
        Returns:
            Dictionary with analytics results
        """
        try:
            if date is None:
                date = (timezone.now() - timezone.timedelta(days=1)).date()
            
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
            end_of_day = start_of_day + timezone.timedelta(days=1)
            
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
                    avg_time=Avg('duration_ms')
                )['avg_time'] or 0
            
            # Calculate event type breakdown
            event_breakdown = deliveries.values('event_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Calculate hourly breakdown
            hourly_breakdown = []
            for hour in range(24):
                hour_start = start_of_day + timezone.timedelta(hours=hour)
                hour_end = hour_start + timezone.timedelta(hours=1)
                
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
    
    def get_event_type_analytics(self, event_type: str, days: int = 30) -> Dict[str, Any]:
        """
        Get analytics for a specific event type over a period.
        
        Args:
            event_type: The event type
            days: Number of days to look back
            
        Returns:
            Dictionary with analytics data
        """
        try:
            from datetime import timedelta
            
            since = timezone.now() - timedelta(days=days)
            
            # Get delivery logs for event type
            deliveries = WebhookDeliveryLog.objects.filter(
                event_type=event_type,
                created_at__gte=since
            )
            
            # Calculate overall statistics
            total_deliveries = deliveries.count()
            successful_deliveries = deliveries.filter(status=DeliveryStatus.SUCCESS).count()
            success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
            
            # Get endpoint breakdown
            endpoint_breakdown = deliveries.values(
                'endpoint__label',
                'endpoint__url'
            ).annotate(
                count=Count('id'),
                successful=Count('id', filter=Q(status=DeliveryStatus.SUCCESS))
            ).order_by('-count')
            
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
                'event_type': event_type,
                'period_days': days,
                'total_deliveries': total_deliveries,
                'successful_deliveries': successful_deliveries,
                'success_rate': round(success_rate, 2),
                'endpoint_breakdown': list(endpoint_breakdown),
                'daily_breakdown': daily_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error getting event type analytics: {str(e)}")
            return {
                'event_type': event_type,
                'error': str(e)
            }
    
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
    
    def get_performance_metrics(self, endpoint_id: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get performance metrics for endpoints.
        
        Args:
            endpoint_id: Optional endpoint ID to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            from datetime import timedelta
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for deliveries
            deliveries = WebhookDeliveryLog.objects.filter(
                created_at__gte=since,
                status=DeliveryStatus.SUCCESS
            )
            
            if endpoint_id:
                deliveries = deliveries.filter(endpoint_id=endpoint_id)
            
            # Calculate response time statistics
            response_times = deliveries.values_list('duration_ms', flat=True)
            
            if not response_times.exists():
                return {
                    'endpoint_id': endpoint_id,
                    'period_days': days,
                    'total_requests': 0,
                    'avg_response_time_ms': 0,
                    'min_response_time_ms': 0,
                    'max_response_time_ms': 0,
                    'p95_response_time_ms': 0,
                    'p99_response_time_ms': 0
                }
            
            response_times_list = list(response_times)
            response_times_list.sort()
            
            # Calculate percentiles
            p95_index = int(len(response_times_list) * 0.95)
            p99_index = int(len(response_times_list) * 0.99)
            
            return {
                'endpoint_id': endpoint_id,
                'period_days': days,
                'total_requests': len(response_times_list),
                'avg_response_time_ms': round(sum(response_times_list) / len(response_times_list), 2),
                'min_response_time_ms': min(response_times_list),
                'max_response_time_ms': max(response_times_list),
                'p95_response_time_ms': response_times_list[p95_index],
                'p99_response_time_ms': response_times_list[p99_index]
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            return {
                'endpoint_id': endpoint_id,
                'error': str(e),
                'period_days': days
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
