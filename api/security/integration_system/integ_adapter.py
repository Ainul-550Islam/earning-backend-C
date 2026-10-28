"""
Integration Adapter Module
Adapter pattern for integration system
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_handler import BaseIntegrationHandler

User = get_user_model()
logger = logging.getLogger('security.integration.adapter')


class IntegrationAdapter:
    """Base adapter for integration system"""
    
    def __init__(self, name: str, target_system: str):
        self.name = name
        self.target_system = target_system
        self.config = {}
        self.mappings = {}
        self.transformations = {}
        self.enabled = True
        self.connection_status = 'disconnected'
        self.last_activity = None
    
    def configure(self, config: Dict[str, Any]):
        """Configure adapter"""
        self.config = config
    
    def connect(self) -> bool:
        """Connect to target system"""
        try:
            # Implementation specific to target system
            self.connection_status = 'connected'
            self.last_activity = timezone.now()
            logger.info(f"Adapter {self.name} connected to {self.target_system}")
            return True
        except Exception as e:
            logger.error(f"Error connecting adapter {self.name}: {e}")
            self.connection_status = 'error'
            return False
    
    def disconnect(self):
        """Disconnect from target system"""
        try:
            # Implementation specific to target system
            self.connection_status = 'disconnected'
            logger.info(f"Adapter {self.name} disconnected from {self.target_system}")
        except Exception as e:
            logger.error(f"Error disconnecting adapter {self.name}: {e}")
    
    def send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to target system"""
        if not self.enabled or self.connection_status != 'connected':
            return {
                'status': 'error',
                'message': 'Adapter not ready'
            }
        
        try:
            # Transform data
            transformed_data = self.transform_data(data)
            
            # Send to target system
            result = self._send_to_target(transformed_data)
            
            self.last_activity = timezone.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending data via adapter {self.name}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def receive_data(self, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Receive data from target system"""
        if not self.enabled or self.connection_status != 'connected':
            return {
                'status': 'error',
                'message': 'Adapter not ready'
            }
        
        try:
            # Receive from target system
            raw_data = self._receive_from_target(query)
            
            # Transform data back
            transformed_data = self.reverse_transform_data(raw_data)
            
            self.last_activity = timezone.now()
            
            return {
                'status': 'success',
                'data': transformed_data
            }
            
        except Exception as e:
            logger.error(f"Error receiving data via adapter {self.name}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for target system"""
        transformed = data.copy()
        
        # Apply field mappings
        for source_field, target_field in self.mappings.items():
            if source_field in transformed:
                transformed[target_field] = transformed.pop(source_field)
        
        # Apply transformations
        for field, transformation in self.transformations.items():
            if field in transformed:
                try:
                    transformed[field] = transformation(transformed[field])
                except Exception as e:
                    logger.error(f"Error transforming field {field}: {e}")
        
        return transformed
    
    def reverse_transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse transform data from target system"""
        transformed = data.copy()
        
        # Reverse field mappings
        reverse_mappings = {v: k for k, v in self.mappings.items()}
        
        for source_field, target_field in reverse_mappings.items():
            if source_field in transformed:
                transformed[target_field] = transformed.pop(source_field)
        
        return transformed
    
    def _send_to_target(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to target system - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _send_to_target")
    
    def _receive_from_target(self, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Receive data from target system - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _receive_from_target")
    
    def add_mapping(self, source_field: str, target_field: str):
        """Add field mapping"""
        self.mappings[source_field] = target_field
    
    def add_transformation(self, field: str, transformation: Callable):
        """Add field transformation"""
        self.transformations[field] = transformation
    
    def enable(self):
        """Enable adapter"""
        self.enabled = True
    
    def disable(self):
        """Disable adapter"""
        self.enabled = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get adapter status"""
        return {
            'name': self.name,
            'target_system': self.target_system,
            'enabled': self.enabled,
            'connection_status': self.connection_status,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'mappings_count': len(self.mappings),
            'transformations_count': len(self.transformations)
        }


class HTTPAdapter(IntegrationAdapter):
    """HTTP adapter for REST API integrations"""
    
    def __init__(self, name: str, base_url: str):
        super().__init__(name, 'http_api')
        self.base_url = base_url
        self.session = None
        self.headers = {}
        self.auth = None
    
    def configure(self, config: Dict[str, Any]):
        """Configure HTTP adapter"""
        super().configure(config)
        
        self.headers = config.get('headers', {})
        self.auth = config.get('auth')
        self.timeout = config.get('timeout', 30)
    
    def connect(self) -> bool:
        """Connect to HTTP API"""
        try:
            import requests
            
            # Create session
            self.session = requests.Session()
            
            # Set headers
            if self.headers:
                self.session.headers.update(self.headers)
            
            # Set auth
            if self.auth:
                if self.auth.get('type') == 'basic':
                    from requests.auth import HTTPBasicAuth
                    self.session.auth = HTTPBasicAuth(
                        self.auth['username'],
                        self.auth['password']
                    )
                elif self.auth.get('type') == 'bearer':
                    self.session.headers['Authorization'] = f"Bearer {self.auth['token']}"
            
            # Test connection
            response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            
            if response.status_code == 200:
                self.connection_status = 'connected'
                self.last_activity = timezone.now()
                return True
            else:
                self.connection_status = 'error'
                return False
                
        except Exception as e:
            logger.error(f"Error connecting HTTP adapter {self.name}: {e}")
            self.connection_status = 'error'
            return False
    
    def disconnect(self):
        """Disconnect HTTP session"""
        if self.session:
            self.session.close()
            self.session = None
        
        super().disconnect()
    
    def _send_to_target(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via HTTP"""
        endpoint = self.config.get('send_endpoint', '/api/data')
        url = f"{self.base_url}{endpoint}"
        
        method = self.config.get('send_method', 'POST')
        
        if method.upper() == 'POST':
            response = self.session.post(url, json=data, timeout=self.timeout)
        elif method.upper() == 'PUT':
            response = self.session.put(url, json=data, timeout=self.timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        if response.status_code in [200, 201]:
            return {
                'status': 'success',
                'response_data': response.json() if response.content else None
            }
        else:
            return {
                'status': 'error',
                'message': f"HTTP {response.status_code}: {response.text}",
                'status_code': response.status_code
            }
    
    def _receive_from_target(self, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Receive data via HTTP"""
        endpoint = self.config.get('receive_endpoint', '/api/data')
        url = f"{self.base_url}{endpoint}"
        
        params = query or {}
        
        response = self.session.get(url, params=params, timeout=self.timeout)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")


class DatabaseAdapter(IntegrationAdapter):
    """Database adapter for database integrations"""
    
    def __init__(self, name: str, connection_string: str):
        super().__init__(name, 'database')
        self.connection_string = connection_string
        self.connection = None
    
    def connect(self) -> bool:
        """Connect to database"""
        try:
            import psycopg2  # PostgreSQL
            
            self.connection = psycopg2.connect(self.connection_string)
            
            # Test connection
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            self.connection_status = 'connected'
            self.last_activity = timezone.now()
            return True
            
        except Exception as e:
            logger.error(f"Error connecting database adapter {self.name}: {e}")
            self.connection_status = 'error'
            return False
    
    def disconnect(self):
        """Disconnect from database"""
        if self.connection:
            self.connection.close()
            self.connection = None
        
        super().disconnect()
    
    def _send_to_target(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to database"""
        table = self.config.get('table', 'integration_data')
        
        # Build INSERT query
        columns = list(data.keys())
        placeholders = ['%s'] * len(columns)
        
        query = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            RETURNING id
        """
        
        cursor = self.connection.cursor()
        
        try:
            cursor.execute(query, list(data.values()))
            self.connection.commit()
            
            row_id = cursor.fetchone()[0]
            
            return {
                'status': 'success',
                'inserted_id': row_id
            }
            
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def _receive_from_target(self, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Receive data from database"""
        table = self.config.get('table', 'integration_data')
        
        # Build SELECT query
        where_clause = ""
        params = []
        
        if query:
            conditions = []
            for key, value in query.items():
                conditions.append(f"{key} = %s")
                params.append(value)
            
            if conditions:
                where_clause = f" WHERE {' AND '.join(conditions)}"
        
        select_query = f"SELECT * FROM {table}{where_clause}"
        
        cursor = self.connection.cursor()
        
        try:
            cursor.execute(select_query, params)
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                result.append(row_dict)
            
            return {
                'data': result
            }
            
        finally:
            cursor.close()


class MessageQueueAdapter(IntegrationAdapter):
    """Message queue adapter for queue integrations"""
    
    def __init__(self, name: str, queue_url: str):
        super().__init__(name, 'message_queue')
        self.queue_url = queue_url
        self.connection = None
        self.channel = None
    
    def connect(self) -> bool:
        """Connect to message queue"""
        try:
            import pika
            
            self.connection = pika.BlockingConnection(pika.URLParameters(self.queue_url))
            self.channel = self.connection.channel()
            
            # Declare queue
            queue_name = self.config.get('queue_name', 'security_events')
            self.channel.queue_declare(queue=queue_name, durable=True)
            
            self.connection_status = 'connected'
            self.last_activity = timezone.now()
            return True
            
        except Exception as e:
            logger.error(f"Error connecting message queue adapter {self.name}: {e}")
            self.connection_status = 'error'
            return False
    
    def disconnect(self):
        """Disconnect from message queue"""
        if self.channel:
            self.channel.close()
            self.channel = None
        
        if self.connection:
            self.connection.close()
            self.connection = None
        
        super().disconnect()
    
    def _send_to_target(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to message queue"""
        import json
        import pika
        
        queue_name = self.config.get('queue_name', 'security_events')
        
        message = json.dumps(data)
        
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                )
            )
            
            return {
                'status': 'success',
                'message_id': SecurityUtils.generate_uuid()
            }
            
        except Exception as e:
            raise e
    
    def _receive_from_target(self, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Receive data from message queue"""
        import json
        import pika
        
        queue_name = self.config.get('queue_name', 'security_events')
        
        method_frame, header_frame, body = self.channel.basic_get(queue=queue_name)
        
        if method_frame:
            # Acknowledge message
            self.channel.basic_ack(method_frame.delivery_tag)
            
            try:
                data = json.loads(body)
                return data
            except json.JSONDecodeError:
                return {'raw_message': body.decode('utf-8')}
        else:
            return {'data': None}


class AdapterRegistry:
    """Registry for integration adapters"""
    
    def __init__(self):
        self.adapters = {}
        self.adapter_types = {
            'http': HTTPAdapter,
            'database': DatabaseAdapter,
            'message_queue': MessageQueueAdapter
        }
    
    def register_adapter(self, adapter: IntegrationAdapter):
        """Register an adapter"""
        self.adapters[adapter.name] = adapter
        logger.info(f"Registered adapter: {adapter.name}")
    
    def unregister_adapter(self, adapter_name: str) -> bool:
        """Unregister an adapter"""
        if adapter_name in self.adapters:
            adapter = self.adapters[adapter_name]
            adapter.disconnect()
            del self.adapters[adapter_name]
            logger.info(f"Unregistered adapter: {adapter_name}")
            return True
        return False
    
    def get_adapter(self, adapter_name: str) -> Optional[IntegrationAdapter]:
        """Get adapter by name"""
        return self.adapters.get(adapter_name)
    
    def create_adapter(self, adapter_type: str, name: str, **kwargs) -> Optional[IntegrationAdapter]:
        """Create a new adapter"""
        adapter_class = self.adapter_types.get(adapter_type)
        
        if not adapter_class:
            logger.error(f"Unknown adapter type: {adapter_type}")
            return None
        
        try:
            adapter = adapter_class(name, **kwargs)
            self.register_adapter(adapter)
            return adapter
        except Exception as e:
            logger.error(f"Error creating adapter {name}: {e}")
            return None
    
    def connect_all(self) -> Dict[str, bool]:
        """Connect all adapters"""
        results = {}
        
        for name, adapter in self.adapters.items():
            results[name] = adapter.connect()
        
        return results
    
    def disconnect_all(self):
        """Disconnect all adapters"""
        for adapter in self.adapters.values():
            adapter.disconnect()
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all adapters"""
        return {
            'total_adapters': len(self.adapters),
            'adapters': {
                name: adapter.get_status()
                for name, adapter in self.adapters.items()
            }
        }


# Global adapter registry
adapter_registry = AdapterRegistry()


# Export symbols
__all__ = [
    'IntegrationAdapter',
    'HTTPAdapter',
    'DatabaseAdapter',
    'MessageQueueAdapter',
    'AdapterRegistry',
    'adapter_registry'
]