"""
plugins.py – Plugin system for postback module.

Provides comprehensive plugin architecture including:
- Plugin registration and discovery
- Plugin lifecycle management
- Plugin configuration and settings
- Plugin communication and hooks
"""
import logging
import importlib
import inspect
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin status enumeration."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class PluginPriority(Enum):
    """Plugin priority for execution order."""
    LOWEST = 1
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


@dataclass
class PluginMetadata:
    """Plugin metadata containing information about the plugin."""
    name: str
    version: str
    description: str
    author: str
    email: str
    website: str = ""
    license: str = ""
    dependencies: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    min_django_version: str = ""
    max_django_version: str = ""
    python_requires: str = ""
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)


class BasePlugin(ABC):
    """
    Base class for all postback plugins.
    
    Provides common functionality and interface that all plugins
    must implement for integration with the plugin system.
    """
    
    def __init__(self):
        self.metadata = self.get_metadata()
        self.status = PluginStatus.INACTIVE
        self.enabled = True
        self.config = {}
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_execution = None
        self.error_log = []
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata.
        
        Returns:
            PluginMetadata instance
        """
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None):
        """
        Initialize the plugin.
        
        Args:
            config: Plugin configuration
        """
        pass
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the plugin logic.
        
        Args:
            context: Execution context
            
        Returns:
            Plugin execution result
        """
        pass
    
    def activate(self):
        """Activate the plugin."""
        if self.enabled and self.status != PluginStatus.ACTIVE:
            try:
                self.initialize(self.config)
                self.status = PluginStatus.ACTIVE
                logger.info(f"Plugin {self.metadata.name} activated")
            except Exception as e:
                self.status = PluginStatus.ERROR
                self.log_error(f"Failed to activate plugin: {str(e)}")
                logger.error(f"Failed to activate plugin {self.metadata.name}: {str(e)}")
    
    def deactivate(self):
        """Deactivate the plugin."""
        if self.status == PluginStatus.ACTIVE:
            try:
                self.cleanup()
                self.status = PluginStatus.INACTIVE
                logger.info(f"Plugin {self.metadata.name} deactivated")
            except Exception as e:
                self.status = PluginStatus.ERROR
                self.log_error(f"Failed to deactivate plugin: {str(e)}")
                logger.error(f"Failed to deactivate plugin {self.metadata.name}: {str(e)}")
    
    def cleanup(self):
        """Clean up plugin resources."""
        # Override in subclasses if needed
        pass
    
    def execute_with_monitoring(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute plugin with monitoring and error handling.
        
        Args:
            context: Execution context
            
        Returns:
            Plugin execution result
        """
        if not self.enabled or self.status != PluginStatus.ACTIVE:
            return {
                'status': 'skipped',
                'reason': f'Plugin not active (status: {self.status.value})',
                'plugin_name': self.metadata.name,
            }
        
        start_time = timezone.now()
        self.execution_count += 1
        
        try:
            logger.debug(f"Executing plugin: {self.metadata.name}")
            
            # Execute plugin
            result = self.execute(context)
            
            # Update statistics
            self.success_count += 1
            self.last_execution = timezone.now()
            
            execution_time = (timezone.now() - start_time).total_seconds()
            
            logger.debug(f"Plugin {self.metadata.name} executed successfully in {execution_time:.3f}s")
            
            return {
                'status': 'success',
                'result': result,
                'plugin_name': self.metadata.name,
                'execution_time': execution_time,
            }
            
        except Exception as e:
            self.error_count += 1
            self.last_execution = timezone.now()
            self.log_error(f"Plugin execution failed: {str(e)}")
            
            execution_time = (timezone.now() - start_time).total_seconds()
            
            logger.error(f"Plugin {self.metadata.name} failed: {str(e)}")
            
            return {
                'status': 'error',
                'error': str(e),
                'plugin_name': self.metadata.name,
                'execution_time': execution_time,
            }
    
    def configure(self, config: Dict[str, Any]):
        """Configure the plugin."""
        self.config.update(config)
        
        if self.status == PluginStatus.ACTIVE:
            # Reinitialize with new config
            self.initialize(config)
    
    def enable(self):
        """Enable the plugin."""
        self.enabled = True
        logger.info(f"Plugin {self.metadata.name} enabled")
    
    def disable(self):
        """Disable the plugin."""
        self.enabled = False
        self.deactivate()
        logger.info(f"Plugin {self.metadata.name} disabled")
    
    def log_error(self, message: str):
        """Log an error message."""
        error_entry = {
            'message': message,
            'timestamp': timezone.now().isoformat(),
        }
        self.error_log.append(error_entry)
        
        # Keep only last 50 errors
        if len(self.error_log) > 50:
            self.error_log = self.error_log[-50:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        
        return {
            'name': self.metadata.name,
            'version': self.metadata.version,
            'status': self.status.value,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': f"{success_rate:.2f}%",
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
            'error_count': len(self.error_log),
            'config_keys': list(self.config.keys()),
        }


class PluginRegistry:
    """
    Registry for managing plugins and their lifecycle.
    
    Provides centralized plugin management including registration,
    discovery, execution ordering, and dependency resolution.
    """
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_metadata: Dict[str, PluginMetadata] = {}
        self.execution_history = []
        self.enabled = True
    
    def register(self, plugin: BasePlugin):
        """
        Register a plugin in the registry.
        
        Args:
            plugin: Plugin instance to register
        """
        plugin_name = plugin.metadata.name
        
        if plugin_name in self.plugins:
            logger.warning(f"Plugin {plugin_name} already registered, replacing")
        
        self.plugins[plugin_name] = plugin
        self.plugin_metadata[plugin_name] = plugin.metadata
        
        logger.info(f"Registered plugin: {plugin_name} v{plugin.metadata.version}")
    
    def unregister(self, plugin_name: str):
        """
        Unregister a plugin from the registry.
        
        Args:
            plugin_name: Name of plugin to unregister
        """
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.deactivate()
            
            del self.plugins[plugin_name]
            del self.plugin_metadata[plugin_name]
            
            logger.info(f"Unregistered plugin: {plugin_name}")
        else:
            logger.warning(f"Plugin {plugin_name} not found in registry")
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self, status: PluginStatus = None) -> List[BasePlugin]:
        """
        List plugins with optional status filter.
        
        Args:
            status: Filter by plugin status
            
        Returns:
            List of plugins
        """
        plugins = list(self.plugins.values())
        
        if status:
            plugins = [p for p in plugins if p.status == status]
        
        return plugins
    
    def activate_plugin(self, plugin_name: str):
        """Activate a specific plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            plugin.activate()
        else:
            logger.warning(f"Plugin {plugin_name} not found")
    
    def deactivate_plugin(self, plugin_name: str):
        """Deactivate a specific plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            plugin.deactivate()
        else:
            logger.warning(f"Plugin {plugin_name} not found")
    
    def execute_plugins(self, context: Dict[str, Any], plugin_names: List[str] = None) -> Dict[str, Any]:
        """
        Execute plugins with optional filtering.
        
        Args:
            context: Execution context
            plugin_names: Specific plugins to execute (None = all active)
            
        Returns:
            Execution results
        """
        if not self.enabled:
            return {'status': 'disabled', 'message': 'Plugin registry disabled'}
        
        start_time = timezone.now()
        execution_id = self._generate_execution_id()
        
        try:
            # Determine which plugins to execute
            if plugin_names:
                plugins_to_execute = [
                    self.plugins[name] for name in plugin_names
                    if name in self.plugins
                ]
            else:
                plugins_to_execute = [
                    plugin for plugin in self.plugins.values()
                    if plugin.status == PluginStatus.ACTIVE
                ]
            
            if not plugins_to_execute:
                return {
                    'execution_id': execution_id,
                    'status': 'no_plugins',
                    'message': 'No active plugins to execute'
                }
            
            # Sort plugins by priority (highest first)
            plugins_to_execute.sort(key=lambda p: p.metadata.name)  # Sort by name for consistency
            
            # Execute plugins
            results = []
            
            for plugin in plugins_to_execute:
                result = plugin.execute_with_monitoring(context)
                results.append(result)
            
            execution_time = (timezone.now() - start_time).total_seconds()
            
            # Record execution
            self._record_execution(execution_id, results, execution_time)
            
            return {
                'execution_id': execution_id,
                'status': 'completed',
                'execution_time': execution_time,
                'plugins_executed': len(results),
                'results': results,
            }
            
        except Exception as e:
            execution_time = (timezone.now() - start_time).total_seconds()
            
            logger.error(f"Error executing plugins: {str(e)}")
            
            return {
                'execution_id': execution_id,
                'status': 'failed',
                'execution_time': execution_time,
                'error': str(e),
            }
    
    def discover_plugins(self):
        """Discover and auto-load plugins from configured modules."""
        plugin_modules = getattr(settings, 'POSTBACK_PLUGIN_MODULES', [])
        
        for module_path in plugin_modules:
            try:
                module = importlib.import_module(module_path)
                
                # Look for plugin classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BasePlugin) and 
                        obj != BasePlugin and 
                        not inspect.isabstract(obj)):
                        
                        # Instantiate and register the plugin
                        plugin_instance = obj()
                        self.register(plugin_instance)
                        logger.info(f"Auto-discovered plugin: {plugin_instance.metadata.name}")
                
            except ImportError as e:
                logger.error(f"Failed to import plugin module {module_path}: {str(e)}")
            except Exception as e:
                logger.error(f"Error loading plugins from {module_path}: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        status_counts = {}
        for status in PluginStatus:
            status_counts[status.value] = len([
                p for p in self.plugins.values() 
                if p.status == status
            ])
        
        return {
            'total_plugins': len(self.plugins),
            'enabled_plugins': len([p for p in self.plugins.values() if p.enabled]),
            'active_plugins': len([p for p in self.plugins.values() if p.status == PluginStatus.ACTIVE]),
            'status_distribution': status_counts,
            'plugin_details': {
                name: plugin.get_statistics()
                for name, plugin in self.plugins.items()
            },
            'execution_history_count': len(self.execution_history),
            'enabled': self.enabled,
        }
    
    def enable_all(self):
        """Enable all plugins."""
        for plugin in self.plugins.values():
            plugin.enable()
        
        self.enabled = True
        logger.info("All plugins enabled")
    
    def disable_all(self):
        """Disable all plugins."""
        for plugin in self.plugins.values():
            plugin.disable()
        
        self.enabled = False
        logger.info("All plugins disabled")
    
    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _record_execution(self, execution_id: str, results: List[Dict], execution_time: float):
        """Record plugin execution details."""
        execution_record = {
            'execution_id': execution_id,
            'results': results,
            'execution_time': execution_time,
            'timestamp': timezone.now().isoformat(),
        }
        
        self.execution_history.append(execution_record)
        
        # Keep only last 100 executions
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
        
        # Cache execution record
        cache_key = f"plugin_execution_{execution_id}"
        cache.set(cache_key, execution_record, timeout=3600)  # 1 hour


# Built-in plugin examples
class AnalyticsPlugin(BasePlugin):
    """Built-in analytics plugin."""
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="analytics_plugin",
            version="1.0.0",
            description="Built-in analytics plugin for postback data",
            author="Postback Team",
            email="team@postback.com",
            provides=["analytics", "metrics"]
        )
    
    def initialize(self, config: Dict[str, Any] = None):
        """Initialize analytics plugin."""
        self.config = config or {}
        logger.info("Analytics plugin initialized")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analytics processing."""
        # Example analytics logic
        postback_data = context.get('postback_data', {})
        
        analytics_result = {
            'processed_at': timezone.now().isoformat(),
            'data_size': len(str(postback_data)),
            'has_payout': 'payout' in postback_data,
            'network_key': postback_data.get('network_key'),
        }
        
        # Add analytics to context
        context.setdefault('analytics', {}).update(analytics_result)
        
        return analytics_result


class NotificationPlugin(BasePlugin):
    """Built-in notification plugin."""
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="notification_plugin",
            version="1.0.0",
            description="Built-in notification plugin for postback events",
            author="Postback Team",
            email="team@postback.com",
            provides=["notifications", "alerts"]
        )
    
    def initialize(self, config: Dict[str, Any] = None):
        """Initialize notification plugin."""
        self.config = config or {}
        logger.info("Notification plugin initialized")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute notification processing."""
        # Example notification logic
        postback_data = context.get('postback_data', {})
        status = postback_data.get('status')
        
        notifications = []
        
        if status == 'FAILED':
            notifications.append({
                'type': 'failure',
                'message': f"Postback failed: {postback_data.get('rejection_reason', 'Unknown')}",
                'timestamp': timezone.now().isoformat(),
            })
        
        # Add notifications to context
        context.setdefault('notifications', []).extend(notifications)
        
        return {'notifications_sent': len(notifications)}


# Global plugin registry instance
plugin_registry = PluginRegistry()


# Convenience functions
def register_plugin(plugin: BasePlugin):
    """Register a plugin."""
    plugin_registry.register(plugin)


def unregister_plugin(plugin_name: str):
    """Unregister a plugin."""
    plugin_registry.unregister(plugin_name)


def execute_plugins(context: Dict[str, Any], plugin_names: List[str] = None) -> Dict[str, Any]:
    """Execute plugins."""
    return plugin_registry.execute_plugins(context, plugin_names)


def get_plugin_statistics() -> Dict[str, Any]:
    """Get plugin system statistics."""
    return plugin_registry.get_statistics()


# Plugin system initialization
def initialize_plugin_system():
    """Initialize the plugin system."""
    try:
        # Register built-in plugins
        plugin_registry.register(AnalyticsPlugin())
        plugin_registry.register(NotificationPlugin())
        
        # Discover and load external plugins
        plugin_registry.discover_plugins()
        
        logger.info("Plugin system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing plugin system: {str(e)}")


# Plugin management functions
def activate_plugin(plugin_name: str):
    """Activate a specific plugin."""
    plugin_registry.activate_plugin(plugin_name)


def deactivate_plugin(plugin_name: str):
    """Deactivate a specific plugin."""
    plugin_registry.deactivate_plugin(plugin_name)


def configure_plugin(plugin_name: str, config: Dict[str, Any]):
    """Configure a specific plugin."""
    plugin = plugin_registry.get_plugin(plugin_name)
    if plugin:
        plugin.configure(config)
        logger.info(f"Configured plugin: {plugin_name}")
    else:
        logger.warning(f"Plugin {plugin_name} not found for configuration")


# Plugin discovery and management
def refresh_plugins():
    """Refresh plugin discovery."""
    plugin_registry.discover_plugins()


def get_plugin_info(plugin_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a plugin."""
    plugin = plugin_registry.get_plugin(plugin_name)
    if plugin:
        return {
            'metadata': {
                'name': plugin.metadata.name,
                'version': plugin.metadata.version,
                'description': plugin.metadata.description,
                'author': plugin.metadata.author,
                'dependencies': plugin.metadata.dependencies,
                'provides': plugin.metadata.provides,
                'tags': plugin.metadata.tags,
            },
            'statistics': plugin.get_statistics(),
            'config': plugin.config,
            'error_log': plugin.error_log[-10:],  # Last 10 errors
        }
    return None


# Plugin dependency resolution
def resolve_plugin_dependencies(plugin_name: str) -> List[str]:
    """Resolve plugin dependencies."""
    plugin = plugin_registry.get_plugin(plugin_name)
    if plugin:
        return plugin.metadata.dependencies
    return []


def check_plugin_dependencies(plugin_name: str) -> Dict[str, Any]:
    """Check if plugin dependencies are satisfied."""
    plugin = plugin_registry.get_plugin(plugin_name)
    if not plugin:
        return {'status': 'error', 'message': 'Plugin not found'}
    
    dependencies = plugin.metadata.dependencies
    missing_deps = []
    satisfied_deps = []
    
    for dep in dependencies:
        if dep in plugin_registry.plugins:
            satisfied_deps.append(dep)
        else:
            missing_deps.append(dep)
    
    return {
        'plugin_name': plugin_name,
        'dependencies': dependencies,
        'satisfied_dependencies': satisfied_deps,
        'missing_dependencies': missing_deps,
        'all_satisfied': len(missing_deps) == 0,
    }
