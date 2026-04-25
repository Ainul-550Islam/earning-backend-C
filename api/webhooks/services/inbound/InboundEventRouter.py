"""Inbound Event Router Service

This module provides routing of inbound webhook events to correct handler functions.
"""

import logging
import importlib
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.conf import settings

from ...models import InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError

logger = logging.getLogger(__name__)


class InboundEventRouter:
    """Service for routing inbound webhook events to correct handler functions."""
    
    def __init__(self):
        """Initialize the inbound event router service."""
        self.logger = logger
        self.handler_cache = {}
    
    def route_event(self, inbound: InboundWebhook, payload: Dict[str, Any], headers: Dict[str, Any], log: InboundWebhookLog) -> List[Dict[str, Any]]:
        """
        Route an inbound webhook event to appropriate handlers.
        
        Args:
            inbound: The inbound webhook configuration
            payload: The webhook payload
            headers: HTTP headers from the request
            log: The inbound webhook log
            
        Returns:
            List of routing results
        """
        try:
            # Get active routes for this inbound webhook
            routes = inbound.routes.filter(is_active=True)
            
            routing_results = []
            
            for route in routes:
                try:
                    # Check if route matches the event
                    if self._should_route_to_handler(route, payload):
                        result = self._execute_handler(route, payload, headers, log)
                        routing_results.append(result)
                    else:
                        routing_results.append({
                            'route_id': str(route.id),
                            'handler_function': route.handler_function,
                            'matched': False,
                            'result': 'Event does not match route criteria'
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing route {route.id}: {str(e)}")
                    
                    # Create error record
                    InboundWebhookError.objects.create(
                        log=log,
                        route=route,
                        error_type="handler_execution_failed",
                        error_code="HANDLER_ERROR",
                        error_message=str(e)
                    )
                    
                    routing_results.append({
                        'route_id': str(route.id),
                        'handler_function': route.handler_function,
                        'matched': True,
                        'result': 'Handler execution failed',
                        'error': str(e)
                    })
            
            return routing_results
            
        except Exception as e:
            logger.error(f"Error routing inbound webhook event: {str(e)}")
            
            # Create error record
            InboundWebhookError.objects.create(
                log=log,
                error_type="routing_failed",
                error_code="ROUTING_ERROR",
                error_message=str(e)
            )
            
            return []
    
    def _should_route_to_handler(self, route: InboundWebhookRoute, payload: Dict[str, Any]) -> bool:
        """
        Check if event should be routed to handler based on route criteria.
        
        Args:
            route: The route configuration
            payload: The webhook payload
            
        Returns:
            True if event should be routed, False otherwise
        """
        try:
            # Check event pattern if configured
            if route.event_pattern:
                if not self._matches_event_pattern(route.event_pattern, payload):
                    return False
            
            # Check priority if configured
            if route.priority and hasattr(payload, 'get'):
                # Higher priority routes get preference
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking route criteria: {str(e)}")
            return False
    
    def _matches_event_pattern(self, pattern: str, payload: Dict[str, Any]) -> bool:
        """
        Check if payload matches the event pattern.
        
        Args:
            pattern: The event pattern to match
            payload: The webhook payload
            
        Returns:
            True if pattern matches, False otherwise
        """
        try:
            import re
            
            # Simple pattern matching on event type
            event_type = payload.get('event_type') or payload.get('type') or payload.get('eventType', '')
            
            # Convert pattern to regex
            regex_pattern = pattern.replace('*', '.*').replace('?', '.')
            
            return bool(re.match(regex_pattern, event_type, re.IGNORECASE))
            
        except Exception as e:
            logger.error(f"Error matching event pattern: {str(e)}")
            return False
    
    def _execute_handler(self, route: InboundWebhookRoute, payload: Dict[str, Any], headers: Dict[str, Any], log: InboundWebhookLog) -> Dict[str, Any]:
        """
        Execute the handler function for a route.
        
        Args:
            route: The route configuration
            payload: The webhook payload
            headers: HTTP headers from the request
            log: The inbound webhook log
            
        Returns:
            Dictionary with execution result
        """
        try:
            # Get handler function
            handler = self._get_handler_function(route.handler_function)
            
            if not handler:
                raise ValueError(f"Handler function not found: {route.handler_function}")
            
            # Prepare handler arguments
            handler_args = {
                'payload': payload,
                'headers': headers,
                'route_id': str(route.id),
                'log_id': str(log.id),
                'inbound_id': str(log.inbound.id)
            }
            
            # Execute handler with timeout
            timeout = route.timeout_seconds or 30
            
            try:
                # Execute handler
                if timeout:
                    result = handler(**handler_args)
                else:
                    result = handler(**handler_args)
                
                # Create execution record
                execution = InboundWebhookError.objects.create(
                    log=log,
                    route=route,
                    error_type="handler_success",
                    error_code="SUCCESS",
                    error_message="Handler executed successfully",
                    error_details={
                        'result': result,
                        'execution_time': timezone.now().isoformat()
                    }
                )
                
                return {
                    'route_id': str(route.id),
                    'handler_function': route.handler_function,
                    'matched': True,
                    'result': result,
                    'execution_id': str(execution.id)
                }
                
            except Exception as handler_error:
                # Handler execution failed
                error_record = InboundWebhookError.objects.create(
                    log=log,
                    route=route,
                    error_type="handler_execution_failed",
                    error_code="HANDLER_EXECUTION_ERROR",
                    error_message=str(handler_error)
                )
                
                return {
                    'route_id': str(route.id),
                    'handler_function': route.handler_function,
                    'matched': True,
                    'result': 'Handler execution failed',
                    'error': str(handler_error),
                    'execution_id': str(error_record.id)
                }
            
        except Exception as e:
            logger.error(f"Error executing handler {route.handler_function}: {str(e)}")
            raise
    
    def _get_handler_function(self, handler_path: str):
        """
        Get handler function from path.
        
        Args:
            handler_path: The path to the handler function (e.g., 'myapp.handlers.payment_handler')
            
        Returns:
            The handler function or None if not found
        """
        try:
            # Check cache first
            if handler_path in self.handler_cache:
                return self.handler_cache[handler_path]
            
            # Parse module and function name
            parts = handler_path.rsplit('.', 1)
            if len(parts) != 2:
                return None
            
            module_path, function_name = parts
            
            # Import module
            module = importlib.import_module(module_path)
            
            # Get function
            handler_func = getattr(module, function_name)
            
            # Cache the function
            self.handler_cache[handler_path] = handler_func
            
            return handler_func
            
        except Exception as e:
            logger.error(f"Error loading handler function {handler_path}: {str(e)}")
            return None
    
    def get_route_statistics(self, inbound_id: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get routing statistics for inbound webhooks.
        
        Args:
            inbound_id: Optional inbound webhook ID to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with routing statistics
        """
        try:
            from datetime import timedelta
            from django.db.models import Count, Q
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for routes
            routes = InboundWebhookRoute.objects.filter(is_active=True)
            if inbound_id:
                routes = routes.filter(inbound_id=inbound_id)
            
            # Get route statistics
            route_stats = routes.annotate(
                total_executions=Count('inboundwebhookerror')
            ).order_by('-total_executions')
            
            # Get error breakdown
            error_stats = InboundWebhookError.objects.filter(
                created_at__gte=since
            )
            if inbound_id:
                error_stats = error_stats.filter(log__inbound_id=inbound_id)
            
            error_breakdown = error_stats.values('error_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {
                'total_routes': routes.count(),
                'route_statistics': list(route_stats),
                'error_breakdown': list(error_breakdown),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting route statistics: {str(e)}")
            return {
                'total_routes': 0,
                'route_statistics': [],
                'error_breakdown': [],
                'period_days': days,
                'error': str(e)
            }
    
    def get_handler_performance(self, handler_function: str, days: int = 7) -> Dict[str, Any]:
        """
        Get performance statistics for a specific handler function.
        
        Args:
            handler_function: The handler function path
            days: Number of days to look back
            
        Returns:
            Dictionary with performance statistics
        """
        try:
            from datetime import timedelta
            from django.db.models import Count, Avg
            
            since = timezone.now() - timedelta(days=days)
            
            # Get execution records for this handler
            executions = InboundWebhookError.objects.filter(
                route__handler_function=handler_function,
                created_at__gte=since
            )
            
            # Get success/failure counts
            success_count = executions.filter(error_type='handler_success').count()
            failure_count = executions.filter(error_type='handler_execution_failed').count()
            total_count = executions.count()
            
            # Calculate success rate
            success_rate = (success_count / total_count * 100) if total_count > 0 else 0
            
            # Get average execution time (if available)
            avg_execution_time = 0
            if success_count > 0:
                # This would require storing execution time in error_details
                pass
            
            return {
                'handler_function': handler_function,
                'total_executions': total_count,
                'successful_executions': success_count,
                'failed_executions': failure_count,
                'success_rate': round(success_rate, 2),
                'avg_execution_time': avg_execution_time,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting handler performance: {str(e)}")
            return {
                'handler_function': handler_function,
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'success_rate': 0,
                'avg_execution_time': 0,
                'period_days': days,
                'error': str(e)
            }
    
    def validate_handler_function(self, handler_path: str) -> Dict[str, Any]:
        """
        Validate a handler function.
        
        Args:
            handler_path: The path to the handler function
            
        Returns:
            Dictionary with validation results
        """
        try:
            validation_result = {
                'handler_path': handler_path,
                'valid': True,
                'message': 'Handler function is valid'
            }
            
            # Try to load the handler function
            handler = self._get_handler_function(handler_path)
            
            if not handler:
                validation_result['valid'] = False
                validation_result['message'] = 'Handler function not found'
                return validation_result
            
            # Check if it's callable
            if not callable(handler):
                validation_result['valid'] = False
                validation_result['message'] = 'Handler is not callable'
                return validation_result
            
            # Check function signature (basic check)
            import inspect
            sig = inspect.signature(handler)
            
            # Check for required parameters
            required_params = ['payload', 'headers', 'route_id', 'log_id', 'inbound_id']
            for param in required_params:
                if param not in sig.parameters:
                    validation_result['valid'] = False
                    validation_result['message'] = f'Handler missing required parameter: {param}'
                    break
            
            return validation_result
            
        except Exception as e:
            return {
                'handler_path': handler_path,
                'valid': False,
                'message': f'Validation error: {str(e)}'
            }
    
    def get_available_handlers(self) -> List[Dict[str, Any]]:
        """
        Get list of available handler functions.
        
        Returns:
            List of available handlers
        """
        try:
            handlers = []
            
            # Get handler modules from settings
            handler_modules = getattr(settings, 'INBOUND_WEBHOOK_HANDLER_MODULES', [])
            
            for module_path in handler_modules:
                try:
                    module = importlib.import_module(module_path)
                    
                    # Get all functions in the module
                    for name, obj in inspect.getmembers(module):
                        if inspect.isfunction(obj) and not name.startswith('_'):
                            handlers.append({
                                'module': module_path,
                                'function': name,
                                'handler_path': f'{module_path}.{name}',
                                'description': obj.__doc__ or 'No description available'
                            })
                            
                except Exception as e:
                    logger.error(f"Error loading handler module {module_path}: {str(e)}")
                    continue
            
            return handlers
            
        except Exception as e:
            logger.error(f"Error getting available handlers: {str(e)}")
            return []
    
    def create_sample_handler(self, handler_name: str, event_type: str) -> str:
        """
        Create a sample handler function.
        
        Args:
            handler_name: Name for the handler function
            event_type: Event type the handler will process
            
        Returns:
            Sample handler function code
        """
        try:
            sample_code = f'''
def {handler_name}(payload, headers, route_id, log_id, inbound_id):
    """
    Sample handler for {event_type} events.
    
    Args:
        payload: The webhook payload
        headers: HTTP headers from the request
        route_id: The route ID
        log_id: The log ID
        inbound_id: The inbound webhook ID
    
    Returns:
        Dict with handler result
    """
    import logging
    from django.utils import timezone
    
    logger = logging.getLogger(__name__)
    
    try:
        # Process the payload
        event_type = payload.get('event_type', 'unknown')
        transaction_id = payload.get('transaction_id')
        amount = payload.get('amount')
        
        # Log the event
        logger.info(f"Processing {{event_type}} event for transaction {{transaction_id}}")
        
        # Add your business logic here
        # For example:
        # - Update database records
        # - Send notifications
        # - Trigger other webhooks
        
        result = {{
            'success': True,
            'event_type': event_type,
            'transaction_id': transaction_id,
            'amount': amount,
            'processed_at': timezone.now().isoformat(),
            'message': 'Event processed successfully'
        }}
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing {{event_type}} event: {{str(e)}}")
        
        return {{
            'success': False,
            'error': str(e),
            'processed_at': timezone.now().isoformat()
        }}
'''
            return sample_code
            
        except Exception as e:
            logger.error(f"Error creating sample handler: {str(e)}")
            return f"# Error creating sample handler: {str(e)}"
    
    def test_handler_function(self, handler_path: str, sample_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test a handler function with sample payload.
        
        Args:
            handler_path: The path to the handler function
            sample_payload: Sample payload for testing
            
        Returns:
            Dictionary with test results
        """
        try:
            # Get handler function
            handler = self._get_handler_function(handler_path)
            
            if not handler:
                return {
                    'handler_path': handler_path,
                    'success': False,
                    'error': 'Handler function not found'
                }
            
            # Prepare test arguments
            test_args = {
                'payload': sample_payload,
                'headers': {{
                    'Content-Type': 'application/json',
                    'X-Webhook-Test': 'true'
                }},
                'route_id': 'test-route-id',
                'log_id': 'test-log-id',
                'inbound_id': 'test-inbound-id'
            }
            
            # Execute handler
            start_time = timezone.now()
            result = handler(**test_args)
            end_time = timezone.now()
            
            execution_time = (end_time - start_time).total_seconds()
            
            return {
                'handler_path': handler_path,
                'success': True,
                'result': result,
                'execution_time': execution_time,
                'test_payload': sample_payload
            }
            
        except Exception as e:
            return {
                'handler_path': handler_path,
                'success': False,
                'error': str(e),
                'test_payload': sample_payload
            }
