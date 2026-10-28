"""
Gamification Plugins — Plugin system for gamification module.

This module provides a comprehensive plugin system for extending gamification
functionality through custom plugins and extensions.
"""

from __future__ import annotations

import logging
import importlib
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union, Callable
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plugin System Base Classes
# ---------------------------------------------------------------------------

@dataclass
class PluginInfo:
    """Information about a plugin."""
    
    name: str
    version: str
    description: str
    author: str
    email: str
    url: Optional[str] = None
    license: str = "MIT"
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True
    installed_at: datetime = field(default_factory=lambda: timezone.now())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plugin info to dictionary."""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'email': self.email,
            'url': self.url,
            'license': self.license,
            'dependencies': self.dependencies,
            'enabled': self.enabled,
            'installed_at': self.installed_at.isoformat(),
            'metadata': self.metadata
        }


class BasePlugin(ABC):
    """Abstract base class for gamification plugins."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._enabled = True
        self._initialized = False
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Get plugin information."""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the plugin."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the plugin."""
        pass
    
    @property
    def enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled and self._initialized
    
    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set plugin enabled status."""
        self._enabled = value
    
    @property
    def initialized(self) -> bool:
        """Check if plugin is initialized."""
        return self._initialized
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.info.name} v{self.info.version})"


# ---------------------------------------------------------------------------
# Plugin Types
# ---------------------------------------------------------------------------

class GamificationPlugin(BasePlugin):
    """Base class for gamification plugins."""
    
    @abstractmethod
    def on_contest_created(self, contest_data: Dict[str, Any]) -> None:
        """Called when a contest is created."""
        pass
    
    @abstractmethod
    def on_achievement_awarded(self, achievement_data: Dict[str, Any]) -> None:
        """Called when an achievement is awarded."""
        pass
    
    @abstractmethod
    def on_badge_earned(self, badge_data: Dict[str, Any]) -> None:
        """Called when a badge is earned."""
        pass
    
    @abstractmethod
    def on_points_updated(self, points_data: Dict[str, Any]) -> None:
        """Called when points are updated."""
        pass


class NotificationPlugin(BasePlugin):
    """Base class for notification plugins."""
    
    @abstractmethod
    def send_notification(self, user_id: str, notification_data: Dict[str, Any]) -> bool:
        """Send a notification to a user."""
        pass
    
    @abstractmethod
    def get_supported_channels(self) -> List[str]:
        """Get list of supported notification channels."""
        pass


class AnalyticsPlugin(BasePlugin):
    """Base class for analytics plugins."""
    
    @abstractmethod
    def track_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Track an analytics event."""
        pass
    
    @abstractmethod
    def generate_report(self, report_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an analytics report."""
        pass


class IntegrationPlugin(BasePlugin):
    """Base class for integration plugins."""
    
    @abstractmethod
    def sync_data(self, sync_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Sync data with external service."""
        pass
    
    @abstractmethod
    def get_integration_info(self) -> Dict[str, Any]:
        """Get integration information."""
        pass


# ---------------------------------------------------------------------------
# Plugin Manager
# ---------------------------------------------------------------------------

class PluginManager:
    """Manager for loading and managing plugins."""
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_registry: Dict[str, Type[BasePlugin]] = {}
        self.logger = logging.getLogger(__name__)
        self._plugin_directories: List[Path] = []
        self._auto_discover = True
    
    def add_plugin_directory(self, directory: Path) -> None:
        """Add a directory to search for plugins."""
        if directory.exists() and directory.is_dir():
            self._plugin_directories.append(directory)
            self.logger.info(f"Added plugin directory: {directory}")
        else:
            self.logger.warning(f"Plugin directory does not exist: {directory}")
    
    def register_plugin_class(self, plugin_class: Type[BasePlugin]) -> None:
        """Register a plugin class."""
        plugin_name = plugin_class.__name__
        self.plugin_registry[plugin_name] = plugin_class
        self.logger.info(f"Registered plugin class: {plugin_name}")
    
    def discover_plugins(self) -> None:
        """Discover plugins in registered directories."""
        if not self._auto_discover:
            return
        
        for directory in self._plugin_directories:
            self._discover_plugins_in_directory(directory)
    
    def _discover_plugins_in_directory(self, directory: Path) -> None:
        """Discover plugins in a specific directory."""
        try:
            for file_path in directory.glob("*.py"):
                if file_path.name.startswith("_"):
                    continue
                
                module_name = file_path.stem
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for plugin classes in the module
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BasePlugin) and 
                            obj != BasePlugin):
                            self.register_plugin_class(obj)
                            
                except Exception as e:
                    self.logger.error(f"Error loading plugin from {file_path}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error discovering plugins in {directory}: {e}")
    
    def load_plugin(self, plugin_name: str, **kwargs: Any) -> BasePlugin:
        """Load a plugin by name."""
        if plugin_name in self.plugins:
            return self.plugins[plugin_name]
        
        plugin_class = self.plugin_registry.get(plugin_name)
        if not plugin_class:
            raise ValueError(f"Plugin not found: {plugin_name}")
        
        try:
            plugin = plugin_class(**kwargs)
            self.plugins[plugin_name] = plugin
            
            # Initialize the plugin
            plugin.initialize()
            
            self.logger.info(f"Loaded plugin: {plugin_name}")
            return plugin
            
        except Exception as e:
            self.logger.error(f"Error loading plugin {plugin_name}: {e}")
            raise GamificationServiceError(f"Failed to load plugin {plugin_name}: {e}")
    
    def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin."""
        if plugin_name not in self.plugins:
            return
        
        plugin = self.plugins[plugin_name]
        
        try:
            # Shutdown the plugin
            plugin.shutdown()
            
            # Remove from registry
            del self.plugins[plugin_name]
            
            self.logger.info(f"Unloaded plugin: {plugin_name}")
            
        except Exception as e:
            self.logger.error(f"Error unloading plugin {plugin_name}: {e}")
    
    def enable_plugin(self, plugin_name: str) -> None:
        """Enable a plugin."""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not loaded: {plugin_name}")
        
        plugin = self.plugins[plugin_name]
        plugin.enabled = True
        self.logger.info(f"Enabled plugin: {plugin_name}")
    
    def disable_plugin(self, plugin_name: str) -> None:
        """Disable a plugin."""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not loaded: {plugin_name}")
        
        plugin = self.plugins[plugin_name]
        plugin.enabled = False
        self.logger.info(f"Disabled plugin: {plugin_name}")
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: Type[BasePlugin]) -> List[BasePlugin]:
        """Get all plugins of a specific type."""
        return [plugin for plugin in self.plugins.values() 
                if isinstance(plugin, plugin_type)]
    
    def list_plugins(self) -> List[str]:
        """List all loaded plugins."""
        return list(self.plugins.keys())
    
    def list_enabled_plugins(self) -> List[str]:
        """List all enabled plugins."""
        return [name for name, plugin in self.plugins.items() if plugin.enabled]
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get plugin information."""
        plugin = self.get_plugin(plugin_name)
        return plugin.info if plugin else None
    
    def reload_plugin(self, plugin_name: str) -> BasePlugin:
        """Reload a plugin."""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not loaded: {plugin_name}")
        
        # Unload first
        self.unload_plugin(plugin_name)
        
        # Load again
        return self.load_plugin(plugin_name)
    
    def initialize_all_plugins(self) -> None:
        """Initialize all loaded plugins."""
        for plugin_name, plugin in self.plugins.items():
            if not plugin.initialized:
                try:
                    plugin.initialize()
                    self.logger.info(f"Initialized plugin: {plugin_name}")
                except Exception as e:
                    self.logger.error(f"Error initializing plugin {plugin_name}: {e}")
    
    def shutdown_all_plugins(self) -> None:
        """Shutdown all loaded plugins."""
        for plugin_name, plugin in self.plugins.items():
            try:
                plugin.shutdown()
                self.logger.info(f"Shutdown plugin: {plugin_name}")
            except Exception as e:
                self.logger.error(f"Error shutting down plugin {plugin_name}: {e}")
    
    def get_plugin_stats(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        return {
            'total_plugins': len(self.plugins),
            'enabled_plugins': len(self.list_enabled_plugins()),
            'plugin_types': {
                'gamification': len(self.get_plugins_by_type(GamificationPlugin)),
                'notification': len(self.get_plugins_by_type(NotificationPlugin)),
                'analytics': len(self.get_plugins_by_type(AnalyticsPlugin)),
                'integration': len(self.get_plugins_by_type(IntegrationPlugin)),
            },
            'plugins': [plugin.info.to_dict() for plugin in self.plugins.values()]
        }


# ---------------------------------------------------------------------------
# Built-in Plugins
# ---------------------------------------------------------------------------

class EmailNotificationPlugin(NotificationPlugin):
    """Email notification plugin."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="EmailNotificationPlugin",
            version="1.0.0",
            description="Send email notifications for gamification events",
            author="Gamification Team",
            email="team@gamification.com"
        )
    
    def initialize(self) -> None:
        """Initialize the email notification plugin."""
        self._initialized = True
        self.logger.info("Email notification plugin initialized")
    
    def shutdown(self) -> None:
        """Shutdown the email notification plugin."""
        self._initialized = False
        self.logger.info("Email notification plugin shutdown")
    
    def send_notification(self, user_id: str, notification_data: Dict[str, Any]) -> bool:
        """Send email notification."""
        try:
            # This would integrate with Django's email system
            # For now, we'll just log it
            self.logger.info(f"Sending email notification to user {user_id}: {notification_data}")
            return True
        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")
            return False
    
    def get_supported_channels(self) -> List[str]:
        """Get supported notification channels."""
        return ["email"]


class LoggingAnalyticsPlugin(AnalyticsPlugin):
    """Logging analytics plugin."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="LoggingAnalyticsPlugin",
            version="1.0.0",
            description="Log analytics events to Django logger",
            author="Gamification Team",
            email="team@gamification.com"
        )
    
    def initialize(self) -> None:
        """Initialize the logging analytics plugin."""
        self._initialized = True
        self.logger.info("Logging analytics plugin initialized")
    
    def shutdown(self) -> None:
        """Shutdown the logging analytics plugin."""
        self._initialized = False
        self.logger.info("Logging analytics plugin shutdown")
    
    def track_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Track an analytics event."""
        self.logger.info(f"Analytics event: {event_name} - {event_data}")
    
    def generate_report(self, report_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an analytics report."""
        # This would generate actual reports based on the report type
        return {
            'report_type': report_type,
            'parameters': parameters,
            'data': 'Sample report data',
            'generated_at': timezone.now().isoformat()
        }


