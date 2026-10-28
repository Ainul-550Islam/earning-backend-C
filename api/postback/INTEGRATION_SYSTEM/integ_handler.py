"""
integ_handler.py – Integration Handler for postback module.

Provides comprehensive integration handling functionality including:
- Integration orchestration
- Request/response processing
- Error handling and retry logic
- Integration lifecycle management
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException, IntegrationTimeoutException
from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationStatus, IntegrationType
from api.postback.INTEGRATION_SYSTEM.integ_registry import integration_registry
from api.postback.INTEGRATION_SYSTEM.integ_adapter import IntegrationAdapter
from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class IntegrationHandler:
    """
    Main integration handler for postback module.
    
    Orchestrates integrations, handles requests/responses,
    and manages integration lifecycle.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.adapters: Dict[str, IntegrationAdapter] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.request_queue: List[Dict[str, Any]] = []
        self.response_cache = {}
        self._setup_default_integrations()
    
    def _setup_default_integrations(self):
        """Setup default integrations."""
        # Register default integrations
        default_integrations = [
            {
                'name': 'webhook_processor',
                'type': IntegrationType.WEBHOOK,
                'endpoint': '/api/postback/webhook/',
                'timeout': 30,
                'retry_attempts': 3,
                'circuit_breaker_threshold': 5,
            },
            {
                'name': 'analytics_collector',
                'type': IntegrationType.ANALYTICS,
                'endpoint': '/api/postback/analytics/',
                'timeout': 60,
                'retry_attempts': 2,
                'circuit_breaker_threshold': 3,
            },
            {
                'name': 'notification_sender',
                'type': IntegrationType.NOTIFICATION,
                'endpoint': '/api/postback/notifications/',
                'timeout': 15,
                'retry_attempts': 5,
                'circuit_breaker_threshold': 10,
            },
        ]
        
        for integration_config in default_integrations:
            self.register_integration(integration_config)
    
    def register_integration(self, config: Dict[str, Any]) -> bool:
        """
        Register integration.
        
        Args:
            config: Integration configuration
            
        Returns:
            True if registered successfully
        """
        try:
            name = config['name']
            
            # Create adapter
            adapter = IntegrationAdapter(config)
            self.adapters[name] = adapter
            
            # Create circuit breaker
            circuit_breaker = CircuitBreaker(
                failure_threshold=config.get('circuit_breaker_threshold', 5),
                recovery_timeout=config.get('recovery_timeout', 60),
                expected_exception=IntegrationException
            )
            self.circuit_breakers[name] = circuit_breaker
            
            # Register in registry
            integration_registry.register(name, config)
            
            self.logger.info(f"Integration registered: {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to register integration: {str(e)}")
            return False
    
    def unregister_integration(self, name: str) -> bool:
        """
        Unregister integration.
        
        Args:
            name: Integration name
            
        Returns:
            True if unregistered successfully
        """
        try:
            if name in self.adapters:
                del self.adapters[name]
            
            if name in self.circuit_breakers:
                del self.circuit_breakers[name]
            
            integration_registry.unregister(name)
            
            self.logger.info(f"Integration unregistered: {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to unregister integration {name}: {str(e)}")
            return False
    
    def process_request(self, integration_name: str, request_data: Dict[str, Any],
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process integration request.
        
        Args:
            integration_name: Name of integration
            request_data: Request data
            context: Additional context
            
        Returns:
            Response data
        """
        context = context or {}
        start_time = timezone.now()
        
        try:
            # Check if integration exists
            if integration_name not in self.adapters:
                raise IntegrationException(f"Integration {integration_name} not found")
            
            adapter = self.adapters[integration_name]
            circuit_breaker = self.circuit_breakers[integration_name]
            
            # Check circuit breaker
            if circuit_breaker.is_open():
                raise IntegrationException(f"Circuit breaker open for {integration_name}")
            
            # Check cache for cached response
            cache_key = self._generate_cache_key(integration_name, request_data)
            cached_response = self.response_cache.get(cache_key)
            if cached_response and not context.get('bypass_cache', False):
                self.logger.info(f"Cache hit for {integration_name}")
                return cached_response
            
            # Pre-process request
            processed_request = adapter.pre_process_request(request_data, context)
            
            # Execute request with circuit breaker
            with circuit_breaker:
                response = self._execute_request(adapter, processed_request, context)
            
            # Post-process response
            processed_response = adapter.post_process_response(response, context)
            
            # Cache response
            cache_timeout = adapter.config.get('cache_timeout', 300)
            self.response_cache[cache_key] = processed_response
            
            # Log success
            processing_time = (timezone.now() - start_time).total_seconds()
            self.logger.info(f"Request processed successfully: {integration_name} in {processing_time:.3f}s")
            
            return processed_response
        
        except IntegrationException as e:
            processing_time = (timezone.now() - start_time).total_seconds()
            self.logger.error(f"Integration request failed: {integration_name} in {processing_time:.3f}s - {str(e)}")
            
            # Add to retry queue if retryable
            if self._is_retryable_error(e) and context.get('retry_on_failure', True):
                self._add_to_retry_queue(integration_name, request_data, context)
            
            return {
                'success': False,
                'error': str(e),
                'integration': integration_name,
                'processing_time': processing_time,
            }
        
        except Exception as e:
            processing_time = (timezone.now() - start_time).total_seconds()
            self.logger.error(f"Unexpected error processing request: {integration_name} - {str(e)}")
            
            return {
                'success': False,
                'error': f"Internal error: {str(e)}",
                'integration': integration_name,
                'processing_time': processing_time,
            }
    
    def _execute_request(self, adapter: IntegrationAdapter, request_data: Dict[str, Any],
                        context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute integration request."""
        timeout = adapter.config.get('timeout', 30)
        retry_attempts = adapter.config.get('retry_attempts', 3)
        
        for attempt in range(retry_attempts):
            try:
                # Execute request
                response = adapter.execute_request(request_data, context, timeout)
                
                # Validate response
                if not adapter.validate_response(response):
                    raise IntegrationException("Invalid response from integration")
                
                return response
            
            except IntegrationTimeoutException:
                if attempt < retry_attempts - 1:
                    self.logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                    continue
                raise
            
            except IntegrationException as e:
                if attempt < retry_attempts - 1 and self._is_retryable_error(e):
                    self.logger.warning(f"Error on attempt {attempt + 1}, retrying: {str(e)}")
                    continue
                raise
        
        raise IntegrationException(f"Request failed after {retry_attempts} attempts")
    
    def process_batch_requests(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple integration requests in batch.
        
        Args:
            requests: List of request dictionaries
            
        Returns:
            List of responses
        """
        responses = []
        
        for request in requests:
            integration_name = request.get('integration_name')
            request_data = request.get('request_data', {})
            context = request.get('context', {})
            
            response = self.process_request(integration_name, request_data, context)
            responses.append(response)
        
        return responses
    
    def get_integration_status(self, integration_name: str = None) -> Dict[str, Any]:
        """
        Get integration status.
        
        Args:
            integration_name: Specific integration name (None = all)
            
        Returns:
            Integration status information
        """
        if integration_name:
            if integration_name not in self.adapters:
                return {'error': f'Integration {integration_name} not found'}
            
            adapter = self.adapters[integration_name]
            circuit_breaker = self.circuit_breakers[integration_name]
            
            return {
                'name': integration_name,
                'type': adapter.config.get('type'),
                'status': adapter.get_status(),
                'circuit_breaker': {
                    'state': circuit_breaker.state.value,
                    'failure_count': circuit_breaker.failure_count,
                    'last_failure_time': circuit_breaker.last_failure_time.isoformat() if circuit_breaker.last_failure_time else None,
                },
                'last_request_time': adapter.last_request_time.isoformat() if adapter.last_request_time else None,
                'total_requests': adapter.total_requests,
                'successful_requests': adapter.successful_requests,
                'failed_requests': adapter.failed_requests,
            }
        
        # Return all integrations status
        all_status = {}
        for name in self.adapters.keys():
            all_status[name] = self.get_integration_status(name)
        
        return all_status
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all integrations.
        
        Returns:
            Health check results
        """
        health_status = {
            'overall': 'healthy',
            'integrations': {},
            'issues': [],
        }
        
        for name, adapter in self.adapters.items():
            try:
                # Check adapter health
                adapter_health = adapter.health_check()
                
                # Check circuit breaker
                circuit_breaker = self.circuit_breakers[name]
                circuit_health = circuit_breaker.state.value
                
                integration_health = 'healthy'
                if adapter_health != 'healthy' or circuit_health == 'open':
                    integration_health = 'unhealthy'
                    health_status['issues'].append(f"Integration {name} is unhealthy")
                
                health_status['integrations'][name] = {
                    'adapter': adapter_health,
                    'circuit_breaker': circuit_health,
                    'overall': integration_health,
                }
            
            except Exception as e:
                health_status['integrations'][name] = {
                    'error': str(e),
                    'overall': 'error',
                }
                health_status['issues'].append(f"Error checking {name}: {str(e)}")
        
        if health_status['issues']:
            health_status['overall'] = 'unhealthy'
        
        return health_status
    
    def _generate_cache_key(self, integration_name: str, request_data: Dict[str, Any]) -> str:
        """Generate cache key for request."""
        import hashlib
        import json
        
        # Create hash of request data
        request_hash = hashlib.md5(
            json.dumps(request_data, sort_keys=True).encode()
        ).hexdigest()
        
        return f"integ_cache_{integration_name}_{request_hash}"
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable."""
        if isinstance(error, IntegrationTimeoutException):
            return True
        
        error_message = str(error).lower()
        retryable_errors = ['timeout', 'connection', 'network', 'temporary']
        
        return any(error_type in error_message for error_type in retryable_errors)
    
    def _add_to_retry_queue(self, integration_name: str, request_data: Dict[str, Any],
                           context: Dict[str, Any]):
        """Add failed request to retry queue."""
        retry_request = {
            'integration_name': integration_name,
            'request_data': request_data,
            'context': context,
            'created_at': timezone.now(),
            'retry_count': context.get('retry_count', 0) + 1,
            'next_retry_at': timezone.now() + timedelta(minutes=2 ** context.get('retry_count', 0)),
        }
        
        self.request_queue.append(retry_request)
        self.logger.info(f"Added to retry queue: {integration_name}")
    
    def process_retry_queue(self) -> int:
        """
        Process retry queue.
        
        Returns:
            Number of requests processed
        """
        processed_count = 0
        now = timezone.now()
        remaining_requests = []
        
        for request in self.request_queue:
            if request['next_retry_at'] <= now:
                integration_name = request['integration_name']
                request_data = request['request_data']
                context = request['context']
                
                # Update retry count
                context['retry_count'] = request['retry_count']
                
                # Process request
                response = self.process_request(integration_name, request_data, context)
                
                if response.get('success', False):
                    processed_count += 1
                else:
                    # Re-queue if still retryable
                    if request['retry_count'] < 5:
                        request['next_retry_at'] = now + timedelta(minutes=2 ** request['retry_count'])
                        remaining_requests.append(request)
            else:
                remaining_requests.append(request)
        
        self.request_queue = remaining_requests
        
        if processed_count > 0:
            self.logger.info(f"Processed {processed_count} retry requests")
        
        return processed_count
    
    def clear_cache(self, integration_name: str = None):
        """Clear response cache."""
        if integration_name:
            # Clear cache for specific integration
            keys_to_remove = [key for key in self.response_cache.keys() if key.startswith(f"integ_cache_{integration_name}_")]
            for key in keys_to_remove:
                del self.response_cache[key]
        else:
            # Clear all cache
            self.response_cache.clear()
        
        self.logger.info(f"Cache cleared for: {integration_name or 'all integrations'}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get integration statistics."""
        stats = {
            'total_integrations': len(self.adapters),
            'active_integrations': 0,
            'failed_integrations': 0,
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_queue_size': len(self.request_queue),
            'cache_size': len(self.response_cache),
            'integration_stats': {},
        }
        
        for name, adapter in self.adapters.items():
            adapter_stats = {
                'total_requests': adapter.total_requests,
                'successful_requests': adapter.successful_requests,
                'failed_requests': adapter.failed_requests,
                'success_rate': (adapter.successful_requests / adapter.total_requests * 100) if adapter.total_requests > 0 else 0,
                'last_request_time': adapter.last_request_time.isoformat() if adapter.last_request_time else None,
            }
            
            stats['integration_stats'][name] = adapter_stats
            
            # Update totals
            stats['total_requests'] += adapter.total_requests
            stats['successful_requests'] += adapter.successful_requests
            stats['failed_requests'] += adapter.failed_requests
            
            # Count active/failed
            if adapter.get_status() == 'active':
                stats['active_integrations'] += 1
            else:
                stats['failed_integrations'] += 1
        
        # Calculate overall success rate
        if stats['total_requests'] > 0:
            stats['overall_success_rate'] = (stats['successful_requests'] / stats['total_requests']) * 100
        else:
            stats['overall_success_rate'] = 0
        
        return stats


# Global integration handler instance
integration_handler = IntegrationHandler()


# Convenience functions
def process_integration_request(integration_name: str, request_data: Dict[str, Any],
                               context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Process integration request."""
    return integration_handler.process_request(integration_name, request_data, context)


def register_integration(config: Dict[str, Any]) -> bool:
    """Register integration."""
    return integration_handler.register_integration(config)


def get_integration_status(integration_name: str = None) -> Dict[str, Any]:
    """Get integration status."""
    return integration_handler.get_integration_status(integration_name)


def perform_health_check() -> Dict[str, Any]:
    """Perform health check."""
    return integration_handler.health_check()


def process_retry_queue() -> int:
    """Process retry queue."""
    return integration_handler.process_retry_queue()


def get_integration_statistics() -> Dict[str, Any]:
    """Get integration statistics."""
    return integration_handler.get_statistics()
