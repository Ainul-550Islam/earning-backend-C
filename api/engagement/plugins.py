# engagement/plugins.py
"""
Plugin system for engagement gamification.
Provides extensible architecture for custom plugins and modules.
"""
import logging
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """Types of plugins."""
    ENGAGEMENT = "engagement"
    ANALYTICS = "analytics"
    NOTIFICATION = "notification"
    VALIDATION = "validation"
    REWARD = "reward"
    SOCIAL = "social"
    GAMIFICATION = "gamification"
    INTEGRATION = "integration"
    UI = "ui"


class PluginStatus(Enum):
    """Plugin status."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginInfo:
    """Plugin information."""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = None
    config_schema: Dict[str, Any] = None
    status: PluginStatus = PluginStatus.INACTIVE
    enabled: bool = True
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.config_schema is None:
            self.config_schema = {}


class BasePlugin(ABC):
    """Base class for all engagement plugins."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.info = self.get_plugin_info()
        self._initialized = False
    
    @abstractmethod
    def get_plugin_info(self) -> PluginInfo:
        """Get plugin information."""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the plugin."""
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """Cleanup the plugin."""
        pass
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self.info.enabled and self.info.status == PluginStatus.ACTIVE
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value: Any):
        """Set configuration value."""
        self.config[key] = value


class EngagementPlugin(BasePlugin):
    """Base class for engagement plugins."""
    
    @abstractmethod
    def on_user_action(self, action_type: str, user_id: int, **kwargs) -> Dict[str, Any]:
        """Handle user action."""
        pass
    
    @abstractmethod
    def get_reward_multipliers(self, user_id: int) -> Dict[str, float]:
        """Get reward multipliers for user."""
        pass
    
    @abstractmethod
    def validate_action(self, action_type: str, user_id: int, **kwargs) -> bool:
        """Validate user action."""
        pass


class AnalyticsPlugin(BasePlugin):
    """Base class for analytics plugins."""
    
    @abstractmethod
    def track_event(self, event_type: str, user_id: Optional[int], **kwargs) -> bool:
        """Track analytics event."""
        pass
    
    @abstractmethod
    def get_user_metrics(self, user_id: int, period: str = 'day') -> Dict[str, Any]:
        """Get user metrics."""
        pass
    
    @abstractmethod
    def get_platform_metrics(self, period: str = 'day') -> Dict[str, Any]:
        """Get platform metrics."""
        pass


class NotificationPlugin(BasePlugin):
    """Base class for notification plugins."""
    
    @abstractmethod
    def send_notification(self, user_id: int, notification_type: str, **kwargs) -> bool:
        """Send notification."""
        pass
    
    @abstractmethod
    def get_notification_channels(self, user_id: int) -> List[str]:
        """Get available notification channels."""
        pass
    
    @abstractmethod
    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user notification preferences."""
        pass


class ValidationPlugin(BasePlugin):
    """Base class for validation plugins."""
    
    @abstractmethod
    def validate_action(self, action_type: str, user_id: int, **kwargs) -> Dict[str, Any]:
        """Validate action."""
        pass
    
    @abstractmethod
    def get_validation_rules(self, action_type: str) -> List[Dict[str, Any]]:
        """Get validation rules."""
        pass


class RewardPlugin(BasePlugin):
    """Base class for reward plugins."""
    
    @abstractmethod
    def calculate_rewards(self, action_type: str, user_id: int, **kwargs) -> Dict[str, Any]:
        """Calculate rewards."""
        pass
    
    @abstractmethod
    def grant_rewards(self, user_id: int, rewards: Dict[str, Any]) -> bool:
        """Grant rewards to user."""
        pass
    
    @abstractmethod
    def get_reward_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get reward history."""
        pass


class SocialPlugin(BasePlugin):
    """Base class for social plugins."""
    
    @abstractmethod
    def on_social_action(self, action_type: str, user_id: int, target_id: int, **kwargs) -> Dict[str, Any]:
        """Handle social action."""
        pass
    
    @abstractmethod
    def get_social_feed(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get social feed."""
        pass
    
    @abstractmethod
    def get_friends_list(self, user_id: int) -> List[Dict[str, Any]]:
        """Get friends list."""
        pass


