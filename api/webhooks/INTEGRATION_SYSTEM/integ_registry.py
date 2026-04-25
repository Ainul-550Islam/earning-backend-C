"""Integration Registry

This module provides registry management for integration system
with comprehensive handler registration and discovery capabilities.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .integ_constants import IntegrationType, HandlerType
from .integ_exceptions import RegistryError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Integration registry for webhook system.
    Manages handler registration, discovery, and lifecycle.
    """
    
    def __init__(self):
        """Initialize the integration registry."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        
        # Registry storage
        self._handlers = {}
        self._integrations = {}
        self._event_mappings = {}
        self._handler_metadata = {}
        
        # Load configuration
        self._load_configuration()
        
        # Initialize registry
        self._initialize_registry()
    
    def _load_configuration(self):
        """Load registry configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_REGISTRY_CONFIG', {})
            self.cache_timeout = self.config.get('cache_timeout', 300)  # 5 minutes
            self.auto_discovery = self.config.get('auto_discovery', True)
            self.max_handlers = self.config.get('max_handlers', 1000)
            self.max_integrations = self.config.get('max_integrations', 100)
            
            self.logger.info("Registry configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading registry configuration: {str(e)}")
            self.config = {}
            self.cache_timeout = 300
            self.auto_discovery = True
            self.max_handlers = 1000
            self.max_integrations = 100
    
    def _initialize_registry(self):
        """Initialize the registry."""
        try:
            # Load initial handlers from configuration
            initial_handlers = self.config.get('initial_handlers', {})
            for handler_name, handler_config in initial_handlers.items():
                self._register_handler_from_config(handler_name, handler_config)
            
            # Auto-discover handlers if enabled
            if self.auto_discovery:
                self._auto_discover_handlers()
            
            self.logger.info(f"Registry initialized with {len(self._handlers)} handlers")
            
        except Exception as e:
            self.logger.error(f"Error initializing registry: {str(e)}")
    
    def _register_handler_from_config(self, handler_name: str, config: Dict[str, Any]):
        """Register handler from configuration."""
        try:
            handler_path = config.get('path')
            if not handler_path:
                self.logger.warning(f"No path specified for handler {handler_name}")
                return
            
            # Import handler
            module_path, function_name = handler_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            handler = getattr(module, function_name)
            
            # Register handler
            self.register_handler(handler_name, handler, config)
            
        except Exception as e:
            self.logger.error(f"Error registering handler {handler_name} from config: {str(e)}")
    
    def _auto_discover_handlers(self):
        """Auto-discover handlers from configured modules."""
        try:
            discovery_modules = self.config.get('discovery_modules', [])
            
            for module_name in discovery_modules:
                try:
                    module = __import__(module_name, fromlist=[''])
                    
                    # Look for handler functions
                    for attr_name in dir(module):
                        if attr_name.startswith('handle_') and callable(getattr(module, attr_name)):
                            handler = getattr(module, attr_name)
                            handler_name = f"{module_name}.{attr_name}"
                            
                            # Auto-register with default config
                            config = {
                                'module': module_name,
                                'function': attr_name,
                                'auto_discovered': True,
                                'registered_at': timezone.now()
                            }
                            
                            self.register_handler(handler_name, handler, config)
                            
                except Exception as e:
                    self.logger.error(f"Error discovering handlers in module {module_name}: {str(e)}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error in auto-discovery: {str(e)}")
    
    def register_handler(self, name: str, handler: Callable, config: Dict[str, Any] = None) -> bool:
        """
        Register a handler in the registry.
        
        Args:
            name: Handler name
            handler: Handler function
            config: Handler configuration
            
        Returns:
            True if registration successful
        """
        try:
            # Check handler limit
            if len(self._handlers) >= self.max_handlers:
                raise RegistryError(f"Maximum handlers limit reached: {self.max_handlers}")
            
            # Validate handler
            if not callable(handler):
                raise RegistryError("Handler must be callable")
            
            # Check if handler already exists
            if name in self._handlers:
                self.logger.warning(f"Handler {name} already exists, updating...")
            
            # Prepare handler metadata
            metadata = {
                'name': name,
                'handler': handler,
                'config': config or {},
                'registered_at': timezone.now(),
                'last_used': None,
                'usage_count': 0,
                'status': 'active'
            }
            
            # Store handler
            self._handlers[name] = metadata
            
            # Update event mappings
            event_types = config.get('event_types', [])
            for event_type in event_types:
                if event_type not in self._event_mappings:
                    self._event_mappings[event_type] = []
                self._event_mappings[event_type].append(name)
            
            # Cache handler info
            self._cache_handler_info(name, metadata)
            
            self.logger.info(f"Handler {name} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering handler {name}: {str(e)}")
            return False
    
    def unregister_handler(self, name: str) -> bool:
        """
        Unregister a handler from the registry.
        
        Args:
            name: Handler name
            
        Returns:
            True if unregistration successful
        """
        try:
            if name not in self._handlers:
                self.logger.warning(f"Handler {name} not found")
                return False
            
            # Get handler metadata
            metadata = self._handlers[name]
            
            # Remove from event mappings
            event_types = metadata['config'].get('event_types', [])
            for event_type in event_types:
                if event_type in self._event_mappings:
                    if name in self._event_mappings[event_type]:
                        self._event_mappings[event_type].remove(name)
                    
                    # Remove empty mappings
                    if not self._event_mappings[event_type]:
                        del self._event_mappings[event_type]
            
            # Remove handler
            del self._handlers[name]
            
            # Clear cache
            cache.delete(f"handler_info:{name}")
            
            self.logger.info(f"Handler {name} unregistered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unregistering handler {name}: {str(e)}")
            return False
    
    def get_handler(self, name: str) -> Optional[Callable]:
        """
        Get a handler by name.
        
        Args:
            name: Handler name
            
        Returns:
            Handler function or None
        """
        try:
            # Try cache first
            cached_info = cache.get(f"handler_info:{name}")
            if cached_info:
                # Update usage statistics
                self._update_handler_usage(name)
                return cached_info['handler']
            
            # Get from registry
            if name in self._handlers:
                metadata = self._handlers[name]
                self._update_handler_usage(name)
                return metadata['handler']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting handler {name}: {str(e)}")
            return None
    
    def _update_handler_usage(self, name: str):
        """Update handler usage statistics."""
        try:
            if name in self._handlers:
                self._handlers[name]['last_used'] = timezone.now()
                self._handlers[name]['usage_count'] += 1
                
                # Update cache
                self._cache_handler_info(name, self._handlers[name])
                
        except Exception as e:
            self.logger.error(f"Error updating handler usage: {str(e)}")
    
    def _cache_handler_info(self, name: str, metadata: Dict[str, Any]):
        """Cache handler information."""
        try:
            cache.set(f"handler_info:{name}", metadata, self.cache_timeout)
        except Exception as e:
            self.logger.error(f"Error caching handler info: {str(e)}")
    
    def get_handlers_for_event(self, event_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get handlers for a specific event type.
        
        Args:
            event_type: Event type
            
        Returns:
            Dictionary of handlers
        """
        try:
            handlers = {}
            
            # Get handlers from event mappings
            if event_type in self._event_mappings:
                for handler_name in self._event_mappings[event_type]:
                    if handler_name in self._handlers:
                        handlers[handler_name] = self._handlers[handler_name]
            
            # Get wildcard handlers
            if '*' in self._event_mappings:
                for handler_name in self._event_mappings['*']:
                    if handler_name not in handlers and handler_name in self._handlers:
                        handlers[handler_name] = self._handlers[handler_name]
            
            return handlers
            
        except Exception as e:
            self.logger.error(f"Error getting handlers for event {event_type}: {str(e)}")
            return {}
    
    def get_all_handlers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered handlers.
        
        Returns:
            Dictionary of all handlers
        """
        try:
            return self._handlers.copy()
        except Exception as e:
            self.logger.error(f"Error getting all handlers: {str(e)}")
            return {}
    
    def get_handler_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get handler information.
        
        Args:
            name: Handler name
            
        Returns:
            Handler information or None
        """
        try:
            if name in self._handlers:
                return {
                    'name': name,
                    'config': self._handlers[name]['config'],
                    'registered_at': self._handlers[name]['registered_at'],
                    'last_used': self._handlers[name]['last_used'],
                    'usage_count': self._handlers[name]['usage_count'],
                    'status': self._handlers[name]['status']
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting handler info {name}: {str(e)}")
            return None
    
    def search_handlers(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search handlers by query and filters.
        
        Args:
            query: Search query
            filters: Additional filters
            
        Returns:
            List of matching handlers
        """
        try:
            results = []
            
            for name, metadata in self._handlers.items():
                # Check query match
                if query and query.lower() not in name.lower():
                    continue
                
                # Check filters
                if filters:
                    match = True
                    
                    if 'event_types' in filters:
                        handler_events = set(metadata['config'].get('event_types', []))
                        filter_events = set(filters['event_types'])
                        if not handler_events.intersection(filter_events):
                            match = False
                    
                    if 'status' in filters:
                        if metadata['status'] != filters['status']:
                            match = False
                    
                    if 'module' in filters:
                        handler_module = metadata['config'].get('module', '')
                        if filters['module'] not in handler_module:
                            match = False
                    
                    if not match:
                        continue
                
                # Add to results
                results.append({
                    'name': name,
                    'config': metadata['config'],
                    'registered_at': metadata['registered_at'],
                    'last_used': metadata['last_used'],
                    'usage_count': metadata['usage_count'],
                    'status': metadata['status']
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching handlers: {str(e)}")
            return []
    
    def register_integration(self, integration_type: str, config: Dict[str, Any]) -> bool:
        """
        Register an integration.
        
        Args:
            integration_type: Type of integration
            config: Integration configuration
            
        Returns:
            True if registration successful
        """
        try:
            # Check integration limit
            if len(self._integrations) >= self.max_integrations:
                raise RegistryError(f"Maximum integrations limit reached: {self.max_integrations}")
            
            # Validate integration type
            if integration_type not in IntegrationType.CHOICES:
                raise RegistryError(f"Invalid integration type: {integration_type}")
            
            # Check if integration already exists
            if integration_type in self._integrations:
                self.logger.warning(f"Integration {integration_type} already exists, updating...")
            
            # Store integration
            self._integrations[integration_type] = {
                'type': integration_type,
                'config': config,
                'registered_at': timezone.now(),
                'status': 'active'
            }
            
            self.logger.info(f"Integration {integration_type} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering integration {integration_type}: {str(e)}")
            return False
    
    def unregister_integration(self, integration_type: str) -> bool:
        """
        Unregister an integration.
        
        Args:
            integration_type: Type of integration
            
        Returns:
            True if unregistration successful
        """
        try:
            if integration_type in self._integrations:
                del self._integrations[integration_type]
                self.logger.info(f"Integration {integration_type} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Integration {integration_type} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering integration {integration_type}: {str(e)}")
            return False
    
    def get_integration(self, integration_type: str) -> Optional[Dict[str, Any]]:
        """
        Get integration by type.
        
        Args:
            integration_type: Type of integration
            
        Returns:
            Integration configuration or None
        """
        try:
            return self._integrations.get(integration_type)
        except Exception as e:
            self.logger.error(f"Error getting integration {integration_type}: {str(e)}")
            return None
    
    def get_all_integrations(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered integrations.
        
        Returns:
            Dictionary of all integrations
        """
        try:
            return self._integrations.copy()
        except Exception as e:
            self.logger.error(f"Error getting all integrations: {str(e)}")
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get registry status.
        
        Returns:
            Registry status
        """
        try:
            return {
                'registry': {
                    'status': 'running',
                    'total_handlers': len(self._handlers),
                    'total_integrations': len(self._integrations),
                    'event_mappings': len(self._event_mappings),
                    'cache_timeout': self.cache_timeout,
                    'auto_discovery': self.auto_discovery,
                    'uptime': self.monitor.get_uptime()
                },
                'handlers': {
                    'active': len([h for h in self._handlers.values() if h['status'] == 'active']),
                    'total': len(self._handlers),
                    'usage_stats': {
                        'total_usage': sum(h['usage_count'] for h in self._handlers.values()),
                        'most_used': max(self._handlers.items(), key=lambda x: x[1]['usage_count'])[0] if self._handlers else None
                    }
                },
                'integrations': {
                    'active': len([i for i in self._integrations.values() if i['status'] == 'active']),
                    'total': len(self._integrations)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting registry status: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of registry.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': 'healthy',
                'components': {},
                'checks': []
            }
            
            # Check handlers
            active_handlers = len([h for h in self._handlers.values() if h['status'] == 'active'])
            health_status['components']['handlers'] = {
                'status': 'healthy',
                'total_handlers': len(self._handlers),
                'active_handlers': active_handlers
            }
            
            # Check integrations
            active_integrations = len([i for i in self._integrations.values() if i['status'] == 'active'])
            health_status['components']['integrations'] = {
                'status': 'healthy',
                'total_integrations': len(self._integrations),
                'active_integrations': active_integrations
            }
            
            # Check cache
            try:
                cache.set('health_check', 'test', 10)
                cache_result = cache.get('health_check')
                health_status['components']['cache'] = {
                    'status': 'healthy' if cache_result == 'test' else 'unhealthy'
                }
            except Exception:
                health_status['components']['cache'] = {
                    'status': 'unhealthy',
                    'error': 'Cache connection failed'
                }
                health_status['overall'] = 'unhealthy'
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': 'unhealthy',
                'error': str(e)
            }
    
    def clear_cache(self) -> bool:
        """
        Clear registry cache.
        
        Returns:
            True if clear successful
        """
        try:
            # Clear all handler info cache
            for name in self._handlers:
                cache.delete(f"handler_info:{name}")
            
            self.logger.info("Registry cache cleared")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    def reload_configuration(self) -> bool:
        """
        Reload registry configuration.
        
        Returns:
            True if reload successful
        """
        try:
            # Clear current registry
            self._handlers.clear()
            self._integrations.clear()
            self._event_mappings.clear()
            
            # Clear cache
            self.clear_cache()
            
            # Reload configuration
            self._load_configuration()
            self._initialize_registry()
            
            self.logger.info("Registry configuration reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {str(e)}")
            return False
