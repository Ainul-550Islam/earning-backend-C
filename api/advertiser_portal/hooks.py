"""
Plugin Hooks System for Advertiser Portal

This module provides a plugin/hook system that allows extending
the application functionality through customizable hooks.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import inspect
import importlib
import pkgutil

from .exceptions import *
from .utils import *


logger = logging.getLogger(__name__)


class HookType(Enum):
    """Types of hooks available in the system."""
    FILTER = "filter"  # Modify data
    ACTION = "action"  # Perform action
    VALIDATION = "validation"  # Validate data
    NOTIFICATION = "notification"  # Send notifications
    INTEGRATION = "integration"  # Third-party integrations
    ANALYTICS = "analytics"  # Analytics tracking
    SECURITY = "security"  # Security checks


class HookPriority(Enum):
    """Hook execution priority."""
    LOWEST = 1
    LOW = 2
    NORMAL = 3
    HIGH = 4
    HIGHEST = 5


@dataclass
class Hook:
    """Hook definition."""
    name: str
    hook_type: HookType
    function: Callable
    priority: HookPriority = HookPriority.NORMAL
    description: str = ""
    enabled: bool = True
    module: str = ""
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.description:
            self.description = self.function.__doc__ or f"Hook: {self.name}"
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute the hook function."""
        if not self.enabled:
            return None
        
        try:
            return self.function(*args, **kwargs)
        except Exception as e:
            logger.error(f"Hook {self.name} execution failed: {str(e)}")
            raise HookExecutionError(f"Hook {self.name} failed: {str(e)}")


