# =============================================================================
# fraud_detection/registry.py
# =============================================================================
"""
Registry System for Fraud Detection System.

Provides centralized registry for managing fraud detection
components, configurations, and system-wide resources.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Type, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from threading import RLock

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from api.fraud_detection.exceptions import RegistryError


logger = logging.getLogger(__name__)


class RegistryType(Enum):
    """Registry types for different components."""
    DETECTORS = "detectors"
    ASSESSORS = "assessors"
    SERVICES = "services"
    PROVIDERS = "providers"
    NOTIFIERS = "notifiers"
    VALIDATORS = "validators"
    TRANSFORMERS = "transformers"
    EXPORTERS = "exporters"
    INTEGRATORS = "integrators"
    RULES = "rules"
    CONFIGURATIONS = "configurations"
    METRICS = "metrics"
    TEMPLATES = "templates"
    WORKFLOWS = "workflows"


@dataclass
class RegistryEntry:
    """Registry entry for components."""
    name: str
    component_type: RegistryType
    component_class: Type
    instance: Optional[Any] = None
    configuration: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    registered_at: datetime = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    enabled: bool = True
    priority: int = 50
    
    def __post_init__(self):
        if self.registered_at is None:
            self.registered_at = timezone.now()
        if self.metadata is None:
            self.metadata = {}
        if self.configuration is None:
            self.configuration = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert registry entry to dictionary."""
        data = asdict(self)
        data['component_type'] = self.component_type.value
        if self.registered_at:
            data['registered_at'] = self.registered_at.isoformat()
        if self.last_accessed:
            data['last_accessed'] = self.last_accessed.isoformat()
        return data


