"""
integ_registry.py – Integration Registry for postback module.

Provides comprehensive registry functionality including:
- Integration registration and discovery
- Configuration management
- Lifecycle management
- Registry statistics
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.utils import timezone
from django.core.cache import cache

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationType, IntegrationStatus, IntegrationProtocol
from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class RegistryStatus(Enum):
    """Registry status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class IntegrationRegistration:
    """Integration registration data structure."""
    name: str
    type: IntegrationType
    protocol: IntegrationProtocol
    config: Dict[str, Any]
    status: IntegrationStatus
    registered_at: datetime = field(default_factory=timezone.now)
    last_updated: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'type': self.type.value,
            'protocol': self.protocol.value,
            'config': self.config,
            'status': self.status.value,
            'registered_at': self.registered_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'metadata': self.metadata,
        }


class IntegrationRegistry:
    """
    Registry for integration configurations and metadata.
    
    Manages integration registration, discovery,
    and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.registrations: Dict[str, IntegrationRegistration] = {}
        self.type_index: Dict[IntegrationType, List[str]] = {}
        self.protocol_index: Dict[IntegrationProtocol, List[str]] = {}
        self.status_index: Dict[IntegrationStatus, List[str]] = {}
        self.registry_status = RegistryStatus.ACTIVE
        self._setup_registry()
    
    def _setup_registry(self):
        """Setup registry with default integrations."""
        # Load integrations from cache if available
        cached_registrations = cache.get('integration_registry')
        if cached_registrations:
            for reg_data in cached_registrations:
                self._load_registration_from_cache(reg_data)
        
        self.logger.info(f"Registry initialized with {len(self.registrations)} integrations")
    
    def register(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Register integration.
        
        Args:
            name: Integration name
            config: Integration configuration
            
        Returns:
            True if registered successfully
        """
        try:
            # Validate configuration
            if not self._validate_config(config):
                raise IntegrationException("Invalid integration configuration")
            
            # Check if already registered
            if name in self.registrations:
                return self.update(name, config)
            
            # Create registration
            registration = IntegrationRegistration(
                name=name,
                type=config.get('type', IntegrationType.WEBHOOK),
                protocol=config.get('protocol', IntegrationProtocol.HTTP),
                config=config,
                status=IntegrationStatus.ACTIVE,
                metadata=config.get('metadata', {})
            )
            
            # Add to registry
            self.registrations[name] = registration
            
            # Update indexes
            self._update_indexes(registration, 'add')
            
            # Cache registration
            self._cache_registration(registration)
            
            self.logger.info(f"Integration registered: {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to register integration {name}: {str(e)}")
            return False
    
    def unregister(self, name: str) -> bool:
        """
        Unregister integration.
        
        Args:
            name: Integration name
            
        Returns:
            True if unregistered successfully
        """
        try:
            if name not in self.registrations:
                self.logger.warning(f"Integration not found: {name}")
                return False
            
            registration = self.registrations[name]
            
            # Update status
            registration.status = IntegrationStatus.INACTIVE
            registration.last_updated = timezone.now()
            
            # Update indexes
            self._update_indexes(registration, 'remove')
            
            # Remove from registry
            del self.registrations[name]
            
            # Remove from cache
            cache_key = f"integration_reg_{name}"
            cache.delete(cache_key)
            
            self.logger.info(f"Integration unregistered: {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to unregister integration {name}: {str(e)}")
            return False
    
    def update(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Update integration configuration.
        
        Args:
            name: Integration name
            config: New configuration
            
        Returns:
            True if updated successfully
        """
        try:
            if name not in self.registrations:
                self.logger.warning(f"Integration not found for update: {name}")
                return False
            
            registration = self.registrations[name]
            
            # Validate new configuration
            if not self._validate_config(config):
                raise IntegrationException("Invalid integration configuration")
            
            # Update registration
            old_type = registration.type
            old_protocol = registration.protocol
            
            registration.config.update(config)
            registration.type = config.get('type', old_type)
            registration.protocol = config.get('protocol', old_protocol)
            registration.last_updated = timezone.now()
            registration.metadata.update(config.get('metadata', {}))
            
            # Update indexes if type or protocol changed
            if old_type != registration.type or old_protocol != registration.protocol:
                self._update_indexes(registration, 'update', old_type, old_protocol)
            
            # Cache updated registration
            self._cache_registration(registration)
            
            self.logger.info(f"Integration updated: {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to update integration {name}: {str(e)}")
            return False
    
    def get(self, name: str) -> Optional[IntegrationRegistration]:
        """
        Get integration registration.
        
        Args:
            name: Integration name
            
        Returns:
            Integration registration or None
        """
        return self.registrations.get(name)
    
    def get_by_type(self, integration_type: IntegrationType) -> List[IntegrationRegistration]:
        """
        Get integrations by type.
        
        Args:
            integration_type: Integration type
            
        Returns:
            List of integrations
        """
        names = self.type_index.get(integration_type, [])
        return [self.registrations[name] for name in names if name in self.registrations]
    
    def get_by_protocol(self, protocol: IntegrationProtocol) -> List[IntegrationRegistration]:
        """
        Get integrations by protocol.
        
        Args:
            protocol: Integration protocol
            
        Returns:
            List of integrations
        """
        names = self.protocol_index.get(protocol, [])
        return [self.registrations[name] for name in names if name in self.registrations]
    
    def get_by_status(self, status: IntegrationStatus) -> List[IntegrationRegistration]:
        """
        Get integrations by status.
        
        Args:
            status: Integration status
            
        Returns:
            List of integrations
        """
        names = self.status_index.get(status, [])
        return [self.registrations[name] for name in names if name in self.registrations]
    
    def list_all(self) -> List[IntegrationRegistration]:
        """Get all integrations."""
        return list(self.registrations.values())
    
    def search(self, query: str, search_fields: List[str] = None) -> List[IntegrationRegistration]:
        """
        Search integrations.
        
        Args:
            query: Search query
            search_fields: Fields to search in
            
        Returns:
            List of matching integrations
        """
        if not query:
            return []
        
        search_fields = search_fields or ['name', 'type', 'protocol', 'endpoint']
        query_lower = query.lower()
        
        results = []
        for registration in self.registrations.values():
            for field in search_fields:
                field_value = self._get_field_value(registration, field)
                if field_value and query_lower in str(field_value).lower():
                    results.append(registration)
                    break
        
        return results
    
    def _get_field_value(self, registration: IntegrationRegistration, field: str) -> Any:
        """Get field value from registration."""
        if field == 'name':
            return registration.name
        elif field == 'type':
            return registration.type.value
        elif field == 'protocol':
            return registration.protocol.value
        elif field == 'endpoint':
            return registration.config.get('endpoint')
        elif field == 'status':
            return registration.status.value
        else:
            return registration.config.get(field)
    
    def activate(self, name: str) -> bool:
        """
        Activate integration.
        
        Args:
            name: Integration name
            
        Returns:
            True if activated successfully
        """
        if name not in self.registrations:
            return False
        
        registration = self.registrations[name]
        registration.status = IntegrationStatus.ACTIVE
        registration.last_updated = timezone.now()
        
        self._update_indexes(registration, 'update')
        self._cache_registration(registration)
        
        self.logger.info(f"Integration activated: {name}")
        return True
    
    def deactivate(self, name: str) -> bool:
        """
        Deactivate integration.
        
        Args:
            name: Integration name
            
        Returns:
            True if deactivated successfully
        """
        if name not in self.registrations:
            return False
        
        registration = self.registrations[name]
        registration.status = IntegrationStatus.INACTIVE
        registration.last_updated = timezone.now()
        
        self._update_indexes(registration, 'update')
        self._cache_registration(registration)
        
        self.logger.info(f"Integration deactivated: {name}")
        return True
    
    def set_status(self, name: str, status: IntegrationStatus) -> bool:
        """
        Set integration status.
        
        Args:
            name: Integration name
            status: New status
            
        Returns:
            True if status set successfully
        """
        if name not in self.registrations:
            return False
        
        registration = self.registrations[name]
        old_status = registration.status
        registration.status = status
        registration.last_updated = timezone.now()
        
        # Update status index
        if old_status != status:
            if old_status in self.status_index:
                self.status_index[old_status].remove(name)
            if status not in self.status_index:
                self.status_index[status] = []
            self.status_index[status].append(name)
        
        self._cache_registration(registration)
        
        self.logger.info(f"Integration status set: {name} -> {status.value}")
        return True
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate integration configuration."""
        required_fields = ['name', 'type', 'protocol']
        
        for field in required_fields:
            if field not in config:
                return False
        
        # Validate type
        if not isinstance(config['type'], IntegrationType):
            try:
                config['type'] = IntegrationType(config['type'])
            except ValueError:
                return False
        
        # Validate protocol
        if not isinstance(config['protocol'], IntegrationProtocol):
            try:
                config['protocol'] = IntegrationProtocol(config['protocol'])
            except ValueError:
                return False
        
        # Validate endpoint for HTTP/HTTPS protocols
        if config['protocol'] in [IntegrationProtocol.HTTP, IntegrationProtocol.HTTPS]:
            if 'endpoint' not in config or not config['endpoint']:
                return False
        
        return True
    
    def _update_indexes(self, registration: IntegrationRegistration, operation: str,
                        old_type: IntegrationType = None, old_protocol: IntegrationProtocol = None):
        """Update registry indexes."""
        name = registration.name
        
        if operation == 'add':
            # Add to type index
            if registration.type not in self.type_index:
                self.type_index[registration.type] = []
            self.type_index[registration.type].append(name)
            
            # Add to protocol index
            if registration.protocol not in self.protocol_index:
                self.protocol_index[registration.protocol] = []
            self.protocol_index[registration.protocol].append(name)
            
            # Add to status index
            if registration.status not in self.status_index:
                self.status_index[registration.status] = []
            self.status_index[registration.status].append(name)
        
        elif operation == 'remove':
            # Remove from type index
            if registration.type in self.type_index:
                self.type_index[registration.type] = [n for n in self.type_index[registration.type] if n != name]
            
            # Remove from protocol index
            if registration.protocol in self.protocol_index:
                self.protocol_index[registration.protocol] = [n for n in self.protocol_index[registration.protocol] if n != name]
            
            # Remove from status index
            if registration.status in self.status_index:
                self.status_index[registration.status] = [n for n in self.status_index[registration.status] if n != name]
        
        elif operation == 'update':
            # Update type index if changed
            if old_type and old_type != registration.type:
                if old_type in self.type_index:
                    self.type_index[old_type] = [n for n in self.type_index[old_type] if n != name]
                if registration.type not in self.type_index:
                    self.type_index[registration.type] = []
                self.type_index[registration.type].append(name)
            
            # Update protocol index if changed
            if old_protocol and old_protocol != registration.protocol:
                if old_protocol in self.protocol_index:
                    self.protocol_index[old_protocol] = [n for n in self.protocol_index[old_protocol] if n != name]
                if registration.protocol not in self.protocol_index:
                    self.protocol_index[registration.protocol] = []
                self.protocol_index[registration.protocol].append(name)
            
            # Update status index
            if registration.status not in self.status_index:
                self.status_index[registration.status] = []
            self.status_index[registration.status].append(name)
    
    def _cache_registration(self, registration: IntegrationRegistration):
        """Cache registration data."""
        cache_key = f"integration_reg_{registration.name}"
        cache.set(cache_key, registration.to_dict(), timeout=3600)
        
        # Update registry cache
        registry_data = [reg.to_dict() for reg in self.registrations.values()]
        cache.set('integration_registry', registry_data, timeout=3600)
    
    def _load_registration_from_cache(self, reg_data: Dict[str, Any]):
        """Load registration from cache data."""
        try:
            registration = IntegrationRegistration(
                name=reg_data['name'],
                type=IntegrationType(reg_data['type']),
                protocol=IntegrationProtocol(reg_data['protocol']),
                config=reg_data['config'],
                status=IntegrationStatus(reg_data['status']),
                registered_at=datetime.fromisoformat(reg_data['registered_at']),
                last_updated=datetime.fromisoformat(reg_data['last_updated']),
                metadata=reg_data.get('metadata', {})
            )
            
            self.registrations[registration.name] = registration
            self._update_indexes(registration, 'add')
        
        except Exception as e:
            self.logger.error(f"Error loading registration from cache: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_integrations = len(self.registrations)
        
        # Count by type
        type_counts = {}
        for integration_type, names in self.type_index.items():
            type_counts[integration_type.value] = len(names)
        
        # Count by protocol
        protocol_counts = {}
        for protocol, names in self.protocol_index.items():
            protocol_counts[protocol.value] = len(names)
        
        # Count by status
        status_counts = {}
        for status, names in self.status_index.items():
            status_counts[status.value] = len(names)
        
        # Recent registrations
        recent_registrations = sorted(
            self.registrations.values(),
            key=lambda x: x.registered_at,
            reverse=True
        )[:10]
        
        return {
            'total_integrations': total_integrations,
            'type_counts': type_counts,
            'protocol_counts': protocol_counts,
            'status_counts': status_counts,
            'registry_status': self.registry_status.value,
            'recent_registrations': [reg.to_dict() for reg in recent_registrations],
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform registry health check."""
        health_status = {
            'overall': 'healthy',
            'registry_status': self.registry_status.value,
            'total_integrations': len(self.registrations),
            'active_integrations': len(self.status_index.get(IntegrationStatus.ACTIVE, [])),
            'inactive_integrations': len(self.status_index.get(IntegrationStatus.INACTIVE, [])),
            'issues': [],
        }
        
        # Check registry status
        if self.registry_status != RegistryStatus.ACTIVE:
            health_status['overall'] = 'unhealthy'
            health_status['issues'].append(f"Registry status: {self.registry_status.value}")
        
        # Check for integrations with errors
        error_integrations = self.get_by_status(IntegrationStatus.ERROR)
        if error_integrations:
            health_status['overall'] = 'degraded'
            health_status['issues'].append(f"{len(error_integrations)} integrations in error state")
        
        return health_status
    
    def export_configurations(self, format_type: str = 'json') -> str:
        """
        Export all configurations.
        
        Args:
            format_type: Export format (json, yaml)
            
        Returns:
            Exported configurations
        """
        configurations = {}
        
        for name, registration in self.registrations.items():
            configurations[name] = registration.to_dict()
        
        if format_type == 'json':
            import json
            return json.dumps(configurations, indent=2)
        elif format_type == 'yaml':
            try:
                import yaml
                return yaml.dump(configurations, default_flow_style=False)
            except ImportError:
                raise IntegrationException("YAML library not available")
        else:
            raise IntegrationException(f"Unsupported export format: {format_type}")
    
    def import_configurations(self, config_data: str, format_type: str = 'json') -> int:
        """
        Import configurations.
        
        Args:
            config_data: Configuration data
            format_type: Data format (json, yaml)
            
        Returns:
            Number of imported configurations
        """
        if format_type == 'json':
            import json
            configurations = json.loads(config_data)
        elif format_type == 'yaml':
            try:
                import yaml
                configurations = yaml.safe_load(config_data)
            except ImportError:
                raise IntegrationException("YAML library not available")
        else:
            raise IntegrationException(f"Unsupported import format: {format_type}")
        
        imported_count = 0
        for name, config in configurations.items():
            if self.register(name, config):
                imported_count += 1
        
        self.logger.info(f"Imported {imported_count} configurations")
        return imported_count


# Global registry instance
integration_registry = IntegrationRegistry()


# Convenience functions
def register_integration(name: str, config: Dict[str, Any]) -> bool:
    """Register integration."""
    return integration_registry.register(name, config)


def unregister_integration(name: str) -> bool:
    """Unregister integration."""
    return integration_registry.unregister(name)


def get_integration(name: str) -> Optional[IntegrationRegistration]:
    """Get integration registration."""
    return integration_registry.get(name)


def list_integrations() -> List[IntegrationRegistration]:
    """List all integrations."""
    return integration_registry.list_all()


def search_integrations(query: str, search_fields: List[str] = None) -> List[IntegrationRegistration]:
    """Search integrations."""
    return integration_registry.search(query, search_fields)


def get_registry_statistics() -> Dict[str, Any]:
    """Get registry statistics."""
    return integration_registry.get_statistics()
