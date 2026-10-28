"""
Integration Handler - Core Integration Management

Central handler for managing all integration operations, routing,
and coordination between different modules and external services.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError, IntegrationTimeoutError
from .integ_registry import IntegrationRegistry
from .performance_monitor import PerformanceMonitor
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class IntegrationMode(Enum):
    """Integration operation modes."""
    SYNC = "sync"
    ASYNC = "async"
    BATCH = "batch"
    STREAM = "stream"


@dataclass
class IntegrationRequest:
    """Integration request data structure."""
    request_id: str
    event_type: IntegrationEvent
    source_module: str
    target_module: str
    payload: Dict[str, Any]
    priority: IntegrationPriority = IntegrationPriority.NORMAL
    mode: IntegrationMode = IntegrationMode.SYNC
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=timezone.now)


@dataclass
class IntegrationResponse:
    """Integration response data structure."""
    request_id: str
    status: IntegrationStatus
    payload: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)


class IntegrationHandler:
    """Core integration handler for managing all integration operations."""
    
    def __init__(self):
        self.registry = IntegrationRegistry()
        self.performance_monitor = PerformanceMonitor()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.active_requests: Dict[str, IntegrationRequest] = {}
        self.request_handlers: Dict[str, Callable] = {}
        self.middleware_stack: List[Callable] = []
        self._initialize_circuit_breakers()
        self._register_default_handlers()
    
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for different integrations."""
        default_config = {
            'failure_threshold': 5,
            'recovery_timeout': 60,
            'expected_exception': IntegrationError,
            'fallback_function': self._handle_circuit_breaker_fallback
        }
        
        # Circuit breakers for common integrations
        integrations = [
            'rate_limit_service', 'abuse_detection', 'ip_blocking',
            'compliance_system', 'monitoring_service', 'analytics_engine'
        ]
        
        for integration in integrations:
            self.circuit_breakers[integration] = CircuitBreaker(
                integration_name=integration,
                **default_config
            )
    
    def _register_default_handlers(self):
        """Register default integration handlers."""
        # Rate limit event handlers
        self.register_handler(
            IntegrationEvent.RATE_LIMIT_EXCEEDED,
            self._handle_rate_limit_exceeded
        )
        
        self.register_handler(
            IntegrationEvent.ABUSE_DETECTED,
            self._handle_abuse_detected
        )
        
        self.register_handler(
            IntegrationEvent.IP_BLOCKED,
            self._handle_ip_blocked
        )
        
        self.register_handler(
            IntegrationEvent.SANCTION_APPLIED,
            self._handle_sanction_applied
        )
    
    def register_handler(self, event_type: IntegrationEvent, handler: Callable):
        """Register an event handler."""
        self.request_handlers[event_type.value] = handler
        logger.info(f"Registered handler for event: {event_type.value}")
    
    def add_middleware(self, middleware: Callable):
        """Add middleware to the integration processing stack."""
        self.middleware_stack.append(middleware)
        logger.info(f"Added middleware: {middleware.__name__}")
    
    async def process_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Process an integration request."""
        start_time = timezone.now()
        
        try:
            # Store active request
            self.active_requests[request.request_id] = request
            
            # Apply middleware stack
            processed_request = await self._apply_middleware(request)
            
            # Get circuit breaker for target module
            circuit_breaker = self.circuit_breakers.get(request.target_module)
            
            if circuit_breaker:
                response = await circuit_breaker.call(
                    self._execute_request, processed_request
                )
            else:
                response = await self._execute_request(processed_request)
            
            # Calculate execution time
            response.execution_time = (timezone.now() - start_time).total_seconds()
            
            # Log performance metrics
            self.performance_monitor.record_request(
                request.source_module,
                request.target_module,
                response.execution_time,
                response.status.value
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Integration request failed: {request.request_id} - {str(e)}")
            return IntegrationResponse(
                request_id=request.request_id,
                status=IntegrationStatus.FAILED,
                error_message=str(e),
                execution_time=(timezone.now() - start_time).total_seconds()
            )
        finally:
            # Clean up active request
            self.active_requests.pop(request.request_id, None)
    
    async def _apply_middleware(self, request: IntegrationRequest) -> IntegrationRequest:
        """Apply middleware stack to the request."""
        processed_request = request
        
        for middleware in self.middleware_stack:
            try:
                processed_request = await middleware(processed_request)
            except Exception as e:
                logger.error(f"Middleware failed: {middleware.__name__} - {str(e)}")
                raise IntegrationError(f"Middleware error: {str(e)}")
        
        return processed_request
    
    async def _execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute the integration request."""
        try:
            # Get handler for event type
            handler = self.request_handlers.get(request.event_type.value)
            
            if not handler:
                raise IntegrationError(f"No handler registered for event: {request.event_type.value}")
            
            # Execute handler based on mode
            if request.mode == IntegrationMode.ASYNC:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(request)
                else:
                    result = handler(request)
            else:
                result = handler(request)
            
            return IntegrationResponse(
                request_id=request.request_id,
                status=IntegrationStatus.SUCCESS,
                payload=result if isinstance(result, dict) else {'result': result}
            )
            
        except Exception as e:
            logger.error(f"Request execution failed: {str(e)}")
            return IntegrationResponse(
                request_id=request.request_id,
                status=IntegrationStatus.FAILED,
                error_message=str(e)
            )
    
    def _handle_circuit_breaker_fallback(self, *args, **kwargs):
        """Fallback function for circuit breaker."""
        logger.warning("Circuit breaker fallback activated")
        return {
            'status': 'fallback',
            'message': 'Integration temporarily unavailable',
            'timestamp': timezone.now().isoformat()
        }
    
    def _handle_rate_limit_exceeded(self, request: IntegrationRequest) -> Dict[str, Any]:
        """Handle rate limit exceeded events."""
        payload = request.payload
        
        # Trigger IP blocking if severe
        if payload.get('severity') == 'high':
            from api.rate_limit.services.IPBlockService import IPBlockService
            ip_service = IPBlockService()
            
            ip_service.block_ip(
                ip_address=payload.get('ip_address'),
                reason='Rate limit exceeded - high severity',
                duration_days=1
            )
        
        # Log event
        from api.rate_limit.models.RateLimitLog import RateLimitLog
        RateLimitLog.objects.create(
            ip_address=payload.get('ip_address'),
            endpoint=payload.get('endpoint'),
            request_method=payload.get('method', 'GET'),
            status='blocked',
            metadata=payload
        )
        
        return {
            'action': 'rate_limit_handled',
            'ip_blocked': payload.get('severity') == 'high',
            'timestamp': timezone.now().isoformat()
        }
    
    def _handle_abuse_detected(self, request: IntegrationRequest) -> Dict[str, Any]:
        """Handle abuse detection events."""
        payload = request.payload
        
        # Create abuse report
        from api.rate_limit.models.AbuseReport import AbuseReport
        abuse_report = AbuseReport.objects.create(
            ip_address=payload.get('ip_address'),
            abuse_type=payload.get('abuse_type'),
            severity=payload.get('severity', 3),
            details=payload.get('details', {}),
            is_investigated=False
        )
        
        # Trigger sanctions if high severity
        if payload.get('severity', 3) >= 4:
            from api.rate_limit.sanctions import SanctionEngine
            sanction_engine = SanctionEngine()
            
            if payload.get('user_id'):
                sanction_engine.evaluate_user(payload.get('user_id'))
            else:
                sanction_engine.evaluate_ip(payload.get('ip_address'))
        
        return {
            'action': 'abuse_handled',
            'report_id': str(abuse_report.id),
            'sanctions_triggered': payload.get('severity', 3) >= 4,
            'timestamp': timezone.now().isoformat()
        }
    
    def _handle_ip_blocked(self, request: IntegrationRequest) -> Dict[str, Any]:
        """Handle IP blocking events."""
        payload = request.payload
        
        # Clear any existing rate limits for this IP
        cache.delete(f"rl:ip:{payload.get('ip_address')}")
        
        # Send notification
        from api.rate_limit.webhooks import WebhookManager
        webhook_manager = WebhookManager()
        
        webhook_manager.send_webhook(
            event_type='ip_blocked',
            payload={
                'ip_address': payload.get('ip_address'),
                'reason': payload.get('reason'),
                'duration': payload.get('duration'),
                'timestamp': timezone.now().isoformat()
            }
        )
        
        return {
            'action': 'ip_block_handled',
            'cache_cleared': True,
            'notification_sent': True,
            'timestamp': timezone.now().isoformat()
        }
    
    def _handle_sanction_applied(self, request: IntegrationRequest) -> Dict[str, Any]:
        """Handle sanction application events."""
        payload = request.payload
        
        # Update user profile if applicable
        if payload.get('user_id'):
            from api.rate_limit.models.UserRateLimitProfile import UserRateLimitProfile
            try:
                profile = UserRateLimitProfile.objects.get(user_id=payload.get('user_id'))
                profile.suspicion_score = min(100, profile.suspicion_score + 10)
                profile.save()
            except UserRateLimitProfile.DoesNotExist:
                pass
        
        # Log compliance event
        from api.rate_limit.compliance import ComplianceAuditTrail
        audit_trail = ComplianceAuditTrail()
        audit_trail.log_action(
            action='sanction_applied',
            user_id=payload.get('user_id'),
            ip_address=payload.get('ip_address'),
            details=payload,
            compliance_relevant=True
        )
        
        return {
            'action': 'sanction_handled',
            'profile_updated': payload.get('user_id') is not None,
            'compliance_logged': True,
            'timestamp': timezone.now().isoformat()
        }
    
    def get_active_requests(self) -> List[IntegrationRequest]:
        """Get list of active integration requests."""
        return list(self.active_requests.values())
    
    def get_request_status(self, request_id: str) -> Optional[IntegrationRequest]:
        """Get status of a specific request."""
        return self.active_requests.get(request_id)
    
    def cancel_request(self, request_id: str) -> bool:
        """Cancel an active request."""
        if request_id in self.active_requests:
            del self.active_requests[request_id]
            logger.info(f"Cancelled request: {request_id}")
            return True
        return False
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics."""
        stats = {
            'active_requests': len(self.active_requests),
            'registered_handlers': len(self.request_handlers),
            'middleware_count': len(self.middleware_stack),
            'circuit_breakers': {}
        }
        
        for name, breaker in self.circuit_breakers.items():
            stats['circuit_breakers'][name] = {
                'state': breaker.state,
                'failure_count': breaker.failure_count,
                'last_failure_time': breaker.last_failure_time
            }
        
        # Add performance stats
        stats['performance'] = self.performance_monitor.get_stats()
        
        return stats


# Global integration handler instance
integration_handler = IntegrationHandler()