class ComponentRegistry:
    """
    Central registry for fraud detection components.
    
    Provides registration, discovery, and management of
    fraud detection system components.
    """
    
    def __init__(self):
        """Initialize component registry."""
        self._entries: Dict[str, RegistryEntry] = {}
        self._type_index: Dict[RegistryType, List[str]] = {
            registry_type: [] for registry_type in RegistryType
        }
        self._lock = RLock()
        self._cache_timeout = getattr(settings, 'FRAUD_REGISTRY_CACHE_TIMEOUT', 300)
        self._max_entries = getattr(settings, 'FRAUD_REGISTRY_MAX_ENTRIES', 1000)
    
    def register(self, name: str, component_class: Type, 
                  component_type: RegistryType,
                  configuration: Optional[Dict[str, Any]] = None,
                  metadata: Optional[Dict[str, Any]] = None,
                  enabled: bool = True,
                  priority: int = 50) -> bool:
        """
        Register a component in the registry.
        
        Args:
            name: Component name
            component_class: Component class
            component_type: Type of component
            configuration: Component configuration
            metadata: Component metadata
            enabled: Whether component is enabled
            priority: Component priority
            
        Returns:
            True if registered successfully
        """
        with self._lock:
            try:
                # Check if already registered
                if name in self._entries:
                    logger.warning(f"Component {name} already registered, updating")
                
                # Check entry limit
                if len(self._entries) >= self._max_entries:
                    self._cleanup_old_entries()
                
                # Create registry entry
                entry = RegistryEntry(
                    name=name,
                    component_type=component_type,
                    component_class=component_class,
                    configuration=configuration,
                    metadata=metadata,
                    enabled=enabled,
                    priority=priority
                )
                
                # Add to registry
                self._entries[name] = entry
                
                # Update type index
                if name not in self._type_index[component_type]:
                    self._type_index[component_type].append(name)
                
                # Sort by priority
                self._type_index[component_type].sort(
                    key=lambda x: self._entries[x].priority,
                    reverse=True
                )
                
                logger.info(f"Registered component: {name} ({component_type.value})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register component {name}: {e}")
                return False
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a component from the registry.
        
        Args:
            name: Component name
            
        Returns:
            True if unregistered successfully
        """
        with self._lock:
            try:
                if name not in self._entries:
                    logger.warning(f"Component {name} not found in registry")
                    return False
                
                entry = self._entries[name]
                
                # Cleanup component instance
                if entry.instance:
                    try:
                        if hasattr(entry.instance, 'cleanup'):
                            entry.instance.cleanup()
                    except Exception as e:
                        logger.error(f"Error cleaning up component {name}: {e}")
                
                # Remove from registry
                del self._entries[name]
                
                # Update type index
                if name in self._type_index[entry.component_type]:
                    self._type_index[entry.component_type].remove(name)
                
                logger.info(f"Unregistered component: {name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to unregister component {name}: {e}")
                return False
    
    def get(self, name: str, create_instance: bool = True) -> Optional[Any]:
        """
        Get component instance by name.
        
        Args:
            name: Component name
            create_instance: Whether to create instance if not exists
            
        Returns:
            Component instance or None
        """
        with self._lock:
            try:
                if name not in self._entries:
                    return None
                
                entry = self._entries[name]
                
                if not entry.enabled:
                    return None
                
                # Update access statistics
                entry.last_accessed = timezone.now()
                entry.access_count += 1
                
                # Create instance if needed
                if create_instance and not entry.instance:
                    entry.instance = self._create_instance(entry)
                
                return entry.instance
                
            except Exception as e:
                logger.error(f"Failed to get component {name}: {e}")
                return None
    
    def get_class(self, name: str) -> Optional[Type]:
        """
        Get component class by name.
        
        Args:
            name: Component name
            
        Returns:
            Component class or None
        """
        with self._lock:
            if name in self._entries:
                return self._entries[name].component_class
            return None
    
    def get_by_type(self, component_type: RegistryType, 
                    enabled_only: bool = True) -> List[Any]:
        """
        Get all components of a specific type.
        
        Args:
            component_type: Component type
            enabled_only: Whether to return only enabled components
            
        Returns:
            List of component instances
        """
        components = []
        
        with self._lock:
            for name in self._type_index[component_type]:
                entry = self._entries.get(name)
                
                if entry and (not enabled_only or entry.enabled):
                    component = self.get(name)
                    if component:
                        components.append(component)
        
        return components
    
    def get_entry(self, name: str) -> Optional[RegistryEntry]:
        """
        Get registry entry by name.
        
        Args:
            name: Component name
            
        Returns:
            Registry entry or None
        """
        with self._lock:
            return self._entries.get(name)
    
    def list_components(self, component_type: Optional[RegistryType] = None,
                        enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        List components in the registry.
        
        Args:
            component_type: Filter by component type
            enabled_only: Filter by enabled status
            
        Returns:
            List of component information
        """
        components = []
        
        with self._lock:
            for name, entry in self._entries.items():
                if component_type and entry.component_type != component_type:
                    continue
                
                if enabled_only and not entry.enabled:
                    continue
                
                components.append(entry.to_dict())
        
        return components
    
    def enable_component(self, name: str) -> bool:
        """
        Enable a component.
        
        Args:
            name: Component name
            
        Returns:
            True if enabled successfully
        """
        with self._lock:
            if name in self._entries:
                self._entries[name].enabled = True
                logger.info(f"Enabled component: {name}")
                return True
            return False
    
    def disable_component(self, name: str) -> bool:
        """
        Disable a component.
        
        Args:
            name: Component name
            
        Returns:
            True if disabled successfully
        """
        with self._lock:
            if name in self._entries:
                self._entries[name].enabled = False
                logger.info(f"Disabled component: {name}")
                return True
            return False
    
    def update_configuration(self, name: str, 
                           configuration: Dict[str, Any]) -> bool:
        """
        Update component configuration.
        
        Args:
            name: Component name
            configuration: New configuration
            
        Returns:
            True if updated successfully
        """
        with self._lock:
            if name not in self._entries:
                return False
            
            entry = self._entries[name]
            entry.configuration.update(configuration)
            entry.metadata['updated_at'] = timezone.now().isoformat()
            
            # Recreate instance with new configuration
            if entry.instance:
                try:
                    if hasattr(entry.instance, 'cleanup'):
                        entry.instance.cleanup()
                    entry.instance = self._create_instance(entry)
                except Exception as e:
                    logger.error(f"Failed to recreate instance for {name}: {e}")
                    return False
            
            logger.info(f"Updated configuration for component: {name}")
            return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Registry statistics
        """
        with self._lock:
            stats = {
                'total_components': len(self._entries),
                'enabled_components': len([e for e in self._entries.values() if e.enabled]),
                'components_by_type': {},
                'most_accessed': [],
                'recently_registered': [],
                'total_accesses': sum(e.access_count for e in self._entries.values())
            }
            
            # Components by type
            for component_type in RegistryType:
                type_count = len(self._type_index[component_type])
                stats['components_by_type'][component_type.value] = type_count
            
            # Most accessed components
            sorted_by_access = sorted(
                self._entries.items(),
                key=lambda x: x[1].access_count,
                reverse=True
            )
            stats['most_accessed'] = [
                {'name': name, 'access_count': entry.access_count}
                for name, entry in sorted_by_access[:10]
            ]
            
            # Recently registered components
            sorted_by_registration = sorted(
                self._entries.items(),
                key=lambda x: x[1].registered_at,
                reverse=True
            )
            stats['recently_registered'] = [
                {'name': name, 'registered_at': entry.registered_at.isoformat()}
                for name, entry in sorted_by_registration[:10]
            ]
            
            return stats
    
    def cleanup(self) -> int:
        """
        Cleanup registry entries.
        
        Returns:
            Number of entries cleaned up
        """
        with self._lock:
            return self._cleanup_old_entries()
    
    def _create_instance(self, entry: RegistryEntry) -> Any:
        """Create component instance from entry."""
        try:
            # Create instance with configuration
            if entry.configuration:
                instance = entry.component_class(**entry.configuration)
            else:
                instance = entry.component_class()
            
            # Initialize if component has initialize method
            if hasattr(instance, 'initialize'):
                if not instance.initialize():
                    raise RegistryError(f"Failed to initialize component {entry.name}")
            
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create instance for {entry.name}: {e}")
            raise RegistryError(f"Instance creation failed: {e}")
    
    def _cleanup_old_entries(self) -> int:
        """Cleanup old registry entries."""
        cleaned_count = 0
        cutoff_time = timezone.now() - timedelta(days=30)
        
        # Remove entries not accessed in 30 days
        entries_to_remove = []
        
        for name, entry in self._entries.items():
            if (entry.last_accessed and entry.last_accessed < cutoff_time and
                not entry.metadata.get('persistent', False)):
                entries_to_remove.append(name)
        
        for name in entries_to_remove:
            self.unregister(name)
            cleaned_count += 1
        
        return cleaned_count


class ConfigurationRegistry:
    """
    Registry for system configurations.
    
    Manages configuration templates, defaults, and
    environment-specific settings.
    """
    
    def __init__(self):
        """Initialize configuration registry."""
        self._configurations: Dict[str, Dict[str, Any]] = {}
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._environments: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        
        # Load default configurations
        self._load_default_configurations()
    
    def register_configuration(self, name: str, configuration: Dict[str, Any],
                              environment: Optional[str] = None) -> bool:
        """
        Register a configuration.
        
        Args:
            name: Configuration name
            configuration: Configuration data
            environment: Environment (optional)
            
        Returns:
            True if registered successfully
        """
        with self._lock:
            try:
                if environment:
                    if environment not in self._environments:
                        self._environments[environment] = {}
                    self._environments[environment][name] = configuration
                else:
                    self._configurations[name] = configuration
                
                logger.info(f"Registered configuration: {name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register configuration {name}: {e}")
                return False
    
    def register_template(self, name: str, template: Dict[str, Any]) -> bool:
        """
        Register a configuration template.
        
        Args:
            name: Template name
            template: Template data
            
        Returns:
            True if registered successfully
        """
        with self._lock:
            try:
                self._templates[name] = template
                logger.info(f"Registered template: {name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register template {name}: {e}")
                return False
    
    def get_configuration(self, name: str, environment: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get configuration by name.
        
        Args:
            name: Configuration name
            environment: Environment (optional)
            
        Returns:
            Configuration data or None
        """
        with self._lock:
            # Check environment-specific configuration first
            if environment and environment in self._environments:
                if name in self._environments[environment]:
                    return self._environments[environment][name]
            
            # Check global configuration
            if name in self._configurations:
                return self._configurations[name]
            
            return None
    
    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration template by name.
        
        Args:
            name: Template name
            
        Returns:
            Template data or None
        """
        with self._lock:
            return self._templates.get(name)
    
    def create_from_template(self, template_name: str, config_name: str,
                           overrides: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create configuration from template.
        
        Args:
            template_name: Template name
            config_name: New configuration name
            overrides: Configuration overrides
            
        Returns:
            True if created successfully
        """
        template = self.get_template(template_name)
        if not template:
            logger.error(f"Template {template_name} not found")
            return False
        
        # Copy template and apply overrides
        configuration = template.copy()
        if overrides:
            configuration.update(overrides)
        
        return self.register_configuration(config_name, configuration)
    
    def list_configurations(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List configurations.
        
        Args:
            environment: Environment filter (optional)
            
        Returns:
            List of configuration information
        """
        with self._lock:
            configurations = []
            
            if environment and environment in self._environments:
                for name, config in self._environments[environment].items():
                    configurations.append({
                        'name': name,
                        'environment': environment,
                        'configuration': config
                    })
            else:
                for name, config in self._configurations.items():
                    configurations.append({
                        'name': name,
                        'environment': 'global',
                        'configuration': config
                    })
            
            return configurations
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """List configuration templates."""
        with self._lock:
            return [
                {'name': name, 'template': template}
                for name, template in self._templates.items()
            ]
    
    def _load_default_configurations(self):
        """Load default configurations."""
        # Default detector configurations
        self.register_configuration('rule_based_detector', {
            'enabled': True,
            'cache_timeout': 300,
            'max_rules': 1000,
            'default_priority': 50
        })
        
        self.register_configuration('statistical_detector', {
            'enabled': True,
            'anomaly_threshold': 2.0,
            'min_sample_size': 100,
            'cache_timeout': 600
        })
        
        self.register_configuration('risk_assessor', {
            'enabled': True,
            'baseline_period_days': 30,
            'update_frequency_hours': 24,
            'cache_timeout': 300
        })
        
        # Default notification configurations
        self.register_configuration('email_notifier', {
            'enabled': True,
            'smtp_host': 'localhost',
            'smtp_port': 587,
            'use_tls': True,
            'max_retries': 3
        })
        
        self.register_configuration('sms_notifier', {
            'enabled': False,
            'provider': 'twilio',
            'max_retries': 3,
            'rate_limit': 10
        })
        
        # Default templates
        self.register_template('detector_template', {
            'enabled': True,
            'cache_timeout': 300,
            'priority': 50,
            'configuration': {}
        })
        
        self.register_template('notifier_template', {
            'enabled': True,
            'max_retries': 3,
            'rate_limit': 100,
            'configuration': {}
        })


class MetricsRegistry:
    """
    Registry for system metrics and monitoring.
    
    Provides centralized metrics collection and
    performance monitoring.
    """
    
    def __init__(self):
        """Initialize metrics registry."""
        self._metrics: Dict[str, Any] = {}
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, List[float]] = {}
        self._lock = RLock()
    
    def increment_counter(self, name: str, value: int = 1) -> bool:
        """
        Increment a counter metric.
        
        Args:
            name: Counter name
            value: Increment value
            
        Returns:
            True if incremented successfully
        """
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value
            return True
    
    def set_gauge(self, name: str, value: float) -> bool:
        """
        Set a gauge metric.
        
        Args:
            name: Gauge name
            value: Gauge value
            
        Returns:
            True if set successfully
        """
        with self._lock:
            self._gauges[name] = value
            return True
    
    def record_timer(self, name: str, value: float) -> bool:
        """
        Record a timer metric.
        
        Args:
            name: Timer name
            value: Timer value in seconds
            
        Returns:
            True if recorded successfully
        """
        with self._lock:
            if name not in self._timers:
                self._timers[name] = []
            
            self._timers[name].append(value)
            
            # Keep only last 1000 values
            if len(self._timers[name]) > 1000:
                self._timers[name] = self._timers[name][-1000:]
            
            return True
    
    def get_counter(self, name: str) -> int:
        """
        Get counter value.
        
        Args:
            name: Counter name
            
        Returns:
            Counter value
        """
        with self._lock:
            return self._counters.get(name, 0)
    
    def get_gauge(self, name: str) -> Optional[float]:
        """
        Get gauge value.
        
        Args:
            name: Gauge name
            
        Returns:
            Gauge value or None
        """
        with self._lock:
            return self._gauges.get(name)
    
    def get_timer_stats(self, name: str) -> Optional[Dict[str, float]]:
        """
        Get timer statistics.
        
        Args:
            name: Timer name
            
        Returns:
            Timer statistics or None
        """
        with self._lock:
            if name not in self._timers:
                return None
            
            values = self._timers[name]
            
            if not values:
                return None
            
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'sum': sum(values)
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics.
        
        Returns:
            All metrics data
        """
        with self._lock:
            metrics = {
                'counters': self._counters.copy(),
                'gauges': self._gauges.copy(),
                'timers': {}
            }
            
            for name in self._timers:
                metrics['timers'][name] = self.get_timer_stats(name)
            
            return metrics
    
    def reset_metric(self, name: str) -> bool:
        """
        Reset a metric.
        
        Args:
            name: Metric name
            
        Returns:
            True if reset successfully
        """
        with self._lock:
            if name in self._counters:
                del self._counters[name]
            if name in self._gauges:
                del self._gauges[name]
            if name in self._timers:
                del self._timers[name]
            
            return True
    
    def reset_all_metrics(self) -> bool:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()
            return True


# Global registry instances
component_registry = ComponentRegistry()
configuration_registry = ConfigurationRegistry()
metrics_registry = MetricsRegistry()


# Registry management functions
def register_component(name: str, component_class: Type, 
                      component_type: RegistryType,
                      **kwargs) -> bool:
    """
    Register a component in the global registry.
    
    Args:
        name: Component name
        component_class: Component class
        component_type: Component type
        **kwargs: Additional registration parameters
        
    Returns:
        True if registered successfully
    """
    return component_registry.register(name, component_class, component_type, **kwargs)


def get_component(name: str, create_instance: bool = True) -> Optional[Any]:
    """
    Get component from global registry.
    
    Args:
        name: Component name
        create_instance: Whether to create instance
        
    Returns:
        Component instance or None
    """
    return component_registry.get(name, create_instance)


def get_components_by_type(component_type: RegistryType) -> List[Any]:
    """
    Get all components of a specific type.
    
    Args:
        component_type: Component type
        
    Returns:
        List of component instances
    """
    return component_registry.get_by_type(component_type)


def register_configuration(name: str, configuration: Dict[str, Any],
                        environment: Optional[str] = None) -> bool:
    """
    Register a configuration in the global registry.
    
    Args:
        name: Configuration name
        configuration: Configuration data
        environment: Environment (optional)
        
    Returns:
        True if registered successfully
    """
    return configuration_registry.register_configuration(name, configuration, environment)


def get_configuration(name: str, environment: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get configuration from global registry.
    
    Args:
        name: Configuration name
        environment: Environment (optional)
        
    Returns:
        Configuration data or None
    """
    return configuration_registry.get_configuration(name, environment)


# Metrics convenience functions
def increment_metric(name: str, value: int = 1) -> bool:
    """Increment a metric counter."""
    return metrics_registry.increment_counter(name, value)


def set_metric(name: str, value: float) -> bool:
    """Set a metric gauge."""
    return metrics_registry.set_gauge(name, value)


def record_timing(name: str, value: float) -> bool:
    """Record a timing metric."""
    return metrics_registry.record_timer(name, value)


def get_metric(name: str) -> Union[int, float, None]:
    """Get a metric value."""
    # Try counter first
    counter_value = metrics_registry.get_counter(name)
    if counter_value > 0:
        return counter_value
    
    # Try gauge
    gauge_value = metrics_registry.get_gauge(name)
    if gauge_value is not None:
        return gauge_value
    
    # Try timer
    timer_stats = metrics_registry.get_timer_stats(name)
    if timer_stats:
        return timer_stats['avg']
    
    return None


# Registry initialization and cleanup
def initialize_registries():
    """Initialize all registries."""
    try:
        logger.info("Initializing fraud detection registries")
        
        # Load configurations from settings
        load_configurations_from_settings()
        
        # Register built-in components
        register_builtin_components()
        
        logger.info("Fraud detection registries initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize registries: {e}")


def cleanup_registries():
    """Cleanup all registries."""
    try:
        logger.info("Cleaning up fraud detection registries")
        
        # Cleanup component registry
        component_registry.cleanup()
        
        # Reset metrics
        metrics_registry.reset_all_metrics()
        
        logger.info("Fraud detection registries cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Failed to cleanup registries: {e}")


def load_configurations_from_settings():
    """Load configurations from Django settings."""
    try:
        fraud_configs = getattr(settings, 'FRAUD_DETECTION_CONFIGURATIONS', {})
        
        for config_name, config_data in fraud_configs.items():
            environment = config_data.get('environment')
            configuration = config_data.get('configuration', {})
            
            configuration_registry.register_configuration(
                config_name, configuration, environment
            )
        
    except Exception as e:
        logger.error(f"Failed to load configurations from settings: {e}")


def register_builtin_components():
    """Register built-in components."""
    try:
        from api.fraud_detection.logic import (
            rule_based_detector, statistical_detector, risk_assessor, hybrid_detector
        )
        
        # Register detectors
        register_component(
            'rule_based_detector',
            type(rule_based_detector),
            RegistryType.DETECTORS,
            configuration={'enabled': True, 'cache_timeout': 300}
        )
        
        register_component(
            'statistical_detector',
            type(statistical_detector),
            RegistryType.DETECTORS,
            configuration={'enabled': True, 'anomaly_threshold': 2.0}
        )
        
        register_component(
            'hybrid_detector',
            type(hybrid_detector),
            RegistryType.DETECTORS,
            configuration={'enabled': True, 'weights': {'rule_based': 0.6, 'statistical': 0.4}}
        )
        
        # Register assessor
        register_component(
            'risk_assessor',
            type(risk_assessor),
            RegistryType.ASSESSORS,
            configuration={'enabled': True, 'baseline_period_days': 30}
        )
        
    except Exception as e:
        logger.error(f"Failed to register built-in components: {e}")


# Export registry instances and functions
__all__ = [
    # Enums and data classes
    'RegistryType',
    'RegistryEntry',
    
    # Registry classes
    'ComponentRegistry',
    'ConfigurationRegistry',
    'MetricsRegistry',
    
    # Global instances
    'component_registry',
    'configuration_registry',
    'metrics_registry',
    
    # Registry management functions
    'register_component',
    'get_component',
    'get_components_by_type',
    'register_configuration',
    'get_configuration',
    
    # Metrics functions
    'increment_metric',
    'set_metric',
    'record_timing',
    'get_metric',
    
    # Registry lifecycle
    'initialize_registries',
    'cleanup_registries',
]


def get_component_registry() -> ComponentRegistry:
    """Return the process-wide ComponentRegistry singleton."""
    return component_registry


def get_configuration_registry() -> ConfigurationRegistry:
    """Return the process-wide ConfigurationRegistry singleton."""
    return configuration_registry
