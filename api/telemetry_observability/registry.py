"""
Registry system for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List, Callable, TypeVar
from enum import Enum


class RegistryType(Enum):
    """Registry type constants."""
    METRIC_COLLECTORS = 'metric_collectors'
    LOG_HANDLERS = 'log_handlers'
    TRACE_PROCESSORS = 'trace_processors'
    ALERT_HANDLERS = 'alert_handlers'
    HEALTH_CHECKERS = 'health_checkers'
    DASHBOARD_WIDGETS = 'dashboard_widgets'
    EXPORTERS = 'exporters'
    IMPORTERS = 'importers'
    NOTIFICATION_CHANNELS = 'notification_channels'


T = TypeVar('T')


class Registry:
    """
    Base registry class.
    """
    
    def __init__(self, name: str):
        """
        Initialize the registry.
        
        Args:
            name: Registry name
        """
        self.name = name
        self._items: Dict[str, T] = {}
    
    def register(self, key: str, item: T) -> None:
        """
        Register an item.
        
        Args:
            key: Item key
            item: Item to register
        """
        self._items[key] = item
    
    def unregister(self, key: str) -> bool:
        """
        Unregister an item.
        
        Args:
            key: Item key
            
        Returns:
            True if unregistered successfully
        """
        if key in self._items:
            del self._items[key]
            return True
        return False
    
    def get(self, key: str) -> Optional[T]:
        """
        Get an item by key.
        
        Args:
            key: Item key
            
        Returns:
            Item or None
        """
        return self._items.get(key)
    
    def list(self) -> List[str]:
        """
        List all keys.
        
        Returns:
            List of keys
        """
        return list(self._items.keys())
    
    def items(self) -> Dict[str, T]:
        """
        Get all items.
        
        Returns:
            Dictionary of items
        """
        return self._items.copy()
    
    def clear(self) -> None:
        """Clear all items."""
        self._items.clear()


class MetricCollectorRegistry(Registry):
    """
    Registry for metric collectors.
    """
    
    def __init__(self):
        """Initialize the metric collector registry."""
        super().__init__(RegistryType.METRIC_COLLECTORS.value)
    
    def register_collector(self, name: str, collector: Callable) -> None:
        """
        Register a metric collector.
        
        Args:
            name: Collector name
            collector: Collector function
        """
        self.register(name, collector)
    
    def get_collector(self, name: str) -> Optional[Callable]:
        """
        Get a metric collector.
        
        Args:
            name: Collector name
            
        Returns:
            Collector function or None
        """
        return self.get(name)


class LogHandlerRegistry(Registry):
    """
    Registry for log handlers.
    """
    
    def __init__(self):
        """Initialize the log handler registry."""
        super().__init__(RegistryType.LOG_HANDLERS.value)
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """
        Register a log handler.
        
        Args:
            name: Handler name
            handler: Handler function
        """
        self.register(name, handler)
    
    def get_handler(self, name: str) -> Optional[Callable]:
        """
        Get a log handler.
        
        Args:
            name: Handler name
            
        Returns:
            Handler function or None
        """
        return self.get(name)


class TraceProcessorRegistry(Registry):
    """
    Registry for trace processors.
    """
    
    def __init__(self):
        """Initialize the trace processor registry."""
        super().__init__(RegistryType.TRACE_PROCESSORS.value)
    
    def register_processor(self, name: str, processor: Callable) -> None:
        """
        Register a trace processor.
        
        Args:
            name: Processor name
            processor: Processor function
        """
        self.register(name, processor)
    
    def get_processor(self, name: str) -> Optional[Callable]:
        """
        Get a trace processor.
        
        Args:
            name: Processor name
            
        Returns:
            Processor function or None
        """
        return self.get(name)


class AlertHandlerRegistry(Registry):
    """
    Registry for alert handlers.
    """
    
    def __init__(self):
        """Initialize the alert handler registry."""
        super().__init__(RegistryType.ALERT_HANDLERS.value)
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """
        Register an alert handler.
        
        Args:
            name: Handler name
            handler: Handler function
        """
        self.register(name, handler)
    
    def get_handler(self, name: str) -> Optional[Callable]:
        """
        Get an alert handler.
        
        Args:
            name: Handler name
            
        Returns:
            Handler function or None
        """
        return self.get(name)


class HealthCheckerRegistry(Registry):
    """
    Registry for health checkers.
    """
    
    def __init__(self):
        """Initialize the health checker registry."""
        super().__init__(RegistryType.HEALTH_CHECKERS.value)
    
    def register_checker(self, name: str, checker: Callable) -> None:
        """
        Register a health checker.
        
        Args:
            name: Checker name
            checker: Checker function
        """
        self.register(name, checker)
    
    def get_checker(self, name: str) -> Optional[Callable]:
        """
        Get a health checker.
        
        Args:
            name: Checker name
            
        Returns:
            Checker function or None
        """
        return self.get(name)


class DashboardWidgetRegistry(Registry):
    """
    Registry for dashboard widgets.
    """
    
    def __init__(self):
        """Initialize the dashboard widget registry."""
        super().__init__(RegistryType.DASHBOARD_WIDGETS.value)
    
    def register_widget(self, name: str, widget: Callable) -> None:
        """
        Register a dashboard widget.
        
        Args:
            name: Widget name
            widget: Widget function
        """
        self.register(name, widget)
    
    def get_widget(self, name: str) -> Optional[Callable]:
        """
        Get a dashboard widget.
        
        Args:
            name: Widget name
            
        Returns:
            Widget function or None
        """
        return self.get(name)


class ExporterRegistry(Registry):
    """
    Registry for data exporters.
    """
    
    def __init__(self):
        """Initialize the exporter registry."""
        super().__init__(RegistryType.EXPORTERS.value)
    
    def register_exporter(self, name: str, exporter: Callable) -> None:
        """
        Register an exporter.
        
        Args:
            name: Exporter name
            exporter: Exporter function
        """
        self.register(name, exporter)
    
    def get_exporter(self, name: str) -> Optional[Callable]:
        """
        Get an exporter.
        
        Args:
            name: Exporter name
            
        Returns:
            Exporter function or None
        """
        return self.get(name)


class ImporterRegistry(Registry):
    """
    Registry for data importers.
    """
    
    def __init__(self):
        """Initialize the importer registry."""
        super().__init__(RegistryType.IMPORTERS.value)
    
    def register_importer(self, name: str, importer: Callable) -> None:
        """
        Register an importer.
        
        Args:
            name: Importer name
            importer: Importer function
        """
        self.register(name, importer)
    
    def get_importer(self, name: str) -> Optional[Callable]:
        """
        Get an importer.
        
        Args:
            name: Importer name
            
        Returns:
            Importer function or None
        """
        return self.get(name)


class NotificationChannelRegistry(Registry):
    """
    Registry for notification channels.
    """
    
    def __init__(self):
        """Initialize the notification channel registry."""
        super().__init__(RegistryType.NOTIFICATION_CHANNELS.value)
    
    def register_channel(self, name: str, channel: Callable) -> None:
        """
        Register a notification channel.
        
        Args:
            name: Channel name
            channel: Channel function
        """
        self.register(name, channel)
    
    def get_channel(self, name: str) -> Optional[Callable]:
        """
        Get a notification channel.
        
        Args:
            name: Channel name
            
        Returns:
            Channel function or None
        """
        return self.get(name)


class RegistryManager:
    """
    Singleton manager for all registries.
    """
    
    _instance = None
    
    def __new__(cls):
        """
        Create singleton instance.
        
        Returns:
            RegistryManager instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registries: Dict[RegistryType, Registry] = {}
            cls._instance._initialize_registries()
        return cls._instance
    
    def _initialize_registries(self):
        """Initialize all registries."""
        self._registries[RegistryType.METRIC_COLLECTORS] = MetricCollectorRegistry()
        self._registries[RegistryType.LOG_HANDLERS] = LogHandlerRegistry()
        self._registries[RegistryType.TRACE_PROCESSORS] = TraceProcessorRegistry()
        self._registries[RegistryType.ALERT_HANDLERS] = AlertHandlerRegistry()
        self._registries[RegistryType.HEALTH_CHECKERS] = HealthCheckerRegistry()
        self._registries[RegistryType.DASHBOARD_WIDGETS] = DashboardWidgetRegistry()
        self._registries[RegistryType.EXPORTERS] = ExporterRegistry()
        self._registries[RegistryType.IMPORTERS] = ImporterRegistry()
        self._registries[RegistryType.NOTIFICATION_CHANNELS] = NotificationChannelRegistry()
    
    def get_registry(self, registry_type: RegistryType) -> Optional[Registry]:
        """
        Get a registry by type.
        
        Args:
            registry_type: Type of registry
            
        Returns:
            Registry or None
        """
        return self._registries.get(registry_type)
    
    def list_registries(self) -> List[str]:
        """
        List all registry names.
        
        Returns:
            List of registry names
        """
        return [registry.name for registry in self._registries.values()]
    
    def clear_all(self) -> None:
        """Clear all registries."""
        for registry in self._registries.values():
            registry.clear()


# Singleton instance
registry_manager = RegistryManager()
