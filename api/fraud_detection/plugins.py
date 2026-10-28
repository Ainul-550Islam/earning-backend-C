# =============================================================================
# fraud_detection/plugins.py
# =============================================================================
"""
Plugin System for Fraud Detection System.

Provides extensible plugin architecture for custom fraud detection
algorithms, third-party integrations, and specialized processing.
"""

from __future__ import annotations

import logging
import importlib
import inspect
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

from django.conf import settings
from django.utils import timezone

from api.fraud_detection.exceptions import PluginError


logger = logging.getLogger(__name__)


class PluginType(Enum):
    """Plugin types for fraud detection system."""
    DETECTION_ALGORITHM = "detection_algorithm"
    DATA_SOURCE = "data_source"
    NOTIFICATION = "notification"
    ANALYTICS = "analytics"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    ENRICHMENT = "enrichment"
    EXPORT = "export"
    INTEGRATION = "integration"


class PluginStatus(Enum):
    """Plugin status levels."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"
    LOADING = "loading"


@dataclass
class PluginMetadata:
    """Plugin metadata information."""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str]
    config_schema: Optional[Dict[str, Any]] = None
    supported_features: List[str] = None
    min_system_version: Optional[str] = None
    max_system_version: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = timezone.now()
        if self.updated_at is None:
            self.updated_at = timezone.now()
        if self.supported_features is None:
            self.supported_features = []


class Plugin(ABC):
    """Abstract base class for fraud detection plugins."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize plugin."""
        self.config = config or {}
        self.status = PluginStatus.INACTIVE
        self.error_message = None
        self.last_error = None
        self.load_time = None
        self.execution_count = 0
        self.last_executed = None
        self.metrics = {}
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize plugin.
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """
        Cleanup plugin resources.
        
        Returns:
            True if cleanup successful
        """
        pass
    
    def execute(self, **kwargs) -> Any:
        """
        Execute plugin logic.
        
        Args:
            **kwargs: Execution parameters
            
        Returns:
            Plugin execution result
        """
        self.execution_count += 1
        self.last_executed = timezone.now()
        
        try:
            return self._execute(**kwargs)
        except Exception as e:
            self.last_error = str(e)
            self.status = PluginStatus.ERROR
            raise PluginError(f"Plugin {self.metadata.name} execution failed: {e}")
    
    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """Internal execution method."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status information."""
        return {
            'name': self.metadata.name,
            'version': self.metadata.version,
            'type': self.metadata.plugin_type.value,
            'status': self.status.value,
            'error_message': self.error_message,
            'last_error': self.last_error,
            'load_time': self.load_time.isoformat() if self.load_time else None,
            'execution_count': self.execution_count,
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'metrics': self.metrics
        }
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        Update plugin configuration.
        
        Args:
            new_config: New configuration
            
        Returns:
            True if update successful
        """
        try:
            self.config.update(new_config)
            self.metadata.updated_at = timezone.now()
            return True
        except Exception as e:
            logger.error(f"Failed to update config for plugin {self.metadata.name}: {e}")
            return False
    
    def record_metric(self, metric_name: str, value: Any):
        """Record plugin metric."""
        self.metrics[metric_name] = value


class DetectionAlgorithmPlugin(Plugin):
    """Base class for detection algorithm plugins."""
    
    @abstractmethod
    def detect_fraud(self, transaction_data: Dict[str, Any], 
                     user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect fraud in transaction data.
        
        Args:
            transaction_data: Transaction data
            user_context: User context
            
        Returns:
            Detection result
        """
        pass
    
    def _execute(self, **kwargs) -> Any:
        """Execute detection algorithm."""
        return self.detect_fraud(
            kwargs.get('transaction_data', {}),
            kwargs.get('user_context', {})
        )


