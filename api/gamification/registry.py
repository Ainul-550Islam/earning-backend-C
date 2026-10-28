"""
Gamification Registry — Registry system for gamification module.

This module provides a comprehensive registry system for managing gamification
components, services, and configurations.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union, Callable
from enum import Enum

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry Types
# ---------------------------------------------------------------------------

class RegistryType(Enum):
    """Types of registries."""
    SERVICE = "service"
    REPOSITORY = "repository"
    VALIDATOR = "validator"
    EVENT_HANDLER = "event_handler"
    PLUGIN = "plugin"
    RULE = "rule"
    CONFIGURATION = "configuration"
    STRATEGY = "strategy"
    FACTORY = "factory"
    BUILDER = "builder"


# ---------------------------------------------------------------------------
# Base Registry Classes
# ---------------------------------------------------------------------------

@dataclass
class RegistryEntry:
    """Entry in a registry."""
    
    name: str
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: timezone.now())
    enabled: bool = True
    priority: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            'name': self.name,
            'value': self.value,
            'metadata': self.metadata,
            'registered_at': self.registered_at.isoformat(),
            'enabled': self.enabled,
            'priority': self.priority
        }


class BaseRegistry(ABC):
    """Abstract base class for registries."""
    
    def __init__(self, registry_type: RegistryType):
        self.registry_type = registry_type
        self.entries: Dict[str, RegistryEntry] = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def register(self, name: str, value: Any, **kwargs: Any) -> None:
        """Register a value in the registry."""
        pass
    
    @abstractmethod
    def unregister(self, name: str) -> bool:
        """Unregister a value from the registry."""
        pass
    
    @abstractmethod
    def get(self, name: str) -> Optional[Any]:
        """Get a value from the registry."""
        pass
    
    def list_names(self) -> List[str]:
        """List all registered names."""
        return list(self.entries.keys())
    
    def list_enabled(self) -> List[str]:
        """List all enabled entries."""
        return [name for name, entry in self.entries.items() if entry.enabled]
    
    def enable(self, name: str) -> bool:
        """Enable an entry."""
        if name in self.entries:
            self.entries[name].enabled = True
            return True
        return False
    
    def disable(self, name: str) -> bool:
        """Disable an entry."""
        if name in self.entries:
            self.entries[name].enabled = False
            return True
        return False
    
    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()
        self.logger.info(f"Cleared {self.registry_type.value} registry")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            'type': self.registry_type.value,
            'total_entries': len(self.entries),
            'enabled_entries': len(self.list_enabled()),
            'disabled_entries': len(self.entries) - len(self.list_enabled())
        }


class DefaultRegistry(BaseRegistry):
    """Default implementation of a registry."""
    
    def register(self, name: str, value: Any, **kwargs: Any) -> None:
        """Register a value in the registry."""
        if name in self.entries:
            self.logger.warning(f"Overwriting existing entry: {name}")
        
        entry = RegistryEntry(
            name=name,
            value=value,
            metadata=kwargs.get('metadata', {}),
            enabled=kwargs.get('enabled', True),
            priority=kwargs.get('priority', 0)
        )
        
        self.entries[name] = entry
        self.logger.info(f"Registered {self.registry_type.value}: {name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a value from the registry."""
        if name in self.entries:
            del self.entries[name]
            self.logger.info(f"Unregistered {self.registry_type.value}: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[Any]:
        """Get a value from the registry."""
        entry = self.entries.get(name)
        if entry and entry.enabled:
            return entry.value
        return None


# ---------------------------------------------------------------------------
# Specialized Registries
# ---------------------------------------------------------------------------

class ServiceRegistry(DefaultRegistry):
    """Registry for gamification services."""
    
    def __init__(self):
        super().__init__(RegistryType.SERVICE)
    
    def register_service(self, name: str, service_class: Type, **kwargs: Any) -> None:
        """Register a service class."""
        self.register(name, service_class, **kwargs)
    
    def get_service(self, name: str) -> Optional[Type]:
        """Get a service class."""
        return self.get(name)
    
    def create_service(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a service."""
        service_class = self.get_service(name)
        if service_class:
            return service_class(**kwargs)
        return None


class RepositoryRegistry(DefaultRegistry):
    """Registry for repositories."""
    
    def __init__(self):
        super().__init__(RegistryType.REPOSITORY)
    
    def register_repository(self, name: str, repository_class: Type, **kwargs: Any) -> None:
        """Register a repository class."""
        self.register(name, repository_class, **kwargs)
    
    def get_repository(self, name: str) -> Optional[Type]:
        """Get a repository class."""
        return self.get(name)
    
    def create_repository(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a repository."""
        repository_class = self.get_repository(name)
        if repository_class:
            return repository_class(**kwargs)
        return None


class ValidatorRegistry(DefaultRegistry):
    """Registry for validators."""
    
    def __init__(self):
        super().__init__(RegistryType.VALIDATOR)
    
    def register_validator(self, name: str, validator_class: Type, **kwargs: Any) -> None:
        """Register a validator class."""
        self.register(name, validator_class, **kwargs)
    
    def get_validator(self, name: str) -> Optional[Type]:
        """Get a validator class."""
        return self.get(name)
    
    def create_validator(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a validator."""
        validator_class = self.get_validator(name)
        if validator_class:
            return validator_class(**kwargs)
        return None


class EventHandlerRegistry(DefaultRegistry):
    """Registry for event handlers."""
    
    def __init__(self):
        super().__init__(RegistryType.EVENT_HANDLER)
    
    def register_handler(self, name: str, handler_class: Type, **kwargs: Any) -> None:
        """Register an event handler class."""
        self.register(name, handler_class, **kwargs)
    
    def get_handler(self, name: str) -> Optional[Type]:
        """Get an event handler class."""
        return self.get(name)
    
    def create_handler(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of an event handler."""
        handler_class = self.get_handler(name)
        if handler_class:
            return handler_class(**kwargs)
        return None


class PluginRegistry(DefaultRegistry):
    """Registry for plugins."""
    
    def __init__(self):
        super().__init__(RegistryType.PLUGIN)
    
    def register_plugin(self, name: str, plugin_class: Type, **kwargs: Any) -> None:
        """Register a plugin class."""
        self.register(name, plugin_class, **kwargs)
    
    def get_plugin(self, name: str) -> Optional[Type]:
        """Get a plugin class."""
        return self.get(name)
    
    def create_plugin(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a plugin."""
        plugin_class = self.get_plugin(name)
        if plugin_class:
            return plugin_class(**kwargs)
        return None


class RuleRegistry(DefaultRegistry):
    """Registry for rules."""
    
    def __init__(self):
        super().__init__(RegistryType.RULE)
    
    def register_rule(self, name: str, rule: Any, **kwargs: Any) -> None:
        """Register a rule."""
        self.register(name, rule, **kwargs)
    
    def get_rule(self, name: str) -> Optional[Any]:
        """Get a rule."""
        return self.get(name)
    
    def get_rules_by_type(self, rule_type: str) -> List[Any]:
        """Get all rules of a specific type."""
        rules = []
        for entry in self.entries.values():
            if entry.enabled and hasattr(entry.value, 'rule_type'):
                if entry.value.rule_type.value == rule_type:
                    rules.append(entry.value)
        return rules


class ConfigurationRegistry(DefaultRegistry):
    """Registry for configurations."""
    
    def __init__(self):
        super().__init__(RegistryType.CONFIGURATION)
    
    def register_config(self, name: str, config: Dict[str, Any], **kwargs: Any) -> None:
        """Register a configuration."""
        self.register(name, config, **kwargs)
    
    def get_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a configuration."""
        return self.get(name)
    
    def get_config_value(self, name: str, key: str, default: Any = None) -> Any:
        """Get a specific value from a configuration."""
        config = self.get_config(name)
        if config:
            return config.get(key, default)
        return default
    
    def set_config_value(self, name: str, key: str, value: Any) -> None:
        """Set a specific value in a configuration."""
        config = self.get_config(name)
        if config:
            config[key] = value
        else:
            self.register_config(name, {key: value})


class StrategyRegistry(DefaultRegistry):
    """Registry for strategies."""
    
    def __init__(self):
        super().__init__(RegistryType.STRATEGY)
    
    def register_strategy(self, name: str, strategy_class: Type, **kwargs: Any) -> None:
        """Register a strategy class."""
        self.register(name, strategy_class, **kwargs)
    
    def get_strategy(self, name: str) -> Optional[Type]:
        """Get a strategy class."""
        return self.get(name)
    
    def create_strategy(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a strategy."""
        strategy_class = self.get_strategy(name)
        if strategy_class:
            return strategy_class(**kwargs)
        return None


class FactoryRegistry(DefaultRegistry):
    """Registry for factories."""
    
    def __init__(self):
        super().__init__(RegistryType.FACTORY)
    
    def register_factory(self, name: str, factory_class: Type, **kwargs: Any) -> None:
        """Register a factory class."""
        self.register(name, factory_class, **kwargs)
    
    def get_factory(self, name: str) -> Optional[Type]:
        """Get a factory class."""
        return self.get(name)
    
    def create_factory(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a factory."""
        factory_class = self.get_factory(name)
        if factory_class:
            return factory_class(**kwargs)
        return None


class BuilderRegistry(DefaultRegistry):
    """Registry for builders."""
    
    def __init__(self):
        super().__init__(RegistryType.BUILDER)
    
    def register_builder(self, name: str, builder_class: Type, **kwargs: Any) -> None:
        """Register a builder class."""
        self.register(name, builder_class, **kwargs)
    
    def get_builder(self, name: str) -> Optional[Type]:
        """Get a builder class."""
        return self.get(name)
    
    def create_builder(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a builder."""
        builder_class = self.get_builder(name)
        if builder_class:
            return builder_class(**kwargs)
        return None


# ---------------------------------------------------------------------------
# Registry Manager
# ---------------------------------------------------------------------------

class RegistryManager:
    """Manager for all registries."""
    
    def __init__(self):
        self.registries: Dict[RegistryType, BaseRegistry] = {}
        self.logger = logging.getLogger(__name__)
        self._initialize_registries()
    
    def _initialize_registries(self) -> None:
        """Initialize all registry types."""
        self.registries[RegistryType.SERVICE] = ServiceRegistry()
        self.registries[RegistryType.REPOSITORY] = RepositoryRegistry()
        self.registries[RegistryType.VALIDATOR] = ValidatorRegistry()
        self.registries[RegistryType.EVENT_HANDLER] = EventHandlerRegistry()
        self.registries[RegistryType.PLUGIN] = PluginRegistry()
        self.registries[RegistryType.RULE] = RuleRegistry()
        self.registries[RegistryType.CONFIGURATION] = ConfigurationRegistry()
        self.registries[RegistryType.STRATEGY] = StrategyRegistry()
        self.registries[RegistryType.FACTORY] = FactoryRegistry()
        self.registries[RegistryType.BUILDER] = BuilderRegistry()
        
        self.logger.info("Initialized all registries")
    
    def get_registry(self, registry_type: Union[RegistryType, str]) -> Optional[BaseRegistry]:
        """Get a registry by type."""
        if isinstance(registry_type, str):
            try:
                registry_type = RegistryType(registry_type)
            except ValueError:
                self.logger.error(f"Invalid registry type: {registry_type}")
                return None
        
        return self.registries.get(registry_type)
    
    def register(self, registry_type: Union[RegistryType, str], name: str, 
                value: Any, **kwargs: Any) -> None:
        """Register a value in a specific registry."""
        registry = self.get_registry(registry_type)
        if registry:
            registry.register(name, value, **kwargs)
        else:
            self.logger.error(f"Registry not found: {registry_type}")
    
    def unregister(self, registry_type: Union[RegistryType, str], name: str) -> bool:
        """Unregister a value from a specific registry."""
        registry = self.get_registry(registry_type)
        if registry:
            return registry.unregister(name)
        return False
    
    def get(self, registry_type: Union[RegistryType, str], name: str) -> Optional[Any]:
        """Get a value from a specific registry."""
        registry = self.get_registry(registry_type)
        if registry:
            return registry.get(name)
        return None
    
    def list_all_registries(self) -> Dict[str, Dict[str, Any]]:
        """List all registries and their stats."""
        result = {}
        
        for registry_type, registry in self.registries.items():
            result[registry_type.value] = registry.get_stats()
        
        return result
    
    def clear_all_registries(self) -> None:
        """Clear all registries."""
        for registry in self.registries.values():
            registry.clear()
        
        self.logger.info("Cleared all registries")
    
    def export_registry_data(self, registry_type: Union[RegistryType, str]) -> Dict[str, Any]:
        """Export registry data."""
        registry = self.get_registry(registry_type)
        if not registry:
            return {}
        
        data = {
            'type': registry.registry_type.value,
            'entries': {}
        }
        
        for name, entry in registry.entries.items():
            data['entries'][name] = entry.to_dict()
        
        return data
    
    def import_registry_data(self, registry_type: Union[RegistryType, str], 
                           data: Dict[str, Any]) -> bool:
        """Import registry data."""
        registry = self.get_registry(registry_type)
        if not registry:
            return False
        
        try:
            for name, entry_data in data.get('entries', {}).items():
                registry.register(
                    name=name,
                    value=entry_data['value'],
                    metadata=entry_data.get('metadata', {}),
                    enabled=entry_data.get('enabled', True),
                    priority=entry_data.get('priority', 0)
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing registry data: {e}")
            return False


# ---------------------------------------------------------------------------
# Registry Utilities
# ---------------------------------------------------------------------------

class RegistryUtils:
    """Utilities for registry operations."""
    
    @staticmethod
    def validate_registry_entry(entry: RegistryEntry) -> List[str]:
        """Validate a registry entry."""
        errors = []
        
        if not entry.name:
            errors.append("Entry name is required")
        
        if entry.value is None:
            errors.append("Entry value is required")
        
        if entry.priority < 0:
            errors.append("Priority cannot be negative")
        
        return errors
    
    @staticmethod
    def search_registries(manager: RegistryManager, query: str) -> Dict[str, List[str]]:
        """Search registries for entries matching a query."""
        results = {}
        query_lower = query.lower()
        
        for registry_type, registry in manager.registries.items():
            matches = []
            
            for name, entry in registry.entries.items():
                if (query_lower in name.lower() or 
                    (isinstance(entry.value, str) and query_lower in entry.value.lower())):
                    matches.append(name)
            
            if matches:
                results[registry_type.value] = matches
        
        return results
    
    @staticmethod
    def backup_registries(manager: RegistryManager) -> Dict[str, Any]:
        """Backup all registries."""
        backup = {
            'timestamp': timezone.now().isoformat(),
            'registries': {}
        }
        
        for registry_type in RegistryType:
            backup['registries'][registry_type.value] = manager.export_registry_data(registry_type)
        
        return backup
    
    @staticmethod
    def restore_registries(manager: RegistryManager, backup: Dict[str, Any]) -> bool:
        """Restore registries from backup."""
        try:
            manager.clear_all_registries()
            
            for registry_name, registry_data in backup.get('registries', {}).items():
                manager.import_registry_data(registry_name, registry_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error restoring registries: {e}")
            return False


# ---------------------------------------------------------------------------
# Registry Cache
# ---------------------------------------------------------------------------

class RegistryCache:
    """Cache for registry data."""
    
    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached registry data."""
        return cache.get(f"registry:{key}")
    
    def set(self, key: str, data: Any) -> None:
        """Set cached registry data."""
        cache.set(f"registry:{key}", data, timeout=self.timeout)
    
    def delete(self, key: str) -> bool:
        """Delete cached registry data."""
        return cache.delete(f"registry:{key}")
    
    def clear(self) -> None:
        """Clear all registry cache."""
        # This would need to be implemented based on your cache backend
        cache.delete_many([f"registry:{key}" for key in cache.keys("registry:*")])
        self.logger.info("Cleared registry cache")


# ---------------------------------------------------------------------------
# Registry Decorators
# ---------------------------------------------------------------------------

def register_in_registry(registry_type: Union[RegistryType, str], name: Optional[str] = None, **kwargs: Any):
    """Decorator to register a class in a registry."""
    def decorator(cls):
        registry_name = name or cls.__name__
        registry_manager.register(registry_type, registry_name, cls, **kwargs)
        return cls
    return decorator


def auto_register_service(name: Optional[str] = None, **kwargs: Any):
    """Decorator to automatically register a service."""
    return register_in_registry(RegistryType.SERVICE, name, **kwargs)


def auto_register_repository(name: Optional[str] = None, **kwargs: Any):
    """Decorator to automatically register a repository."""
    return register_in_registry(RegistryType.REPOSITORY, name, **kwargs)


def auto_register_validator(name: Optional[str] = None, **kwargs: Any):
    """Decorator to automatically register a validator."""
    return register_in_registry(RegistryType.VALIDATOR, name, **kwargs)


# ---------------------------------------------------------------------------
# Global Registry Manager
# ---------------------------------------------------------------------------

registry_manager = RegistryManager()
registry_cache = RegistryCache()
registry_utils = RegistryUtils()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def register_service(name: str, service_class: Type, **kwargs: Any) -> None:
    """Register a service."""
    registry_manager.register(RegistryType.SERVICE, name, service_class, **kwargs)


def register_repository(name: str, repository_class: Type, **kwargs: Any) -> None:
    """Register a repository."""
    registry_manager.register(RegistryType.REPOSITORY, name, repository_class, **kwargs)


def register_validator(name: str, validator_class: Type, **kwargs: Any) -> None:
    """Register a validator."""
    registry_manager.register(RegistryType.VALIDATOR, name, validator_class, **kwargs)


def register_plugin(name: str, plugin_class: Type, **kwargs: Any) -> None:
    """Register a plugin."""
    registry_manager.register(RegistryType.PLUGIN, name, plugin_class, **kwargs)


def get_service(name: str) -> Optional[Type]:
    """Get a service class."""
    return registry_manager.get(RegistryType.SERVICE, name)


def get_repository(name: str) -> Optional[Type]:
    """Get a repository class."""
    return registry_manager.get(RegistryType.REPOSITORY, name)


def get_validator(name: str) -> Optional[Type]:
    """Get a validator class."""
    return registry_manager.get(RegistryType.VALIDATOR, name)


def get_plugin(name: str) -> Optional[Type]:
    """Get a plugin class."""
    return registry_manager.get(RegistryType.PLUGIN, name)


# Initialize logging
logger.info("Gamification registry module initialized")
