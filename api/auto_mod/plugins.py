# =============================================================================
# auto_mod/plugins.py
# =============================================================================

"""
Plugin system for auto moderation.
Provides extensible plugin architecture for custom functionality.
"""

import logging
import importlib
import inspect
from typing import Any, Dict, List, Optional, Union, Callable
from abc import ABC, abstractmethod
from datetime import datetime
from django.utils import timezone
from django.conf import settings

from .models import SuspiciousSubmission, ModerationDecision
from .exceptions import ModerationError

logger = logging.getLogger(__name__)


class PluginType:
    """Plugin types."""
    SCANNER = "scanner"
    ANALYZER = "analyzer"
    FILTER = "filter"
    ENRICHER = "enricher"
    NOTIFIER = "notifier"
    REPORTER = "reporter"
    AUTHENTICATOR = "authenticator"
    VALIDATOR = "validator"


class PluginStatus:
    """Plugin status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    LOADING = "loading"
    DISABLED = "disabled"


class BasePlugin(ABC):
    """Base plugin class."""
    
    def __init__(self, name: str, version: str, description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.status = PluginStatus.INACTIVE
        self.config = {}
        self.metadata = {}
        self.loaded_at = None
        self.error_message = None
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None) -> bool:
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
        Execute the plugin logic.
        
        Returns:
            Plugin execution result
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """
        Cleanup plugin resources.
        
        Returns:
            True if successful
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'status': self.status,
            'type': self.__class__.__bases__[0].__name__ if self.__class__.__bases__ else 'BasePlugin',
            'config': self.config,
            'metadata': self.metadata,
            'loaded_at': self.loaded_at.isoformat() if self.loaded_at else None,
            'error_message': self.error_message,
        }
    
    def set_status(self, status: str, error_message: str = None) -> None:
        """Set plugin status."""
        self.status = status
        self.error_message = error_message
        if status == PluginStatus.ACTIVE:
            self.loaded_at = timezone.now()


class ScannerPlugin(BasePlugin):
    """Base class for scanner plugins."""
    
    @abstractmethod
    def scan(self, submission: SuspiciousSubmission) -> Dict[str, Any]:
        """
        Scan submission for issues.
        
        Args:
            submission: Submission to scan
            
        Returns:
            Scan results
        """
        pass


