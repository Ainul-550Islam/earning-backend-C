"""
api/ad_networks/registry.py
Registry system for ad networks module
SaaS-ready with tenant support
"""

import logging
from typing import Dict, List, Any, Optional, Type, Callable
from datetime import datetime, timedelta
from enum import Enum

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class RegistryType(Enum):
    """Registry types"""
    
    NETWORK_CLIENTS = "network_clients"
    OFFER_PROCESSORS = "offer_processors"
    FRAUD_DETECTORS = "fraud_detectors"
    REWARD_CALCULATORS = "reward_calculators"
    NOTIFICATION_SENDERS = "notification_senders"
    ANALYTICS_PROCESSORS = "analytics_processors"
    EXPORT_HANDLERS = "export_handlers"
    WEBHOOK_HANDLERS = "webhook_handlers"
    CACHE_MANAGERS = "cache_managers"
    VALIDATORS = "validators"
    MIDDLEWARE = "middleware"
    TASKS = "tasks"
    PLUGINS = "plugins"


class Registry:
    """Generic registry for managing components"""
    
    def __init__(self, registry_type: RegistryType):
        self.registry_type = registry_type
        self._registry: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._dependencies: Dict[str, List[str]] = {}
        self._initialized: Dict[str, bool] = {}
        self._load_order: List[str] = []
    
    def register(self, name: str, component: Any, 
                metadata: Dict[str, Any] = None,
                dependencies: List[str] = None) -> bool:
        """Register a component"""
        try:
            if name in self._registry:
                logger.warning(f"Component {name} already registered in {self.registry_type.value}")
                return False
            
            self._registry[name] = component
            self._metadata[name] = metadata or {}
            self._dependencies[name] = dependencies or []
            self._initialized[name] = False
            
            # Update load order
            self._update_load_order()
            
            logger.info(f"Registered component {name} in {self.registry_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering component {name}: {str(e)}")
            return False
    
    def unregister(self, name: str) -> bool:
        """Unregister a component"""
        try:
            if name not in self._registry:
                logger.warning(f"Component {name} not found in {self.registry_type.value}")
                return False
            
            # Check dependencies
            dependents = self._get_dependents(name)
            if dependents:
                logger.error(f"Cannot unregister {name}: has dependents {dependents}")
                return False
            
            # Remove from registry
            del self._registry[name]
            del self._metadata[name]
            del self._dependencies[name]
            del self._initialized[name]
            
            # Update load order
            self._update_load_order()
            
            logger.info(f"Unregistered component {name} from {self.registry_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering component {name}: {str(e)}")
            return False
    
    def get(self, name: str) -> Any:
        """Get a component"""
        return self._registry.get(name)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all components"""
        return self._registry.copy()
    
    def get_metadata(self, name: str) -> Dict[str, Any]:
        """Get component metadata"""
        return self._metadata.get(name, {})
    
    def get_dependencies(self, name: str) -> List[str]:
        """Get component dependencies"""
        return self._dependencies.get(name, [])
    
    def is_registered(self, name: str) -> bool:
        """Check if component is registered"""
        return name in self._registry
    
    def is_initialized(self, name: str) -> bool:
        """Check if component is initialized"""
        return self._initialized.get(name, False)
    
    def initialize(self, name: str, config: Dict[str, Any] = None) -> bool:
        """Initialize a component"""
        try:
            if name not in self._registry:
                logger.error(f"Component {name} not found in {self.registry_type.value}")
                return False
            
            if self._initialized[name]:
                logger.info(f"Component {name} already initialized")
                return True
            
            # Check dependencies
            dependencies = self._dependencies[name]
            for dep in dependencies:
                if not self.is_initialized(dep):
                    if not self.initialize(dep, config):
                        logger.error(f"Failed to initialize dependency {dep} for {name}")
                        return False
            
            component = self._registry[name]
            
            # Initialize component
            if hasattr(component, 'initialize'):
                success = component.initialize(config or {})
                if not success:
                    logger.error(f"Failed to initialize component {name}")
                    return False
            
            self._initialized[name] = True
            logger.info(f"Initialized component {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing component {name}: {str(e)}")
            return False
    
    def initialize_all(self, config: Dict[str, Any] = None) -> Dict[str, bool]:
        """Initialize all components in dependency order"""
        results = {}
        
        for name in self._load_order:
            results[name] = self.initialize(name, config)
        
        return results
    
    def _get_dependents(self, name: str) -> List[str]:
        """Get components that depend on this component"""
        dependents = []
        
        for comp_name, deps in self._dependencies.items():
            if name in deps:
                dependents.append(comp_name)
        
        return dependents
    
    def _update_load_order(self):
        """Update load order based on dependencies"""
        try:
            # Topological sort
            visited = set()
            temp_visited = set()
            order = []
            
            def visit(name: str):
                if name in temp_visited:
                    raise ValueError(f"Circular dependency detected involving {name}")
                
                if name in visited:
                    return
                
                temp_visited.add(name)
                
                for dep in self._dependencies.get(name, []):
                    visit(dep)
                
                temp_visited.remove(name)
                visited.add(name)
                order.append(name)
            
            for name in self._registry:
                if name not in visited:
                    visit(name)
            
            self._load_order = order
            
        except Exception as e:
            logger.error(f"Error updating load order: {str(e)}")
            self._load_order = list(self._registry.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            'registry_type': self.registry_type.value,
            'total_components': len(self._registry),
            'initialized_components': sum(1 for v in self._initialized.values() if v),
            'load_order': self._load_order,
            'components': list(self._registry.keys())
        }


class RegistryManager:
    """Manager for all registries"""
    
    def __init__(self):
        self._registries: Dict[RegistryType, Registry] = {}
        self._global_config = {}
        
        # Initialize registries
        for registry_type in RegistryType:
            self._registries[registry_type] = Registry(registry_type)
    
    def get_registry(self, registry_type: RegistryType) -> Registry:
        """Get a specific registry"""
        return self._registries[registry_type]
    
    def register(self, registry_type: RegistryType, name: str, 
                component: Any, metadata: Dict[str, Any] = None,
                dependencies: List[str] = None) -> bool:
        """Register a component in a specific registry"""
        return self._registries[registry_type].register(
            name, component, metadata, dependencies
        )
    
    def unregister(self, registry_type: RegistryType, name: str) -> bool:
        """Unregister a component from a specific registry"""
        return self._registries[registry_type].unregister(name)
    
    def get(self, registry_type: RegistryType, name: str) -> Any:
        """Get a component from a specific registry"""
        return self._registries[registry_type].get(name)
    
    def initialize_all(self, config: Dict[str, Any] = None) -> Dict[str, Dict[str, bool]]:
        """Initialize all registries"""
        self._global_config = config or {}
        results = {}
        
        for registry_type, registry in self._registries.items():
            results[registry_type.value] = registry.initialize_all(config)
        
        return results
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all registries"""
        stats = {}
        
        for registry_type, registry in self._registries.items():
            stats[registry_type.value] = registry.get_stats()
        
        return stats
    
    def clear_all(self):
        """Clear all registries"""
        for registry in self._registries.values():
            registry._registry.clear()
            registry._metadata.clear()
            registry._dependencies.clear()
            registry._initialized.clear()
            registry._load_order.clear()


