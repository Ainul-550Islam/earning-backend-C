"""
Security Registry Module
Central registry for security components and configurations
"""
from django.utils import timezone

import logging
from typing import Dict, List, Any, Optional, Callable, Type
from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import autodiscover_modules
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger('security.registry')


class ComponentType(Enum):
    """Security component types"""
    AUTHENTICATOR = 'authenticator'
    AUTHORIZER = 'authorizer'
    VALIDATOR = 'validator'
    ENCRYPTOR = 'encryptor'
    AUDITOR = 'auditor'
    MONITOR = 'monitor'
    NOTIFIER = 'notifier'
    FILTER = 'filter'
    MIDDLEWARE = 'middleware'
    THROTTLER = 'throttler'
    CACHE = 'cache'
    WEBHOOK = 'webhook'
    ANALYZER = 'analyzer'
    REPORTER = 'reporter'
    EXPORTER = 'exporter'
    IMPORTER = 'importer'
    PROCESSOR = 'processor'
    TRANSFORMER = 'transformer'
    HANDLER = 'handler'
    SERVICE = 'service'
    REPOSITORY = 'repository'
    USE_CASE = 'use_case'
    SELECTOR = 'selector'
    INTERACTOR = 'interactor'


@dataclass
class ComponentRegistration:
    """Component registration data"""
    name: str
    component_type: ComponentType
    component_class: Type
    priority: int = 100
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = '1.0.0'
    author: str = 'Security Team'
    description: str = ''
    
    def __post_init__(self):
        """Validate registration data"""
        if not self.name:
            raise ValueError("Component name cannot be empty")
        if not self.component_type:
            raise ValueError("Component type is required")
        if not self.component_class:
            raise ValueError("Component class is required")


