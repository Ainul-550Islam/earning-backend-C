"""Analytics Tasks

This module contains background tasks for webhook analytics and statistics.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Sum

from ..models import WebhookEndpoint, WebhookDeliveryLog, WebhookAnalytics, WebhookEventStat
from ..services.analytics import WebhookAnalyticsService


@shared_task
def generate_daily_analytics(endpoint_id, days=7):
    """
    Generate daily analytics for a specific endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint
        days: Number of days to generate analytics for (default: 7)
        
    Returns:
        dict: Result of analytics generation
    """
    try:
        # Get the endpoint
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        
        # Generate analytics
        analytics_service = WebhookAnalyticsService()
        analytics_records = analytics_service.generate_daily_analytics(
            endpoint=endpoint,
            days=days
        )
        
        return {
            'success': True,
            'endpoint_id': str(endpoint_id),
            'records_generated': len(analytics_records),
            'days': days,
            'generation_timestamp': timezone.now().isoformat()
        }
        
    except WebhookEndpoint.DoesNotExist:
        return {
            'success': False,
            'error': 'Endpoint not found',
            'endpoint_id': str(endpoint_id)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'endpoint_id': str(endpoint_id)
        }


@shared_task
def generate_daily_analytics_all_endpoints(days=7):
    """
    Generate daily analytics for all endpoints.
    
    Args:
        days: Number of days to generate analytics for (default: 7)
        
    Returns:
        dict: Summary of analytics generation
    """
    try:
        # Get all endpoints
        endpoints = WebhookEndpoint.objects.all()
        
        analytics_service = WebhookAnalyticsService()
        total_records = 0
        success_count = 0
        error_count = 0
        
        for endpoint in endpoints:
            try:
                # Generate analytics for this endpoint
                analytics_records = analytics_service.generate_daily_analytics(
                    endpoint=endpoint,
                    days=days
                )
                total_records += len(analytics_records)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"Failed to generate analytics for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_processed': endpoints.count(),
            'success_count': success_count,
            'error_count': error_count,
            'total_records_generated': total_records,
            'days': days,
            'generation_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'days': days
        }


@shared_task
def generate_event_statistics(endpoint_id, days=7):
    """
    Generate event type statistics for a specific endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint
        days: Number of days to generate statistics for (default: 7)
        
    Returns:
        dict: Result of statistics generation
    """
    try:
        # Get the endpoint
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get event statistics
        event_stats = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).values('event_type').annotate(
            total_count=Count('id'),
            success_count=Count('id', filter=models.Q(status='success')),
            failed_count=Count('id', filter=models.Q(status='failed')),
            avg_response_time=Avg('duration_ms')
        ).order_by('-total_count')
        
        # Create or update event statistics records
        created_count = 0
        
        for stat in event_stats:
            try:
                # Create or update event stat record
                WebhookEventStat.objects.update_or_create(
                    endpoint=endpoint,
                    event_type=stat['event_type'],
                    date=end_date.date(),
                    defaults={
                        'count': stat['total_count'],
                        'success_count': stat['success_count'],
                        'avg_response_time_ms': stat['avg_response_time'] or 0,
                        'created_by': endpoint.created_by
                    }
                )
                created_count += 1
                
            except Exception as e:
                print(f"Failed to create event stat for {stat['event_type']}: {e}")
        
        return {
            'success': True,
            'endpoint_id': str(endpoint_id),
            'event_types_processed': created_count,
            'days': days,
            'generation_timestamp': timezone.now().isoformat()
        }
        
    except WebhookEndpoint.DoesNotExist:
        return {
            'success': False,
            'error': 'Endpoint not found',
            'endpoint_id': str(endpoint_id)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'endpoint_id': str(endpoint_id)
        }


@shared_task
def generate_event_statistics_all_endpoints(days=7):
    """
    Generate event type statistics for all endpoints.
    
    Args:
        days: Number of days to generate statistics for (default: 7)
        
    Returns:
        dict: Summary of statistics generation
    """
    try:
        # Get all endpoints
        endpoints = WebhookEndpoint.objects.all()
        
        total_event_types = 0
        success_count = 0
        error_count = 0
        
        for endpoint in endpoints:
            try:
                # Generate event statistics for this endpoint
                result = generate_event_statistics(str(endpoint.id), days)
                if result['success']:
                    total_event_types += result['event_types_processed']
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"Failed to generate event statistics for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_processed': endpoints.count(),
            'success_count': success_count,
            'error_count': error_count,
            'total_event_types_processed': total_event_types,
            'days': days,
            'generation_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'days': days
        }


@shared_task
def calculate_performance_metrics(endpoint_id, days=7):
    """
    Calculate performance metrics for a specific endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint
        days: Number of days to calculate metrics for (default: 7)
        
    Returns:
        dict: Result of performance metrics calculation
    """
    try:
        # Get the endpoint
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get performance metrics
        delivery_logs = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint,
            created_at__gte=start_date,
            created_at__lte=end_date,
            status='success'
        ).aggregate(
            avg_response_time=Avg('duration_ms'),
            min_response_time=Min('duration_ms'),
            max_response_time=Max('duration_ms'),
            total_requests=Count('id')
        )
        
        # Calculate percentiles
        response_times = list(
            WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                created_at__gte=start_date,
                created_at__lte=end_date,
                status='success'
            ).values_list('duration_ms', flat=True)
        )
        
        if response_times:
            response_times.sort()
            total_count = len(response_times)
            p95_index = int(total_count * 0.95)
            p99_index = int(total_count * 0.99)
            median_index = total_count // 2
            
            p95_response_time = response_times[p95_index] if p95_index < total_count else response_times[-1]
            p99_response_time = response_times[p99_index] if p99_index < total_count else response_times[-1]
            median_response_time = response_times[median_index]
        else:
            p95_response_time = 0
            p99_response_time = 0
            median_response_time = 0
        
        return {
            'success': True,
            'endpoint_id': str(endpoint_id),
            'performance_metrics': {
                'avg_response_time_ms': delivery_logs['avg_response_time'] or 0,
                'min_response_time_ms': delivery_logs['min_response_time'] or 0,
                'max_response_time_ms': delivery_logs['max_response_time'] or 0,
                'median_response_time_ms': median_response_time,
                'p95_response_time_ms': p95_response_time,
                'p99_response_time_ms': p99_response_time,
                'total_requests': delivery_logs['total_requests'] or 0
            },
            'days': days,
            'calculation_timestamp': timezone.now().isoformat()
        }
        
    except WebhookEndpoint.DoesNotExist:
        return {
            'success': False,
            'error': 'Endpoint not found',
            'endpoint_id': str(endpoint_id)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'endpoint_id': str(endpoint_id)
        }


@shared_task
def calculate_performance_metrics_all_endpoints(days=7):
    """
    Calculate performance metrics for all endpoints.
    
    Args:
        days: Number of days to calculate metrics for (default: 7)
        
    Returns:
        dict: Summary of performance metrics calculation
    """
    try:
        # Get all endpoints
        endpoints = WebhookEndpoint.objects.all()
        
        success_count = 0
        error_count = 0
        
        for endpoint in endpoints:
            try:
                # Calculate performance metrics for this endpoint
                result = calculate_performance_metrics(str(endpoint.id), days)
                if result['success']:
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"Failed to calculate performance metrics for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_processed': endpoints.count(),
            'success_count': success_count,
            'error_count': error_count,
            'days': days,
            'calculation_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'days': days
        }


@shared_task
def generate_hourly_analytics():
    """
    Generate hourly analytics for all endpoints.
    This task is typically run on a schedule (e.g., every hour).
    
    Returns:
        dict: Summary of hourly analytics generation
    """
    try:
        # Calculate time window (last hour)
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=1)
        
        # Get all endpoints
        endpoints = WebhookEndpoint.objects.all()
        
        total_records = 0
        success_count = 0
        error_count = 0
        
        for endpoint in endpoints:
            try:
                # Get hourly statistics
                hourly_stats = WebhookDeliveryLog.objects.filter(
                    endpoint=endpoint,
                    created_at__gte=start_time,
                    created_at__lte=end_time
                ).aggregate(
                    total_count=Count('id'),
                    success_count=Count('id', filter=models.Q(status='success')),
                    failed_count=Count('id', filter=models.Q(status='failed')),
                    avg_response_time=Avg('duration_ms')
                )
                
                if hourly_stats['total_count'] > 0:
                    # Create hourly analytics record
                    WebhookAnalytics.objects.update_or_create(
                        endpoint=endpoint,
                        date=end_time.date(),
                        hour=end_time.hour,
                        defaults={
                            'total_sent': hourly_stats['total_count'],
                            'success_count': hourly_stats['success_count'],
                            'failed_count': hourly_stats['failed_count'],
                            'avg_latency_ms': hourly_stats['avg_response_time'] or 0,
                            'success_rate': (hourly_stats['success_count'] / hourly_stats['total_count'] * 100),
                            'created_by': endpoint.created_by
                        }
                    )
                    total_records += 1
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"Failed to generate hourly analytics for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_processed': endpoints.count(),
            'success_count': success_count,
            'error_count': error_count,
            'records_generated': total_records,
            'hour': end_time.hour,
            'generation_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_analytics(days=365):
    """
    Clean up old analytics records.
    
    Args:
        days: Number of days to keep analytics records (default: 365)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old analytics records
        old_analytics = WebhookAnalytics.objects.filter(
            date__lt=cutoff_date.date()
        )
        
        deleted_count = 0
        
        for analytics in old_analytics:
            try:
                analytics.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete analytics record {analytics.id}: {e}")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'days': days
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'days': days
        }