# Global registry manager instance
registry_manager = RegistryManager()


# Decorators for easy registration
def register_network_client(name: str, metadata: Dict[str, Any] = None,
                          dependencies: List[str] = None):
    """Decorator to register a network client"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.NETWORK_CLIENTS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_offer_processor(name: str, metadata: Dict[str, Any] = None,
                           dependencies: List[str] = None):
    """Decorator to register an offer processor"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.OFFER_PROCESSORS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_fraud_detector(name: str, metadata: Dict[str, Any] = None,
                          dependencies: List[str] = None):
    """Decorator to register a fraud detector"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.FRAUD_DETECTORS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_reward_calculator(name: str, metadata: Dict[str, Any] = None,
                            dependencies: List[str] = None):
    """Decorator to register a reward calculator"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.REWARD_CALCULATORS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_notification_sender(name: str, metadata: Dict[str, Any] = None,
                             dependencies: List[str] = None):
    """Decorator to register a notification sender"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.NOTIFICATION_SENDERS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_analytics_processor(name: str, metadata: Dict[str, Any] = None,
                              dependencies: List[str] = None):
    """Decorator to register an analytics processor"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.ANALYTICS_PROCESSORS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_export_handler(name: str, metadata: Dict[str, Any] = None,
                         dependencies: List[str] = None):
    """Decorator to register an export handler"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.EXPORT_HANDLERS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_webhook_handler(name: str, metadata: Dict[str, Any] = None,
                           dependencies: List[str] = None):
    """Decorator to register a webhook handler"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.WEBHOOK_HANDLERS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_cache_manager(name: str, metadata: Dict[str, Any] = None,
                        dependencies: List[str] = None):
    """Decorator to register a cache manager"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.CACHE_MANAGERS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_validator(name: str, metadata: Dict[str, Any] = None,
                     dependencies: List[str] = None):
    """Decorator to register a validator"""
    def decorator(func):
        registry_manager.register(
            RegistryType.VALIDATORS,
            name,
            func,
            metadata,
            dependencies
        )
        return func
    return decorator


def register_middleware(name: str, metadata: Dict[str, Any] = None,
                      dependencies: List[str] = None):
    """Decorator to register middleware"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.MIDDLEWARE,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


def register_task(name: str, metadata: Dict[str, Any] = None,
                 dependencies: List[str] = None):
    """Decorator to register a task"""
    def decorator(func):
        registry_manager.register(
            RegistryType.TASKS,
            name,
            func,
            metadata,
            dependencies
        )
        return func
    return decorator


def register_plugin(name: str, metadata: Dict[str, Any] = None,
                  dependencies: List[str] = None):
    """Decorator to register a plugin"""
    def decorator(cls):
        registry_manager.register(
            RegistryType.PLUGINS,
            name,
            cls,
            metadata,
            dependencies
        )
        return cls
    return decorator