class SecurityRegistry:
    """Central registry for security components"""
    
    def __init__(self):
        self._components: Dict[str, ComponentRegistration] = {}
        self._type_index: Dict[ComponentType, List[ComponentRegistration]] = {}
        self._priority_index: Dict[int, List[ComponentRegistration]] = {}
        self._dependency_graph: Dict[str, List[str]] = {}
        self._enabled_components: Dict[str, ComponentRegistration] = {}
        self._cache_key = 'security_registry_components'
        self._cache_timeout = 3600  # 1 hour
        
    def register(self, registration: ComponentRegistration) -> None:
        """Register a security component"""
        try:
            # Validate registration
            if registration.name in self._components:
                logger.warning(f"Component {registration.name} already registered, updating...")
            
            # Add to main registry
            self._components[registration.name] = registration
            
            # Update type index
            if registration.component_type not in self._type_index:
                self._type_index[registration.component_type] = []
            self._type_index[registration.component_type].append(registration)
            
            # Update priority index
            if registration.priority not in self._priority_index:
                self._priority_index[registration.priority] = []
            self._priority_index[registration.priority].append(registration)
            
            # Update dependency graph
            self._dependency_graph[registration.name] = registration.dependencies
            
            # Update enabled components
            if registration.enabled:
                self._enabled_components[registration.name] = registration
            
            # Clear cache
            cache.delete(self._cache_key)
            
            logger.info(f"Registered component: {registration.name} ({registration.component_type.value})")
            
        except Exception as e:
            logger.error(f"Failed to register component {registration.name}: {e}")
            raise
    
    def unregister(self, name: str) -> bool:
        """Unregister a security component"""
        try:
            if name not in self._components:
                logger.warning(f"Component {name} not found in registry")
                return False
            
            registration = self._components[name]
            
            # Remove from main registry
            del self._components[name]
            
            # Remove from type index
            if registration.component_type in self._type_index:
                self._type_index[registration.component_type] = [
                    comp for comp in self._type_index[registration.component_type]
                    if comp.name != name
                ]
            
            # Remove from priority index
            if registration.priority in self._priority_index:
                self._priority_index[registration.priority] = [
                    comp for comp in self._priority_index[registration.priority]
                    if comp.name != name
                ]
            
            # Remove from dependency graph
            if name in self._dependency_graph:
                del self._dependency_graph[name]
            
            # Remove from enabled components
            if name in self._enabled_components:
                del self._enabled_components[name]
            
            # Clear cache
            cache.delete(self._cache_key)
            
            logger.info(f"Unregistered component: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister component {name}: {e}")
            return False
    
    def get_component(self, name: str) -> Optional[ComponentRegistration]:
        """Get a component by name"""
        return self._components.get(name)
    
    def get_components_by_type(self, component_type: ComponentType) -> List[ComponentRegistration]:
        """Get all components of a specific type"""
        return self._type_index.get(component_type, [])
    
    def get_components_by_priority(self, priority: int) -> List[ComponentRegistration]:
        """Get all components with a specific priority"""
        return self._priority_index.get(priority, [])
    
    def get_enabled_components(self) -> Dict[str, ComponentRegistration]:
        """Get all enabled components"""
        return self._enabled_components.copy()
    
    def get_component_class(self, name: str) -> Optional[Type]:
        """Get component class by name"""
        registration = self._components.get(name)
        return registration.component_class if registration else None
    
    def is_component_enabled(self, name: str) -> bool:
        """Check if a component is enabled"""
        registration = self._components.get(name)
        return registration.enabled if registration else False
    
    def enable_component(self, name: str) -> bool:
        """Enable a component"""
        registration = self._components.get(name)
        if registration:
            registration.enabled = True
            self._enabled_components[name] = registration
            cache.delete(self._cache_key)
            logger.info(f"Enabled component: {name}")
            return True
        return False
    
    def disable_component(self, name: str) -> bool:
        """Disable a component"""
        registration = self._components.get(name)
        if registration:
            registration.enabled = False
            if name in self._enabled_components:
                del self._enabled_components[name]
            cache.delete(self._cache_key)
            logger.info(f"Disabled component: {name}")
            return True
        return False
    
    def get_dependencies(self, name: str) -> List[str]:
        """Get component dependencies"""
        return self._dependency_graph.get(name, [])
    
    def resolve_dependencies(self, name: str) -> List[str]:
        """Resolve all dependencies for a component (topological sort)"""
        visited = set()
        recursion_stack = set()
        result = []
        
        def dfs(component_name: str):
            if component_name in recursion_stack:
                raise ValueError(f"Circular dependency detected: {component_name}")
            if component_name in visited:
                return
            
            recursion_stack.add(component_name)
            visited.add(component_name)
            
            for dependency in self._dependency_graph.get(component_name, []):
                dfs(dependency)
            
            recursion_stack.remove(component_name)
            result.append(component_name)
        
        dfs(name)
        return result
    
    def validate_dependencies(self) -> Dict[str, List[str]]:
        """Validate all component dependencies"""
        errors = {}
        
        for name, dependencies in self._dependency_graph.items():
            missing_deps = []
            for dep in dependencies:
                if dep not in self._components:
                    missing_deps.append(dep)
            
            if missing_deps:
                errors[name] = missing_deps
        
        return errors
    
    def get_component_statistics(self) -> Dict[str, Any]:
        """Get registry statistics"""
        stats = {
            'total_components': len(self._components),
            'enabled_components': len(self._enabled_components),
            'disabled_components': len(self._components) - len(self._enabled_components),
            'components_by_type': {},
            'components_by_priority': {},
            'dependency_errors': self.validate_dependencies()
        }
        
        # Count by type
        for component_type, components in self._type_index.items():
            stats['components_by_type'][component_type.value] = len(components)
        
        # Count by priority
        for priority, components in self._priority_index.items():
            stats['components_by_priority'][priority] = len(components)
        
        return stats
    
    def export_registry(self) -> Dict[str, Any]:
        """Export registry data"""
        export_data = {
            'components': {},
            'statistics': self.get_component_statistics(),
            'exported_at': timezone.now().isoformat()
        }
        
        for name, registration in self._components.items():
            export_data['components'][name] = {
                'name': registration.name,
                'component_type': registration.component_type.value,
                'priority': registration.priority,
                'enabled': registration.enabled,
                'config': registration.config,
                'dependencies': registration.dependencies,
                'metadata': registration.metadata,
                'version': registration.version,
                'author': registration.author,
                'description': registration.description
            }
        
        return export_data
    
    def import_registry(self, data: Dict[str, Any], overwrite: bool = False) -> Dict[str, bool]:
        """Import registry data"""
        results = {}
        
        for name, component_data in data.get('components', {}).items():
            try:
                if name in self._components and not overwrite:
                    results[name] = False
                    continue
                
                # Convert component type back to enum
                component_type = ComponentType(component_data['component_type'])
                
                # Create registration
                registration = ComponentRegistration(
                    name=component_data['name'],
                    component_type=component_type,
                    component_class=self._components.get(name, {}).component_class if name in self._components else object,
                    priority=component_data.get('priority', 100),
                    enabled=component_data.get('enabled', True),
                    config=component_data.get('config', {}),
                    dependencies=component_data.get('dependencies', []),
                    metadata=component_data.get('metadata', {}),
                    version=component_data.get('version', '1.0.0'),
                    author=component_data.get('author', 'Security Team'),
                    description=component_data.get('description', '')
                )
                
                self.register(registration)
                results[name] = True
                
            except Exception as e:
                logger.error(f"Failed to import component {name}: {e}")
                results[name] = False
        
        return results
    
    def auto_discover_components(self) -> None:
        """Auto-discover security components from installed apps"""
        try:
            autodiscover_modules('security_components')
            logger.info("Auto-discovery completed for security components")
        except Exception as e:
            logger.error(f"Auto-discovery failed: {e}")
    
    def clear_cache(self) -> None:
        """Clear registry cache"""
        cache.delete(self._cache_key)
    
    def reload_from_cache(self) -> bool:
        """Reload registry from cache"""
        try:
            cached_data = cache.get(self._cache_key)
            if cached_data:
                self._components = cached_data['_components']
                self._type_index = cached_data['_type_index']
                self._priority_index = cached_data['_priority_index']
                self._dependency_graph = cached_data['_dependency_graph']
                self._enabled_components = cached_data['_enabled_components']
                logger.info("Registry reloaded from cache")
                return True
        except Exception as e:
            logger.error(f"Failed to reload from cache: {e}")
        
        return False
    
    def save_to_cache(self) -> bool:
        """Save registry to cache"""
        try:
            cache_data = {
                '_components': self._components,
                '_type_index': self._type_index,
                '_priority_index': self._priority_index,
                '_dependency_graph': self._dependency_graph,
                '_enabled_components': self._enabled_components
            }
            cache.set(self._cache_key, cache_data, self._cache_timeout)
            logger.info("Registry saved to cache")
            return True
        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")
            return False


