"""
Integration Adapter for alerts app - Adapter pattern for external system compatibility
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class IntegrationAdapter(ABC):
    """Abstract base adapter for external system integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.version = getattr(self.__class__, 'VERSION', '1.0.0')
        self.supported_formats = getattr(self.__class__, 'SUPPORTED_FORMATS', ['json'])
        self.timeout = config.get('timeout', 30)
        self.retry_count = config.get('retry_count', 3)
        self.retry_delay = config.get('retry_delay', 60)
        
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the adapter"""
        raise NotImplementedError("Subclasses must implement initialize method")
    
    @abstractmethod
    def send_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert data to external system"""
        raise NotImplementedError("Subclasses must implement send_alert method")
    
    @abstractmethod
    def receive_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Receive alert data from external system"""
        raise NotImplementedError("Subclasses must implement receive_alerts method")
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check adapter health"""
        raise NotImplementedError("Subclasses must implement health_check method")
    
    @abstractmethod
    def cleanup(self) -> bool:
        """Cleanup adapter resources"""
        raise NotImplementedError("Subclasses must implement cleanup method")
    
    def transform_outgoing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform outgoing data to external format"""
        return data
    
    def transform_incoming(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform incoming data to internal format"""
        return data
    
    def validate_outgoing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate outgoing data"""
        return {'valid': True, 'errors': []}
    
    def validate_incoming(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate incoming data"""
        return {'valid': True, 'errors': []}
    
    def get_adapter_info(self) -> Dict[str, Any]:
        """Get adapter information"""
        return {
            'name': self.name,
            'version': self.version,
            'supported_formats': self.supported_formats,
            'config': self.config,
            'initialized': getattr(self, '_initialized', False)
        }