# Helper functions
def get_network_client(name: str):
    """Get a network client"""
    return registry_manager.get(RegistryType.NETWORK_CLIENTS, name)


def get_offer_processor(name: str):
    """Get an offer processor"""
    return registry_manager.get(RegistryType.OFFER_PROCESSORS, name)


def get_fraud_detector(name: str):
    """Get a fraud detector"""
    return registry_manager.get(RegistryType.FRAUD_DETECTORS, name)


def get_reward_calculator(name: str):
    """Get a reward calculator"""
    return registry_manager.get(RegistryType.REWARD_CALCULATORS, name)


def get_notification_sender(name: str):
    """Get a notification sender"""
    return registry_manager.get(RegistryType.NOTIFICATION_SENDERS, name)


def get_analytics_processor(name: str):
    """Get an analytics processor"""
    return registry_manager.get(RegistryType.ANALYTICS_PROCESSORS, name)


def get_export_handler(name: str):
    """Get an export handler"""
    return registry_manager.get(RegistryType.EXPORT_HANDLERS, name)


def get_webhook_handler(name: str):
    """Get a webhook handler"""
    return registry_manager.get(RegistryType.WEBHOOK_HANDLERS, name)


def get_cache_manager(name: str):
    """Get a cache manager"""
    return registry_manager.get(RegistryType.CACHE_MANAGERS, name)


def get_validator(name: str):
    """Get a validator"""
    return registry_manager.get(RegistryType.VALIDATORS, name)


def get_middleware(name: str):
    """Get middleware"""
    return registry_manager.get(RegistryType.MIDDLEWARE, name)


def get_task(name: str):
    """Get a task"""
    return registry_manager.get(RegistryType.TASKS, name)


def get_plugin(name: str):
    """Get a plugin"""
    return registry_manager.get(RegistryType.PLUGINS, name)


# Auto-discovery and registration
def auto_register_components():
    """Auto-discover and register components"""
    try:
        # This would scan for components and auto-register them
        # For now, just log
        logger.info("Auto-registering ad networks components")
        
        # Example: Register built-in components
        from .abstracts import (
            AbstractNetworkClient, AbstractOfferProcessor,
            AbstractFraudDetector, AbstractRewardCalculator
        )
        
        # Register built-in implementations
        # This would be expanded with actual implementations
        
    except Exception as e:
        logger.error(f"Error auto-registering components: {str(e)}")


# Registry initialization
def initialize_registries(config: Dict[str, Any] = None):
    """Initialize all registries"""
    try:
        # Auto-register components
        auto_register_components()
        
        # Initialize all registries
        results = registry_manager.initialize_all(config)
        
        # Log results
        for registry_type, init_results in results.items():
            success_count = sum(1 for v in init_results.values() if v)
            total_count = len(init_results)
            logger.info(f"Registry {registry_type}: {success_count}/{total_count} components initialized")
        
        return results
        
    except Exception as e:
        logger.error(f"Error initializing registries: {str(e)}")
        return {}


# Registry monitoring
def get_registry_health() -> Dict[str, Any]:
    """Get registry health status"""
    try:
        stats = registry_manager.get_all_stats()
        
        health_status = {
            'overall_status': 'healthy',
            'registries': {},
            'timestamp': timezone.now().isoformat()
        }
        
        for registry_name, registry_stats in stats.items():
            initialized_ratio = registry_stats['initialized_components'] / registry_stats['total_components']
            
            if initialized_ratio < 0.8:
                health_status['overall_status'] = 'degraded'
            elif initialized_ratio < 0.5:
                health_status['overall_status'] = 'unhealthy'
            
            health_status['registries'][registry_name] = {
                'status': 'healthy' if initialized_ratio >= 0.8 else 'degraded',
                'total_components': registry_stats['total_components'],
                'initialized_components': registry_stats['initialized_components'],
                'initialization_ratio': round(initialized_ratio * 100, 2)
            }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting registry health: {str(e)}")
        return {
            'overall_status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


# Export registry components
__all__ = [
    # Enums
    'RegistryType',
    
    # Classes
    'Registry',
    'RegistryManager',
    
    # Global instance
    'registry_manager',
    
    # Decorators
    'register_network_client',
    'register_offer_processor',
    'register_fraud_detector',
    'register_reward_calculator',
    'register_notification_sender',
    'register_analytics_processor',
    'register_export_handler',
    'register_webhook_handler',
    'register_cache_manager',
    'register_validator',
    'register_middleware',
    'register_task',
    'register_plugin',
    
    # Helper functions
    'get_network_client',
    'get_offer_processor',
    'get_fraud_detector',
    'get_reward_calculator',
    'get_notification_sender',
    'get_analytics_processor',
    'get_export_handler',
    'get_webhook_handler',
    'get_cache_manager',
    'get_validator',
    'get_middleware',
    'get_task',
    'get_plugin',
    
    # Registry management
    'auto_register_components',
    'initialize_registries',
    'get_registry_health'
]
