"""
Integration Registry
Registry for managing integration adapters, transformation rules, and system configurations
"""

import logging
from typing import Dict, Any, Optional, List, Type
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import threading
from collections import defaultdict

from .integ_adapter import BaseIntegrationAdapter, AdapterConfig, AdapterFactory
from .integ_constants import AdapterTypes, DataFormats, ProtocolTypes
from .integ_exceptions import IntegrationException, RegistryException

logger = logging.getLogger(__name__)


class RegistrationStatus(Enum):
    """Registration status enumeration"""
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class SystemRegistration:
    """System registration information"""
    system_name: str
    adapter_type: AdapterTypes
    config: AdapterConfig
    adapter: Optional[BaseIntegrationAdapter] = None
    status: RegistrationStatus = RegistrationStatus.REGISTERED
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def update_timestamp(self):
        """Update the last updated timestamp"""
        self.last_updated = datetime.utcnow()


@dataclass
class TransformationRule:
    """Data transformation rule"""
    source_system: str
    target_system: str
    source_format: DataFormats
    target_format: DataFormats
    field_mappings: Dict[str, str]
    transformations: Dict[str, Any]
    filters: Optional[Dict[str, Any]] = None
    priority: int = 5
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def update_timestamp(self):
        """Update the updated timestamp"""
        self.updated_at = datetime.utcnow()


@dataclass
class SystemCapability:
    """System capability definition"""
    system_name: str
    capabilities: List[str]
    supported_formats: List[DataFormats]
    supported_protocols: List[ProtocolTypes]
    max_request_size: Optional[int] = None
    rate_limit: Optional[int] = None
    authentication_methods: List[str] = field(default_factory=list)
    custom_properties: Dict[str, Any] = field(default_factory=dict)