# Global registry instance
security_registry = SecurityRegistry()


# Decorator for component registration
def register_component(
    name: str,
    component_type: ComponentType,
    priority: int = 100,
    enabled: bool = True,
    config: Optional[Dict[str, Any]] = None,
    dependencies: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    version: str = '1.0.0',
    author: str = 'Security Team',
    description: str = ''
):
    """Decorator for registering security components"""
    def decorator(component_class: Type) -> Type:
        registration = ComponentRegistration(
            name=name,
            component_type=component_type,
            component_class=component_class,
            priority=priority,
            enabled=enabled,
            config=config or {},
            dependencies=dependencies or [],
            metadata=metadata or {},
            version=version,
            author=author,
            description=description
        )
        
        security_registry.register(registration)
        return component_class
    
    return decorator


# Component loader utilities
class ComponentLoader:
    """Utilities for loading and managing components"""
    
    @staticmethod
    def load_component(name: str, **kwargs) -> Any:
        """Load and instantiate a component"""
        registration = security_registry.get_component(name)
        if not registration:
            raise ValueError(f"Component {name} not found")
        
        if not registration.enabled:
            raise ValueError(f"Component {name} is disabled")
        
        # Check dependencies
        for dependency in registration.dependencies:
            if not security_registry.is_component_enabled(dependency):
                raise ValueError(f"Dependency {dependency} is not enabled")
        
        # Merge config with kwargs
        config = registration.config.copy()
        config.update(kwargs)
        
        # Instantiate component
        try:
            return registration.component_class(**config)
        except Exception as e:
            logger.error(f"Failed to instantiate component {name}: {e}")
            raise
    
    @staticmethod
    def load_components_by_type(component_type: ComponentType, **kwargs) -> List[Any]:
        """Load all components of a specific type"""
        components = []
        
        for registration in security_registry.get_components_by_type(component_type):
            if registration.enabled:
                try:
                    component = ComponentLoader.load_component(registration.name, **kwargs)
                    components.append(component)
                except Exception as e:
                    logger.error(f"Failed to load component {registration.name}: {e}")
        
        return components
    
    @staticmethod
    def load_components_with_dependencies(name: str, **kwargs) -> Dict[str, Any]:
        """Load a component and all its dependencies"""
        dependency_order = security_registry.resolve_dependencies(name)
        loaded_components = {}
        
        for dep_name in dependency_order:
            try:
                component = ComponentLoader.load_component(dep_name, **kwargs)
                loaded_components[dep_name] = component
            except Exception as e:
                logger.error(f"Failed to load dependency {dep_name}: {e}")
                raise
        
        return loaded_components


# Export registry and utilities
__all__ = [
    'ComponentType',
    'ComponentRegistration',
    'SecurityRegistry',
    'security_registry',
    'register_component',
    'ComponentLoader'
]