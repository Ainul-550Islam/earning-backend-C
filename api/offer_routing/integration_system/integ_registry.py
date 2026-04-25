"""
Integration Registry

Registry for managing all integrations in the
offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from django.utils import timezone
from django.core.cache import cache
from .integ_constants import IntegrationType, IntegrationStatus
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Registry for managing all integrations.
    
    Provides centralized management for:
    - Integration registration and discovery
    - Configuration management
    - Status tracking
    - Dependency management
    - Version control
    """
    
    def __init__(self):
        self._integrations: Dict[str, Dict[str, Any]] = {}
        self._dependencies: Dict[str, Set[str]] = {}
        self._versions: Dict[str, str] = {}
        self._cache_timeout = 3600  # 1 hour
        self._registry_initialized = False
        
        # Initialize registry
        self._initialize_registry()
    
    def _initialize_registry(self):
        """Initialize the integration registry."""
        try:
            # Load integrations from cache
            cached_integrations = cache.get('integration_registry')
            
            if cached_integrations:
                self._integrations = cached_integrations
                logger.info("Loaded integration registry from cache")
            else:
                # Load from database or configuration
                self._load_integrations_from_config()
                self._cache_registry()
            
            self._registry_initialized = True
            logger.info(f"Initialized integration registry with {len(self._integrations)} integrations")
            
        except Exception as e:
            logger.error(f"Error initializing integration registry: {e}")
            self._integrations = {}
    
    def _load_integrations_from_config(self):
        """Load integrations from Django settings."""
        try:
            from django.conf import settings
            
            integrations = getattr(settings, 'INTEGRATIONS', {})
            
            for integration_name, integration_config in integrations.items():
                self._register_internal(integration_name, integration_config)
                
        except Exception as e:
            logger.error(f"Error loading integrations from config: {e}")
    
    def _cache_registry(self):
        """Cache the integration registry."""
        try:
            cache.set('integration_registry', self._integrations, self._cache_timeout)
        except Exception as e:
            logger.error(f"Error caching integration registry: {e}")
    
    def register(self, name: str, config: Dict[str, Any]) -> str:
        """
        Register a new integration.
        
        Args:
            name: Integration name
            config: Integration configuration
            
        Returns:
            Integration ID
        """
        try:
            integration_id = self._generate_integration_id(name)
            
            self._register_internal(integration_id, config)
            
            # Cache updated registry
            self._cache_registry()
            
            logger.info(f"Registered integration: {name} (ID: {integration_id})")
            
            return integration_id
            
        except Exception as e:
            logger.error(f"Error registering integration {name}: {e}")
            raise IntegrationError(f"Failed to register integration: {e}")
    
    def _register_internal(self, integration_id: str, config: Dict[str, Any]):
        """Internal registration method."""
        self._integrations[integration_id] = {
            'id': integration_id,
            'name': config.get('name', integration_id),
            'type': config.get('type', IntegrationType.WEBHOOK.value),
            'config': config,
            'status': IntegrationStatus.INACTIVE.value,
            'created_at': timezone.now().isoformat(),
            'updated_at': timezone.now().isoformat(),
            'version': config.get('version', '1.0.0'),
            'dependencies': config.get('dependencies', []),
            'last_sync': None,
            'sync_status': None,
            'error_count': 0,
            'last_error': None
        }
        
        # Register dependencies
        dependencies = config.get('dependencies', [])
        self._dependencies[integration_id] = set(dependencies)
        
        # Register version
        self._versions[integration_id] = config.get('version', '1.0.0')
    
    def _generate_integration_id(self, name: str) -> str:
        """Generate unique integration ID."""
        import uuid
        return f"{name}_{uuid.uuid4().hex[:8]}"
    
    def unregister(self, integration_id: str) -> bool:
        """
        Unregister an integration.
        
        Args:
            integration_id: Integration ID to unregister
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if integration_id not in self._integrations:
                logger.warning(f"Integration not found: {integration_id}")
                return False
            
            # Check dependencies
            dependents = self._get_dependents(integration_id)
            if dependents:
                logger.error(f"Cannot unregister {integration_id}: has dependents {dependents}")
                return False
            
            # Remove from registry
            del self._integrations[integration_id]
            del self._dependencies[integration_id]
            del self._versions[integration_id]
            
            # Cache updated registry
            self._cache_registry()
            
            logger.info(f"Unregistered integration: {integration_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering integration {integration_id}: {e}")
            return False
    
    def get_integration(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """
        Get integration by ID.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Integration configuration or None
        """
        return self._integrations.get(integration_id)
    
    def get_integrations_by_type(self, integration_type: str) -> List[Dict[str, Any]]:
        """
        Get integrations by type.
        
        Args:
            integration_type: Integration type
            
        Returns:
            List of integrations
        """
        return [
            integration for integration in self._integrations.values()
            if integration.get('type') == integration_type
        ]
    
    def get_active_integrations(self) -> List[Dict[str, Any]]:
        """
        Get all active integrations.
        
        Returns:
            List of active integrations
        """
        return [
            integration for integration in self._integrations.values()
            if integration.get('status') == IntegrationStatus.ACTIVE.value
        ]
    
    def get_integrations_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Get integrations by status.
        
        Args:
            status: Integration status
            
        Returns:
            List of integrations
        """
        return [
            integration for integration in self._integrations.values()
            if integration.get('status') == status
        ]
    
    def update_integration_status(self, integration_id: str, status: str) -> bool:
        """
        Update integration status.
        
        Args:
            integration_id: Integration ID
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if integration_id not in self._integrations:
                logger.warning(f"Integration not found: {integration_id}")
                return False
            
            self._integrations[integration_id]['status'] = status
            self._integrations[integration_id]['updated_at'] = timezone.now().isoformat()
            
            # Cache updated registry
            self._cache_registry()
            
            logger.info(f"Updated integration {integration_id} status to {status}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating integration status {integration_id}: {e}")
            return False
    
    def update_integration_config(self, integration_id: str, 
                              config: Dict[str, Any]) -> bool:
        """
        Update integration configuration.
        
        Args:
            integration_id: Integration ID
            config: New configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if integration_id not in self._integrations:
                logger.warning(f"Integration not found: {integration_id}")
                return False
            
            # Update configuration
            self._integrations[integration_id]['config'].update(config)
            self._integrations[integration_id]['updated_at'] = timezone.now().isoformat()
            
            # Update dependencies if provided
            if 'dependencies' in config:
                self._dependencies[integration_id] = set(config['dependencies'])
            
            # Cache updated registry
            self._cache_registry()
            
            logger.info(f"Updated configuration for integration {integration_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating integration config {integration_id}: {e}")
            return False
    
    def get_dependencies(self, integration_id: str) -> Set[str]:
        """
        Get dependencies for an integration.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Set of dependency IDs
        """
        return self._dependencies.get(integration_id, set())
    
    def _get_dependents(self, integration_id: str) -> Set[str]:
        """
        Get integrations that depend on this integration.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Set of dependent integration IDs
        """
        dependents = set()
        
        for integ_id, dependencies in self._dependencies.items():
            if integration_id in dependencies:
                dependents.add(integ_id)
        
        return dependents
    
    def check_dependencies(self, integration_id: str) -> Dict[str, Any]:
        """
        Check if all dependencies are satisfied.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Dependency check result
        """
        try:
            dependencies = self.get_dependencies(integration_id)
            
            if not dependencies:
                return {
                    'satisfied': True,
                    'missing': [],
                    'circular': False
                }
            
            # Check for circular dependencies
            if self._has_circular_dependency(integration_id):
                return {
                    'satisfied': False,
                    'missing': [],
                    'circular': True,
                    'circular_path': self._get_circular_path(integration_id)
                }
            
            # Check if dependencies are registered and active
            missing = []
            for dep_id in dependencies:
                if dep_id not in self._integrations:
                    missing.append(dep_id)
                elif self._integrations[dep_id]['status'] != IntegrationStatus.ACTIVE.value:
                    missing.append(dep_id)
            
            return {
                'satisfied': len(missing) == 0,
                'missing': missing,
                'circular': False
            }
            
        except Exception as e:
            logger.error(f"Error checking dependencies for {integration_id}: {e}")
            return {
                'satisfied': False,
                'missing': [],
                'circular': False,
                'error': str(e)
            }
    
    def _has_circular_dependency(self, integration_id: str, 
                              visited: Set[str] = None) -> bool:
        """
        Check for circular dependencies.
        
        Args:
            integration_id: Integration ID to check
            visited: Already visited integrations
            
        Returns:
            True if circular dependency exists
        """
        if visited is None:
            visited = set()
        
        if integration_id in visited:
            return True
        
        visited.add(integration_id)
        
        dependencies = self.get_dependencies(integration_id)
        
        for dep_id in dependencies:
            if self._has_circular_dependency(dep_id, visited.copy()):
                return True
        
        return False
    
    def _get_circular_path(self, integration_id: str, 
                           path: List[str] = None) -> List[str]:
        """
        Get circular dependency path.
        
        Args:
            integration_id: Integration ID to check
            path: Current path
            
        Returns:
            Circular dependency path
        """
        if path is None:
            path = []
        
        if integration_id in path:
            return path + [integration_id]
        
        path.append(integration_id)
        
        dependencies = self.get_dependencies(integration_id)
        
        for dep_id in dependencies:
            circular_path = self._get_circular_path(dep_id, path.copy())
            if circular_path:
                return circular_path
        
        return []
    
    def get_version(self, integration_id: str) -> Optional[str]:
        """
        Get integration version.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Version string or None
        """
        return self._versions.get(integration_id)
    
    def update_version(self, integration_id: str, version: str) -> bool:
        """
        Update integration version.
        
        Args:
            integration_id: Integration ID
            version: New version
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if integration_id not in self._integrations:
                logger.warning(f"Integration not found: {integration_id}")
                return False
            
            self._versions[integration_id] = version
            self._integrations[integration_id]['version'] = version
            self._integrations[integration_id]['updated_at'] = timezone.now().isoformat()
            
            # Cache updated registry
            self._cache_registry()
            
            logger.info(f"Updated integration {integration_id} version to {version}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating integration version {integration_id}: {e}")
            return False
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Registry statistics
        """
        try:
            total_integrations = len(self._integrations)
            active_integrations = len(self.get_active_integrations())
            
            type_counts = {}
            for integration in self._integrations.values():
                integ_type = integration.get('type', 'unknown')
                type_counts[integ_type] = type_counts.get(integ_type, 0) + 1
            
            status_counts = {}
            for integration in self._integrations.values():
                integ_status = integration.get('status', 'unknown')
                status_counts[integ_status] = status_counts.get(integ_status, 0) + 1
            
            return {
                'total_integrations': total_integrations,
                'active_integrations': active_integrations,
                'inactive_integrations': total_integrations - active_integrations,
                'type_distribution': type_counts,
                'status_distribution': status_counts,
                'registry_initialized': self._registry_initialized,
                'last_updated': max(
                    [integ['updated_at'] for integ in self._integrations.values()],
                    default=timezone.now().isoformat()
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting registry stats: {e}")
            return {'error': str(e)}
    
    def validate_registry(self) -> Dict[str, Any]:
        """
        Validate the integration registry.
        
        Returns:
            Validation results
        """
        try:
            validation_results = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'invalid_integrations': [],
                'circular_dependencies': []
            }
            
            # Check each integration
            for integration_id, integration in self._integrations.items():
                # Check configuration
                config_errors = self._validate_integration_config(integration['config'])
                if config_errors:
                    validation_results['invalid_integrations'].append({
                        'integration_id': integration_id,
                        'errors': config_errors
                    })
                    validation_results['valid'] = False
                
                # Check dependencies
                dep_check = self.check_dependencies(integration_id)
                if not dep_check['satisfied']:
                    if dep_check['circular']:
                        validation_results['circular_dependencies'].append({
                            'integration_id': integration_id,
                            'path': dep_check['circular_path']
                        })
                    else:
                        validation_results['errors'].append({
                            'integration_id': integration_id,
                            'missing_dependencies': dep_check['missing']
                        })
                    validation_results['valid'] = False
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating registry: {e}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'invalid_integrations': [],
                'circular_dependencies': []
            }
    
    def _validate_integration_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate integration configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check required fields
        required_fields = ['type', 'name']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Check type
        integration_type = config.get('type')
        if integration_type:
            valid_types = [t.value for t in IntegrationType]
            if integration_type not in valid_types:
                errors.append(f"Invalid integration type: {integration_type}")
        
        # Check endpoint for webhooks and APIs
        if integration_type in [IntegrationType.WEBHOOK.value, IntegrationType.API.value]:
            if not config.get('endpoint'):
                errors.append("Endpoint is required for webhook/API integrations")
        
        return errors
    
    def export_registry(self) -> Dict[str, Any]:
        """
        Export registry configuration.
        
        Returns:
            Exported registry data
        """
        try:
            return {
                'integrations': self._integrations,
                'dependencies': self._dependencies,
                'versions': self._versions,
                'exported_at': timezone.now().isoformat(),
                'export_version': '1.0.0'
            }
            
        except Exception as e:
            logger.error(f"Error exporting registry: {e}")
            return {'error': str(e)}
    
    def import_registry(self, registry_data: Dict[str, Any]) -> bool:
        """
        Import registry configuration.
        
        Args:
            registry_data: Registry data to import
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate registry data
            if not self._validate_import_data(registry_data):
                return False
            
            # Clear current registry
            self._integrations.clear()
            self._dependencies.clear()
            self._versions.clear()
            
            # Import integrations
            for integration_id, integration in registry_data.get('integrations', {}).items():
                self._register_internal(integration_id, integration)
            
            # Import dependencies
            for integration_id, dependencies in registry_data.get('dependencies', {}).items():
                self._dependencies[integration_id] = set(dependencies)
            
            # Import versions
            for integration_id, version in registry_data.get('versions', {}).items():
                self._versions[integration_id] = version
            
            # Cache updated registry
            self._cache_registry()
            
            logger.info("Successfully imported integration registry")
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing registry: {e}")
            return False
    
    def _validate_import_data(self, registry_data: Dict[str, Any]) -> bool:
        """
        Validate import data structure.
        
        Args:
            registry_data: Registry data to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            required_keys = ['integrations', 'dependencies', 'versions']
            
            for key in required_keys:
                if key not in registry_data:
                    logger.error(f"Missing required key in import data: {key}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating import data: {e}")
            return False
    
    def clear_registry(self) -> bool:
        """
        Clear the integration registry.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self._integrations.clear()
            self._dependencies.clear()
            self._versions.clear()
            
            # Clear cache
            cache.delete('integration_registry')
            
            logger.info("Cleared integration registry")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing registry: {e}")
            return False
    
    def reload_registry(self) -> bool:
        """
        Reload the integration registry.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear current registry
            self.clear_registry()
            
            # Reinitialize
            self._initialize_registry()
            
            logger.info("Reloaded integration registry")
            
            return True
            
        except Exception as e:
            logger.error(f"Error reloading registry: {e}")
            return False


# Global registry instance
integration_registry = IntegrationRegistry()
