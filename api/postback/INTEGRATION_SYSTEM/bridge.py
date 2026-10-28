"""
bridge.py – Bridge pattern implementation for postback module.

Provides comprehensive bridge functionality including:
- Service bridging
- Protocol adaptation
- Data transformation bridges
- Bridge lifecycle management
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from django.utils import timezone
from django.core.cache import cache

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationType, IntegrationProtocol, IntegrationStatus
from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS.transformer import DataTransformer
from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class BridgeType(Enum):
    """Bridge type enumeration."""
    PROTOCOL = "protocol"
    DATA = "data"
    SERVICE = "service"
    EVENT = "event"
    SECURITY = "security"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    MONITORING = "monitoring"


class BridgeStatus(Enum):
    """Bridge status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class BridgeConfig:
    """Bridge configuration."""
    name: str
    bridge_type: BridgeType
    source: str
    target: str
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 50
    timeout: int = 30
    retry_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


class Bridge(ABC):
    """
    Abstract base class for bridges.
    
    Provides common bridge functionality that can be
    extended for specific bridge types.
    """
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.name = config.name
        self.bridge_type = config.bridge_type
        self.source = config.source
        self.target = config.target
        self.status = BridgeStatus.ACTIVE
        self.created_at = timezone.now()
        self.last_used = None
        self.usage_count = 0
        self.error_count = 0
        self.logger = logging.getLogger(f"bridge.{self.name}")
        
        # Initialize transformer
        self.transformer = DataTransformer(config.config.get('transformations', {}))
    
    @abstractmethod
    def process(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        Process data through bridge.
        
        Args:
            data: Input data
            context: Processing context
            
        Returns:
            Processed data
        """
        pass
    
    def validate_config(self) -> bool:
        """
        Validate bridge configuration.
        
        Returns:
            True if valid
        """
        return True
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check results
        """
        return {
            'status': self.status.value,
            'usage_count': self.usage_count,
            'error_count': self.error_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'created_at': self.created_at.isoformat(),
        }
    
    def enable(self):
        """Enable bridge."""
        self.status = BridgeStatus.ACTIVE
        self.logger.info(f"Bridge enabled: {self.name}")
    
    def disable(self):
        """Disable bridge."""
        self.status = BridgeStatus.INACTIVE
        self.logger.info(f"Bridge disabled: {self.name}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            'name': self.name,
            'type': self.bridge_type.value,
            'source': self.source,
            'target': self.target,
            'status': self.status.value,
            'usage_count': self.usage_count,
            'error_count': self.error_count,
            'success_rate': ((self.usage_count - self.error_count) / self.usage_count * 100) if self.usage_count > 0 else 0,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
        }


class ProtocolBridge(Bridge):
    """
    Bridge for protocol adaptation.
    
    Handles conversion between different protocols
    (HTTP, WebSocket, gRPC, etc.).
    """
    
    def __init__(self, config: BridgeConfig):
        super().__init__(config)
        self.source_protocol = config.config.get('source_protocol')
        self.target_protocol = config.config.get('target_protocol')
    
    def process(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process protocol bridge data."""
        context = context or {}
        self.usage_count += 1
        self.last_used = timezone.now()
        
        try:
            # Validate input data
            if not self._validate_input(data):
                raise IntegrationException("Invalid input data for protocol bridge")
            
            # Transform data from source to target protocol
            transformed_data = self._transform_protocol(data, context)
            
            # Apply protocol-specific transformations
            processed_data = self._apply_protocol_transformations(transformed_data, context)
            
            return processed_data
        
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error in protocol bridge: {str(e)}")
            raise IntegrationException(f"Protocol bridge processing failed: {str(e)}")
    
    def _validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        return isinstance(data, dict) and 'protocol' in data
    
    def _transform_protocol(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Transform protocol data."""
        transformed = data.copy()
        
        # Update protocol
        transformed['protocol'] = self.target_protocol.value
        
        # Apply protocol-specific transformations
        if self.source_protocol == IntegrationProtocol.HTTP and self.target_protocol == IntegrationProtocol.HTTPS:
            transformed['url'] = transformed.get('url', '').replace('http://', 'https://')
            transformed['port'] = transformed.get('port', 443)
        
        elif self.source_protocol == IntegrationProtocol.HTTPS and self.target_protocol == IntegrationProtocol.HTTP:
            transformed['url'] = transformed.get('url', '').replace('https://', 'http://')
            transformed['port'] = transformed.get('port', 80)
        
        return transformed
    
    def _apply_protocol_transformations(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply protocol-specific transformations."""
        # Apply data transformer
        return self.transformer.transform_request(data, context)


class DataBridge(Bridge):
    """
    Bridge for data transformation.
    
    Handles conversion between different data formats
    (JSON, XML, CSV, etc.).
    """
    
    def __init__(self, config: BridgeConfig):
        super().__init__(config)
        self.source_format = config.config.get('source_format', 'json')
        self.target_format = config.config.get('target_format', 'json')
    
    def process(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """Process data bridge data."""
        context = context or {}
        self.usage_count += 1
        self.last_used = timezone.now()
        
        try:
            # Convert source format to internal format
            internal_data = self._convert_to_internal(data, self.source_format)
            
            # Apply data transformations
            transformed_data = self.transformer.transform_request(internal_data, context)
            
            # Convert internal format to target format
            output_data = self._convert_from_internal(transformed_data, self.target_format)
            
            return output_data
        
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error in data bridge: {str(e)}")
            raise IntegrationException(f"Data bridge processing failed: {str(e)}")
    
    def _convert_to_internal(self, data: Any, source_format: str) -> Dict[str, Any]:
        """Convert data from source format to internal format."""
        if source_format == 'json':
            if isinstance(data, str):
                import json
                return json.loads(data)
            elif isinstance(data, dict):
                return data
            else:
                raise IntegrationException(f"Cannot convert {type(data)} to JSON")
        
        elif source_format == 'xml':
            if isinstance(data, str):
                import xml.etree.ElementTree as ET
                root = ET.fromstring(data)
                return self._xml_to_dict(root)
            else:
                raise IntegrationException(f"Cannot convert {type(data)} to XML")
        
        elif source_format == 'csv':
            if isinstance(data, str):
                import csv
                import io
                reader = csv.DictReader(io.StringIO(data))
                return list(reader)
            else:
                raise IntegrationException(f"Cannot convert {type(data)} to CSV")
        
        elif source_format == 'form':
            if isinstance(data, dict):
                return data
            else:
                raise IntegrationException(f"Cannot convert {type(data)} to form")
        
        else:
            return data
    
    def _convert_from_internal(self, data: Dict[str, Any], target_format: str) -> Any:
        """Convert data from internal format to target format."""
        if target_format == 'json':
            import json
            return json.dumps(data, default=str)
        
        elif target_format == 'xml':
            import xml.etree.ElementTree as ET
            root = self._dict_to_xml(data, 'root')
            return ET.tostring(root, encoding='unicode')
        
        elif target_format == 'csv':
            import csv
            import io
            if isinstance(data, list):
                output = io.StringIO()
                if data:
                    writer = csv.DictWriter(output, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                return output.getvalue()
            else:
                raise IntegrationException("Cannot convert dict to CSV")
        
        elif target_format == 'form':
            return data
        
        else:
            return data
    
    def _xml_to_dict(self, element) -> Dict[str, Any]:
        """Convert XML element to dictionary."""
        result = {}
        
        for child in element:
            if len(child) == 0:
                result[child.tag] = child.text
            elif len(child) == 1 and list(child)[0].tag == child.tag:
                result[child.tag] = self._xml_to_dict(list(child)[0])
            else:
                result[child.tag] = [self._xml_to_dict(grandchild) for grandchild in child]
        
        return result
    
    def _dict_to_xml(self, data: Dict[str, Any], root_name: str) -> Any:
        """Convert dictionary to XML element."""
        import xml.etree.ElementTree as ET
        
        root = ET.Element(root_name)
        
        def build_xml(parent, key, value):
            if isinstance(value, dict):
                child = ET.SubElement(parent, key)
                for k, v in value.items():
                    build_xml(child, k, v)
            elif isinstance(value, list):
                for item in value:
                    build_xml(parent, key, item)
            else:
                child = ET.SubElement(parent, key)
                child.text = str(value)
        
        for key, value in data.items():
            build_xml(root, key, value)
        
        return root


class ServiceBridge(Bridge):
    """
    Bridge for service integration.
    
    Handles communication between different services
    and service orchestration.
    """
    
    def __init__(self, config: BridgeConfig):
        super().__init__(config)
        self.source_service = config.config.get('source_service')
        self.target_service = config.config.get('target_service')
        self.service_mapping = config.config.get('service_mapping', {})
    
    def process(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process service bridge data."""
        context = context or {}
        self.usage_count += 1
        self.last_used = timezone.now()
        
        try:
            # Validate service mapping
            if not self._validate_service_mapping(data):
                raise IntegrationException("Invalid service mapping")
            
            # Transform service call
            transformed_data = self._transform_service_call(data, context)
            
            # Execute service bridge
            response = self._execute_service_bridge(transformed_data, context)
            
            return response
        
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error in service bridge: {str(e)}")
            raise IntegrationException(f"Service bridge processing failed: {str(e)}")
    
    def _validate_service_mapping(self, data: Dict[str, Any]) -> bool:
        """Validate service mapping."""
        return 'service' in data and data['service'] in self.service_mapping
    
    def _transform_service_call(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Transform service call."""
        service = data['service']
        mapping = self.service_mapping.get(service, {})
        
        transformed = data.copy()
        
        # Apply service mapping
        if 'endpoint' in mapping:
            transformed['endpoint'] = mapping['endpoint']
        
        if 'method' in mapping:
            transformed['method'] = mapping['method']
        
        if 'headers' in mapping:
            transformed['headers'] = {**transformed.get('headers', {}), **mapping['headers']}
        
        if 'auth' in mapping:
            transformed['auth'] = mapping['auth']
        
        return transformed
    
    def _execute_service_bridge(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute service bridge."""
        # This would integrate with service discovery and orchestration
        # For now, simulate service bridge execution
        
        return {
            'status': 'success',
            'message': f"Service bridge executed from {self.source_service} to {self.target_service}",
            'original_data': data,
            'processed_at': timezone.now().isoformat(),
        }


class EventBridge(Bridge):
    """
    Bridge for event processing.
    
    Handles event routing, filtering, and transformation
    between different event systems.
    """
    
    def __init__(self, config: BridgeConfig):
        super().__init__(config)
        self.event_filter = config.config.get('event_filter', {})
        self.event_router = config.config.get('event_router', {})
        self.event_transformer = config.config.get('event_transformer', {})
    
    def process(self, event_data: Dict[str, Any], context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Process event bridge data."""
        context = context or {}
        self.usage_count += 1
        self.last_used = timezone.now()
        
        try:
            # Filter events
            if not self._filter_event(event_data):
                return []
            
            # Transform event
            transformed_event = self._transform_event(event_data, context)
            
            # Route event
            routed_events = self._route_event(transformed_event, context)
            
            return routed_events
        
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error in event bridge: {str(e)}")
            raise IntegrationException(f"Event bridge processing failed: {str(e)}")
    
    def _filter_event(self, event_data: Dict[str, Any]) -> bool:
        """Filter event based on configured rules."""
        event_type = event_data.get('event_type')
        
        if not event_type:
            return False
        
        # Check if event type is allowed
        allowed_types = self.event_filter.get('allowed_types', [])
        if allowed_types and event_type not in allowed_types:
            return False
        
        # Check if event type is blocked
        blocked_types = self.event_filter.get('blocked_types', [])
        if blocked_types and event_type in blocked_types:
            return False
        
        return True
    
    def _transform_event(self, event_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Transform event data."""
        event_type = event_data.get('event_type')
        transformer_config = self.event_transformer.get(event_type, {})
        
        if transformer_config:
            # Apply event-specific transformations
            for field, transformation in transformer_config.items():
                if field in event_data:
                    event_data[field] = self._apply_transformation(event_data[field], transformation)
        
        return event_data
    
    def _apply_transformation(self, value: Any, transformation: Dict[str, Any]) -> Any:
        """Apply transformation to value."""
        transform_type = transformation.get('type', 'identity')
        
        if transform_type == 'identity':
            return value
        elif transform_type == 'uppercase':
            return str(value).upper()
        elif transform_type == 'lowercase':
            return str(value).lower()
        elif transform_type == 'format':
            format_string = transformation.get('format', '{}')
            return format_string.format(value)
        elif transform_type == 'map':
            mapping = transformation.get('mapping', {})
            return mapping.get(value, value)
        else:
            return value
    
    def _route_event(self, event_data: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Route event to multiple destinations."""
        event_type = event_data.get('event_type')
        routing_config = self.event_router.get(event_type, {})
        
        routed_events = []
        
        # Route to configured destinations
        destinations = routing_config.get('destinations', [])
        for destination in destinations:
            routed_event = event_data.copy()
            routed_event['destination'] = destination
            routed_event['routed_at'] = timezone.now().isoformat()
            routed_events.append(routed_event)
        
        return routed_events


class BridgeManager:
    """
    Manager for all bridges.
    
    Handles bridge registration, discovery, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bridges: Dict[str, Bridge] = {}
        self.bridge_configs: Dict[str, BridgeConfig] = {}
        self._setup_default_bridges()
    
    def _setup_default_bridges(self):
        """Setup default bridges."""
        default_bridges = [
            BridgeConfig(
                name="http_to_https",
                bridge_type=BridgeType.PROTOCOL,
                source="http",
                target="https",
                config={
                    'source_protocol': IntegrationProtocol.HTTP,
                    'target_protocol': IntegrationProtocol.HTTPS,
                }
            ),
            BridgeConfig(
                name="json_to_xml",
                bridge_type=BridgeType.DATA,
                source="json",
                target="xml",
                config={
                    'source_format': 'json',
                    'target_format': 'xml',
                }
            ),
            BridgeConfig(
                name="service_orchestrator",
                bridge_type=BridgeType.SERVICE,
                source="webhook_service",
                target="api_service",
                config={
                    'service_mapping': {
                        'webhook_to_api': {
                            'endpoint': '/api/v1/webhook',
                            'method': 'POST',
                        }
                    }
                }
            ),
        ]
        
        for bridge_config in default_bridges:
            self.register_bridge(bridge_config)
    
    def register_bridge(self, config: BridgeConfig) -> bool:
        """
        Register bridge.
        
        Args:
            config: Bridge configuration
            
        Returns:
            True if registered successfully
        """
        try:
            # Create bridge instance
            if config.bridge_type == BridgeType.PROTOCOL:
                bridge = ProtocolBridge(config)
            elif config.bridge_type == BridgeType.DATA:
                bridge = DataBridge(config)
            elif config.bridge_type == BridgeType.SERVICE:
                bridge = ServiceBridge(config)
            elif config.bridge_type == BridgeType.EVENT:
                bridge = EventBridge(config)
            else:
                raise IntegrationException(f"Unsupported bridge type: {config.bridge_type}")
            
            # Validate bridge
            if not bridge.validate_config():
                raise IntegrationException("Bridge configuration validation failed")
            
            # Register bridge
            self.bridges[config.name] = bridge
            self.bridge_configs[config.name] = config
            
            self.logger.info(f"Bridge registered: {config.name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to register bridge {config.name}: {str(e)}")
            return False
    
    def unregister_bridge(self, name: str) -> bool:
        """
        Unregister bridge.
        
        Args:
            name: Bridge name
            
        Returns:
            True if unregistered successfully
        """
        if name in self.bridges:
            del self.bridges[name]
            del self.bridge_configs[name]
            self.logger.info(f"Bridge unregistered: {name}")
            return True
        return False
    
    def get_bridge(self, name: str) -> Optional[Bridge]:
        """
        Get bridge by name.
        
        Args:
            name: Bridge name
            
        Returns:
            Bridge instance or None
        """
        return self.bridges.get(name)
    
    def get_bridges_by_type(self, bridge_type: BridgeType) -> List[Bridge]:
        """
        Get bridges by type.
        
        Args:
            bridge_type: Bridge type
            
        Returns:
            List of bridges
        """
        return [bridge for bridge in self.bridges.values() if bridge.bridge_type == bridge_type]
    
    def process_bridge(self, name: str, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        Process data through specific bridge.
        
        Args:
            name: Bridge name
            data: Input data
            context: Processing context
            
        Returns:
            Processed data
        """
        bridge = self.get_bridge(name)
        if not bridge:
            raise IntegrationException(f"Bridge not found: {name}")
        
        if bridge.status != BridgeStatus.ACTIVE:
            raise IntegrationException(f"Bridge not active: {name}")
        
        return bridge.process(data, context)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        stats = {
            'total_bridges': len(self.bridges),
            'active_bridges': len([b for b in self.bridges.values() if b.status == BridgeStatus.ACTIVE]),
            'bridge_types': {},
            'bridge_details': {},
        }
        
        # Count by type
        for bridge in self.bridges.values():
            bridge_type = bridge.bridge_type.value
            stats['bridge_types'][bridge_type] = stats['bridge_types'].get(bridge_type, 0) + 1
        
        # Bridge details
        for name, bridge in self.bridges.items():
            stats['bridge_details'][name] = bridge.get_statistics()
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all bridges."""
        health_status = {
            'overall': 'healthy',
            'total_bridges': len(self.bridges),
            'healthy_bridges': 0,
            'unhealthy_bridges': 0,
            'bridge_health': {},
            'issues': [],
        }
        
        for name, bridge in self.bridges.items():
            try:
                bridge_health = bridge.health_check()
                health_status['bridge_health'][name] = bridge_health
                
                if bridge_health['status'] == 'active':
                    health_status['healthy_bridges'] += 1
                else:
                    health_status['unhealthy_bridges'] += 1
                    health_status['issues'].append(f"Bridge {name} is {bridge_health['status']}")
            
            except Exception as e:
                health_status['unhealthy_bridges'] += 1
                health_status['issues'].append(f"Error checking bridge {name}: {str(e)}")
        
        if health_status['issues']:
            health_status['overall'] = 'unhealthy'
        
        return health_status


# Global bridge manager instance
bridge_manager = BridgeManager()


# Convenience functions
def register_bridge(config: BridgeConfig) -> bool:
    """Register bridge."""
    return bridge_manager.register_bridge(config)


def process_bridge(name: str, data: Any, context: Dict[str, Any] = None) -> Any:
    """Process data through bridge."""
    return bridge_manager.process_bridge(name, data, context)


def get_bridge_statistics() -> Dict[str, Any]:
    """Get bridge statistics."""
    return bridge_manager.get_statistics()


def perform_bridge_health_check() -> Dict[str, Any]:
    """Perform bridge health check."""
    return bridge_manager.health_check()