class AnalyzerPlugin(BasePlugin):
    """Base class for analyzer plugins."""
    
    @abstractmethod
    def analyze(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze content.
        
        Args:
            content: Content to analyze
            metadata: Additional metadata
            
        Returns:
            Analysis results
        """
        pass


class FilterPlugin(BasePlugin):
    """Base class for filter plugins."""
    
    @abstractmethod
    def filter(self, submission: SuspiciousSubmission) -> bool:
        """
        Filter submission.
        
        Args:
            submission: Submission to filter
            
        Returns:
            True if submission passes filter
        """
        pass


class EnricherPlugin(BasePlugin):
    """Base class for enricher plugins."""
    
    @abstractmethod
    def enrich(self, submission: SuspiciousSubmission) -> Dict[str, Any]:
        """
        Enrich submission with additional data.
        
        Args:
            submission: Submission to enrich
            
        Returns:
            Enrichment data
        """
        pass


class NotifierPlugin(BasePlugin):
    """Base class for notifier plugins."""
    
    @abstractmethod
    def notify(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Send notification.
        
        Args:
            event_type: Type of event
            data: Event data
            
        Returns:
            True if notification sent
        """
        pass


class ReporterPlugin(BasePlugin):
    """Base class for reporter plugins."""
    
    @abstractmethod
    def generate_report(self, report_type: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate report.
        
        Args:
            report_type: Type of report
            parameters: Report parameters
            
        Returns:
            Report data
        """
        pass


class PluginManager:
    """
    Manager for plugin system.
    """
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_registry: Dict[str, Dict[str, Any]] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._load_plugin_configs()
    
    def _load_plugin_configs(self) -> None:
        """Load plugin configurations."""
        try:
            self.plugin_configs = getattr(settings, 'AUTO_MOD_PLUGINS', {})
        except Exception as exc:
            logger.error(f"Load plugin configs failed: {exc}")
            self.plugin_configs = {}
    
    def register_plugin(self, plugin: BasePlugin) -> bool:
        """
        Register a plugin.
        
        Args:
            plugin: Plugin to register
            
        Returns:
            True if successful
        """
        try:
            if plugin.name in self.plugins:
                logger.warning(f"Plugin {plugin.name} already registered")
                return False
            
            # Get plugin config
            config = self.plugin_configs.get(plugin.name, {})
            
            # Initialize plugin
            if plugin.initialize(config):
                self.plugins[plugin.name] = plugin
                plugin.set_status(PluginStatus.ACTIVE)
                logger.info(f"Plugin {plugin.name} registered successfully")
                return True
            else:
                plugin.set_status(PluginStatus.ERROR, "Initialization failed")
                logger.error(f"Plugin {plugin.name} initialization failed")
                return False
                
        except Exception as exc:
            logger.error(f"Register plugin failed: {exc}")
            if hasattr(plugin, 'set_status'):
                plugin.set_status(PluginStatus.ERROR, str(exc))
            return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        Unregister a plugin.
        
        Args:
            plugin_name: Name of plugin to unregister
            
        Returns:
            True if successful
        """
        try:
            plugin = self.plugins.get(plugin_name)
            if not plugin:
                logger.warning(f"Plugin {plugin_name} not found")
                return False
            
            # Cleanup plugin
            plugin.cleanup()
            
            # Remove from registry
            del self.plugins[plugin_name]
            plugin.set_status(PluginStatus.INACTIVE)
            
            logger.info(f"Plugin {plugin_name} unregistered successfully")
            return True
            
        except Exception as exc:
            logger.error(f"Unregister plugin failed: {exc}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get plugin by name."""
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: type) -> List[BasePlugin]:
        """Get plugins by type."""
        return [plugin for plugin in self.plugins.values() 
                if isinstance(plugin, plugin_type)]
    
    def execute_plugin(self, plugin_name: str, *args, **kwargs) -> Any:
        """
        Execute a plugin.
        
        Args:
            plugin_name: Name of plugin to execute
            
        Returns:
            Plugin execution result
        """
        try:
            plugin = self.get_plugin(plugin_name)
            if not plugin:
                raise ValueError(f"Plugin {plugin_name} not found")
            
            if plugin.status != PluginStatus.ACTIVE:
                raise ValueError(f"Plugin {plugin_name} is not active")
            
            return plugin.execute(*args, **kwargs)
            
        except Exception as exc:
            logger.error(f"Execute plugin failed: {exc}")
            plugin = self.get_plugin(plugin_name)
            if plugin:
                plugin.set_status(PluginStatus.ERROR, str(exc))
            raise ModerationError(f"Failed to execute plugin {plugin_name}: {exc}")
    
    def execute_plugins_by_type(self, plugin_type: type, *args, **kwargs) -> List[Any]:
        """
        Execute all plugins of a specific type.
        
        Args:
            plugin_type: Type of plugins to execute
            
        Returns:
            List of execution results
        """
        results = []
        plugins = self.get_plugins_by_type(plugin_type)
        
        for plugin in plugins:
            try:
                if plugin.status == PluginStatus.ACTIVE:
                    result = plugin.execute(*args, **kwargs)
                    results.append({
                        'plugin_name': plugin.name,
                        'status': 'success',
                        'result': result
                    })
                else:
                    results.append({
                        'plugin_name': plugin.name,
                        'status': 'inactive',
                        'result': None
                    })
            except Exception as exc:
                logger.error(f"Execute plugin {plugin.name} failed: {exc}")
                plugin.set_status(PluginStatus.ERROR, str(exc))
                results.append({
                    'plugin_name': plugin.name,
                    'status': 'error',
                    'error': str(exc),
                    'result': None
                })
        
        return results
    
    def scan_submission(self, submission: SuspiciousSubmission) -> Dict[str, Any]:
        """
        Scan submission with all scanner plugins.
        
        Args:
            submission: Submission to scan
            
        Returns:
            Combined scan results
        """
        scanner_plugins = self.get_plugins_by_type(ScannerPlugin)
        results = {}
        
        for plugin in scanner_plugins:
            try:
                if plugin.status == PluginStatus.ACTIVE:
                    result = plugin.scan(submission)
                    results[plugin.name] = result
            except Exception as exc:
                logger.error(f"Scanner plugin {plugin.name} failed: {exc}")
                plugin.set_status(PluginStatus.ERROR, str(exc))
                results[plugin.name] = {'error': str(exc)}
        
        return results
    
    def analyze_content(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze content with all analyzer plugins.
        
        Args:
            content: Content to analyze
            metadata: Additional metadata
            
        Returns:
            Combined analysis results
        """
        analyzer_plugins = self.get_plugins_by_type(AnalyzerPlugin)
        results = {}
        
        for plugin in analyzer_plugins:
            try:
                if plugin.status == PluginStatus.ACTIVE:
                    result = plugin.analyze(content, metadata)
                    results[plugin.name] = result
            except Exception as exc:
                logger.error(f"Analyzer plugin {plugin.name} failed: {exc}")
                plugin.set_status(PluginStatus.ERROR, str(exc))
                results[plugin.name] = {'error': str(exc)}
        
        return results
    
    def filter_submission(self, submission: SuspiciousSubmission) -> bool:
        """
        Filter submission with all filter plugins.
        
        Args:
            submission: Submission to filter
            
        Returns:
            True if submission passes all filters
        """
        filter_plugins = self.get_plugins_by_type(FilterPlugin)
        
        for plugin in filter_plugins:
            try:
                if plugin.status == PluginStatus.ACTIVE:
                    if not plugin.filter(submission):
                        return False
            except Exception as exc:
                logger.error(f"Filter plugin {plugin.name} failed: {exc}")
                plugin.set_status(PluginStatus.ERROR, str(exc))
                return False
        
        return True
    
    def enrich_submission(self, submission: SuspiciousSubmission) -> Dict[str, Any]:
        """
        Enrich submission with all enricher plugins.
        
        Args:
            submission: Submission to enrich
            
        Returns:
            Combined enrichment data
        """
        enricher_plugins = self.get_plugins_by_type(EnricherPlugin)
        results = {}
        
        for plugin in enricher_plugins:
            try:
                if plugin.status == PluginStatus.ACTIVE:
                    result = plugin.enrich(submission)
                    results[plugin.name] = result
            except Exception as exc:
                logger.error(f"Enricher plugin {plugin.name} failed: {exc}")
                plugin.set_status(PluginStatus.ERROR, str(exc))
                results[plugin.name] = {'error': str(exc)}
        
        return results
    
    def send_notifications(self, event_type: str, data: Dict[str, Any]) -> List[bool]:
        """
        Send notifications with all notifier plugins.
        
        Args:
            event_type: Type of event
            data: Event data
            
        Returns:
            List of notification results
        """
        notifier_plugins = self.get_plugins_by_type(NotifierPlugin)
        results = []
        
        for plugin in notifier_plugins:
            try:
                if plugin.status == PluginStatus.ACTIVE:
                    result = plugin.notify(event_type, data)
                    results.append(result)
                else:
                    results.append(False)
            except Exception as exc:
                logger.error(f"Notifier plugin {plugin.name} failed: {exc}")
                plugin.set_status(PluginStatus.ERROR, str(exc))
                results.append(False)
        
        return results
    
    def generate_reports(self, report_type: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate reports with all reporter plugins.
        
        Args:
            report_type: Type of report
            parameters: Report parameters
            
        Returns:
            Combined report data
        """
        reporter_plugins = self.get_plugins_by_type(ReporterPlugin)
        results = {}
        
        for plugin in reporter_plugins:
            try:
                if plugin.status == PluginStatus.ACTIVE:
                    result = plugin.generate_report(report_type, parameters)
                    results[plugin.name] = result
            except Exception as exc:
                logger.error(f"Reporter plugin {plugin.name} failed: {exc}")
                plugin.set_status(PluginStatus.ERROR, str(exc))
                results[plugin.name] = {'error': str(exc)}
        
        return results
    
    def get_plugin_status(self) -> Dict[str, Any]:
        """Get status of all plugins."""
        plugin_info = {}
        
        for plugin_name, plugin in self.plugins.items():
            plugin_info[plugin_name] = plugin.get_info()
        
        return {
            'total_plugins': len(self.plugins),
            'active_plugins': len([p for p in self.plugins.values() if p.status == PluginStatus.ACTIVE]),
            'error_plugins': len([p for p in self.plugins.values() if p.status == PluginStatus.ERROR]),
            'inactive_plugins': len([p for p in self.plugins.values() if p.status == PluginStatus.INACTIVE]),
            'plugins': plugin_info,
            'checked_at': timezone.now().isoformat(),
        }
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a plugin.
        
        Args:
            plugin_name: Name of plugin to reload
            
        Returns:
            True if successful
        """
        try:
            plugin = self.get_plugin(plugin_name)
            if not plugin:
                return False
            
            # Cleanup and reinitialize
            plugin.cleanup()
            config = self.plugin_configs.get(plugin_name, {})
            
            if plugin.initialize(config):
                plugin.set_status(PluginStatus.ACTIVE)
                logger.info(f"Plugin {plugin_name} reloaded successfully")
                return True
            else:
                plugin.set_status(PluginStatus.ERROR, "Reload failed")
                logger.error(f"Plugin {plugin_name} reload failed")
                return False
                
        except Exception as exc:
            logger.error(f"Reload plugin failed: {exc}")
            return False
    
    def load_plugins_from_directory(self, directory: str) -> int:
        """
        Load plugins from directory.
        
        Args:
            directory: Directory to load plugins from
            
        Returns:
            Number of plugins loaded
        """
        loaded_count = 0
        
        try:
            import os
            import sys
            
            # Add directory to Python path
            if directory not in sys.path:
                sys.path.insert(0, directory)
            
            # Find plugin files
            for filename in os.listdir(directory):
                if filename.endswith('.py') and not filename.startswith('__'):
                    module_name = filename[:-3]
                    
                    try:
                        # Import module
                        module = importlib.import_module(module_name)
                        
                        # Find plugin classes
                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            if (issubclass(obj, BasePlugin) and 
                                obj != BasePlugin and 
                                not inspect.isabstract(obj)):
                                
                                # Create plugin instance
                                plugin = obj()
                                if self.register_plugin(plugin):
                                    loaded_count += 1
                                    break
                                    
                    except Exception as exc:
                        logger.error(f"Load plugin module {module_name} failed: {exc}")
                        continue
            
            logger.info(f"Loaded {loaded_count} plugins from {directory}")
            return loaded_count
            
        except Exception as exc:
            logger.error(f"Load plugins from directory failed: {exc}")
            return 0


# Global plugin manager
plugin_manager = PluginManager()


# Utility functions
def register_plugin(plugin: BasePlugin) -> bool:
    """Register a plugin."""
    return plugin_manager.register_plugin(plugin)


def get_plugin(plugin_name: str) -> Optional[BasePlugin]:
    """Get plugin by name."""
    return plugin_manager.get_plugin(plugin_name)


def scan_submission_with_plugins(submission: SuspiciousSubmission) -> Dict[str, Any]:
    """Scan submission with all scanner plugins."""
    return plugin_manager.scan_submission(submission)


def analyze_content_with_plugins(content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Analyze content with all analyzer plugins."""
    return plugin_manager.analyze_content(content, metadata)


def filter_submission_with_plugins(submission: SuspiciousSubmission) -> bool:
    """Filter submission with all filter plugins."""
    return plugin_manager.filter_submission(submission)


def enrich_submission_with_plugins(submission: SuspiciousSubmission) -> Dict[str, Any]:
    """Enrich submission with all enricher plugins."""
    return plugin_manager.enrich_submission(submission)


def send_notifications_with_plugins(event_type: str, data: Dict[str, Any]) -> List[bool]:
    """Send notifications with all notifier plugins."""
    return plugin_manager.send_notifications(event_type, data)


# Initialize logging
logger.info("Plugins module initialized with extensible plugin architecture")
