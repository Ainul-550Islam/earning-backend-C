"""
Integration Bridge

Bridge for connecting external systems with
offer routing system using standardized protocols.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from .integ_handler import integration_handler
from .integ_signals import integration_signals
from .integ_constants import IntegrationType, IntegrationStatus
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class IntegrationBridge:
    """
    Bridge for connecting external systems.
    
    Provides standardized interface for:
    - System-to-system communication
    - Data transformation
    - Protocol translation
    - Error handling
    - Performance monitoring
    """
    
    def __init__(self):
        self.active_bridges = {}
        self.protocol_handlers = {}
        self.data_transformers = {}
        self.error_handlers = {}
        
        # Initialize default bridges
        self._initialize_default_bridges()
    
    def _initialize_default_bridges(self):
        """Initialize default bridges from configuration."""
        try:
            default_bridges = getattr(settings, 'DEFAULT_BRIDGES', {})
            
            for bridge_name, bridge_config in default_bridges.items():
                self.register_bridge(bridge_name, bridge_config)
                
        except Exception as e:
            logger.error(f"Error initializing default bridges: {e}")
    
    def register_bridge(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Register a new bridge.
        
        Args:
            name: Bridge name
            config: Bridge configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate bridge configuration
            if not self._validate_bridge_config(config):
                logger.error(f"Invalid bridge configuration for {name}")
                return False
            
            # Create bridge instance
            bridge = self._create_bridge(name, config)
            
            if bridge:
                self.active_bridges[name] = bridge
                
                # Emit signal
                integration_signals.bridge_registered.send(
                    sender=self.__class__,
                    bridge_name=name,
                    config=config
                )
                
                logger.info(f"Successfully registered bridge: {name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error registering bridge {name}: {e}")
            return False
    
    def _validate_bridge_config(self, config: Dict[str, Any]) -> bool:
        """Validate bridge configuration."""
        try:
            required_fields = ['target_system', 'protocol', 'endpoint']
            
            for field in required_fields:
                if field not in config:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate protocol
            protocol = config.get('protocol')
            if protocol not in ['http', 'https', 'websocket', 'mqtt', 'amqp']:
                logger.error(f"Invalid protocol: {protocol}")
                return False
            
            # Validate endpoint
            endpoint = config.get('endpoint')
            if not endpoint or not isinstance(endpoint, str):
                logger.error(f"Invalid endpoint: {endpoint}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating bridge config: {e}")
            return False
    
    def _create_bridge(self, name: str, config: Dict[str, Any]):
        """Create bridge instance from configuration."""
        try:
            protocol = config.get('protocol')
            
            if protocol in ['http', 'https']:
                from .http_bridge import HTTPBridge
                return HTTPBridge(name, config)
            elif protocol == 'websocket':
                from .websocket_bridge import WebSocketBridge
                return WebSocketBridge(name, config)
            elif protocol == 'mqtt':
                from .mqtt_bridge import MQTTBridge
                return MQTTBridge(name, config)
            elif protocol == 'amqp':
                from .amqp_bridge import AMQPBridge
                return AMQPBridge(name, config)
            else:
                logger.error(f"Unknown protocol: {protocol}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating bridge {name}: {e}")
            return None
    
    def send_message(self, bridge_name: str, message: Dict[str, Any], 
                   target_system: str = None) -> Dict[str, Any]:
        """
        Send message through bridge.
        
        Args:
            bridge_name: Bridge name
            message: Message to send
            target_system: Target system (optional)
            
        Returns:
            Send result
        """
        try:
            bridge = self.active_bridges.get(bridge_name)
            
            if not bridge:
                raise IntegrationError(f"Bridge not found: {bridge_name}")
            
            # Pre-send signal
            integration_signals.bridge_before_send.send(
                sender=self.__class__,
                bridge_name=bridge_name,
                message=message,
                target_system=target_system
            )
            
            # Send message
            result = bridge.send_message(message, target_system)
            
            # Post-send signal
            integration_signals.bridge_after_send.send(
                sender=self.__class__,
                bridge_name=bridge_name,
                message=message,
                target_system=target_system,
                result=result
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending message through bridge {bridge_name}: {e}")
            
            # Error signal
            integration_signals.bridge_error.send(
                sender=self.__class__,
                bridge_name=bridge_name,
                error=str(e),
                message=message
            )
            
            raise IntegrationError(f"Bridge send failed: {e}")
    
    def receive_message(self, bridge_name: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive message from bridge.
        
        Args:
            bridge_name: Bridge name
            message: Received message
            
        Returns:
            Processing result
        """
        try:
            bridge = self.active_bridges.get(bridge_name)
            
            if not bridge:
                raise IntegrationError(f"Bridge not found: {bridge_name}")
            
            # Pre-receive signal
            integration_signals.bridge_before_receive.send(
                sender=self.__class__,
                bridge_name=bridge_name,
                message=message
            )
            
            # Process message
            result = bridge.receive_message(message)
            
            # Post-receive signal
            integration_signals.bridge_after_receive.send(
                sender=self.__class__,
                bridge_name=bridge_name,
                message=message,
                result=result
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error receiving message from bridge {bridge_name}: {e}")
            
            # Error signal
            integration_signals.bridge_error.send(
                sender=self.__class__,
                bridge_name=bridge_name,
                error=str(e),
                message=message
            )
            
            raise IntegrationError(f"Bridge receive failed: {e}")
    
    def transform_data(self, bridge_name: str, data: Dict[str, Any], 
                     target_format: str) -> Dict[str, Any]:
        """
        Transform data for target system.
        
        Args:
            bridge_name: Bridge name
            data: Data to transform
            target_format: Target format
            
        Returns:
            Transformed data
        """
        try:
            bridge = self.active_bridges.get(bridge_name)
            
            if not bridge:
                raise IntegrationError(f"Bridge not found: {bridge_name}")
            
            # Get transformer for target format
            transformer = self.data_transformers.get(target_format)
            
            if not transformer:
                # Use default transformer
                transformer = self._default_transformer
            
            return transformer(data, target_format)
            
        except Exception as e:
            logger.error(f"Error transforming data for bridge {bridge_name}: {e}")
            raise IntegrationError(f"Data transformation failed: {e}")
    
    def _default_transformer(self, data: Dict[str, Any], target_format: str) -> Dict[str, Any]:
        """Default data transformer."""
        try:
            if target_format == 'json':
                return data
            elif target_format == 'xml':
                return self._to_xml(data)
            elif target_format == 'csv':
                return self._to_csv(data)
            else:
                return data
                
        except Exception as e:
            logger.error(f"Error in default transformer: {e}")
            return data
    
    def _to_xml(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert data to XML format."""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.Element('data')
            
            def dict_to_xml(parent, dict_data):
                for key, value in dict_data.items():
                    if isinstance(value, dict):
                        child = ET.SubElement(parent, key)
                        dict_to_xml(child, value)
                    elif isinstance(value, list):
                        for item in value:
                            child = ET.SubElement(parent, key)
                            child.text = str(item)
                    else:
                        child = ET.SubElement(parent, key)
                        child.text = str(value)
            
            dict_to_xml(root, data)
            
            return {
                'format': 'xml',
                'data': ET.tostring(root, encoding='unicode')
            }
            
        except Exception as e:
            logger.error(f"Error converting to XML: {e}")
            return {'format': 'xml', 'data': ''}
    
    def _to_csv(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert data to CSV format."""
        try:
            import csv
            from io import StringIO
            
            output = StringIO()
            
            if not data:
                return {'format': 'csv', 'data': ''}
            
            # Get keys from first item
            if isinstance(data, dict):
                keys = data.keys()
                values = [data]
            elif isinstance(data, list) and data:
                keys = data[0].keys()
                values = data
            else:
                return {'format': 'csv', 'data': ''}
            
            writer = csv.DictWriter(output, fieldnames=keys)
            writer.writeheader()
            writer.writerows(values)
            
            return {
                'format': 'csv',
                'data': output.getvalue()
            }
            
        except Exception as e:
            logger.error(f"Error converting to CSV: {e}")
            return {'format': 'csv', 'data': ''}
    
    def register_transformer(self, format_name: str, transformer: Callable) -> bool:
        """
        Register custom data transformer.
        
        Args:
            format_name: Format name
            transformer: Transformer function
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.data_transformers[format_name] = transformer
            logger.info(f"Registered transformer for format: {format_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering transformer: {e}")
            return False
    
    def get_bridge_status(self, bridge_name: str) -> Dict[str, Any]:
        """
        Get status of a specific bridge.
        
        Args:
            bridge_name: Bridge name
            
        Returns:
            Bridge status
        """
        try:
            bridge = self.active_bridges.get(bridge_name)
            
            if not bridge:
                return {
                    'status': IntegrationStatus.NOT_FOUND.value,
                    'message': 'Bridge not found'
                }
            
            return bridge.get_status()
            
        except Exception as e:
            logger.error(f"Error getting bridge status {bridge_name}: {e}")
            return {
                'status': IntegrationStatus.ERROR.value,
                'message': str(e)
            }
    
    def list_bridges(self, protocol: str = None) -> List[Dict[str, Any]]:
        """
        List all registered bridges.
        
        Args:
            protocol: Filter by protocol
            
        Returns:
            List of bridges
        """
        try:
            bridges = []
            
            for bridge_name, bridge in self.active_bridges.items():
                if protocol and bridge.get_protocol() != protocol:
                    continue
                
                bridges.append({
                    'name': bridge_name,
                    'protocol': bridge.get_protocol(),
                    'target_system': bridge.get_target_system(),
                    'status': bridge.get_status(),
                    'config': bridge.get_safe_config()
                })
            
            return bridges
            
        except Exception as e:
            logger.error(f"Error listing bridges: {e}")
            return []
    
    def enable_bridge(self, bridge_name: str) -> bool:
        """
        Enable a bridge.
        
        Args:
            bridge_name: Bridge name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bridge = self.active_bridges.get(bridge_name)
            
            if not bridge:
                logger.error(f"Bridge not found: {bridge_name}")
                return False
            
            # Enable bridge
            result = bridge.enable()
            
            if result:
                # Emit enable signal
                integration_signals.bridge_enabled.send(
                    sender=self.__class__,
                    bridge_name=bridge_name
                )
                
                logger.info(f"Enabled bridge {bridge_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error enabling bridge {bridge_name}: {e}")
            return False
    
    def disable_bridge(self, bridge_name: str) -> bool:
        """
        Disable a bridge.
        
        Args:
            bridge_name: Bridge name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bridge = self.active_bridges.get(bridge_name)
            
            if not bridge:
                logger.error(f"Bridge not found: {bridge_name}")
                return False
            
            # Disable bridge
            result = bridge.disable()
            
            if result:
                # Emit disable signal
                integration_signals.bridge_disabled.send(
                    sender=self.__class__,
                    bridge_name=bridge_name
                )
                
                logger.info(f"Disabled bridge {bridge_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error disabling bridge {bridge_name}: {e}")
            return False
    
    def remove_bridge(self, bridge_name: str) -> bool:
        """
        Remove a bridge completely.
        
        Args:
            bridge_name: Bridge name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bridge = self.active_bridges.get(bridge_name)
            
            if not bridge:
                logger.error(f"Bridge not found: {bridge_name}")
                return False
            
            # Disable first
            bridge.disable()
            
            # Remove from active bridges
            del self.active_bridges[bridge_name]
            
            # Emit remove signal
            integration_signals.bridge_removed.send(
                sender=self.__class__,
                bridge_name=bridge_name
            )
            
            logger.info(f"Removed bridge {bridge_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing bridge {bridge_name}: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all bridges.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall_status': 'healthy',
                'bridges': {},
                'timestamp': timezone.now().isoformat()
            }
            
            for bridge_name, bridge in self.active_bridges.items():
                bridge_health = bridge.health_check()
                health_status['bridges'][bridge_name] = bridge_health
                
                # Update overall status if any bridge is unhealthy
                if bridge_health.get('status') != 'healthy':
                    health_status['overall_status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error performing bridge health check: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def get_bridge_metrics(self, bridge_name: str = None) -> Dict[str, Any]:
        """
        Get metrics for bridges.
        
        Args:
            bridge_name: Specific bridge name (None for all)
            
        Returns:
            Bridge metrics
        """
        try:
            if bridge_name:
                bridge = self.active_bridges.get(bridge_name)
                
                if not bridge:
                    return {'error': f'Bridge not found: {bridge_name}'}
                
                return bridge.get_metrics()
            
            # Get metrics for all bridges
            all_metrics = {}
            
            for name, bridge in self.active_bridges.items():
                all_metrics[name] = bridge.get_metrics()
            
            return all_metrics
            
        except Exception as e:
            logger.error(f"Error getting bridge metrics: {e}")
            return {'error': str(e)}


# Global bridge instance
integration_bridge = IntegrationBridge()