class IntegrationRegistry:
    """
    Registry for managing integration components
    """
    
    def __init__(self):
        self._systems: Dict[str, SystemRegistration] = {}
        self._adapters: Dict[str, Type[BaseIntegrationAdapter]] = {}
        self._transformation_rules: Dict[str, List[TransformationRule]] = defaultdict(list)
        self._system_capabilities: Dict[str, SystemCapability] = {}
        self._lock = threading.RLock()
        
        # Registry statistics
        self._stats = {
            'total_systems': 0,
            'active_systems': 0,
            'total_rules': 0,
            'registration_count': 0,
            'unregistration_count': 0
        }
    
    def register_system(self, system_name: str, adapter_type: AdapterTypes, 
                       config: AdapterConfig, metadata: Optional[Dict[str, Any]] = None,
                       tags: Optional[List[str]] = None) -> SystemRegistration:
        """
        Register a system with the registry
        
        Args:
            system_name: Name of the system
            adapter_type: Type of adapter to use
            config: Adapter configuration
            metadata: Additional metadata
            tags: System tags
            
        Returns:
            System registration information
        """
        with self._lock:
            if system_name in self._systems:
                raise RegistryException(f"System {system_name} is already registered")
            
            try:
                # Create adapter
                adapter = AdapterFactory.create_adapter(config)
                
                # Create registration
                registration = SystemRegistration(
                    system_name=system_name,
                    adapter_type=adapter_type,
                    config=config,
                    adapter=adapter,
                    metadata=metadata or {},
                    tags=tags or []
                )
                
                # Store registration
                self._systems[system_name] = registration
                self._stats['total_systems'] += 1
                self._stats['registration_count'] += 1
                
                logger.info(f"Registered system: {system_name}")
                
                return registration
                
            except Exception as e:
                logger.error(f"Failed to register system {system_name}: {e}")
                raise RegistryException(f"Failed to register system: {e}")
    
    def unregister_system(self, system_name: str) -> bool:
        """
        Unregister a system from the registry
        
        Args:
            system_name: Name of the system to unregister
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if system_name not in self._systems:
                return False
            
            try:
                registration = self._systems[system_name]
                
                # Shutdown adapter if active
                if registration.status == RegistrationStatus.ACTIVE:
                    if registration.adapter:
                        # In async context, this would be awaited
                        pass  # registration.adapter.shutdown()
                
                # Remove from registry
                del self._systems[system_name]
                
                # Update statistics
                self._stats['total_systems'] -= 1
                self._stats['unregistration_count'] += 1
                
                if registration.status == RegistrationStatus.ACTIVE:
                    self._stats['active_systems'] -= 1
                
                logger.info(f"Unregistered system: {system_name}")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to unregister system {system_name}: {e}")
                return False
    
    def activate_system(self, system_name: str) -> bool:
        """
        Activate a registered system
        
        Args:
            system_name: Name of the system to activate
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if system_name not in self._systems:
                raise RegistryException(f"System {system_name} is not registered")
            
            registration = self._systems[system_name]
            
            if registration.status == RegistrationStatus.ACTIVE:
                return True
            
            try:
                # Initialize adapter
                if registration.adapter:
                    # In async context, this would be awaited
                    success = True  # await registration.adapter.initialize()
                    if success:
                        registration.status = RegistrationStatus.ACTIVE
                        registration.update_timestamp()
                        self._stats['active_systems'] += 1
                        logger.info(f"Activated system: {system_name}")
                        return True
                    else:
                        registration.status = RegistrationStatus.ERROR
                        raise RegistryException("Failed to initialize adapter")
                
                return False
                
            except Exception as e:
                registration.status = RegistrationStatus.ERROR
                logger.error(f"Failed to activate system {system_name}: {e}")
                return False
    
    def deactivate_system(self, system_name: str) -> bool:
        """
        Deactivate a registered system
        
        Args:
            system_name: Name of the system to deactivate
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if system_name not in self._systems:
                raise RegistryException(f"System {system_name} is not registered")
            
            registration = self._systems[system_name]
            
            if registration.status != RegistrationStatus.ACTIVE:
                return True
            
            try:
                # Shutdown adapter
                if registration.adapter:
                    # In async context, this would be awaited
                    pass  # await registration.adapter.shutdown()
                
                registration.status = RegistrationStatus.INACTIVE
                registration.update_timestamp()
                self._stats['active_systems'] -= 1
                
                logger.info(f"Deactivated system: {system_name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to deactivate system {system_name}: {e}")
                return False
    
    def get_adapter(self, system_name: str) -> Optional[BaseIntegrationAdapter]:
        """
        Get adapter for a system
        
        Args:
            system_name: Name of the system
            
        Returns:
            Adapter instance or None
        """
        with self._lock:
            registration = self._systems.get(system_name)
            if registration and registration.status == RegistrationStatus.ACTIVE:
                return registration.adapter
            return None
    
    def get_system_registration(self, system_name: str) -> Optional[SystemRegistration]:
        """
        Get system registration information
        
        Args:
            system_name: Name of the system
            
        Returns:
            System registration or None
        """
        with self._lock:
            return self._systems.get(system_name)
    
    def list_systems(self, status: Optional[RegistrationStatus] = None, 
                      tags: Optional[List[str]] = None) -> List[SystemRegistration]:
        """
        List registered systems
        
        Args:
            status: Filter by status (optional)
            tags: Filter by tags (optional)
            
        Returns:
            List of system registrations
        """
        with self._lock:
            systems = list(self._systems.values())
            
            # Filter by status
            if status:
                systems = [s for s in systems if s.status == status]
            
            # Filter by tags
            if tags:
                systems = [s for s in systems if any(tag in s.tags for tag in tags)]
            
            return systems
    
    def get_registered_systems(self) -> List[str]:
        """
        Get list of registered system names
        
        Returns:
            List of system names
        """
        with self._lock:
            return list(self._systems.keys())
    
    def register_transformation_rule(self, rule: TransformationRule) -> str:
        """
        Register a transformation rule
        
        Args:
            rule: Transformation rule to register
            
        Returns:
            Rule ID
        """
        with self._lock:
            rule_id = f"{rule.source_system}_to_{rule.target_system}"
            
            # Add to transformation rules
            self._transformation_rules[rule_id].append(rule)
            
            # Sort by priority
            self._transformation_rules[rule_id].sort(key=lambda r: r.priority)
            
            self._stats['total_rules'] += 1
            
            logger.info(f"Registered transformation rule: {rule_id}")
            
            return rule_id
    
    def get_transformation_rules(self, source_system: str, target_system: str) -> List[TransformationRule]:
        """
        Get transformation rules for system pair
        
        Args:
            source_system: Source system name
            target_system: Target system name
            
        Returns:
            List of transformation rules
        """
        with self._lock:
            rule_id = f"{source_system}_to_{target_system}"
            return self._transformation_rules.get(rule_id, [])
    
    def register_system_capability(self, capability: SystemCapability):
        """
        Register system capabilities
        
        Args:
            capability: System capability definition
        """
        with self._lock:
            self._system_capabilities[capability.system_name] = capability
            logger.info(f"Registered capabilities for system: {capability.system_name}")
    
    def get_system_capability(self, system_name: str) -> Optional[SystemCapability]:
        """
        Get system capabilities
        
        Args:
            system_name: Name of the system
            
        Returns:
            System capability or None
        """
        with self._lock:
            return self._system_capabilities.get(system_name)
    
    def find_compatible_systems(self, required_capabilities: List[str], 
                              data_format: Optional[DataFormats] = None,
                              protocol: Optional[ProtocolTypes] = None) -> List[str]:
        """
        Find systems that match required capabilities
        
        Args:
            required_capabilities: Required capabilities
            data_format: Required data format (optional)
            protocol: Required protocol (optional)
            
        Returns:
            List of compatible system names
        """
        with self._lock:
            compatible_systems = []
            
            for system_name, capability in self._system_capabilities.items():
                # Check capabilities
                if not all(cap in capability.capabilities for cap in required_capabilities):
                    continue
                
                # Check data format
                if data_format and data_format not in capability.supported_formats:
                    continue
                
                # Check protocol
                if protocol and protocol not in capability.supported_protocols:
                    continue
                
                compatible_systems.append(system_name)
            
            return compatible_systems
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics
        
        Returns:
            Registry statistics
        """
        with self._lock:
            stats = self._stats.copy()
            
            # Add detailed breakdowns
            stats['systems_by_status'] = {}
            for status in RegistrationStatus:
                stats['systems_by_status'][status.value] = len([
                    s for s in self._systems.values() if s.status == status
                ])
            
            stats['systems_by_type'] = {}
            for registration in self._systems.values():
                adapter_type = registration.adapter_type.value
                stats['systems_by_type'][adapter_type] = stats['systems_by_type'].get(adapter_type, 0) + 1
            
            stats['rules_by_system_pair'] = {
                rule_id: len(rules) for rule_id, rules in self._transformation_rules.items()
            }
            
            return stats
    
    def export_configuration(self, system_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Export registry configuration
        
        Args:
            system_name: Specific system to export (optional)
            
        Returns:
            Configuration data
        """
        with self._lock:
            config = {
                'exported_at': datetime.utcnow().isoformat(),
                'version': '1.0',
                'systems': {},
                'transformation_rules': [],
                'system_capabilities': {}
            }
            
            # Export systems
            systems_to_export = [system_name] if system_name else list(self._systems.keys())
            
            for sys_name in systems_to_export:
                if sys_name in self._systems:
                    registration = self._systems[sys_name]
                    config['systems'][sys_name] = {
                        'system_name': registration.system_name,
                        'adapter_type': registration.adapter_type.value,
                        'config': {
                            'endpoint': registration.config.endpoint,
                            'timeout': registration.config.timeout,
                            'data_format': registration.config.data_format.value,
                            'protocol': registration.config.protocol.value,
                            'custom_settings': registration.config.custom_settings
                        },
                        'status': registration.status.value,
                        'metadata': registration.metadata,
                        'tags': registration.tags,
                        'registered_at': registration.registered_at.isoformat(),
                        'last_updated': registration.last_updated.isoformat()
                    }
            
            # Export transformation rules
            for rule_id, rules in self._transformation_rules.items():
                for rule in rules:
                    if not system_name or (system_name in [rule.source_system, rule.target_system]):
                        config['transformation_rules'].append({
                            'source_system': rule.source_system,
                            'target_system': rule.target_system,
                            'source_format': rule.source_format.value,
                            'target_format': rule.target_format.value,
                            'field_mappings': rule.field_mappings,
                            'transformations': rule.transformations,
                            'filters': rule.filters,
                            'priority': rule.priority,
                            'enabled': rule.enabled,
                            'created_at': rule.created_at.isoformat(),
                            'updated_at': rule.updated_at.isoformat()
                        })
            
            # Export system capabilities
            capabilities_to_export = [system_name] if system_name else list(self._system_capabilities.keys())
            
            for sys_name in capabilities_to_export:
                if sys_name in self._system_capabilities:
                    capability = self._system_capabilities[sys_name]
                    config['system_capabilities'][sys_name] = {
                        'system_name': capability.system_name,
                        'capabilities': capability.capabilities,
                        'supported_formats': [f.value for f in capability.supported_formats],
                        'supported_protocols': [p.value for p in capability.supported_protocols],
                        'max_request_size': capability.max_request_size,
                        'rate_limit': capability.rate_limit,
                        'authentication_methods': capability.authentication_methods,
                        'custom_properties': capability.custom_properties
                    }
            
            return config
    
    def import_configuration(self, config_data: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
        """
        Import registry configuration
        
        Args:
            config_data: Configuration data
            overwrite: Whether to overwrite existing systems
            
        Returns:
            Import results
        """
        results = {
            'imported_systems': [],
            'failed_systems': [],
            'imported_rules': [],
            'failed_rules': [],
            'imported_capabilities': [],
            'failed_capabilities': []
        }
        
        with self._lock:
            # Import systems
            for system_name, system_data in config_data.get('systems', {}).items():
                try:
                    if system_name in self._systems and not overwrite:
                        results['failed_systems'].append({
                            'system': system_name,
                            'error': 'System already exists and overwrite is False'
                        })
                        continue
                    
                    # Create adapter config
                    adapter_config = AdapterConfig(
                        adapter_type=AdapterTypes(system_data['adapter_type']),
                        system_name=system_name,
                        endpoint=system_data['config']['endpoint'],
                        timeout=system_data['config']['timeout'],
                        data_format=DataFormats(system_data['config']['data_format']),
                        protocol=ProtocolTypes(system_data['config']['protocol']),
                        custom_settings=system_data['config']['custom_settings']
                    )
                    
                    # Register system
                    registration = self.register_system(
                        system_name=system_name,
                        adapter_type=adapter_config.adapter_type,
                        config=adapter_config,
                        metadata=system_data.get('metadata', {}),
                        tags=system_data.get('tags', [])
                    )
                    
                    results['imported_systems'].append(system_name)
                    
                except Exception as e:
                    results['failed_systems'].append({
                        'system': system_name,
                        'error': str(e)
                    })
            
            # Import transformation rules
            for rule_data in config_data.get('transformation_rules', []):
                try:
                    rule = TransformationRule(
                        source_system=rule_data['source_system'],
                        target_system=rule_data['target_system'],
                        source_format=DataFormats(rule_data['source_format']),
                        target_format=DataFormats(rule_data['target_format']),
                        field_mappings=rule_data['field_mappings'],
                        transformations=rule_data['transformations'],
                        filters=rule_data.get('filters'),
                        priority=rule_data.get('priority', 5),
                        enabled=rule_data.get('enabled', True)
                    )
                    
                    rule_id = self.register_transformation_rule(rule)
                    results['imported_rules'].append(rule_id)
                    
                except Exception as e:
                    results['failed_rules'].append({
                        'rule': f"{rule_data.get('source_system', 'unknown')}_to_{rule_data.get('target_system', 'unknown')}",
                        'error': str(e)
                    })
            
            # Import system capabilities
            for system_name, capability_data in config_data.get('system_capabilities', {}).items():
                try:
                    capability = SystemCapability(
                        system_name=system_name,
                        capabilities=capability_data['capabilities'],
                        supported_formats=[DataFormats(f) for f in capability_data['supported_formats']],
                        supported_protocols=[ProtocolTypes(p) for p in capability_data['supported_protocols']],
                        max_request_size=capability_data.get('max_request_size'),
                        rate_limit=capability_data.get('rate_limit'),
                        authentication_methods=capability_data.get('authentication_methods', []),
                        custom_properties=capability_data.get('custom_properties', {})
                    )
                    
                    self.register_system_capability(capability)
                    results['imported_capabilities'].append(system_name)
                    
                except Exception as e:
                    results['failed_capabilities'].append({
                        'system': system_name,
                        'error': str(e)
                    })
        
        return results


# Global registry instance
_integration_registry = None


def get_integration_registry() -> IntegrationRegistry:
    """Get the global integration registry instance"""
    global _integration_registry
    if _integration_registry is None:
        _integration_registry = IntegrationRegistry()
    return _integration_registry


def initialize_integration_registry() -> IntegrationRegistry:
    """Initialize the global integration registry"""
    global _integration_registry
    _integration_registry = IntegrationRegistry()
    return _integration_registry


# Export main classes and functions
__all__ = [
    'IntegrationRegistry',
    'SystemRegistration',
    'TransformationRule',
    'SystemCapability',
    'RegistrationStatus',
    'get_integration_registry',
    'initialize_integration_registry',
]
