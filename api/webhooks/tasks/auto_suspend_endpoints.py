"""Auto Suspend Endpoints Task

This module contains the background task for automatically suspending unhealthy endpoints.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from ..models import WebhookEndpoint, WebhookHealthLog
from ..services.analytics import HealthMonitorService
from ..choices import WebhookStatus


@shared_task
def auto_suspend_endpoints(consecutive_failures=3, hours=24):
    """
    Automatically suspend endpoints with consecutive health check failures.
    
    Args:
        consecutive_failures: Number of consecutive failures to trigger suspension (default: 3)
        hours: Time window in hours to check for failures (default: 24)
        
    Returns:
        dict: Summary of suspension operations
    """
    try:
        # Calculate time window
        since = timezone.now() - timedelta(hours=hours)
        
        # Get endpoints with consecutive failures
        suspended_count = 0
        endpoint_count = 0
        
        # Get all active endpoints
        active_endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE)
        
        for endpoint in active_endpoints:
            try:
                # Get recent health logs for this endpoint
                recent_logs = WebhookHealthLog.objects.filter(
                    endpoint=endpoint,
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
                            # Suspend the endpoint
                            health_monitor = HealthMonitorService()
                            result = health_monitor.auto_suspend_unhealthy_endpoint(
                                endpoint,
                                consecutive_failures=consecutive_failures
                            )
                            
                            if result['suspended']:
                                suspended_count += 1
                            break
                
                endpoint_count += 1
                
            except Exception as e:
                print(f"Failed to process endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_checked': endpoint_count,
            'endpoints_suspended': suspended_count,
            'consecutive_failures': consecutive_failures,
            'hours': hours
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'consecutive_failures': consecutive_failures,
            'hours': hours
        }


@shared_task
def auto_suspend_by_success_rate(success_rate_threshold=70, hours=24):
    """
    Automatically suspend endpoints with low success rates.
    
    Args:
        success_rate_threshold: Success rate percentage threshold (default: 70)
        hours: Time window in hours to check success rate (default: 24)
        
    Returns:
        dict: Summary of suspension operations
    """
    try:
        # Calculate time window
        since = timezone.now() - timedelta(hours=hours)
        
        # Get endpoints with low success rates
        suspended_count = 0
        endpoint_count = 0
        
        # Get all active endpoints
        active_endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE)
        
        for endpoint in active_endpoints:
            try:
                # Get delivery logs for this endpoint
                delivery_logs = endpoint.delivery_logs.filter(
                    created_at__gte=since
                )
                
                if delivery_logs.exists():
                    # Calculate success rate
                    total_count = delivery_logs.count()
                    success_count = delivery_logs.filter(status='success').count()
                    success_rate = (success_count / total_count) * 100
                    
                    if success_rate < success_rate_threshold:
                        # Suspend the endpoint
                        endpoint.status = WebhookStatus.SUSPENDED
                        endpoint.suspension_reason = f"Low success rate: {success_rate:.1f}% < {success_rate_threshold}%"
                        endpoint.save()
                        
                        # Create health log
                        WebhookHealthLog.objects.create(
                            endpoint=endpoint,
                            is_healthy=False,
                            response_time_ms=0,
                            status_code=0,
                            error=f"Auto-suspended due to low success rate: {success_rate:.1f}%"
                        )
                        
                        suspended_count += 1
                
                endpoint_count += 1
                
            except Exception as e:
                print(f"Failed to process endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_checked': endpoint_count,
            'endpoints_suspended': suspended_count,
            'success_rate_threshold': success_rate_threshold,
            'hours': hours
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'success_rate_threshold': success_rate_threshold,
            'hours': hours
        }


@shared_task
def auto_resume_endpoints(hours=6):
    """
    Automatically resume suspended endpoints that are now healthy.
    
    Args:
        hours: Time window in hours to check for health (default: 6)
        
    Returns:
        dict: Summary of resume operations
    """
    try:
        # Calculate time window
        since = timezone.now() - timedelta(hours=hours)
        
        # Get suspended endpoints
        suspended_endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.SUSPENDED)
        
        resumed_count = 0
        
        for endpoint in suspended_endpoints:
            try:
                # Get recent health logs for this endpoint
                recent_logs = WebhookHealthLog.objects.filter(
                    endpoint=endpoint,
                    checked_at__gte=since
                ).order_by('-checked_at')
                
                if recent_logs.exists():
                    # Check if the most recent logs are healthy
                    recent_healthy_count = 0
                    for log in recent_logs:
                        if log.is_healthy:
                            recent_healthy_count += 1
                        else:
                            break  # Stop at first unhealthy check
                        
                        if recent_healthy_count >= 3:  # 3 consecutive healthy checks
                            # Resume the endpoint
                            endpoint.status = WebhookStatus.ACTIVE
                            endpoint.suspension_reason = None
                            endpoint.save()
                            
                            # Create health log
                            WebhookHealthLog.objects.create(
                                endpoint=endpoint,
                                is_healthy=True,
                                response_time_ms=0,
                                status_code=200,
                                error="Auto-resumed after health recovery"
                            )
                            
                            resumed_count += 1
                            break
                
            except Exception as e:
                print(f"Failed to process endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_checked': suspended_endpoints.count(),
            'endpoints_resumed': resumed_count,
            'hours': hours
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'hours': hours
        }


@shared_task
def check_endpoint_health_summary():
    """
    Get a summary of endpoint health status.
    
    Returns:
        dict: Health summary statistics
    """
    try:
        from django.db.models import Count
        
        # Get counts by status
        status_counts = WebhookEndpoint.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Get health statistics
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        
        health_stats = {
            'total_endpoints': WebhookEndpoint.objects.count(),
            'active_endpoints': WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE).count(),
            'suspended_endpoints': WebhookEndpoint.objects.filter(status=WebhookStatus.SUSPENDED).count(),
            'health_checks_last_24h': WebhookHealthLog.objects.filter(checked_at__gte=last_24h).count(),
            'healthy_checks_last_24h': WebhookHealthLog.objects.filter(
                checked_at__gte=last_24h,
                is_healthy=True
            ).count(),
            'unhealthy_checks_last_24h': WebhookHealthLog.objects.filter(
                checked_at__gte=last_24h,
                is_healthy=False
            ).count(),
        }
        
        return {
            'success': True,
            'status_counts': list(status_counts),
            'health_stats': health_stats,
            'summary_timestamp': now.isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
