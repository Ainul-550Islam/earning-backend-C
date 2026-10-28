"""
Plugin system for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from abc import ABC, abstractmethod


class PluginType(Enum):
    """Plugin type constants."""
    METRIC_COLLECTOR = 'metric_collector'
    LOG_HANDLER = 'log_handler'
    TRACE_PROCESSOR = 'trace_processor'
    ALERT_HANDLER = 'alert_handler'
    HEALTH_CHECKER = 'health_checker'
    EXPORTER = 'exporter'
    IMPORTER = 'importer'
    NOTIFICATION = 'notification'
    DASHBOARD_WIDGET = 'dashboard_widget'


class PluginStatus(Enum):
    """Plugin status constants."""
    DISABLED = 'disabled'
    ENABLED = 'enabled'
    ERROR = 'error'


class BasePlugin(ABC):
    """
    Base class for plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        self.name = name
        self.version = version
        self.status = PluginStatus.DISABLED
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize the plugin.
        
        Args:
            config: Plugin configuration
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the plugin.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Plugin execution result
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """
        Shutdown the plugin.
        
        Returns:
            True if successful
        """
        pass
    
    def enable(self) -> None:
        """Enable the plugin."""
        self.status = PluginStatus.ENABLED
    
    def disable(self) -> None:
        """Disable the plugin."""
        self.status = PluginStatus.DISABLED
    
    def is_enabled(self) -> bool:
        """
        Check if plugin is enabled.
        
        Returns:
            True if enabled
        """
        return self.status == PluginStatus.ENABLED


class MetricCollectorPlugin(BasePlugin):
    """
    Base class for metric collector plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the metric collector plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.METRIC_COLLECTOR
    
    @abstractmethod
    def collect_metrics(self) -> List[Dict[str, Any]]:
        """
        Collect metrics.
        
        Returns:
            List of metric data
        """
        pass


class LogHandlerPlugin(BasePlugin):
    """
    Base class for log handler plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the log handler plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.LOG_HANDLER
    
    @abstractmethod
    def handle_log(self, log_data: Dict[str, Any]) -> bool:
        """
        Handle a log entry.
        
        Args:
            log_data: Log data
            
        Returns:
            True if handled successfully
        """
        pass


class TraceProcessorPlugin(BasePlugin):
    """
    Base class for trace processor plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the trace processor plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.TRACE_PROCESSOR
    
    @abstractmethod
    def process_trace(self, trace_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a trace.
        
        Args:
            trace_data: Trace data
            
        Returns:
            Processed trace data
        """
        pass


class AlertHandlerPlugin(BasePlugin):
    """
    Base class for alert handler plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the alert handler plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.ALERT_HANDLER
    
    @abstractmethod
    def handle_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Handle an alert.
        
        Args:
            alert_data: Alert data
            
        Returns:
            True if handled successfully
        """
        pass


class HealthCheckerPlugin(BasePlugin):
    """
    Base class for health checker plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the health checker plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.HEALTH_CHECKER
    
    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Check health.
        
        Returns:
            Health status data
        """
        pass


class ExporterPlugin(BasePlugin):
    """
    Base class for exporter plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the exporter plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.EXPORTER
    
    @abstractmethod
    def export(self, data: Any, format: str = "json") -> str:
        """
        Export data.
        
        Args:
            data: Data to export
            format: Export format
            
        Returns:
            Exported data string
        """
        pass


class ImporterPlugin(BasePlugin):
    """
    Base class for importer plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the importer plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.IMPORTER
    
    @abstractmethod
    def import_data(self, data: str, format: str = "json") -> Any:
        """
        Import data.
        
        Args:
            data: Data string to import
            format: Import format
            
        Returns:
            Imported data
        """
        pass


class NotificationPlugin(BasePlugin):
    """
    Base class for notification plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the notification plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.NOTIFICATION
    
    @abstractmethod
    def send_notification(self, message: str, recipients: List[str]) -> bool:
        """
        Send a notification.
        
        Args:
            message: Notification message
            recipients: List of recipients
            
        Returns:
            True if sent successfully
        """
        pass


class DashboardWidgetPlugin(BasePlugin):
    """
    Base class for dashboard widget plugins.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize the dashboard widget plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
        """
        super().__init__(name, version)
        self.plugin_type = PluginType.DASHBOARD_WIDGET
    
    @abstractmethod
    def render_widget(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a dashboard widget.
        
        Args:
            config: Widget configuration
            
        Returns:
            Rendered widget data
        """
        pass


class PluginManager:
    """
    Singleton manager for plugins.
    """
    
    _instance = None
    
    def __new__(cls):
        """
        Create singleton instance.
        
        Returns:
            PluginManager instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: Dict[str, BasePlugin] = {}
        return cls._instance
    
    def register(self, plugin: BasePlugin) -> bool:
        """
        Register a plugin.
        
        Args:
            plugin: Plugin to register
            
        Returns:
            True if registered successfully
        """
        if plugin.name in self._plugins:
            return False
        
        self._plugins[plugin.name] = plugin
        return True
    
    def unregister(self, plugin_name: str) -> bool:
        """
        Unregister a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if unregistered successfully
        """
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            plugin.shutdown()
            del self._plugins[plugin_name]
            return True
        return False
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """
        Get a plugin by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin or None
        """
        return self._plugins.get(plugin_name)
    
    def list_plugins(self, plugin_type: Optional[PluginType] = None) -> List[str]:
        """
        List all plugins or plugins of a specific type.
        
        Args:
            plugin_type: Optional plugin type filter
            
        Returns:
            List of plugin names
        """
        if plugin_type:
            return [
                name for name, plugin in self._plugins.items()
                if plugin.plugin_type == plugin_type
            ]
        return list(self._plugins.keys())
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """
        Enable a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if enabled successfully
        """
        plugin = self.get_plugin(plugin_name)
        if plugin:
            plugin.enable()
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if disabled successfully
        """
        plugin = self.get_plugin(plugin_name)
        if plugin:
            plugin.disable()
            return True
        return False
    
    def configure_plugin(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        Configure a plugin.
        
        Args:
            plugin_name: Name of the plugin
            config: Configuration dictionary
            
        Returns:
            True if configured successfully
        """
        plugin = self.get_plugin(plugin_name)
        if plugin:
            plugin.config = config
            return plugin.initialize(config)
        return False
    
    def execute_plugin(self, plugin_name: str, *args, **kwargs) -> Any:
        """
        Execute a plugin.
        
        Args:
            plugin_name: Name of the plugin
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Plugin execution result
        """
        plugin = self.get_plugin(plugin_name)
        if plugin and plugin.is_enabled():
            return plugin.execute(*args, **kwargs)
        return None


# Singleton instance
plugin_manager = PluginManager()
