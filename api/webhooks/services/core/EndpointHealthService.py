"""Endpoint Health Service

This module provides webhook endpoint health monitoring with ping functionality and auto-suspension.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import WebhookEndpoint, WebhookHealthLog
from ..choices import WebhookStatus

logger = logging.getLogger(__name__)


class EndpointHealthService:
    """Service for monitoring webhook endpoint health with ping and auto-suspension."""
    
    def __init__(self):
        """Initialize the endpoint health service."""
        self.default_timeout = getattr(settings, 'WEBHOOK_HEALTH_TIMEOUT', 10)
        self.max_consecutive_failures = getattr(settings, 'WEBHOOK_MAX_CONSECUTIVE_FAILURES', 3)
        self.health_check_interval = getattr(settings, 'WEBHOOK_HEALTH_CHECK_INTERVAL', 300)  # 5 minutes
        self.auto_suspend_enabled = getattr(settings, 'WEBHOOK_AUTO_SUSPEND_ENABLED', True)
    
    def ping_endpoint(self, endpoint: WebhookEndpoint) -> Dict[str, Any]:
        """
        Ping a webhook endpoint to check its health.
        
        Args:
            endpoint: The webhook endpoint to ping
            
        Returns:
            Dictionary with health check results
        """
        try:
            start_time = time.time()
            
            # Prepare health check payload
            health_payload = {
                'type': 'health_check',
                'timestamp': timezone.now().isoformat(),
                'endpoint_id': str(endpoint.id),
                'ping': True
            }
            
            # Make health check request
            response = self._make_health_check_request(endpoint, health_payload)
            
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            # Determine health status
            is_healthy = self._determine_health_status(response)
            
            # Create health log
            health_log = WebhookHealthLog.objects.create(
                endpoint=endpoint,
                is_healthy=is_healthy,
                status_code=response.get('status_code', 0),
                response_time_ms=response_time_ms,
                error=response.get('error') if not is_healthy else None,
                checked_at=timezone.now(),
                created_by=endpoint.owner
            )
            
            # Check for auto-suspension
            if self.auto_suspend_enabled and not is_healthy:
                self._check_auto_suspension(endpoint)
            
            result = {
                'endpoint_id': str(endpoint.id),
                'is_healthy': is_healthy,
                'status_code': response.get('status_code'),
                'response_time_ms': response_time_ms,
                'error': response.get('error'),
                'checked_at': health_log.checked_at.isoformat(),
                'health_log_id': str(health_log.id)
            }
            
            logger.info(f"Health check completed for endpoint {endpoint.id}: {'Healthy' if is_healthy else 'Unhealthy'}")
            return result
            
        except Exception as e:
            logger.error(f"Error pinging endpoint {endpoint.id}: {str(e)}")
            
            # Create health log for error
            try:
                health_log = WebhookHealthLog.objects.create(
                    endpoint=endpoint,
                    is_healthy=False,
                    status_code=0,
                    response_time_ms=0,
                    error=str(e),
                    checked_at=timezone.now(),
                    created_by=endpoint.owner
                )
                
                # Check for auto-suspension
                if self.auto_suspend_enabled:
                    self._check_auto_suspension(endpoint)
                
                return {
                    'endpoint_id': str(endpoint.id),
                    'is_healthy': False,
                    'status_code': 0,
                    'response_time_ms': 0,
                    'error': str(e),
                    'checked_at': health_log.checked_at.isoformat(),
                    'health_log_id': str(health_log.id)
                }
                
            except Exception as log_error:
                logger.error(f"Error creating health log for endpoint {endpoint.id}: {str(log_error)}")
                return {
                    'endpoint_id': str(endpoint.id),
                    'is_healthy': False,
                    'status_code': 0,
                    'response_time_ms': 0,
                    'error': str(e),
                    'checked_at': timezone.now().isoformat()
                }
    
    def _make_health_check_request(self, endpoint: WebhookEndpoint, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP health check request to endpoint.
        
        Args:
            endpoint: The webhook endpoint
            payload: Health check payload
            
        Returns:
            Response data dictionary
        """
        try:
            import requests
            import json
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Webhook-Health-Check/1.0',
                'X-Webhook-Health-Check': 'true'
            }
            
            # Add custom headers if configured
            if endpoint.headers:
                headers.update(endpoint.headers)
            
            # Add signature
            from .SignatureEngine import SignatureEngine
            signature_engine = SignatureEngine()
            signature_headers = signature_engine.get_signature_headers(payload, endpoint.secret_key)
            headers.update(signature_headers)
            
            # Make request
            response = requests.post(
                url=endpoint.url,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.default_timeout,
                verify=endpoint.verify_ssl
            )
            
            return {
                'status_code': response.status_code,
                'response_body': response.text,
                'response_headers': dict(response.headers),
                'success': response.status_code < 400
            }
            
        except requests.exceptions.Timeout:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'success': False,
                'error': 'Request timeout'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'success': False,
                'error': 'Connection error'
            }
        except Exception as e:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'success': False,
                'error': str(e)
            }
    
    def _determine_health_status(self, response: Dict[str, Any]) -> bool:
        """
        Determine if endpoint is healthy based on response.
        
        Args:
            response: Response data from health check
            
        Returns:
            True if endpoint is healthy, False otherwise
        """
        try:
            # Check if request was successful
            if not response.get('success', False):
                return False
            
            # Check status code
            status_code = response.get('status_code', 0)
            if status_code < 200 or status_code >= 300:
                return False
            
            # Check response body for health status
            response_body = response.get('response_body', '')
            if response_body:
                try:
                    import json
                    response_data = json.loads(response_body)
                    
                    # Look for explicit health status
                    if 'status' in response_data:
                        return response_data['status'].lower() == 'healthy'
                    
                    # Look for health field
                    if 'health' in response_data:
                        return response_data['health'].lower() in ['healthy', 'ok', 'good']
                    
                    # Look for success field
                    if 'success' in response_data:
                        return response_data['success']
                        
                except json.JSONDecodeError:
                    # If response is not JSON, consider it healthy if status code is good
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Error determining health status: {str(e)}")
            return False
    
    def _check_auto_suspension(self, endpoint: WebhookEndpoint) -> bool:
        """
        Check if endpoint should be auto-suspended based on recent health checks.
        
        Args:
            endpoint: The webhook endpoint to check
            
        Returns:
            True if endpoint was suspended, False otherwise
        """
        try:
            # Get recent health logs
            from datetime import timedelta
            recent_logs = WebhookHealthLog.objects.filter(
                endpoint=endpoint,
                checked_at__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-checked_at')
            
            # Check consecutive failures
            consecutive_failures = 0
            for log in recent_logs:
                if not log.is_healthy:
                    consecutive_failures += 1
                    if consecutive_failures >= self.max_consecutive_failures:
                        # Suspend endpoint
                        endpoint.status = WebhookStatus.SUSPENDED
                        endpoint.suspension_reason = f"Auto-suspended after {consecutive_failures} consecutive health check failures"
                        endpoint.save()
                        
                        logger.warning(f"Auto-suspended endpoint {endpoint.id} after {consecutive_failures} consecutive failures")
                        return True
                else:
                    break  # Stop at first healthy check
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking auto-suspension for endpoint {endpoint.id}: {str(e)}")
            return False
    
    def check_all_endpoints(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check health of all active endpoints.
        
        Args:
            user_id: Optional user ID to filter endpoints
            
        Returns:
            Dictionary with health check results
        """
        try:
            # Get endpoints to check
            endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE)
            if user_id:
                endpoints = endpoints.filter(owner_id=user_id)
            
            results = {
                'total_endpoints': endpoints.count(),
                'healthy_endpoints': 0,
                'unhealthy_endpoints': 0,
                'error_endpoints': 0,
                'results': []
            }
            
            for endpoint in endpoints:
                try:
                    health_result = self.ping_endpoint(endpoint)
                    
                    if health_result['is_healthy']:
                        results['healthy_endpoints'] += 1
                    else:
                        results['unhealthy_endpoints'] += 1
                    
                    results['results'].append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_label': endpoint.label,
                        'endpoint_url': endpoint.url,
                        'is_healthy': health_result['is_healthy'],
                        'status_code': health_result.get('status_code'),
                        'response_time_ms': health_result.get('response_time_ms'),
                        'error': health_result.get('error')
                    })
                    
                except Exception as e:
                    results['error_endpoints'] += 1
                    results['results'].append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_label': endpoint.label,
                        'endpoint_url': endpoint.url,
                        'is_healthy': False,
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking all endpoints: {str(e)}")
            return {
                'total_endpoints': 0,
                'healthy_endpoints': 0,
                'unhealthy_endpoints': 0,
                'error_endpoints': 0,
                'results': [],
                'error': str(e)
            }
    
    def get_endpoint_health_summary(self, endpoint: WebhookEndpoint, days: int = 7) -> Dict[str, Any]:
        """
        Get health summary for an endpoint.
        
        Args:
            endpoint: The webhook endpoint
            days: Number of days to look back
            
        Returns:
            Dictionary with health summary
        """
        try:
            from datetime import timedelta
            since = timezone.now() - timedelta(days=days)
            
            # Get health logs
            health_logs = WebhookHealthLog.objects.filter(
                endpoint=endpoint,
                checked_at__gte=since
            ).order_by('-checked_at')
            
            if not health_logs.exists():
                return {
                    'endpoint_id': str(endpoint.id),
                    'total_checks': 0,
                    'healthy_checks': 0,
                    'unhealthy_checks': 0,
                    'uptime_percentage': 0,
                    'avg_response_time_ms': 0,
                    'last_check': None,
                    'period_days': days
                }
            
            # Calculate statistics
            total_checks = health_logs.count()
            healthy_checks = health_logs.filter(is_healthy=True).count()
            unhealthy_checks = total_checks - healthy_checks
            uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
            
            # Calculate average response time
            healthy_logs = health_logs.filter(is_healthy=True)
            avg_response_time = 0
            if healthy_logs.exists():
                avg_response_time = healthy_logs.aggregate(
                    avg_time=models.Avg('response_time_ms')
                )['avg_time'] or 0
            
            # Get last check
            last_check = health_logs.first()
            
            return {
                'endpoint_id': str(endpoint.id),
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': unhealthy_checks,
                'uptime_percentage': round(uptime_percentage, 2),
                'avg_response_time_ms': round(avg_response_time, 2),
                'last_check': last_check.checked_at.isoformat() if last_check else None,
                'last_check_healthy': last_check.is_healthy if last_check else None,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting health summary for endpoint {endpoint.id}: {str(e)}")
            return {
                'endpoint_id': str(endpoint.id),
                'total_checks': 0,
                'healthy_checks': 0,
                'unhealthy_checks': 0,
                'uptime_percentage': 0,
                'avg_response_time_ms': 0,
                'last_check': None,
                'period_days': days,
                'error': str(e)
            }
    
    def get_health_trends(self, endpoint: WebhookEndpoint, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get health trends for an endpoint over time.
        
        Args:
            endpoint: The webhook endpoint
            days: Number of days to look back
            
        Returns:
            List of daily health data
        """
        try:
            from datetime import timedelta
            trends = []
            
            for day in range(days):
                date = (timezone.now() - timedelta(days=day)).date()
                
                # Get health logs for this day
                day_logs = WebhookHealthLog.objects.filter(
                    endpoint=endpoint,
                    checked_at__date=date
                )
                
                total_checks = day_logs.count()
                healthy_checks = day_logs.filter(is_healthy=True).count()
                uptime = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
                
                # Calculate average response time
                avg_response_time = 0
                if healthy_checks > 0:
                    avg_response_time = day_logs.filter(is_healthy=True).aggregate(
                        avg_time=models.Avg('response_time_ms')
                    )['avg_time'] or 0
                
                trends.append({
                    'date': date.isoformat(),
                    'total_checks': total_checks,
                    'healthy_checks': healthy_checks,
                    'unhealthy_checks': total_checks - healthy_checks,
                    'uptime_percentage': round(uptime, 2),
                    'avg_response_time_ms': round(avg_response_time, 2)
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting health trends for endpoint {endpoint.id}: {str(e)}")
            return []
    
    def resume_suspended_endpoint(self, endpoint: WebhookEndpoint) -> bool:
        """
        Resume a suspended endpoint after health recovery.
        
        Args:
            endpoint: The webhook endpoint to resume
            
        Returns:
            True if endpoint was resumed, False otherwise
        """
        try:
            if endpoint.status != WebhookStatus.SUSPENDED:
                return False
            
            # Check recent health
            recent_health = WebhookHealthLog.objects.filter(
                endpoint=endpoint,
                checked_at__gte=timezone.now() - timezone.timedelta(hours=1)
            ).order_by('-checked_at')
            
            if recent_health.exists():
                # Check if recent health checks are healthy
                healthy_count = recent_health.filter(is_healthy=True).count()
                if healthy_count >= 3:  # Need 3 consecutive healthy checks
                    # Resume endpoint
                    endpoint.status = WebhookStatus.ACTIVE
                    endpoint.suspension_reason = None
                    endpoint.save()
                    
                    logger.info(f"Resumed suspended endpoint {endpoint.id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error resuming endpoint {endpoint.id}: {str(e)}")
            return False
    
    def get_unhealthy_endpoints(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get endpoints that are currently unhealthy.
        
        Args:
            hours: Number of hours to look back for health checks
            
        Returns:
            List of unhealthy endpoint data
        """
        try:
            from datetime import timedelta
            since = timezone.now() - timedelta(hours=hours)
            
            # Get endpoints with recent unhealthy checks
            unhealthy_endpoints = []
            
            # Get all active endpoints
            endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE)
            
            for endpoint in endpoints:
                # Get recent health logs
                recent_logs = WebhookHealthLog.objects.filter(
                    endpoint=endpoint,
                    checked_at__gte=since
                ).order_by('-checked_at')
                
                if recent_logs.exists():
                    # Check if most recent check is unhealthy
                    last_check = recent_logs.first()
                    if not last_check.is_healthy:
                        # Calculate consecutive failures
                        consecutive_failures = 0
                        for log in recent_logs:
                            if not log.is_healthy:
                                consecutive_failures += 1
                            else:
                                break
                        
                        unhealthy_endpoints.append({
                            'endpoint_id': str(endpoint.id),
                            'endpoint_label': endpoint.label,
                            'endpoint_url': endpoint.url,
                            'consecutive_failures': consecutive_failures,
                            'last_check': last_check.checked_at.isoformat(),
                            'last_status_code': last_check.status_code,
                            'last_error': last_check.error
                        })
            
            return unhealthy_endpoints
            
        except Exception as e:
            logger.error(f"Error getting unhealthy endpoints: {str(e)}")
            return []
    
    def schedule_health_checks(self) -> bool:
        """
        Schedule periodic health checks for all active endpoints.
        
        Returns:
            True if scheduling was successful, False otherwise
        """
        try:
            # Queue health check task
            from ..tasks.health_check_tasks import health_check_all_endpoints
            health_check_all_endpoints.delay()
            
            logger.info("Scheduled health checks for all active endpoints")
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling health checks: {str(e)}")
            return False