class DataSourcePlugin(Plugin):
    """Base class for data source plugins."""
    
    @abstractmethod
    def fetch_data(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch data from external source.
        
        Args:
            query: Data query
            
        Returns:
            Fetched data
        """
        pass
    
    def _execute(self, **kwargs) -> Any:
        """Execute data fetch."""
        return self.fetch_data(kwargs.get('query', {}))


class NotificationPlugin(Plugin):
    """Base class for notification plugins."""
    
    @abstractmethod
    def send_notification(self, notification_data: Dict[str, Any]) -> bool:
        """
        Send notification.
        
        Args:
            notification_data: Notification data
            
        Returns:
            True if sent successfully
        """
        pass
    
    def _execute(self, **kwargs) -> Any:
        """Execute notification."""
        return self.send_notification(kwargs.get('notification_data', {}))


class AnalyticsPlugin(Plugin):
    """Base class for analytics plugins."""
    
    @abstractmethod
    def generate_analytics(self, data: Dict[str, Any], 
                          analysis_type: str) -> Dict[str, Any]:
        """
        Generate analytics.
        
        Args:
            data: Data to analyze
            analysis_type: Type of analysis
            
        Returns:
            Analytics results
        """
        pass
    
    def _execute(self, **kwargs) -> Any:
        """Execute analytics."""
        return self.generate_analytics(
            kwargs.get('data', {}),
            kwargs.get('analysis_type', 'summary')
        )


class ValidationPlugin(Plugin):
    """Base class for validation plugins."""
    
    @abstractmethod
    def validate_data(self, data: Dict[str, Any], 
                      validation_type: str) -> Dict[str, Any]:
        """
        Validate data.
        
        Args:
            data: Data to validate
            validation_type: Type of validation
            
        Returns:
            Validation results
        """
        pass
    
    def _execute(self, **kwargs) -> Any:
        """Execute validation."""
        return self.validate_data(
            kwargs.get('data', {}),
            kwargs.get('validation_type', 'basic')
        )


class PluginRegistry:
    """Registry for managing fraud detection plugins."""
    
    def __init__(self):
        """Initialize plugin registry."""
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self.plugin_dependencies: Dict[str, List[str]] = {}
        self.load_order: List[str] = []
        self.initialized_plugins: List[str] = []
    
    def register_plugin(self, plugin: Plugin, config: Optional[Dict[str, Any]] = None):
        """
        Register plugin.
        
        Args:
            plugin: Plugin instance
            config: Plugin configuration
        """
        plugin_name = plugin.metadata.name
        
        if plugin_name in self.plugins:
            logger.warning(f"Plugin {plugin_name} already registered, overwriting")
        
        self.plugins[plugin_name] = plugin
        self.plugin_configs[plugin_name] = config or {}
        self.plugin_dependencies[plugin_name] = plugin.metadata.dependencies
        
        # Update load order
        self._calculate_load_order()
        
        logger.info(f"Registered plugin: {plugin_name} v{plugin.metadata.version}")
    
    def unregister_plugin(self, plugin_name: str):
        """
        Unregister plugin.
        
        Args:
            plugin_name: Plugin name
        """
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            
            # Cleanup plugin
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin {plugin_name}: {e}")
            
            del self.plugins[plugin_name]
            del self.plugin_configs[plugin_name]
            del self.plugin_dependencies[plugin_name]
            
            # Update load order
            self._calculate_load_order()
            
            logger.info(f"Unregistered plugin: {plugin_name}")
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load and initialize plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if loaded successfully
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not registered")
            return False
        
        plugin = self.plugins[plugin_name]
        plugin.status = PluginStatus.LOADING
        
        try:
            # Check dependencies
            if not self._check_dependencies(plugin_name):
                return False
            
            # Initialize plugin
            start_time = timezone.now()
            success = plugin.initialize()
            
            if success:
                plugin.status = PluginStatus.ACTIVE
                plugin.load_time = start_time
                self.initialized_plugins.append(plugin_name)
                
                logger.info(f"Loaded plugin: {plugin_name}")
                return True
            else:
                plugin.status = PluginStatus.ERROR
                plugin.error_message = "Initialization failed"
                return False
                
        except Exception as e:
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return False
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """
        Load all registered plugins.
        
        Returns:
            Dictionary of plugin load results
        """
        results = {}
        
        for plugin_name in self.load_order:
            results[plugin_name] = self.load_plugin(plugin_name)
        
        return results
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if unloaded successfully
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not registered")
            return False
        
        plugin = self.plugins[plugin_name]
        
        try:
            # Cleanup plugin
            success = plugin.cleanup()
            
            if success:
                plugin.status = PluginStatus.INACTIVE
                
                if plugin_name in self.initialized_plugins:
                    self.initialized_plugins.remove(plugin_name)
                
                logger.info(f"Unloaded plugin: {plugin_name}")
                return True
            else:
                plugin.status = PluginStatus.ERROR
                plugin.error_message = "Cleanup failed"
                return False
                
        except Exception as e:
            plugin.status = PluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """
        Get plugin by name.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Plugin instance or None
        """
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[Plugin]:
        """
        Get plugins by type.
        
        Args:
            plugin_type: Plugin type
            
        Returns:
            List of plugins
        """
        return [
            plugin for plugin in self.plugins.values()
            if plugin.metadata.plugin_type == plugin_type
        ]
    
    def get_active_plugins(self) -> List[Plugin]:
        """Get all active plugins."""
        return [
            plugin for plugin in self.plugins.values()
            if plugin.status == PluginStatus.ACTIVE
        ]
    
    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin status.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Plugin status or None
        """
        plugin = self.plugins.get(plugin_name)
        if plugin:
            return plugin.get_status()
        return None
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all plugins."""
        return {
            name: plugin.get_status()
            for name, plugin in self.plugins.items()
        }
    
    def execute_plugin(self, plugin_name: str, **kwargs) -> Any:
        """
        Execute plugin.
        
        Args:
            plugin_name: Plugin name
            **kwargs: Execution parameters
            
        Returns:
            Plugin execution result
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise PluginError(f"Plugin {plugin_name} not found")
        
        if plugin.status != PluginStatus.ACTIVE:
            raise PluginError(f"Plugin {plugin_name} is not active")
        
        return plugin.execute(**kwargs)
    
    def execute_plugins_by_type(self, plugin_type: PluginType, **kwargs) -> Dict[str, Any]:
        """
        Execute all plugins of a specific type.
        
        Args:
            plugin_type: Plugin type
            **kwargs: Execution parameters
            
        Returns:
            Dictionary of execution results
        """
        results = {}
        
        for plugin in self.get_plugins_by_type(plugin_type):
            if plugin.status == PluginStatus.ACTIVE:
                try:
                    results[plugin.metadata.name] = plugin.execute(**kwargs)
                except Exception as e:
                    logger.error(f"Error executing plugin {plugin.metadata.name}: {e}")
                    results[plugin.metadata.name] = {'error': str(e)}
        
        return results
    
    def _calculate_load_order(self):
        """Calculate plugin load order based on dependencies."""
        visited = set()
        order = []
        
        def visit(plugin_name: str):
            if plugin_name in visited:
                return
            
            visited.add(plugin_name)
            
            dependencies = self.plugin_dependencies.get(plugin_name, [])
            for dep in dependencies:
                if dep in self.plugins:
                    visit(dep)
            
            order.append(plugin_name)
        
        for plugin_name in self.plugins:
            visit(plugin_name)
        
        self.load_order = order
    
    def _check_dependencies(self, plugin_name: str) -> bool:
        """Check if plugin dependencies are satisfied."""
        dependencies = self.plugin_dependencies.get(plugin_name, [])
        
        for dep in dependencies:
            if dep not in self.initialized_plugins:
                logger.error(f"Plugin {plugin_name} depends on {dep} which is not loaded")
                return False
        
        return True


# Built-in plugins
class BasicRuleDetectionPlugin(DetectionAlgorithmPlugin):
    """Basic rule-based detection plugin."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="basic_rule_detection",
            version="1.0.0",
            description="Basic rule-based fraud detection",
            author="System",
            plugin_type=PluginType.DETECTION_ALGORITHM,
            dependencies=[],
            supported_features=["rule_detection", "basic_scoring"]
        )
    
    def initialize(self) -> bool:
        """Initialize plugin."""
        self.rules = self.config.get('rules', [])
        return True
    
    def cleanup(self) -> bool:
        """Cleanup plugin."""
        return True
    
    def detect_fraud(self, transaction_data: Dict[str, Any], 
                     user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Detect fraud using basic rules."""
        risk_score = 0
        indicators = []
        
        # Rule: High amount threshold
        amount = transaction_data.get('amount', 0)
        if amount > 10000:
            risk_score += 30
            indicators.append("high_amount")
        
        # Rule: Unusual location
        ip_address = transaction_data.get('ip_address')
        if ip_address and self._is_suspicious_ip(ip_address):
            risk_score += 25
            indicators.append("suspicious_ip")
        
        # Rule: New user
        account_age = user_context.get('account_age_days', 0)
        if account_age < 7:
            risk_score += 20
            indicators.append("new_user")
        
        return {
            'risk_score': min(risk_score, 100),
            'indicators': indicators,
            'detection_method': 'basic_rules',
            'confidence': 0.7
        }
    
    def _is_suspicious_ip(self, ip_address: str) -> bool:
        """Check if IP is suspicious."""
        # Simplified IP checking
        suspicious_ranges = ['192.168.', '10.', '172.16.']
        return any(ip_address.startswith(range) for range in suspicious_ranges)


class EmailNotificationPlugin(NotificationPlugin):
    """Email notification plugin."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="email_notification",
            version="1.0.0",
            description="Email notification system",
            author="System",
            plugin_type=PluginType.NOTIFICATION,
            dependencies=[],
            supported_features=["email_alerts", "html_templates"]
        )
    
    def initialize(self) -> bool:
        """Initialize plugin."""
        self.smtp_config = self.config.get('smtp', {})
        return True
    
    def cleanup(self) -> bool:
        """Cleanup plugin."""
        return True
    
    def send_notification(self, notification_data: Dict[str, Any]) -> bool:
        """Send email notification."""
        # Simplified email sending
        logger.info(f"Would send email: {notification_data.get('subject', 'No subject')}")
        return True


class FileExportPlugin(Plugin):
    """File export plugin."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="file_export",
            version="1.0.0",
            description="File export functionality",
            author="System",
            plugin_type=PluginType.EXPORT,
            dependencies=[],
            supported_features=["csv_export", "excel_export", "pdf_export"]
        )
    
    def initialize(self) -> bool:
        """Initialize plugin."""
        return True
    
    def cleanup(self) -> bool:
        """Cleanup plugin."""
        return True
    
    def _execute(self, **kwargs) -> Any:
        """Execute export."""
        export_type = kwargs.get('export_type', 'csv')
        data = kwargs.get('data', {})
        
        if export_type == 'csv':
            return self._export_csv(data)
        elif export_type == 'excel':
            return self._export_excel(data)
        elif export_type == 'pdf':
            return self._export_pdf(data)
        else:
            raise PluginError(f"Unsupported export type: {export_type}")
    
    def _export_csv(self, data: Dict[str, Any]) -> str:
        """Export to CSV."""
        # Simplified CSV export
        return "CSV export data"
    
    def _export_excel(self, data: Dict[str, Any]) -> bytes:
        """Export to Excel."""
        # Simplified Excel export
        return b"Excel export data"
    
    def _export_pdf(self, data: Dict[str, Any]) -> bytes:
        """Export to PDF."""
        # Simplified PDF export
        return b"PDF export data"


