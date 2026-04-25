"""
Plugin System for Offer Routing System

This module provides a plugin system for extending the offer routing functionality,
including custom condition evaluators, action executors, and routing strategies.
"""

import logging
import importlib
import inspect
from typing import Dict, Any, List, Optional, Type, Callable
from abc import ABC, abstractmethod
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


# Base Plugin Classes

class BasePlugin(ABC):
    """Base class for all routing plugins."""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.enabled = True
        self.config = {}
        self.logger = logging.getLogger(f"plugin.{name}")
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize the plugin with configuration."""
        pass
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Any:
        """Execute the plugin logic."""
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            'name': self.name,
            'version': self.version,
            'enabled': self.enabled,
            'config': self.config
        }


class ConditionPlugin(BasePlugin):
    """Base class for condition evaluation plugins."""
    
    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the condition and return True/False."""
        pass
    
    def get_supported_fields(self) -> List[str]:
        """Get list of supported field names."""
        return []


class ActionPlugin(BasePlugin):
    """Base class for action execution plugins."""
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the action and return result."""
        pass
    
    def get_required_parameters(self) -> List[str]:
        """Get list of required parameters."""
        return []


class RoutingPlugin(BasePlugin):
    """Base class for routing strategy plugins."""
    
    @abstractmethod
    def route(self, context: Dict[str, Any], routes: List[Any]) -> Optional[Any]:
        """Route to the best option."""
        pass
    
    def get_priority(self) -> int:
        """Get plugin priority for execution order."""
        return 50


class AnalyticsPlugin(BasePlugin):
    """Base class for analytics plugins."""
    
    @abstractmethod
    def collect_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect analytics data."""
        pass
    
    @abstractmethod
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process collected analytics data."""
        pass


# Built-in Plugins

class GeoConditionPlugin(ConditionPlugin):
    """Plugin for geographic condition evaluation."""
    
    def __init__(self):
        super().__init__("geo_condition", "1.0.0")
        self.supported_countries = []
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
            self.supported_countries = config.get('supported_countries', [])
        return True
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        user_country = context.get('country')
        target_countries = context.get('target_countries', [])
        
        if not user_country:
            return True
        
        if not target_countries:
            return True
        
        return user_country in target_countries
    
    def get_supported_fields(self) -> List[str]:
        return ['country', 'target_countries']


class DeviceConditionPlugin(ConditionPlugin):
    """Plugin for device condition evaluation."""
    
    def __init__(self):
        super().__init__("device_condition", "1.0.0")
        self.supported_devices = []
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
            self.supported_devices = config.get('supported_devices', [])
        return True
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        user_device = context.get('device_type')
        target_devices = context.get('target_devices', [])
        
        if not user_device:
            return True
        
        if not target_devices:
            return True
        
        return user_device in target_devices
    
    def get_supported_fields(self) -> List[str]:
        return ['device_type', 'target_devices']


class TimeConditionPlugin(ConditionPlugin):
    """Plugin for time-based condition evaluation."""
    
    def __init__(self):
        super().__init__("time_condition", "1.0.0")
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
        return True
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        current_time = timezone.now()
        
        # Check hours
        target_hours = context.get('target_hours', [])
        if target_hours and current_time.hour not in target_hours:
            return False
        
        # Check days of week
        target_days = context.get('target_days_of_week', [])
        if target_days and current_time.weekday() not in target_days:
            return False
        
        # Check date range
        start_date = context.get('start_date')
        end_date = context.get('end_date')
        
        if start_date and current_time < start_date:
            return False
        
        if end_date and current_time > end_date:
            return False
        
        return True
    
    def get_supported_fields(self) -> List[str]:
        return ['target_hours', 'target_days_of_week', 'start_date', 'end_date']


class ShowOfferActionPlugin(ActionPlugin):
    """Plugin for showing offers."""
    
    def __init__(self):
        super().__init__("show_offer_action", "1.0.0")
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        offer_ids = context.get('offer_ids', [])
        
        if not offer_ids:
            return {
                'success': False,
                'error': 'No offer IDs provided'
            }
        
        # Logic to show offers
        self.logger.info(f"Showing offers: {offer_ids}")
        
        return {
            'success': True,
            'action': 'show_offers',
            'offer_ids': offer_ids,
            'timestamp': timezone.now()
        }
    
    def get_required_parameters(self) -> List[str]:
        return ['offer_ids']


class LogEventActionPlugin(ActionPlugin):
    """Plugin for logging events."""
    
    def __init__(self):
        super().__init__("log_event_action", "1.0.0")
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        event_type = context.get('event_type', 'routing_action')
        event_data = context.get('event_data', {})
        
        # Log the event
        self.logger.info(f"Event logged: {event_type} - {event_data}")
        
        return {
            'success': True,
            'action': 'log_event',
            'event_type': event_type,
            'event_data': event_data,
            'timestamp': timezone.now()
        }
    
    def get_required_parameters(self) -> List[str]:
        return ['event_type']


class PriorityRoutingPlugin(RoutingPlugin):
    """Plugin for priority-based routing."""
    
    def __init__(self):
        super().__init__("priority_routing", "1.0.0")
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
        return True
    
    def route(self, context: Dict[str, Any], routes: List[Any]) -> Optional[Any]:
        if not routes:
            return None
        
        # Sort by priority (higher priority first)
        sorted_routes = sorted(routes, key=lambda r: getattr(r, 'priority', 50), reverse=True)
        
        # Return the highest priority route
        return sorted_routes[0]
    
    def get_priority(self) -> int:
        return 100


class PersonalizedRoutingPlugin(RoutingPlugin):
    """Plugin for personalized routing."""
    
    def __init__(self):
        super().__init__("personalized_routing", "1.0.0")
        self.user_preferences = {}
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
            self.user_preferences = config.get('user_preferences', {})
        return True
    
    def route(self, context: Dict[str, Any], routes: List[Any]) -> Optional[Any]:
        user_id = context.get('user_id')
        
        if not user_id or not routes:
            return None
        
        # Get user preferences
        user_prefs = self.user_preferences.get(str(user_id), {})
        
        # Score routes based on user preferences
        scored_routes = []
        for route in routes:
            score = self._calculate_route_score(route, user_prefs, context)
            scored_routes.append((route, score))
        
        # Sort by score (highest first)
        scored_routes.sort(key=lambda x: x[1], reverse=True)
        
        # Return the highest scoring route
        return scored_routes[0][0] if scored_routes else None
    
    def _calculate_route_score(self, route, user_prefs: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Calculate route score based on user preferences."""
        base_score = getattr(route, 'priority', 50)
        
        # Add preference-based scoring
        if 'preferred_categories' in user_prefs:
            route_categories = getattr(route, 'categories', [])
            preferred_categories = user_prefs['preferred_categories']
            
            # Bonus for matching categories
            matching_categories = set(route_categories) & set(preferred_categories)
            base_score += len(matching_categories) * 10
        
        return base_score
    
    def get_priority(self) -> int:
        return 90


