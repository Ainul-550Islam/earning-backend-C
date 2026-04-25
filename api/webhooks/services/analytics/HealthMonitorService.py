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
    
    def check_endpoint_health(self, endpoint: WebhookEndpoint) -> Dict[str, Any]:
        """
        Perform health check on a webhook endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            
        Returns:
            Dict: Health check results
        """
        try:
            start_time = time.time()
            
            # Make HTTP request to endpoint
            response = self._make_health_request(endpoint)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Determine health status
            is_healthy = (
                response.status_code == 200 and
                response_time_ms <= endpoint.timeout_seconds * 1000
            )
            
            # Log health check
            health_log = WebhookHealthLog.objects.create(
                endpoint=endpoint,
                is_healthy=is_healthy,
                response_time_ms=response_time_ms,
                status_code=response.status_code,
                error=response.error if not is_healthy else '',
            )
            
            # Update endpoint status if needed
            if not is_healthy and endpoint.status == WebhookStatus.ACTIVE:
                self._auto_suspend_endpoint(endpoint, "Health check failed")
            
            self.logger.info(
                f"Health check for {endpoint.url}: {'Healthy' if is_healthy else 'Unhealthy'} "
                f"({response_time_ms}ms, {response.status_code})"
            )
            
            return {
                'endpoint_id': endpoint.id,
                'url': endpoint.url,
                'is_healthy': is_healthy,
                'response_time_ms': response_time_ms,
                'status_code': response.status_code,
                'error': response.error if not is_healthy else '',
                'checked_at': health_log.checked_at,
            }
            
        except Exception as e:
            self.logger.error(f"Health check error for {endpoint.url}: {e}")
            
            # Log error
            WebhookHealthLog.objects.create(
                endpoint=endpoint,
                is_healthy=False,
                response_time_ms=None,
                status_code=None,
                error=str(e),
            )
            
            return {
                'endpoint_id': endpoint.id,
                'url': endpoint.url,
                'is_healthy': False,
                'response_time_ms': None,
                'status_code': None,
                'error': str(e),
                'checked_at': timezone.now(),
            }
    
    def check_all_endpoints(self) -> List[Dict[str, Any]]:
        """
        Perform health checks on all active endpoints.
        
        Returns:
            List[Dict]: Health check results for all endpoints
        """
        results = []
        
        active_endpoints = WebhookEndpoint.objects.filter(
            status=WebhookStatus.ACTIVE
        )
        
        for endpoint in active_endpoints:
            result = self.check_endpoint_health(endpoint)
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
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Calculate uptime percentage
            uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
            
            return {
                'endpoint_id': endpoint.id,
                'url': endpoint.url,
                'period_hours': hours,
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': unhealthy_checks,
                'uptime_percentage': round(uptime_percentage, 2),
                'avg_response_time_ms': round(avg_response_time, 2),
                'current_status': endpoint.status,
                'last_check': health_logs.first().checked_at if health_logs.exists() else None,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get health summary: {e}")
            return {}
    
    def _make_health_request(self, endpoint: WebhookEndpoint) -> Any:
        """
        Make HTTP request to endpoint for health check.
        
        Args:
            endpoint: WebhookEndpoint instance
            
        Returns:
            Any: Response object
        """
        import requests
        
        headers = {
            'User-Agent': 'Webhook-Health-Monitor/1.0',
            'Accept': 'application/json',
        }
        
        # Add authentication if endpoint has secret
        if hasattr(endpoint, 'secret') and endpoint.secret:
            headers['X-Webhook-Signature'] = self._generate_health_signature(endpoint)
        
        try:
            response = requests.get(
                endpoint.url,
                headers=headers,
                timeout=endpoint.timeout_seconds,
                verify=False,  # Skip SSL verification for health checks
            )
            
            class Response:
                def __init__(self, status_code, error=None):
                    self.status_code = status_code
                    self.error = error
            
            return Response(
                status_code=response.status_code,
                error=response.text if response.status_code >= 400 else None
            )
            
        except requests.exceptions.Timeout:
            return Response(status_code=None, error="Request timeout")
        except requests.exceptions.ConnectionError:
            return Response(status_code=None, error="Connection error")
        except requests.exceptions.RequestException as e:
            return Response(status_code=None, error=str(e))
    
    def _generate_health_signature(self, endpoint: WebhookEndpoint) -> str:
        """
        Generate signature for health check request.
        
        Args:
            endpoint: WebhookEndpoint instance
            
        Returns:
            str: HMAC signature
        """
        import hmac
        import hashlib
        
        payload = f"health_check_{endpoint.id}_{timezone.now().timestamp()}"
        signature = hmac.new(
            endpoint.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
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
                    f"Auto-suspended endpoint {endpoint.url}: {reason}"
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
                
                self.logger.info(f"Resumed endpoint {endpoint.url}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to resume endpoint: {e}")
            return False