class HookRegistry:
    """Registry for managing hooks."""
    
    def __init__(self):
        self.hooks: Dict[str, List[Hook]] = {}
        self._load_builtin_hooks()
    
    def _load_builtin_hooks(self):
        """Load built-in hooks."""
        # Register built-in hooks here
        pass
    
    def register(self, hook: Hook) -> bool:
        """
        Register a hook.
        
        Args:
            hook: Hook to register
            
        Returns:
            True if registered successfully
        """
        try:
            if hook.name not in self.hooks:
                self.hooks[hook.name] = []
            
            # Check for duplicate hooks
            for existing_hook in self.hooks[hook.name]:
                if existing_hook.function == hook.function:
                    logger.warning(f"Hook {hook.name} already registered")
                    return False
            
            # Insert hook based on priority
            inserted = False
            for i, existing_hook in enumerate(self.hooks[hook.name]):
                if hook.priority.value > existing_hook.priority.value:
                    self.hooks[hook.name].insert(i, hook)
                    inserted = True
                    break
            
            if not inserted:
                self.hooks[hook.name].append(hook)
            
            logger.info(f"Hook {hook.name} registered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register hook {hook.name}: {str(e)}")
            return False
    
    def unregister(self, hook_name: str, function: Optional[Callable] = None) -> bool:
        """
        Unregister a hook.
        
        Args:
            hook_name: Name of hook to unregister
            function: Specific function to unregister (optional)
            
        Returns:
            True if unregistered successfully
        """
        try:
            if hook_name not in self.hooks:
                return False
            
            if function:
                # Remove specific function
                self.hooks[hook_name] = [
                    hook for hook in self.hooks[hook_name] 
                    if hook.function != function
                ]
            else:
                # Remove all hooks with this name
                self.hooks[hook_name] = []
            
            logger.info(f"Hook {hook_name} unregistered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister hook {hook_name}: {str(e)}")
            return False
    
    def get_hooks(self, hook_name: str) -> List[Hook]:
        """
        Get all hooks for a specific name.
        
        Args:
            hook_name: Name of hooks to retrieve
            
        Returns:
            List of hooks
        """
        return self.hooks.get(hook_name, [])
    
    def execute_hooks(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        Execute all hooks for a specific name.
        
        Args:
            hook_name: Name of hooks to execute
            *args: Arguments to pass to hooks
            **kwargs: Keyword arguments to pass to hooks
            
        Returns:
            List of results from executed hooks
        """
        results = []
        hooks = self.get_hooks(hook_name)
        
        for hook in hooks:
            if hook.enabled:
                try:
                    result = hook.execute(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Hook {hook.name} failed during execution: {str(e)}")
                    results.append(None)
        
        return results
    
    def execute_filter_hooks(self, hook_name: str, data: Any, *args, **kwargs) -> Any:
        """
        Execute filter hooks (each hook receives and returns data).
        
        Args:
            hook_name: Name of hooks to execute
            data: Data to filter
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Filtered data
        """
        hooks = self.get_hooks(hook_name)
        current_data = data
        
        for hook in hooks:
            if hook.enabled and hook.hook_type == HookType.FILTER:
                try:
                    current_data = hook.execute(current_data, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Filter hook {hook.name} failed: {str(e)}")
        
        return current_data
    
    def enable_hook(self, hook_name: str, function: Callable) -> bool:
        """Enable a specific hook."""
        hooks = self.get_hooks(hook_name)
        for hook in hooks:
            if hook.function == function:
                hook.enabled = True
                return True
        return False
    
    def disable_hook(self, hook_name: str, function: Callable) -> bool:
        """Disable a specific hook."""
        hooks = self.get_hooks(hook_name)
        for hook in hooks:
            if hook.function == function:
                hook.enabled = False
                return True
        return False
    
    def list_hooks(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all registered hooks."""
        result = {}
        for hook_name, hooks in self.hooks.items():
            result[hook_name] = [
                {
                    'name': hook.name,
                    'type': hook.hook_type.value,
                    'priority': hook.priority.value,
                    'description': hook.description,
                    'enabled': hook.enabled,
                    'module': hook.module
                }
                for hook in hooks
            ]
        return result


class HookManager:
    """Manager for hook system operations."""
    
    def __init__(self):
        self.registry = HookRegistry()
        self.plugins: Dict[str, 'Plugin'] = {}
    
    def register_plugin(self, plugin: 'Plugin') -> bool:
        """
        Register a plugin and its hooks.
        
        Args:
            plugin: Plugin to register
            
        Returns:
            True if registered successfully
        """
        try:
            if plugin.name in self.plugins:
                logger.warning(f"Plugin {plugin.name} already registered")
                return False
            
            # Initialize plugin
            if not plugin.initialize():
                logger.error(f"Failed to initialize plugin {plugin.name}")
                return False
            
            # Register plugin hooks
            for hook in plugin.get_hooks():
                self.registry.register(hook)
            
            self.plugins[plugin.name] = plugin
            logger.info(f"Plugin {plugin.name} registered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register plugin {plugin.name}: {str(e)}")
            return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        Unregister a plugin and its hooks.
        
        Args:
            plugin_name: Name of plugin to unregister
            
        Returns:
            True if unregistered successfully
        """
        try:
            if plugin_name not in self.plugins:
                return False
            
            plugin = self.plugins[plugin_name]
            
            # Unregister plugin hooks
            for hook in plugin.get_hooks():
                self.registry.unregister(hook.name, hook.function)
            
            # Cleanup plugin
            plugin.cleanup()
            
            del self.plugins[plugin_name]
            logger.info(f"Plugin {plugin_name} unregistered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister plugin {plugin_name}: {str(e)}")
            return False
    
    def load_plugins_from_directory(self, directory: str) -> int:
        """
        Load plugins from a directory.
        
        Args:
            directory: Directory to load plugins from
            
        Returns:
            Number of plugins loaded
        """
        loaded_count = 0
        
        try:
            # Import all modules in the directory
            for module_info in pkgutil.iter_modules([directory]):
                module_name = module_info.name
                try:
                    module = importlib.import_module(f"{directory}.{module_name}")
                    
                    # Look for plugin classes
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (inspect.isclass(attr) and 
                            issubclass(attr, Plugin) and 
                            attr != Plugin):
                            
                            plugin = attr()
                            if self.register_plugin(plugin):
                                loaded_count += 1
                
                except Exception as e:
                    logger.error(f"Failed to load plugin module {module_name}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Failed to load plugins from directory {directory}: {str(e)}")
        
        return loaded_count
    
    def get_plugin(self, plugin_name: str) -> Optional['Plugin']:
        """Get a specific plugin."""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all registered plugins."""
        return [
            {
                'name': plugin.name,
                'version': plugin.version,
                'description': plugin.description,
                'enabled': plugin.enabled,
                'hooks_count': len(plugin.get_hooks())
            }
            for plugin in self.plugins.values()
        ]


# Plugin base class
class Plugin(ABC):
    """Abstract base class for plugins."""
    
    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.enabled = True
        self.hooks: List[Hook] = []
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the plugin.
        
        Returns:
            True if initialized successfully
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass
    
    def get_hooks(self) -> List[Hook]:
        """Get all hooks provided by this plugin."""
        return self.hooks
    
    def add_hook(self, hook: Hook) -> None:
        """Add a hook to this plugin."""
        hook.module = self.name
        self.hooks.append(hook)
    
    def enable(self) -> None:
        """Enable the plugin."""
        self.enabled = True
        for hook in self.hooks:
            hook.enabled = True
    
    def disable(self) -> None:
        """Disable the plugin."""
        self.enabled = False
        for hook in self.hooks:
            hook.enabled = False


# Built-in plugins
class EmailNotificationsPlugin(Plugin):
    """Plugin for email notifications."""
    
    def __init__(self):
        super().__init__(
            name="email_notifications",
            version="1.0.0",
            description="Sends email notifications for various events"
        )
    
    def initialize(self) -> bool:
        """Initialize email notification hooks."""
        try:
            # Advertiser created notification
            self.add_hook(Hook(
                name="advertiser_created_notification",
                hook_type=HookType.NOTIFICATION,
                function=self._send_advertiser_created_email,
                priority=HookPriority.NORMAL
            ))
            
            # Campaign status change notification
            self.add_hook(Hook(
                name="campaign_status_changed_notification",
                hook_type=HookType.NOTIFICATION,
                function=self._send_campaign_status_email,
                priority=HookPriority.HIGH
            ))
            
            # Budget alert notification
            self.add_hook(Hook(
                name="budget_threshold_notification",
                hook_type=HookType.NOTIFICATION,
                function=self._send_budget_alert_email,
                priority=HookPriority.URGENT
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize email notifications plugin: {str(e)}")
            return False
    
    def cleanup(self) -> None:
        """Cleanup email notification resources."""
        pass
    
    def _send_advertiser_created_email(self, advertiser_data: Dict[str, Any]) -> bool:
        """Send welcome email to new advertiser."""
        try:
            # Implementation would send actual email
            logger.info(f"Welcome email sent to {advertiser_data.get('contact_email')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send advertiser created email: {str(e)}")
            return False
    
    def _send_campaign_status_email(self, campaign_data: Dict[str, Any]) -> bool:
        """Send campaign status change email."""
        try:
            # Implementation would send actual email
            logger.info(f"Campaign status email sent for {campaign_data.get('campaign_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send campaign status email: {str(e)}")
            return False
    
    def _send_budget_alert_email(self, budget_data: Dict[str, Any]) -> bool:
        """Send budget alert email."""
        try:
            # Implementation would send actual email
            logger.info(f"Budget alert email sent for campaign {budget_data.get('campaign_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send budget alert email: {str(e)}")
            return False


class AnalyticsTrackingPlugin(Plugin):
    """Plugin for analytics tracking."""
    
    def __init__(self):
        super().__init__(
            name="analytics_tracking",
            version="1.0.0",
            description="Tracks events for analytics purposes"
        )
    
    def initialize(self) -> bool:
        """Initialize analytics tracking hooks."""
        try:
            # Campaign creation tracking
            self.add_hook(Hook(
                name="campaign_created_analytics",
                hook_type=HookType.ANALYTICS,
                function=self._track_campaign_creation,
                priority=HookPriority.NORMAL
            ))
            
            # Creative upload tracking
            self.add_hook(Hook(
                name="creative_uploaded_analytics",
                hook_type=HookType.ANALYTICS,
                function=self._track_creative_upload,
                priority=HookPriority.NORMAL
            ))
            
            # Performance tracking
            self.add_hook(Hook(
                name="performance_update_analytics",
                hook_type=HookType.ANALYTICS,
                function=self._track_performance_update,
                priority=HookPriority.LOW
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize analytics tracking plugin: {str(e)}")
            return False
    
    def cleanup(self) -> None:
        """Cleanup analytics tracking resources."""
        pass
    
    def _track_campaign_creation(self, campaign_data: Dict[str, Any]) -> bool:
        """Track campaign creation in analytics."""
        try:
            # Implementation would track in analytics system
            logger.info(f"Campaign creation tracked: {campaign_data.get('campaign_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to track campaign creation: {str(e)}")
            return False
    
    def _track_creative_upload(self, creative_data: Dict[str, Any]) -> bool:
        """Track creative upload in analytics."""
        try:
            # Implementation would track in analytics system
            logger.info(f"Creative upload tracked: {creative_data.get('creative_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to track creative upload: {str(e)}")
            return False
    
    def _track_performance_update(self, performance_data: Dict[str, Any]) -> bool:
        """Track performance updates in analytics."""
        try:
            # Implementation would track in analytics system
            logger.info(f"Performance update tracked")
            return True
        except Exception as e:
            logger.error(f"Failed to track performance update: {str(e)}")
            return False


class SecurityValidationPlugin(Plugin):
    """Plugin for security validation."""
    
    def __init__(self):
        super().__init__(
            name="security_validation",
            version="1.0.0",
            description="Provides security validation for various operations"
        )
    
    def initialize(self) -> bool:
        """Initialize security validation hooks."""
        try:
            # Input validation
            self.add_hook(Hook(
                name="input_security_validation",
                hook_type=HookType.SECURITY,
                function=self._validate_input_security,
                priority=HookPriority.HIGHEST
            ))
            
            # API rate limiting
            self.add_hook(Hook(
                name="api_rate_limit_check",
                hook_type=HookType.SECURITY,
                function=self._check_rate_limit,
                priority=HookPriority.HIGH
            ))
            
            # IP validation
            self.add_hook(Hook(
                name="ip_security_validation",
                hook_type=HookType.SECURITY,
                function=self._validate_ip_security,
                priority=HookPriority.NORMAL
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize security validation plugin: {str(e)}")
            return False
    
    def cleanup(self) -> None:
        """Cleanup security validation resources."""
        pass
    
    def _validate_input_security(self, data: Any) -> Any:
        """Validate input security."""
        try:
            # Implementation would perform security checks
            if isinstance(data, str):
                # Check for XSS, SQL injection, etc.
                import re
                xss_pattern = r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>'
                if re.search(xss_pattern, data, re.IGNORECASE):
                    raise SecurityValidationError("Potential XSS attack detected")
            
            return data
            
        except Exception as e:
            logger.error(f"Input security validation failed: {str(e)}")
            raise
    
    def _check_rate_limit(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check API rate limits."""
        try:
            # Implementation would check rate limits
            client_id = request_data.get('client_id')
            if client_id:
                # Check rate limit logic here
                pass
            
            return request_data
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            return request_data
    
    def _validate_ip_security(self, ip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate IP security."""
        try:
            # Implementation would validate IP against blacklists, etc.
            ip_address = ip_data.get('ip_address')
            if ip_address:
                # Check IP blacklist, geolocation, etc.
                pass
            
            return ip_data
            
        except Exception as e:
            logger.error(f"IP security validation failed: {str(e)}")
            return ip_data


# Hook decorators
def hook(hook_name: str, hook_type: HookType = HookType.ACTION, 
         priority: HookPriority = HookPriority.NORMAL):
    """
    Decorator to register a function as a hook.
    
    Args:
        hook_name: Name of the hook
        hook_type: Type of hook
        priority: Execution priority
    """
    def decorator(func):
        hook = Hook(
            name=hook_name,
            hook_type=hook_type,
            function=func,
            priority=priority
        )
        
        # Register with global registry
        global_hook_manager.registry.register(hook)
        
        return func
    
    return decorator


def filter_hook(hook_name: str, priority: HookPriority = HookPriority.NORMAL):
    """
    Decorator to register a filter hook.
    
    Args:
        hook_name: Name of the hook
        priority: Execution priority
    """
    return hook(hook_name, HookType.FILTER, priority)


def action_hook(hook_name: str, priority: HookPriority = HookPriority.NORMAL):
    """
    Decorator to register an action hook.
    
    Args:
        hook_name: Name of the hook
        priority: Execution priority
    """
    return hook(hook_name, HookType.ACTION, priority)


def validation_hook(hook_name: str, priority: HookPriority = HookPriority.HIGH):
    """
    Decorator to register a validation hook.
    
    Args:
        hook_name: Name of the hook
        priority: Execution priority
    """
    return hook(hook_name, HookType.VALIDATION, priority)


# Global hook manager instance
global_hook_manager = HookManager()

# Initialize built-in plugins
def initialize_builtin_plugins():
    """Initialize built-in plugins."""
    plugins = [
        EmailNotificationsPlugin(),
        AnalyticsTrackingPlugin(),
        SecurityValidationPlugin()
    ]
    
    for plugin in plugins:
        global_hook_manager.register_plugin(plugin)


# Convenience functions
def register_hook(hook: Hook) -> bool:
    """Register a hook with the global manager."""
    return global_hook_manager.registry.register(hook)


def execute_hooks(hook_name: str, *args, **kwargs) -> List[Any]:
    """Execute hooks with the global manager."""
    return global_hook_manager.registry.execute_hooks(hook_name, *args, **kwargs)


def execute_filter_hooks(hook_name: str, data: Any, *args, **kwargs) -> Any:
    """Execute filter hooks with the global manager."""
    return global_hook_manager.registry.execute_filter_hooks(hook_name, data, *args, **kwargs)


def register_plugin(plugin: Plugin) -> bool:
    """Register a plugin with the global manager."""
    return global_hook_manager.register_plugin(plugin)


def unregister_plugin(plugin_name: str) -> bool:
    """Unregister a plugin with the global manager."""
    return global_hook_manager.unregister_plugin(plugin_name)


# Custom exceptions
class HookExecutionError(Exception):
    """Raised when hook execution fails."""
    pass


class SecurityValidationError(Exception):
    """Raised when security validation fails."""
    pass


# Initialize built-in plugins on module import
initialize_builtin_plugins()