# Global plugin registry
plugin_registry = PluginRegistry()

# Register built-in plugins
plugin_registry.register_plugin(BasicRuleDetectionPlugin())
plugin_registry.register_plugin(EmailNotificationPlugin())
plugin_registry.register_plugin(FileExportPlugin())


# Plugin management functions
def load_plugins_from_settings():
    """Load plugins from Django settings."""
    try:
        plugin_configs = getattr(settings, 'FRAUD_DETECTION_PLUGINS', {})
        
        for plugin_name, plugin_config in plugin_configs.items():
            try:
                plugin_module = plugin_config.get('module')
                plugin_class = plugin_config.get('class')
                plugin_config_data = plugin_config.get('config', {})
                
                if plugin_module and plugin_class:
                    # Import plugin module
                    module = importlib.import_module(plugin_module)
                    plugin_class_obj = getattr(module, plugin_class)
                    
                    # Create plugin instance
                    plugin = plugin_class_obj(plugin_config_data)
                    
                    # Register plugin
                    plugin_registry.register_plugin(plugin, plugin_config_data)
                    
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
                
    except Exception as e:
        logger.error(f"Error loading plugins from settings: {e}")


# Load plugins from settings on module import
load_plugins_from_settings()


# Convenience functions
def get_plugin(plugin_name: str) -> Optional[Plugin]:
    """Get plugin by name."""
    return plugin_registry.get_plugin(plugin_name)