class PerformanceAnalyticsPlugin(AnalyticsPlugin):
    """Plugin for performance analytics."""
    
    def __init__(self):
        super().__init__("performance_analytics", "1.0.0")
        self.performance_data = {}
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        if config:
            self.config = config
        return True
    
    def collect_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect performance data."""
        return {
            'timestamp': timezone.now(),
            'user_id': context.get('user_id'),
            'route_id': context.get('route_id'),
            'response_time': context.get('response_time'),
            'success': context.get('success', False),
            'score': context.get('score')
        }
    
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process collected performance data."""
        # Store in cache for aggregation
        cache_key = f"perf_analytics:{data.get('user_id')}"
        
        # Get existing data
        existing_data = cache.get(cache_key, [])
        existing_data.append(data)
        
        # Keep only last 100 entries per user
        if len(existing_data) > 100:
            existing_data = existing_data[-100:]
        
        # Update cache
        cache.set(cache_key, existing_data, timeout=3600)  # 1 hour
        
        # Calculate aggregates
        if existing_data:
            avg_response_time = sum(d.get('response_time', 0) for d in existing_data) / len(existing_data)
            success_rate = sum(1 for d in existing_data if d.get('success', False)) / len(existing_data)
        else:
            avg_response_time = 0
            success_rate = 0
        
        return {
            'user_id': data.get('user_id'),
            'total_requests': len(existing_data),
            'avg_response_time': avg_response_time,
            'success_rate': success_rate,
            'last_updated': timezone.now()
        }


# Plugin Manager