class JSONAdapter(IntegrationAdapter):
    """JSON adapter for systems using JSON format"""
    
    VERSION = '1.0.0'
    SUPPORTED_FORMATS = ['json', 'application/json']
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pretty_print = config.get('pretty_print', False)
        self.indent = config.get('indent', 2)
        
    def initialize(self) -> bool:
        """Initialize JSON adapter"""
        try:
            import json
            self.json_module = json
            self._initialized = True
            logger.info(f"JSON adapter {self.name} initialized")
            return True
        except ImportError as e:
            logger.error(f"JSON adapter initialization failed: {e}")
            return False
    
    def send_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert as JSON"""
        if not getattr(self, '_initialized', False):
            return {'success': False, 'error': 'Adapter not initialized'}
        
        try:
            # Validate outgoing data
            validation = self.validate_outgoing(alert_data)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation['errors']
                }
            
            # Transform data
            transformed_data = self.transform_outgoing(alert_data)
            
            # Convert to JSON
            if self.pretty_print:
                json_data = self.json_module.dumps(
                    transformed_data,
                    indent=self.indent,
                    sort_keys=True
                )
            else:
                json_data = self.json_module.dumps(transformed_data)
            
            return {
                'success': True,
                'data': json_data,
                'format': 'json',
                'size': len(json_data)
            }
            
        except Exception as e:
            logger.error(f"Error sending JSON alert: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def receive_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Receive alerts from JSON data"""
        if not getattr(self, '_initialized', False):
            return []
        
        try:
            # This would typically fetch from external source
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error receiving JSON alerts: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check JSON adapter health"""
        return {
            'healthy': getattr(self, '_initialized', False),
            'format': 'json',
            'supported_formats': self.supported_formats,
            'last_check': timezone.now().isoformat()
        }
    
    def cleanup(self) -> bool:
        """Cleanup JSON adapter"""
        self._initialized = False
        logger.info(f"JSON adapter {self.name} cleaned up")
        return True


class XMLAdapter(IntegrationAdapter):
    """XML adapter for systems using XML format"""
    
    VERSION = '1.0.0'
    SUPPORTED_FORMATS = ['xml', 'application/xml']
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.root_element = config.get('root_element', 'alerts')
        self.item_element = config.get('item_element', 'alert')
        self.encoding = config.get('encoding', 'utf-8')
        
    def initialize(self) -> bool:
        """Initialize XML adapter"""
        try:
            import xml.etree.ElementTree as ET
            self.xml_module = ET
            self._initialized = True
            logger.info(f"XML adapter {self.name} initialized")
            return True
        except ImportError as e:
            logger.error(f"XML adapter initialization failed: {e}")
            return False
    
    def send_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert as XML"""
        if not getattr(self, '_initialized', False):
            return {'success': False, 'error': 'Adapter not initialized'}
        
        try:
            # Validate outgoing data
            validation = self.validate_outgoing(alert_data)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation['errors']
                }
            
            # Transform data
            transformed_data = self.transform_outgoing(alert_data)
            
            # Convert to XML
            root = self.xml_module.Element(self.root_element)
            
            # Add alert item
            alert_elem = self.xml_module.SubElement(root, self.item_element)
            
            # Add fields as sub-elements
            for key, value in transformed_data.items():
                if isinstance(value, dict):
                    # Handle nested objects
                    nested_elem = self.xml_module.SubElement(alert_elem, key)
                    for nested_key, nested_value in value.items():
                        nested_sub = self.xml_module.SubElement(nested_elem, nested_key)
                        nested_sub.text = str(nested_value)
                elif isinstance(value, list):
                    # Handle arrays
                    for item in value:
                        item_elem = self.xml_module.SubElement(alert_elem, key)
                        item_elem.text = str(item)
                else:
                    # Handle simple values
                    elem = self.xml_module.SubElement(alert_elem, key)
                    elem.text = str(value)
            
            # Generate XML string
            xml_data = self.xml_module.tostring(root, encoding=self.encoding)
            
            return {
                'success': True,
                'data': xml_data.decode(self.encoding),
                'format': 'xml',
                'size': len(xml_data)
            }
            
        except Exception as e:
            logger.error(f"Error sending XML alert: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def receive_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Receive alerts from XML data"""
        if not getattr(self, '_initialized', False):
            return []
        
        try:
            # This would typically fetch from external source
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error receiving XML alerts: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check XML adapter health"""
        return {
            'healthy': getattr(self, '_initialized', False),
            'format': 'xml',
            'supported_formats': self.supported_formats,
            'last_check': timezone.now().isoformat()
        }
    
    def cleanup(self) -> bool:
        """Cleanup XML adapter"""
        self._initialized = False
        logger.info(f"XML adapter {self.name} cleaned up")
        return True


class CSVAdapter(IntegrationAdapter):
    """CSV adapter for systems using CSV format"""
    
    VERSION = '1.0.0'
    SUPPORTED_FORMATS = ['csv', 'text/csv']
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.delimiter = config.get('delimiter', ',')
        self.quotechar = config.get('quotechar', '"')
        self.include_headers = config.get('include_headers', True)
        self.field_order = config.get('field_order', [])
        
    def initialize(self) -> bool:
        """Initialize CSV adapter"""
        try:
            import csv
            import io
            self.csv_module = csv
            self.io_module = io
            self._initialized = True
            logger.info(f"CSV adapter {self.name} initialized")
            return True
        except ImportError as e:
            logger.error(f"CSV adapter initialization failed: {e}")
            return False
    
    def send_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert as CSV"""
        if not getattr(self, '_initialized', False):
            return {'success': False, 'error': 'Adapter not initialized'}
        
        try:
            # Validate outgoing data
            validation = self.validate_outgoing(alert_data)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation['errors']
                }
            
            # Transform data
            transformed_data = self.transform_outgoing(alert_data)
            
            # Convert to CSV
            output = self.io_module.StringIO()
            writer = self.csv_module.writer(
                output,
                delimiter=self.delimiter,
                quotechar=self.quotechar
            )
            
            # Write headers if configured
            if self.include_headers:
                if self.field_order:
                    headers = self.field_order
                else:
                    headers = list(transformed_data.keys())
                writer.writerow(headers)
            
            # Write data row
            if self.field_order:
                row = [transformed_data.get(field, '') for field in self.field_order]
            else:
                row = list(transformed_data.values())
            writer.writerow(row)
            
            csv_data = output.getvalue()
            
            return {
                'success': True,
                'data': csv_data,
                'format': 'csv',
                'size': len(csv_data)
            }
            
        except Exception as e:
            logger.error(f"Error sending CSV alert: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def receive_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Receive alerts from CSV data"""
        if not getattr(self, '_initialized', False):
            return []
        
        try:
            # This would typically fetch from external source
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error receiving CSV alerts: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check CSV adapter health"""
        return {
            'healthy': getattr(self, '_initialized', False),
            'format': 'csv',
            'supported_formats': self.supported_formats,
            'last_check': timezone.now().isoformat()
        }
    
    def cleanup(self) -> bool:
        """Cleanup CSV adapter"""
        self._initialized = False
        logger.info(f"CSV adapter {self.name} cleaned up")
        return True


class ProtocolAdapter(IntegrationAdapter):
    """Protocol adapter for different communication protocols"""
    
    VERSION = '1.0.0'
    SUPPORTED_FORMATS = ['http', 'https', 'tcp', 'udp', 'websocket']
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.protocol = config.get('protocol', 'http')
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', 8080)
        self.path = config.get('path', '/')
        self.use_ssl = config.get('use_ssl', False)
        
    def initialize(self) -> bool:
        """Initialize protocol adapter"""
        try:
            if self.protocol in ['http', 'https']:
                import requests
                self.http_module = requests
            elif self.protocol in ['tcp', 'udp']:
                import socket
                self.socket_module = socket
            elif self.protocol == 'websocket':
                import websockets
                self.websocket_module = websockets
            
            self._initialized = True
            logger.info(f"Protocol adapter {self.name} ({self.protocol}) initialized")
            return True
        except ImportError as e:
            logger.error(f"Protocol adapter initialization failed: {e}")
            return False
    
    def send_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert using configured protocol"""
        if not getattr(self, '_initialized', False):
            return {'success': False, 'error': 'Adapter not initialized'}
        
        try:
            # Validate outgoing data
            validation = self.validate_outgoing(alert_data)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation['errors']
                }
            
            # Transform data
            transformed_data = self.transform_outgoing(alert_data)
            
            if self.protocol in ['http', 'https']:
                return self._send_http(transformed_data)
            elif self.protocol == 'tcp':
                return self._send_tcp(transformed_data)
            elif self.protocol == 'udp':
                return self._send_udp(transformed_data)
            elif self.protocol == 'websocket':
                return self._send_websocket(transformed_data)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported protocol: {self.protocol}'
                }
                
        except Exception as e:
            logger.error(f"Error sending protocol alert: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _send_http(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via HTTP/HTTPS"""
        url = f"{'https' if self.use_ssl else 'http'}://{self.host}:{self.port}{self.path}"
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'AlertSystem/{self.name}/{self.version}'
        }
        
        response = self.http_module.post(
            url,
            json=data,
            headers=headers,
            timeout=self.timeout
        )
        
        return {
            'success': response.status_code in [200, 201, 202],
            'response_code': response.status_code,
            'response_text': response.text,
            'protocol': self.protocol
        }
    
    def _send_tcp(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via TCP"""
        import json
        
        # Convert data to JSON string
        json_data = json.dumps(data)
        
        # Create TCP socket
        sock = self.socket_module.socket(self.socket_module.AF_INET, self.socket_module.SOCK_STREAM)
        
        try:
            sock.connect((self.host, self.port))
            sock.sendall(json_data.encode('utf-8'))
            
            # Receive response
            response = sock.recv(4096)
            sock.close()
            
            return {
                'success': True,
                'response': response.decode('utf-8'),
                'protocol': self.protocol
            }
        except Exception as e:
            sock.close()
            raise e
    
    def _send_udp(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via UDP"""
        import json
        
        # Convert data to JSON string
        json_data = json.dumps(data)
        
        # Create UDP socket
        sock = self.socket_module.socket(self.socket_module.AF_INET, self.socket_module.SOCK_DGRAM)
        
        try:
            sock.sendto(json_data.encode('utf-8'), (self.host, self.port))
            
            return {
                'success': True,
                'protocol': self.protocol
            }
        except Exception as e:
            sock.close()
            raise e
    
    def _send_websocket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via WebSocket"""
        import json
        import asyncio
        
        uri = f"{'wss' if self.use_ssl else 'ws'}://{self.host}:{self.port}{self.path}"
        
        async def send_websocket_data():
            async with self.websocket_module.connect(uri) as websocket:
                await websocket.send(json.dumps(data))
                response = await websocket.recv()
                return response
        
        try:
            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(send_websocket_data())
            loop.close()
            
            return {
                'success': True,
                'response': response,
                'protocol': self.protocol
            }
        except Exception as e:
            raise e
    
    def receive_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Receive alerts using configured protocol"""
        if not getattr(self, '_initialized', False):
            return []
        
        try:
            # This would typically listen for incoming data
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error receiving protocol alerts: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check protocol adapter health"""
        try:
            if self.protocol in ['http', 'https']:
                url = f"{'https' if self.use_ssl else 'http'}://{self.host}:{self.port}/health"
                response = self.http_module.get(url, timeout=5)
                healthy = response.status_code == 200
            else:
                # For other protocols, just check if initialized
                healthy = getattr(self, '_initialized', False)
            
            return {
                'healthy': healthy,
                'protocol': self.protocol,
                'host': self.host,
                'port': self.port,
                'last_check': timezone.now().isoformat()
            }
        except Exception:
            logger.exception("Unhandled error in health_check")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'last_check': timezone.now().isoformat()
            }
    
    def cleanup(self) -> bool:
        """Cleanup protocol adapter"""
        self._initialized = False
        logger.info(f"Protocol adapter {self.name} ({self.protocol}) cleaned up")
        return True


# Adapter factory
class AdapterFactory:
    """Factory for creating integration adapters"""
    
    _adapters = {
        'json': JSONAdapter,
        'xml': XMLAdapter,
        'csv': CSVAdapter,
        'http': ProtocolAdapter,
        'https': ProtocolAdapter,
        'tcp': ProtocolAdapter,
        'udp': ProtocolAdapter,
        'websocket': ProtocolAdapter
    }
    
    @classmethod
    def create_adapter(cls, adapter_type: str, config: Dict[str, Any]) -> Optional[IntegrationAdapter]:
        """Create adapter by type"""
        adapter_class = cls._adapters.get(adapter_type)
        if not adapter_class:
            logger.error(f"Unknown adapter type: {adapter_type}")
            return None
        
        try:
            return adapter_class(config)
        except Exception as e:
            logger.error(f"Error creating adapter {adapter_type}: {e}")
            return None
    
    @classmethod
    def register_adapter(cls, adapter_type: str, adapter_class: type):
        """Register a new adapter type"""
        cls._adapters[adapter_type] = adapter_class
        logger.info(f"Registered adapter: {adapter_type}")
    
    @classmethod
    def get_available_adapters(cls) -> List[str]:
        """Get list of available adapters"""
        return list(cls._adapters.keys())
    
    @classmethod
    def get_adapter_info(cls, adapter_type: str) -> Optional[Dict[str, Any]]:
        """Get adapter information"""
        adapter_class = cls._adapters.get(adapter_type)
        if not adapter_class:
            return None
        
        return {
            'type': adapter_type,
            'class': adapter_class.__name__,
            'version': getattr(adapter_class, 'VERSION', '1.0.0'),
            'supported_formats': getattr(adapter_class, 'SUPPORTED_FORMATS', [])
        }


# Utility functions
def create_adapter_chain(configs: List[Dict[str, Any]]) -> List[IntegrationAdapter]:
    """Create a chain of adapters"""
    adapters = []
    
    for config in configs:
        adapter_type = config.get('type', 'json')
        adapter = AdapterFactory.create_adapter(adapter_type, config)
        if adapter:
            adapters.append(adapter)
    
    return adapters


def send_through_adapters(alert_data: Dict[str, Any], adapters: List[IntegrationAdapter]) -> List[Dict[str, Any]]:
    """Send alert through multiple adapters"""
    results = []
    
    for adapter in adapters:
        try:
            result = adapter.send_alert(alert_data)
            result['adapter'] = adapter.name
            result['adapter_type'] = type(adapter).__name__
            results.append(result)
        except Exception as e:
            logger.error(f"Error sending through adapter {adapter.name}: {e}")
            results.append({
                'success': False,
                'error': str(e),
                'adapter': adapter.name
            })
    
    return results


def validate_adapter_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate adapter configuration"""
    errors = []
    
    # Check required fields
    if 'type' not in config:
        errors.append('Adapter type is required')
    
    # Check type-specific requirements
    adapter_type = config.get('type')
    
    if adapter_type in ['http', 'https', 'tcp', 'udp', 'websocket']:
        if 'host' not in config:
            errors.append('Host is required for protocol adapters')
        if 'port' not in config:
            errors.append('Port is required for protocol adapters')
    
    if adapter_type == 'csv':
        if 'delimiter' not in config:
            errors.append('Delimiter is required for CSV adapter')
    
    if adapter_type == 'xml':
        if 'root_element' not in config:
            errors.append('Root element is required for XML adapter')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


# ─────────────────────────────────────────────────────────────────
# Module-level singleton — used by bridge.py, data_bridge.py, etc.
# ─────────────────────────────────────────────────────────────────
class GenericIntegrationAdapter(IntegrationAdapter):
    """
    Concrete, generic adapter implementation used as a shared singleton
    for cross-module alert adaptation. Provides initialize/send_alert/
    receive_alerts/health_check/cleanup stubs plus adapt_external_alert(),
    which other integration modules call to normalize alert payloads
    coming from external systems (Prometheus, Datadog, etc.).
    """
    VERSION = '1.0.0'
    SUPPORTED_FORMATS = ['json', 'xml', 'csv']

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self._initialized = False

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def send_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        return {'success': True, 'sent': alert_data}

    def receive_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        return []

    def health_check(self) -> Dict[str, Any]:
        return {'status': 'healthy', 'initialized': self._initialized}

    def cleanup(self) -> bool:
        self._initialized = False
        return True

    def adapt_external_alert(self, source_system: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize an alert payload received from `source_system` (e.g.
        'prometheus', 'datadog', 'grafana') into the internal alert
        schema understood by api.alerts.integration.integ_handler.
        """
        try:
            adapted = self.transform_incoming(data)
            validation = self.validate_incoming(adapted)
            adapted.setdefault('source_system', source_system)
            adapted.setdefault('alert_type', adapted.get('alert_type', 'server_error'))
            adapted.setdefault('severity', adapted.get('severity', 'medium'))
            return {
                'source_system': source_system,
                'data': adapted,
                'validation': validation,
            }
        except Exception as e:
            logger.error(f"GenericIntegrationAdapter.adapt_external_alert error: {e}")
            return {'source_system': source_system, 'data': data, 'error': 'Operation failed'}


# Shared singleton instance
integration_adapter = GenericIntegrationAdapter()