class GamificationPlugin(BasePlugin):
    """Base class for gamification plugins."""
    
    @abstractmethod
    def on_gamification_event(self, event_type: str, user_id: int, **kwargs) -> Dict[str, Any]:
        """Handle gamification event."""
        pass
    
    @abstractmethod
    def get_user_progress(self, user_id: int) -> Dict[str, Any]:
        """Get user progress."""
        pass
    
    @abstractmethod
    def get_leaderboard(self, period: str = 'day', limit: int = 100) -> List[Dict[str, Any]]:
        """Get leaderboard."""
        pass


class IntegrationPlugin(BasePlugin):
    """Base class for integration plugins."""
    
    @abstractmethod
    def sync_data(self, direction: str = 'export') -> bool:
        """Sync data with external system."""
        pass
    
    @abstractmethod
    def handle_webhook(self, webhook_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle webhook from external system."""
        pass
    
    @abstractmethod
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status."""
        pass


class UIPlugin(BasePlugin):
    """Base class for UI plugins."""
    
    @abstractmethod
    def get_ui_components(self, component_type: str) -> List[Dict[str, Any]]:
        """Get UI components."""
        pass
    
    @abstractmethod
    def render_component(self, component_id: str, context: Dict[str, Any]) -> str:
        """Render UI component."""
        pass
    
    @abstractmethod
    def get_assets(self) -> Dict[str, List[str]]:
        """Get plugin assets (CSS, JS, images)."""
        pass


class PluginManager:
    """Manages all engagement plugins."""
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        self._load_builtin_plugins()
    
    def _load_builtin_plugins(self):
        """Load built-in plugins."""
        # Load built-in plugins here
        pass
    
    def register_plugin(self, plugin: BasePlugin, config: Dict[str, Any] = None) -> bool:
        """Register a plugin."""
        try:
            plugin_name = plugin.info.name
            
            # Check if plugin already exists
            if plugin_name in self.plugins:
                logger.warning(f"Plugin {plugin_name} already registered")
                return False
            
            # Check dependencies
            if not self._check_dependencies(plugin):
                logger.error(f"Plugin {plugin_name} has unmet dependencies")
                return False
            
            # Initialize plugin
            if config:
                plugin.config.update(config)
            
            if plugin.initialize():
                self.plugins[plugin_name] = plugin
                self.plugin_configs[plugin_name] = plugin.config
                plugin.info.status = PluginStatus.ACTIVE
                
                logger.info(f"Plugin {plugin_name} registered successfully")
                return True
            else:
                plugin.info.status = PluginStatus.ERROR
                logger.error(f"Failed to initialize plugin {plugin_name}")
                return False
                
        except Exception as exc:
            logger.error(f"Error registering plugin: {exc}")
            return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """Unregister a plugin."""
        try:
            if plugin_name not in self.plugins:
                logger.warning(f"Plugin {plugin_name} not found")
                return False
            
            plugin = self.plugins[plugin_name]
            
            # Cleanup plugin
            if plugin.cleanup():
                del self.plugins[plugin_name]
                del self.plugin_configs[plugin_name]
                plugin.info.status = PluginStatus.INACTIVE
                
                logger.info(f"Plugin {plugin_name} unregistered successfully")
                return True
            else:
                logger.error(f"Failed to cleanup plugin {plugin_name}")
                return False
                
        except Exception as exc:
            logger.error(f"Error unregistering plugin: {exc}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[BasePlugin]:
        """Get all plugins of a specific type."""
        return [
            plugin for plugin in self.plugins.values()
            if plugin.info.plugin_type == plugin_type and plugin.is_enabled()
        ]
    
    def get_enabled_plugins(self) -> List[BasePlugin]:
        """Get all enabled plugins."""
        return [plugin for plugin in self.plugins.values() if plugin.is_enabled()]
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin and not plugin.is_enabled():
            plugin.info.enabled = True
            if plugin.initialize():
                plugin.info.status = PluginStatus.ACTIVE
                logger.info(f"Plugin {plugin_name} enabled")
                return True
            else:
                plugin.info.status = PluginStatus.ERROR
                logger.error(f"Failed to enable plugin {plugin_name}")
                return False
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin and plugin.is_enabled():
            plugin.info.enabled = False
            plugin.info.status = PluginStatus.DISABLED
            logger.info(f"Plugin {plugin_name} disabled")
            return True
        return False
    
    def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Execute a hook across all relevant plugins."""
        results = []
        
        for plugin in self.get_enabled_plugins():
            if hasattr(plugin, hook_name):
                try:
                    method = getattr(plugin, hook_name)
                    result = method(*args, **kwargs)
                    results.append(result)
                except Exception as exc:
                    logger.error(f"Error executing hook {hook_name} on plugin {plugin.info.name}: {exc}")
        
        return results
    
    def _check_dependencies(self, plugin: BasePlugin) -> bool:
        """Check if plugin dependencies are met."""
        for dependency in plugin.info.dependencies:
            if dependency not in self.plugins:
                return False
        return True
    
    def get_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all plugins."""
        status = {}
        
        for plugin_name, plugin in self.plugins.items():
            status[plugin_name] = {
                'name': plugin.info.name,
                'version': plugin.info.version,
                'type': plugin.info.plugin_type.value,
                'status': plugin.info.status.value,
                'enabled': plugin.info.enabled,
                'dependencies': plugin.info.dependencies,
                'initialized': plugin._initialized
            }
        
        return status


# Global plugin manager instance
plugin_manager = PluginManager()


# ── Plugin Decorators ─────────────────────────────────────────────────────

def plugin_hook(hook_name: str):
    """Decorator to register plugin hooks."""
    def decorator(func):
        plugin_manager.hooks.setdefault(hook_name, []).append(func)
        return func
    return decorator


def engagement_plugin(name: str, version: str, description: str, author: str):
    """Decorator to create engagement plugins."""
    def decorator(cls):
        # Create plugin info
        info = PluginInfo(
            name=name,
            version=version,
            description=description,
            author=author,
            plugin_type=PluginType.ENGAGEMENT
        )
        
        # Set plugin info on class
        cls._plugin_info = info
        
        return cls
    return decorator


# ── Built-in Plugin Examples ─────────────────────────────────────────────────

@engagement_plugin("basic_rewards", "1.0.0", "Basic reward calculations", "Engagement Team")
class BasicRewardsPlugin(EngagementPlugin):
    """Basic rewards plugin."""
    
    def get_plugin_info(self) -> PluginInfo:
        return self._plugin_info
    
    def initialize(self) -> bool:
        self._initialized = True
        return True
    
    def cleanup(self) -> bool:
        self._initialized = False
        return True
    
    def on_user_action(self, action_type: str, user_id: int, **kwargs) -> Dict[str, Any]:
        rewards = {}
        
        if action_type == "checkin":
            rewards['coins'] = 10.0
            rewards['xp'] = 10
        elif action_type == "spin":
            rewards['coins'] = 5.0
            rewards['xp'] = 5
        
        return rewards
    
    def get_reward_multipliers(self, user_id: int) -> Dict[str, float]:
        return {
            'coins': 1.0,
            'xp': 1.0
        }
    
    def validate_action(self, action_type: str, user_id: int, **kwargs) -> bool:
        return True


@engagement_plugin("basic_analytics", "1.0.0", "Basic analytics tracking", "Engagement Team")
class BasicAnalyticsPlugin(AnalyticsPlugin):
    """Basic analytics plugin."""
    
    def get_plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="basic_analytics",
            version="1.0.0",
            description="Basic analytics tracking",
            author="Engagement Team",
            plugin_type=PluginType.ANALYTICS
        )
    
    def initialize(self) -> bool:
        self._initialized = True
        return True
    
    def cleanup(self) -> bool:
        self._initialized = False
        return True
    
    def track_event(self, event_type: str, user_id: Optional[int], **kwargs) -> bool:
        # Basic event tracking implementation
        logger.info(f"Event tracked: {event_type} for user {user_id}")
        return True
    
    def get_user_metrics(self, user_id: int, period: str = 'day') -> Dict[str, Any]:
        # Basic metrics implementation
        return {
            'events_count': 0,
            'last_activity': None
        }
    
    def get_platform_metrics(self, period: str = 'day') -> Dict[str, Any]:
        # Basic platform metrics implementation
        return {
            'total_events': 0,
            'active_users': 0
        }


@engagement_plugin("email_notifications", "1.0.0", "Email notification system", "Engagement Team")
class EmailNotificationPlugin(NotificationPlugin):
    """Email notification plugin."""
    
    def get_plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="email_notifications",
            version="1.0.0",
            description="Email notification system",
            author="Engagement Team",
            plugin_type=PluginType.NOTIFICATION
        )
    
    def initialize(self) -> bool:
        self._initialized = True
        return True
    
    def cleanup(self) -> bool:
        self._initialized = False
        return True
    
    def send_notification(self, user_id: int, notification_type: str, **kwargs) -> bool:
        # Basic email notification implementation
        logger.info(f"Email notification sent: {notification_type} to user {user_id}")
        return True
    
    def get_notification_channels(self, user_id: int) -> List[str]:
        return ['email']
    
    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        return {
            'email_enabled': True,
            'push_enabled': False
        }