class PluginManager:
    """Manager for all routing plugins."""
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.condition_plugins: Dict[str, ConditionPlugin] = {}
        self.action_plugins: Dict[str, ActionPlugin] = {}
        self.routing_plugins: Dict[str, RoutingPlugin] = {}
        self.analytics_plugins: Dict[str, AnalyticsPlugin] = {}
        self.logger = logging.getLogger(__name__)
        
        self._load_builtin_plugins()
        self._load_external_plugins()
    
    def _load_builtin_plugins(self):
        """Load built-in plugins."""
        builtin_plugins = [
            GeoConditionPlugin(),
            DeviceConditionPlugin(),
            TimeConditionPlugin(),
            ShowOfferActionPlugin(),
            LogEventActionPlugin(),
            PriorityRoutingPlugin(),
            PersonalizedRoutingPlugin(),
            PerformanceAnalyticsPlugin()
        ]
        
        for plugin in builtin_plugins:
            self.register_plugin(plugin)
    
    def _load_external_plugins(self):
        """Load external plugins from settings."""
        external_plugins = getattr(settings, 'EXTERNAL_ROUTING_PLUGINS', [])
        
        for plugin_config in external_plugins:
            try:
                plugin = self._load_external_plugin(plugin_config)
                if plugin:
                    self.register_plugin(plugin)
            except Exception as e:
                self.logger.error(f"Failed to load external plugin {plugin_config}: {str(e)}")
    
    def _load_external_plugin(self, plugin_config: Dict[str, Any]) -> Optional[BasePlugin]:
        """Load an external plugin from configuration."""
        module_path = plugin_config.get('module')
        class_name = plugin_config.get('class')
        config = plugin_config.get('config', {})
        
        if not module_path or not class_name:
            self.logger.error("Plugin config must include 'module' and 'class'")
            return None
        
        try:
            # Import the module
            module = importlib.import_module(module_path)
            
            # Get the class
            plugin_class = getattr(module, class_name)
            
            # Check if it's a valid plugin class
            if not issubclass(plugin_class, BasePlugin):
                self.logger.error(f"Class {class_name} is not a valid plugin class")
                return None
            
            # Create plugin instance
            plugin = plugin_class()
            
            # Initialize plugin
            if plugin.initialize(config):
                self.logger.info(f"Loaded external plugin: {plugin.name}")
                return plugin
            else:
                self.logger.error(f"Failed to initialize plugin: {plugin.name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading external plugin {module_path}.{class_name}: {str(e)}")
            return None
    
    def register_plugin(self, plugin: BasePlugin):
        """Register a plugin."""
        self.plugins[plugin.name] = plugin
        
        # Register in specific plugin categories
        if isinstance(plugin, ConditionPlugin):
            self.condition_plugins[plugin.name] = plugin
        elif isinstance(plugin, ActionPlugin):
            self.action_plugins[plugin.name] = plugin
        elif isinstance(plugin, RoutingPlugin):
            self.routing_plugins[plugin.name] = plugin
        elif isinstance(plugin, AnalyticsPlugin):
            self.analytics_plugins[plugin.name] = plugin
        
        self.logger.info(f"Registered plugin: {plugin.name}")
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """Unregister a plugin."""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            
            # Remove from specific categories
            self.condition_plugins.pop(plugin_name, None)
            self.action_plugins.pop(plugin_name, None)
            self.routing_plugins.pop(plugin_name, None)
            self.analytics_plugins.pop(plugin_name, None)
            
            self.logger.info(f"Unregistered plugin: {plugin_name}")
            return True
        
        return False
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: Type[BasePlugin]) -> List[BasePlugin]:
        """Get all plugins of a specific type."""
        plugins = []
        for plugin in self.plugins.values():
            if isinstance(plugin, plugin_type):
                plugins.append(plugin)
        return plugins
    
    def get_enabled_plugins(self) -> List[BasePlugin]:
        """Get all enabled plugins."""
        return [plugin for plugin in self.plugins.values() if plugin.enabled]
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            plugin.enabled = True
            self.logger.info(f"Enabled plugin: {plugin_name}")
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            plugin.enabled = False
            self.logger.info(f"Disabled plugin: {plugin_name}")
            return True
        return False
    
    def execute_condition_plugins(self, context: Dict[str, Any]) -> Dict[str, bool]:
        """Execute all enabled condition plugins."""
        results = {}
        
        for plugin in self.get_enabled_plugins():
            if isinstance(plugin, ConditionPlugin):
                try:
                    result = plugin.evaluate(context)
                    results[plugin.name] = result
                except Exception as e:
                    self.logger.error(f"Error executing condition plugin {plugin.name}: {str(e)}")
                    results[plugin.name] = False
        
        return results
    
    def execute_action_plugins(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all enabled action plugins."""
        results = {}
        
        for plugin in self.get_enabled_plugins():
            if isinstance(plugin, ActionPlugin):
                try:
                    result = plugin.execute(context)
                    results[plugin.name] = result
                except Exception as e:
                    self.logger.error(f"Error executing action plugin {plugin.name}: {str(e)}")
                    results[plugin.name] = {'success': False, 'error': str(e)}
        
        return results
    
    def execute_routing_plugins(self, context: Dict[str, Any], routes: List[Any]) -> Optional[Any]:
        """Execute routing plugins in priority order."""
        routing_plugins = sorted(
            self.get_enabled_plugins(),
            key=lambda p: p.get_priority() if isinstance(p, RoutingPlugin) else 0,
            reverse=True
        )
        
        for plugin in routing_plugins:
            if isinstance(plugin, RoutingPlugin):
                try:
                    result = plugin.route(context, routes)
                    if result:
                        return result
                except Exception as e:
                    self.logger.error(f"Error executing routing plugin {plugin.name}: {str(e)}")
        
        return None
    
    def execute_analytics_plugins(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all enabled analytics plugins."""
        results = {}
        
        for plugin in self.get_enabled_plugins():
            if isinstance(plugin, AnalyticsPlugin):
                try:
                    # Collect data
                    data = plugin.collect_data(context)
                    
                    # Process data
                    processed_data = plugin.process_data(data)
                    
                    results[plugin.name] = processed_data
                except Exception as e:
                    self.logger.error(f"Error executing analytics plugin {plugin.name}: {str(e)}")
                    results[plugin.name] = {'error': str(e)}
        
        return results
    
    def get_plugin_status(self) -> Dict[str, Any]:
        """Get status of all plugins."""
        status = {
            'total_plugins': len(self.plugins),
            'enabled_plugins': len(self.get_enabled_plugins()),
            'condition_plugins': len(self.condition_plugins),
            'action_plugins': len(self.action_plugins),
            'routing_plugins': len(self.routing_plugins),
            'analytics_plugins': len(self.analytics_plugins),
            'plugins': {}
        }
        
        for name, plugin in self.plugins.items():
            status['plugins'][name] = plugin.get_info()
        
        return status
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin."""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return False
        
        try:
            # Reinitialize plugin
            if plugin.initialize(plugin.config):
                self.logger.info(f"Reloaded plugin: {plugin_name}")
                return True
            else:
                self.logger.error(f"Failed to reinitialize plugin: {plugin_name}")
                return False
        except Exception as e:
            self.logger.error(f"Error reloading plugin {plugin_name}: {str(e)}")
            return False


# Global plugin manager instance
plugin_manager = PluginManager()


# Utility Functions

def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager."""
    return plugin_manager


def register_plugin(plugin: BasePlugin) -> bool:
    """Register a plugin."""
    return plugin_manager.register_plugin(plugin)


def unregister_plugin(plugin_name: str) -> bool:
    """Unregister a plugin."""
    return plugin_manager.unregister_plugin(plugin_name)


def execute_plugin_type(plugin_type: Type[BasePlugin], context: Dict[str, Any]) -> Any:
    """Execute plugins of a specific type."""
    if plugin_type == ConditionPlugin:
        return plugin_manager.execute_condition_plugins(context)
    elif plugin_type == ActionPlugin:
        return plugin_manager.execute_action_plugins(context)
    elif plugin_type == RoutingPlugin:
        return plugin_manager.execute_routing_plugins(context, context.get('routes', []))
    elif plugin_type == AnalyticsPlugin:
        return plugin_manager.execute_analytics_plugins(context)
    else:
        return None


# Export all classes and functions
__all__ = [
    # Base classes
    'BasePlugin',
    'ConditionPlugin',
    'ActionPlugin',
    'RoutingPlugin',
    'AnalyticsPlugin',
    
    # Built-in plugins
    'GeoConditionPlugin',
    'DeviceConditionPlugin',
    'TimeConditionPlugin',
    'ShowOfferActionPlugin',
    'LogEventActionPlugin',
    'PriorityRoutingPlugin',
    'PersonalizedRoutingPlugin',
    'PerformanceAnalyticsPlugin',
    
    # Plugin manager
    'PluginManager',
    'plugin_manager',
    
    # Utility functions
    'get_plugin_manager',
    'register_plugin',
    'unregister_plugin',
    'execute_plugin_type',
]