class BasicGamificationPlugin(GamificationPlugin):
    """Basic gamification plugin with default implementations."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="BasicGamificationPlugin",
            version="1.0.0",
            description="Basic gamification plugin with default handlers",
            author="Gamification Team",
            email="team@gamification.com"
        )
    
    def initialize(self) -> None:
        """Initialize the basic gamification plugin."""
        self._initialized = True
        self.logger.info("Basic gamification plugin initialized")
    
    def shutdown(self) -> None:
        """Shutdown the basic gamification plugin."""
        self._initialized = False
        self.logger.info("Basic gamification plugin shutdown")
    
    def on_contest_created(self, contest_data: Dict[str, Any]) -> None:
        """Handle contest creation."""
        self.logger.info(f"Contest created: {contest_data.get('name')}")
    
    def on_achievement_awarded(self, achievement_data: Dict[str, Any]) -> None:
        """Handle achievement award."""
        self.logger.info(f"Achievement awarded: {achievement_data.get('achievement_type')}")
    
    def on_badge_earned(self, badge_data: Dict[str, Any]) -> None:
        """Handle badge earning."""
        self.logger.info(f"Badge earned: {badge_data.get('badge_name')}")
    
    def on_points_updated(self, points_data: Dict[str, Any]) -> None:
        """Handle points update."""
        self.logger.info(f"Points updated: {points_data.get('points')}")


# ---------------------------------------------------------------------------
# Plugin Utilities
# ---------------------------------------------------------------------------

class PluginUtils:
    """Utilities for plugin management."""
    
    @staticmethod
    def validate_plugin(plugin: BasePlugin) -> List[str]:
        """Validate a plugin."""
        errors = []
        
        if not plugin.info.name:
            errors.append("Plugin name is required")
        
        if not plugin.info.version:
            errors.append("Plugin version is required")
        
        if not plugin.info.author:
            errors.append("Plugin author is required")
        
        if not plugin.info.email:
            errors.append("Plugin email is required")
        
        return errors
    
    @staticmethod
    def check_dependencies(plugin: BasePlugin, available_plugins: List[str]) -> List[str]:
        """Check plugin dependencies."""
        missing_deps = []
        
        for dep in plugin.info.dependencies:
            if dep not in available_plugins:
                missing_deps.append(dep)
        
        return missing_deps
    
    @staticmethod
    def get_plugin_config(plugin_name: str) -> Dict[str, Any]:
        """Get plugin configuration from Django settings."""
        plugin_settings = getattr(settings, 'GAMIFICATION_PLUGINS', {})
        return plugin_settings.get(plugin_name, {})
    
    @staticmethod
    def save_plugin_config(plugin_name: str, config: Dict[str, Any]) -> None:
        """Save plugin configuration (this would need to be implemented based on your storage needs)."""
        # This would typically save to database or config file
        # For now, we'll just log it
        logger.info(f"Saving config for plugin {plugin_name}: {config}")


# ---------------------------------------------------------------------------
# Plugin Events
# ---------------------------------------------------------------------------

class PluginEvent:
    """Plugin event system."""
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_listener(self, event_name: str, listener: Callable) -> None:
        """Register an event listener."""
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        
        self.listeners[event_name].append(listener)
        self.logger.info(f"Registered listener for event: {event_name}")
    
    def unregister_listener(self, event_name: str, listener: Callable) -> None:
        """Unregister an event listener."""
        if event_name in self.listeners:
            try:
                self.listeners[event_name].remove(listener)
                self.logger.info(f"Unregistered listener for event: {event_name}")
            except ValueError:
                pass
    
    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all listeners."""
        if event_name in self.listeners:
            for listener in self.listeners[event_name]:
                try:
                    listener(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error in event listener for {event_name}: {e}")


# Global instances
plugin_manager = PluginManager()
plugin_event = PluginEvent()


# Initialize built-in plugins
def initialize_built_in_plugins() -> None:
    """Initialize built-in plugins."""
    try:
        # Register built-in plugin classes
        plugin_manager.register_plugin_class(EmailNotificationPlugin)
        plugin_manager.register_plugin_class(LoggingAnalyticsPlugin)
        plugin_manager.register_plugin_class(BasicGamificationPlugin)
        
        # Load built-in plugins
        plugin_manager.load_plugin("EmailNotificationPlugin")
        plugin_manager.load_plugin("LoggingAnalyticsPlugin")
        plugin_manager.load_plugin("BasicGamificationPlugin")
        
        logger.info("Initialized built-in plugins")
        
    except Exception as e:
        logger.error(f"Error initializing built-in plugins: {e}")


# Initialize plugin directories
def initialize_plugin_directories() -> None:
    """Initialize plugin directories from settings."""
    try:
        plugin_dirs = getattr(settings, 'GAMIFICATION_PLUGIN_DIRS', [])
        
        for dir_path in plugin_dirs:
            plugin_manager.add_plugin_directory(Path(dir_path))
        
        # Add default plugin directory
        default_dir = Path(__file__).parent / "plugins"
        if default_dir.exists():
            plugin_manager.add_plugin_directory(default_dir)
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        logger.info("Initialized plugin directories")
        
    except Exception as e:
        logger.error(f"Error initializing plugin directories: {e}")


# Initialize on module import
try:
    initialize_plugin_directories()
    initialize_built_in_plugins()
    logger.info("Gamification plugins module initialized")
except Exception as e:
    logger.error(f"Error initializing plugins module: {e}")