# ── Plugin Management Functions ─────────────────────────────────────────────

def register_plugin_from_config(config: Dict[str, Any]) -> bool:
    """Register plugin from configuration."""
    try:
        plugin_name = config.get('name')
        plugin_class = config.get('class')
        plugin_config = config.get('config', {})
        
        if not plugin_name or not plugin_class:
            logger.error("Plugin config missing name or class")
            return False
        
        # Import plugin class
        module_path, class_name = plugin_class.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        plugin_cls = getattr(module, class_name)
        
        # Create plugin instance
        plugin = plugin_cls(plugin_config)
        
        # Register plugin
        return plugin_manager.register_plugin(plugin, plugin_config)
        
    except Exception as exc:
        logger.error(f"Error registering plugin from config: {exc}")
        return False


def load_plugins_from_directory(directory: str) -> int:
    """Load plugins from directory."""
    import os
    import importlib.util
    
    loaded_count = 0
    
    try:
        for filename in os.listdir(directory):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_path = os.path.join(directory, filename)
                module_name = filename[:-3]  # Remove .py extension
                
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for plugin classes in module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BasePlugin) and 
                        attr != BasePlugin):
                        
                        plugin_instance = attr()
                        if plugin_manager.register_plugin(plugin_instance):
                            loaded_count += 1
        
        logger.info(f"Loaded {loaded_count} plugins from {directory}")
        
    except Exception as exc:
        logger.error(f"Error loading plugins from directory: {exc}")
    
    return loaded_count


def get_plugin_info(plugin_name: str) -> Optional[Dict[str, Any]]:
    """Get plugin information."""
    plugin = plugin_manager.get_plugin(plugin_name)
    if plugin:
        return {
            'name': plugin.info.name,
            'version': plugin.info.version,
            'description': plugin.info.description,
            'author': plugin.info.author,
            'type': plugin.info.plugin_type.value,
            'status': plugin.info.status.value,
            'enabled': plugin.info.enabled,
            'dependencies': plugin.info.dependencies,
            'config_schema': plugin.info.config_schema
        }
    return None


def list_available_plugins() -> List[Dict[str, Any]]:
    """List all available plugins."""
    plugins = []
    
    for plugin in plugin_manager.plugins.values():
        plugins.append({
            'name': plugin.info.name,
            'version': plugin.info.version,
            'description': plugin.info.description,
            'author': plugin.info.author,
            'type': plugin.info.plugin_type.value,
            'status': plugin.info.status.value,
            'enabled': plugin.info.enabled
        })
    
    return plugins
