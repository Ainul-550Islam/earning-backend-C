"""Health Check Tasks

This module contains background tasks for webhook endpoint health monitoring.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from ..models import WebhookEndpoint, WebhookHealthLog
from ..services.analytics import HealthMonitorService
from ..choices import WebhookStatus


@shared_task
def health_check_all_endpoints():
    """
    Perform health checks on all active endpoints.
    This task is typically run on a schedule (e.g., every 5 minutes).
    
    Returns:
        dict: Summary of health check operations
    """
    try:
        # Get all active endpoints
        active_endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE)
        
        health_monitor = HealthMonitorService()
        checked_count = 0
        healthy_count = 0
        unhealthy_count = 0
        error_count = 0
        
        for endpoint in active_endpoints:
            try:
                # Perform health check
                health_result = health_monitor.check_endpoint_health(endpoint)
                
                if health_result['is_healthy']:
                    healthy_count += 1
                else:
                    unhealthy_count += 1
                
                checked_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"Failed to check health for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_checked': checked_count,
            'healthy_endpoints': healthy_count,
            'unhealthy_endpoints': unhealthy_count,
            'error_count': error_count,
            'check_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def health_check_endpoint(self, endpoint_id):
    """
    Perform health check on a specific endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint to check
        
    Returns:
        dict: Result of the health check
    """
    try:
        # Get the endpoint
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        
        # Perform health check
        health_monitor = HealthMonitorService()
        health_result = health_monitor.check_endpoint_health(endpoint)
        
        return {
            'success': True,
            'endpoint_id': str(endpoint_id),
            'is_healthy': health_result['is_healthy'],
            'status_code': health_result.get('status_code'),
            'response_time_ms': health_result.get('response_time_ms'),
            'error': health_result.get('error'),
            'check_timestamp': timezone.now().isoformat()
        }
        
    except WebhookEndpoint.DoesNotExist:
        return {
            'success': False,
            'error': 'Endpoint not found',
            'endpoint_id': str(endpoint_id)
        }
    except Exception as e:
        # Retry the task if there's an unexpected error
        raise self.retry(exc=e, countdown=60)


@shared_task
def health_check_endpoint_batch(endpoint_ids):
    """
    Perform health checks on a batch of endpoints.
    
    Args:
        endpoint_ids: List of endpoint IDs to check
        
    Returns:
        dict: Summary of health check operations
    """
    try:
        # Get endpoints
        endpoints = WebhookEndpoint.objects.filter(id__in=endpoint_ids)
        
        health_monitor = HealthMonitorService()
        checked_count = 0
        healthy_count = 0
        unhealthy_count = 0
        error_count = 0
        
        for endpoint in endpoints:
            try:
                # Perform health check
                health_result = health_monitor.check_endpoint_health(endpoint)
                
                if health_result['is_healthy']:
                    healthy_count += 1
                else:
                    unhealthy_count += 1
                
                checked_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"Failed to check health for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_checked': checked_count,
            'healthy_endpoints': healthy_count,
            'unhealthy_endpoints': unhealthy_count,
            'error_count': error_count,
            'check_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def schedule_health_checks():
    """
    Schedule health checks for endpoints that need monitoring.
    This task runs periodically to ensure endpoints are being checked regularly.
    
    Returns:
        dict: Summary of scheduled health checks
    """
    try:
        # Get endpoints that need health checks
        # Check endpoints that haven't been checked in the last 5 minutes
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        
        endpoints_needing_check = WebhookEndpoint.objects.filter(
            status=WebhookStatus.ACTIVE
        ).exclude(
            health_logs__checked_at__gte=five_minutes_ago
        ).distinct()
        
        scheduled_count = 0
        
        for endpoint in endpoints_needing_check:
            try:
                # Queue individual health check task
                health_check_endpoint.delay(str(endpoint.id))
                scheduled_count += 1
            except Exception as e:
                print(f"Failed to schedule health check for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'scheduled_count': scheduled_count,
            'endpoints_needing_check': endpoints_needing_check.count(),
            'schedule_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_health_logs(days=30):
    """
    Clean up old health logs.
    
    Args:
        days: Number of days to keep health logs (default: 30)
        
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old health logs
        old_logs = WebhookHealthLog.objects.filter(
            checked_at__lt=cutoff_date
        )
        
        deleted_count = 0
        
        for log in old_logs:
            try:
                log.delete()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete health log {log.id}: {e}")
        
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


@shared_task
def generate_health_report(hours=24):
    """
    Generate a health report for all endpoints.
    
    Args:
        hours: Time window in hours for the report (default: 24)
        
    Returns:
        dict: Health report summary
    """
    try:
        # Calculate time window
        since = timezone.now() - timedelta(hours=hours)
        
        # Get health statistics
        total_checks = WebhookHealthLog.objects.filter(checked_at__gte=since).count()
        healthy_checks = WebhookHealthLog.objects.filter(
            checked_at__gte=since,
            is_healthy=True
        ).count()
        unhealthy_checks = total_checks - healthy_checks
        
        # Get endpoint statistics
        endpoint_stats = {}
        endpoints = WebhookEndpoint.objects.all()
        
        for endpoint in endpoints:
            endpoint_health = endpoint.health_logs.filter(checked_at__gte=since)
            if endpoint_health.exists():
                healthy = endpoint_health.filter(is_healthy=True).count()
                total = endpoint_health.count()
                uptime = (healthy / total * 100) if total > 0 else 0
                
                endpoint_stats[str(endpoint.id)] = {
                    'endpoint_label': endpoint.label or endpoint.url,
                    'total_checks': total,
                    'healthy_checks': healthy,
                    'uptime_percentage': round(uptime, 2)
                }
        
        return {
            'success': True,
            'report_period_hours': hours,
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': unhealthy_checks,
            'overall_uptime': round((healthy_checks / total_checks * 100) if total_checks > 0 else 0, 2),
            'endpoint_stats': endpoint_stats,
            'report_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'hours': hours
        }


@shared_task
def health_monitor_summary():
    """
    Get a summary of health monitoring status.
    
    Returns:
        dict: Health monitoring summary
    """
    try:
        from django.db.models import Count, Avg
        
        # Get overall statistics
        total_endpoints = WebhookEndpoint.objects.count()
        active_endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE).count()
        
        # Get recent health check statistics
        last_hour = timezone.now() - timedelta(hours=1)
        recent_checks = WebhookHealthLog.objects.filter(checked_at__gte=last_hour)
        
        if recent_checks.exists():
            avg_response_time = recent_checks.aggregate(
                avg_response=Avg('response_time_ms')
            )['avg_response'] or 0
            
            healthy_percentage = (
                recent_checks.filter(is_healthy=True).count() / recent_checks.count() * 100
            )
        else:
            avg_response_time = 0
            healthy_percentage = 0
        
        return {
            'success': True,
            'total_endpoints': total_endpoints,
            'active_endpoints': active_endpoints,
            'checks_last_hour': recent_checks.count(),
            'healthy_percentage_last_hour': round(healthy_percentage, 2),
            'avg_response_time_last_hour': round(avg_response_time, 2),
            'summary_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
