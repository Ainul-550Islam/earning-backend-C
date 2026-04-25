"""Integration Handler

This module provides the main integration handler for webhook system
with comprehensive event processing and routing capabilities.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError

from .integ_registry import IntegrationRegistry
from .integ_adapter import IntegrationAdapter
from .integ_exceptions import IntegrationError, HandlerError
from .integ_constants import IntegrationType, HandlerStatus
from .data_validator import DataValidator
from .fallback_logic import FallbackLogic
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class IntegrationHandler:
    """
    Main integration handler for webhook system.
    Coordinates all integration components and provides unified interface.
    """
    
    def __init__(self):
        """Initialize the integration handler."""
        self.registry = IntegrationRegistry()
        self.adapter = IntegrationAdapter()
        self.validator = DataValidator()
        self.fallback = FallbackLogic()
        self.monitor = PerformanceMonitor()
        self.logger = logger
        
        # Initialize handlers
        self._handlers = {}
        self._middleware = []
        self._hooks = {}
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load integration configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_INTEGRATION_CONFIG', {})
            self.enabled_handlers = self.config.get('enabled_handlers', [])
            self.middleware_config = self.config.get('middleware', [])
            self.hooks_config = self.config.get('hooks', {})
            
            self.logger.info("Integration configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading integration configuration: {str(e)}")
            self.config = {}
            self.enabled_handlers = []
            self.middleware_config = []
            self.hooks_config = {}
    
    def register_handler(self, name: str, handler: Callable, config: Dict[str, Any] = None) -> bool:
        """
        Register a new integration handler.
        
        Args:
            name: Handler name
            handler: Handler function or class
            config: Handler configuration
            
        Returns:
            True if registration successful
        """
        try:
            # Validate handler
            if not callable(handler):
                raise HandlerError("Handler must be callable")
            
            # Check if handler is enabled
            if self.enabled_handlers and name not in self.enabled_handlers:
                self.logger.warning(f"Handler {name} not in enabled handlers list")
                return False
            
            # Register handler
            self._handlers[name] = {
                'handler': handler,
                'config': config or {},
                'status': HandlerStatus.REGISTERED,
                'registered_at': timezone.now()
            }
            
            # Register in registry
            self.registry.register_handler(name, handler, config)
            
            self.logger.info(f"Handler {name} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering handler {name}: {str(e)}")
            return False
    
    def unregister_handler(self, name: str) -> bool:
        """
        Unregister an integration handler.
        
        Args:
            name: Handler name
            
        Returns:
            True if unregistration successful
        """
        try:
            if name in self._handlers:
                del self._handlers[name]
                self.registry.unregister_handler(name)
                self.logger.info(f"Handler {name} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Handler {name} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering handler {name}: {str(e)}")
            return False
    
    def handle_event(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle an integration event.
        
        Args:
            event_type: Type of event to handle
            data: Event data
            context: Additional context
            
        Returns:
            Handler result
        """
        try:
            # Start performance monitoring
            with self.monitor.measure_event(event_type) as measurement:
                # Validate event data
                self.validator.validate_event_data(event_type, data)
                
                # Apply middleware
                processed_data = self._apply_middleware(event_type, data, context)
                
                # Execute hooks
                self._execute_hooks('before_handle', event_type, processed_data, context)
                
                # Get handlers for event type
                handlers = self.registry.get_handlers_for_event(event_type)
                
                if not handlers:
                    self.logger.warning(f"No handlers found for event type: {event_type}")
                    return self._handle_no_handlers(event_type, processed_data, context)
                
                # Execute handlers
                results = []
                for handler_name, handler_info in handlers.items():
                    try:
                        result = self._execute_handler(handler_name, handler_info, event_type, processed_data, context)
                        results.append({
                            'handler': handler_name,
                            'success': True,
                            'result': result
                        })
                    except Exception as e:
                        self.logger.error(f"Error in handler {handler_name}: {str(e)}")
                        
                        # Apply fallback logic
                        fallback_result = self.fallback.handle_handler_error(handler_name, e, event_type, processed_data, context)
                        results.append({
                            'handler': handler_name,
                            'success': False,
                            'error': str(e),
                            'fallback_result': fallback_result
                        })
                
                # Execute post hooks
                self._execute_hooks('after_handle', event_type, processed_data, context, results)
                
                # Compile final result
                final_result = {
                    'event_type': event_type,
                    'success': any(r['success'] for r in results),
                    'handlers': results,
                    'processed_at': timezone.now().isoformat(),
                    'performance': measurement.get_metrics()
                }
                
                return final_result
                
        except Exception as e:
            self.logger.error(f"Error handling event {event_type}: {str(e)}")
            return {
                'event_type': event_type,
                'success': False,
                'error': str(e),
                'processed_at': timezone.now().isoformat()
            }
    
    def _apply_middleware(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply middleware to event data."""
        processed_data = data.copy()
        
        for middleware_config in self.middleware_config:
            try:
                middleware_name = middleware_config.get('name')
                middleware_class = middleware_config.get('class')
                middleware_options = middleware_config.get('options', {})
                
                if not middleware_class:
                    continue
                
                # Import and instantiate middleware
                module_path, class_name = middleware_class.rsplit('.', 1)
                module = __import__(module_path, fromlist=[class_name])
                middleware_class = getattr(module, class_name)
                middleware = middleware_class(**middleware_options)
                
                # Apply middleware
                if hasattr(middleware, 'process'):
                    processed_data = middleware.process(event_type, processed_data, context)
                
            except Exception as e:
                self.logger.error(f"Error applying middleware {middleware_name}: {str(e)}")
                continue
        
        return processed_data
    
    def _execute_hooks(self, hook_type: str, event_type: str, data: Dict[str, Any], context: Dict[str, Any], results: List[Dict] = None):
        """Execute hooks for event processing."""
        hooks = self.hooks_config.get(hook_type, [])
        
        for hook_config in hooks:
            try:
                hook_name = hook_config.get('name')
                hook_function = hook_config.get('function')
                hook_options = hook_config.get('options', {})
                
                if not hook_function:
                    continue
                
                # Import and execute hook
                module_path, function_name = hook_function.rsplit('.', 1)
                module = __import__(module_path, fromlist=[function_name])
                hook_func = getattr(module, function_name)
                
                if hook_type == 'before_handle':
                    hook_func(event_type, data, context, **hook_options)
                elif hook_type == 'after_handle':
                    hook_func(event_type, data, context, results, **hook_options)
                
            except Exception as e:
                self.logger.error(f"Error executing hook {hook_name}: {str(e)}")
                continue
    
    def _execute_handler(self, handler_name: str, handler_info: Dict[str, Any], event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute a specific handler."""
        handler = handler_info['handler']
        config = handler_info['config']
        
        # Update handler status
        self._handlers[handler_name]['status'] = HandlerStatus.RUNNING
        self._handlers[handler_name]['last_run'] = timezone.now()
        
        try:
            # Execute handler
            if hasattr(handler, '__call__'):
                result = handler(event_type, data, context, config)
            else:
                result = handler(event_type, data, context)
            
            # Update handler status
            self._handlers[handler_name]['status'] = HandlerStatus.SUCCESS
            self._handlers[handler_name]['last_success'] = timezone.now()
            
            return result
            
        except Exception as e:
            # Update handler status
            self._handlers[handler_name]['status'] = HandlerStatus.ERROR
            self._handlers[handler_name]['last_error'] = str(e)
            self._handlers[handler_name]['last_error_time'] = timezone.now()
            
            raise
    
    def _handle_no_handlers(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle case when no handlers are found."""
        self.logger.warning(f"No handlers found for event type: {event_type}")
        
        # Apply fallback logic
        return self.fallback.handle_no_handlers(event_type, data, context)
    
    def get_handler_status(self, handler_name: str = None) -> Dict[str, Any]:
        """
        Get status of handlers.
        
        Args:
            handler_name: Optional specific handler name
            
        Returns:
            Handler status information
        """
        try:
            if handler_name:
                if handler_name in self._handlers:
                    return {
                        'handler': handler_name,
                        'status': self._handlers[handler_name]['status'],
                        'config': self._handlers[handler_name]['config'],
                        'registered_at': self._handlers[handler_name]['registered_at'],
                        'last_run': self._handlers[handler_name].get('last_run'),
                        'last_success': self._handlers[handler_name].get('last_success'),
                        'last_error': self._handlers[handler_name].get('last_error'),
                        'last_error_time': self._handlers[handler_name].get('last_error_time')
                    }
                else:
                    return {'error': f'Handler {handler_name} not found'}
            else:
                return {
                    'total_handlers': len(self._handlers),
                    'handlers': {
                        name: {
                            'status': info['status'],
                            'registered_at': info['registered_at'],
                            'last_run': info.get('last_run'),
                            'last_success': info.get('last_success'),
                            'last_error': info.get('last_error')
                        }
                        for name, info in self._handlers.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting handler status: {str(e)}")
            return {'error': str(e)}
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get overall system status.
        
        Returns:
            System status information
        """
        try:
            return {
                'integration_handler': {
                    'status': 'running',
                    'registered_handlers': len(self._handlers),
                    'enabled_handlers': len(self.enabled_handlers),
                    'middleware_count': len(self.middleware_config),
                    'hooks_count': len(self.hooks_config),
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'registry': self.registry.get_status(),
                'adapter': self.adapter.get_status(),
                'validator': self.validator.get_status(),
                'fallback': self.fallback.get_status()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of integration system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': 'healthy',
                'components': {},
                'checks': []
            }
            
            # Check registry
            registry_health = self.registry.health_check()
            health_status['components']['registry'] = registry_health
            if registry_health['status'] != 'healthy':
                health_status['overall'] = 'unhealthy'
            
            # Check adapter
            adapter_health = self.adapter.health_check()
            health_status['components']['adapter'] = adapter_health
            if adapter_health['status'] != 'healthy':
                health_status['overall'] = 'unhealthy'
            
            # Check validator
            validator_health = self.validator.health_check()
            health_status['components']['validator'] = validator_health
            if validator_health['status'] != 'healthy':
                health_status['overall'] = 'unhealthy'
            
            # Check handlers
            failed_handlers = []
            for name, info in self._handlers.items():
                if info['status'] == HandlerStatus.ERROR:
                    failed_handlers.append(name)
            
            if failed_handlers:
                health_status['components']['handlers'] = {
                    'status': 'unhealthy',
                    'failed_handlers': failed_handlers
                }
                health_status['overall'] = 'unhealthy'
            else:
                health_status['components']['handlers'] = {
                    'status': 'healthy',
                    'total_handlers': len(self._handlers)
                }
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': 'unhealthy',
                'error': str(e)
            }
    
    def reload_configuration(self) -> bool:
        """
        Reload integration configuration.
        
        Returns:
            True if reload successful
        """
        try:
            self._load_configuration()
            self.logger.info("Integration configuration reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {str(e)}")
            return False