def execute_detection_plugin(plugin_name: str, transaction_data: Dict[str, Any], 
                           user_context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute detection plugin."""
    return plugin_registry.execute_plugin(
        plugin_name,
        transaction_data=transaction_data,
        user_context=user_context
    )


def execute_all_detection_plugins(transaction_data: Dict[str, Any], 
                                  user_context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute all detection plugins."""
    return plugin_registry.execute_plugins_by_type(
        PluginType.DETECTION_ALGORITHM,
        transaction_data=transaction_data,
        user_context=user_context
    )


def execute_notification_plugin(plugin_name: str, notification_data: Dict[str, Any]) -> bool:
    """Execute notification plugin."""
    return plugin_registry.execute_plugin(plugin_name, notification_data=notification_data)


def execute_all_notification_plugins(notification_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute all notification plugins."""
    return plugin_registry.execute_plugins_by_type(
        PluginType.NOTIFICATION,
        notification_data=notification_data
    )


def get_plugin_status(plugin_name: str = None) -> Union[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Get plugin status."""
    if plugin_name:
        return plugin_registry.get_plugin_status(plugin_name)
    else:
        return plugin_registry.get_all_status()


# Plugin discovery utilities
def discover_plugins(plugin_directory: str) -> List[str]:
    """Discover plugins in directory."""
    import os
    import glob
    
    plugin_files = glob.glob(os.path.join(plugin_directory, "*_plugin.py"))
    return [os.path.basename(f)[:-3] for f in plugin_files]


def install_plugin(plugin_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Install plugin from file."""
    try:
        # Load plugin from file
        spec = importlib.util.spec_from_file_location("plugin", plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find plugin class
        plugin_classes = [
            obj for name, obj in inspect.getmembers(module)
            if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin
        ]
        
        if not plugin_classes:
            logger.error(f"No plugin class found in {plugin_path}")
            return False
        
        # Create plugin instance
        plugin_class = plugin_classes[0]
        plugin = plugin_class(config)
        
        # Register plugin
        plugin_registry.register_plugin(plugin, config)
        
        logger.info(f"Installed plugin from {plugin_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to install plugin from {plugin_path}: {e}")
        return False


_plugin_manager_instance: Optional[PluginRegistry] = None


def get_plugin_manager() -> PluginRegistry:
    """Return the process-wide PluginRegistry singleton."""
    global _plugin_manager_instance
    if _plugin_manager_instance is None:
        _plugin_manager_instance = PluginRegistry()
    return _plugin_manager_instance
