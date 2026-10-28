# engagement/integration_system/integ_adapter.py
"""
Integration adapter system.
Provides adapters for different integration types and data transformation.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import base64

from django.utils import timezone
from django.conf import settings

from .integ_constants import (
    IntegrationType, DataType, HttpMethod, ERROR_CODES,
    TRANSFORMATION_RULES, VALIDATION_RULES
)

logger = logging.getLogger(__name__)


class AdapterType(Enum):
    """Types of adapters."""
    HTTP_ADAPTER = "http_adapter"
    DATABASE_ADAPTER = "database_adapter"
    MESSAGE_QUEUE_ADAPTER = "message_queue_adapter"
    EMAIL_ADAPTER = "email_adapter"
    SMS_ADAPTER = "sms_adapter"
    FILE_ADAPTER = "file_adapter"
    WEBHOOK_ADAPTER = "webhook_adapter"
    CUSTOM_ADAPTER = "custom_adapter"


@dataclass
class AdapterConfig:
    """Configuration for an adapter."""
    type: AdapterType
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1
    headers: Dict[str, str] = field(default_factory=dict)
    auth_config: Dict[str, Any] = field(default_factory=dict)
    transformation_config: Dict[str, Any] = field(default_factory=dict)
    validation_config: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """Base adapter class."""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._is_connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection."""
        pass
    
    @abstractmethod
    def send(self, data: Any, target: str = None) -> Any:
        """Send data through adapter."""
        pass
    
    @abstractmethod
    def receive(self, source: str = None) -> Any:
        """Receive data through adapter."""
        pass
    
    @abstractmethod
    def validate_data(self, data: Any) -> bool:
        """Validate data format."""
        pass
    
    @abstractmethod
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform data format."""
        pass
    
    def is_connected(self) -> bool:
        """Check if adapter is connected."""
        return self._is_connected
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.config.get(key, default)


class HTTPAdapter(BaseAdapter):
    """HTTP adapter for API and webhook integrations."""
    
    def connect(self) -> bool:
        """Test HTTP connectivity."""
        try:
            import requests
            
            # Test connection with a simple request
            test_url = self.get_config_value('test_url')
            if test_url:
                response = requests.get(
                    test_url,
                    timeout=self.config.timeout,
                    headers=self.config.headers
                )
                self._is_connected = response.status_code < 400
            else:
                self._is_connected = True  # Assume connected if no test URL
            
            return self._is_connected
            
        except Exception as exc:
            self.logger.error(f"HTTP adapter connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close HTTP connections."""
        self._is_connected = False
        return True
    
    def send(self, data: Any, target: str = None) -> Any:
        """Send HTTP request."""
        try:
            import requests
            
            url = target or self.get_config_value('url')
            method = HttpMethod(self.get_config_value('method', 'POST'))
            timeout = self.config.timeout
            headers = self.config.headers.copy()
            
            # Transform data
            transformed_data = self.transform_data(data, 'outbound')
            
            # Prepare request
            if method == HttpMethod.GET:
                response = requests.get(
                    url,
                    params=transformed_data,
                    headers=headers,
                    timeout=timeout,
                    auth=self._get_auth()
                )
            elif method == HttpMethod.POST:
                response = requests.post(
                    url,
                    json=transformed_data,
                    headers=headers,
                    timeout=timeout,
                    auth=self._get_auth()
                )
            elif method == HttpMethod.PUT:
                response = requests.put(
                    url,
                    json=transformed_data,
                    headers=headers,
                    timeout=timeout,
                    auth=self._get_auth()
                )
            elif method == HttpMethod.DELETE:
                response = requests.delete(
                    url,
                    headers=headers,
                    timeout=timeout,
                    auth=self._get_auth()
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle response
            if response.status_code >= 400:
                raise requests.HTTPError(f"HTTP {response.status_code}: {response.text}")
            
            # Transform response data
            response_data = self.transform_data(response.json(), 'inbound')
            
            return {
                'status_code': response.status_code,
                'data': response_data,
                'headers': dict(response.headers),
                'success': True
            }
            
        except Exception as exc:
            self.logger.error(f"HTTP adapter send failed: {exc}")
            raise
    
    def receive(self, source: str = None) -> Any:
        """Receive HTTP data (for webhook endpoints)."""
        # This would typically be used in a webhook context
        # For now, return empty data
        return None
    
    def validate_data(self, data: Any) -> bool:
        """Validate HTTP data."""
        try:
            if isinstance(data, dict):
                return True
            elif isinstance(data, str):
                # Try to parse as JSON
                json.loads(data)
                return True
            else:
                return False
        except Exception:
            return False
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform HTTP data."""
        if direction == 'outbound':
            # Apply outbound transformations
            return self._apply_transformation(data, 'outbound')
        else:
            # Apply inbound transformations
            return self._apply_transformation(data, 'inbound')
    
    def _get_auth(self):
        """Get authentication credentials."""
        auth_config = self.config.auth_config
        
        if not auth_config:
            return None
        
        auth_type = auth_config.get('type')
        
        if auth_type == 'basic':
            from requests.auth import HTTPBasicAuth
            return HTTPBasicAuth(
                auth_config['username'],
                auth_config['password']
            )
        elif auth_type == 'bearer':
            return {'Authorization': f"Bearer {auth_config['token']}"}
        elif auth_type == 'api_key':
            return {'X-API-Key': auth_config['key']}
        
        return None
    
    def _apply_transformation(self, data: Any, direction: str) -> Any:
        """Apply data transformations."""
        transformation_config = self.config.transformation_config
        
        if not transformation_config:
            return data
        
        # Apply field mappings
        field_mappings = transformation_config.get('field_mappings', {})
        if field_mappings and isinstance(data, dict):
            transformed_data = {}
            for old_field, new_field in field_mappings.items():
                if old_field in data:
                    transformed_data[new_field] = data[old_field]
            
            # Keep unmapped fields if specified
            if transformation_config.get('keep_unmapped', True):
                for field, value in data.items():
                    if field not in field_mappings:
                        transformed_data[field] = value
            
            data = transformed_data
        
        # Apply data type conversions
        type_conversions = transformation_config.get('type_conversions', {})
        if type_conversions and isinstance(data, dict):
            for field, target_type in type_conversions.items():
                if field in data:
                    try:
                        if target_type == 'int':
                            data[field] = int(data[field])
                        elif target_type == 'float':
                            data[field] = float(data[field])
                        elif target_type == 'str':
                            data[field] = str(data[field])
                        elif target_type == 'bool':
                            data[field] = bool(data[field])
                    except (ValueError, TypeError):
                        pass
        
        return data


class DatabaseAdapter(BaseAdapter):
    """Database adapter for data storage integrations."""
    
    def connect(self) -> bool:
        """Connect to database."""
        try:
            # This would establish database connection
            # For now, assume connection is successful
            self._is_connected = True
            return True
            
        except Exception as exc:
            self.logger.error(f"Database adapter connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close database connection."""
        self._is_connected = False
        return True
    
    def send(self, data: Any, target: str = None) -> Any:
        """Save data to database."""
        try:
            # Transform data
            transformed_data = self.transform_data(data, 'outbound')
            
            # Save to database (mock implementation)
            table_name = target or self.get_config_value('table_name')
            
            # This would actually save to database
            result = {
                'table': table_name,
                'data': transformed_data,
                'success': True,
                'inserted_id': 123  # Mock ID
            }
            
            return result
            
        except Exception as exc:
            self.logger.error(f"Database adapter send failed: {exc}")
            raise
    
    def receive(self, source: str = None) -> Any:
        """Retrieve data from database."""
        try:
            table_name = source or self.get_config_value('table_name')
            
            # This would actually query database
            data = {
                'table': table_name,
                'data': [{'id': 1, 'field': 'value'}],  # Mock data
                'success': True
            }
            
            # Transform data
            transformed_data = self.transform_data(data, 'inbound')
            
            return transformed_data
            
        except Exception as exc:
            self.logger.error(f"Database adapter receive failed: {exc}")
            raise
    
    def validate_data(self, data: Any) -> bool:
        """Validate database data."""
        try:
            # Basic validation
            return isinstance(data, (dict, list))
        except Exception:
            return False
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform database data."""
        if direction == 'outbound':
            # Apply outbound transformations
            return self._apply_database_transformations(data, 'outbound')
        else:
            # Apply inbound transformations
            return self._apply_database_transformations(data, 'inbound')
    
    def _apply_database_transformations(self, data: Any, direction: str) -> Any:
        """Apply database-specific transformations."""
        # Add timestamps
        if direction == 'outbound' and isinstance(data, dict):
            data['created_at'] = timezone.now().isoformat()
            data['updated_at'] = timezone.now().isoformat()
        
        return data


class MessageQueueAdapter(BaseAdapter):
    """Message queue adapter for async messaging."""
    
    def connect(self) -> bool:
        """Connect to message queue."""
        try:
            # This would connect to message queue system
            # For now, assume connection is successful
            self._is_connected = True
            return True
            
        except Exception as exc:
            self.logger.error(f"Message queue adapter connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close message queue connection."""
        self._is_connected = False
        return True
    
    def send(self, data: Any, target: str = None) -> Any:
        """Send message to queue."""
        try:
            # Transform data
            transformed_data = self.transform_data(data, 'outbound')
            
            # Send to queue
            queue_name = target or self.get_config_value('queue_name')
            
            # This would actually send to message queue
            result = {
                'queue': queue_name,
                'message': transformed_data,
                'success': True,
                'message_id': 'msg_123'  # Mock message ID
            }
            
            return result
            
        except Exception as exc:
            self.logger.error(f"Message queue adapter send failed: {exc}")
            raise
    
    def receive(self, source: str = None) -> Any:
        """Receive message from queue."""
        try:
            queue_name = source or self.get_config_value('queue_name')
            
            # This would actually receive from message queue
            message = {
                'queue': queue_name,
                'message': {'id': 1, 'content': 'test'},  # Mock message
                'success': True,
                'message_id': 'msg_123'
            }
            
            # Transform data
            transformed_message = self.transform_data(message, 'inbound')
            
            return transformed_message
            
        except Exception as exc:
            self.logger.error(f"Message queue adapter receive failed: {exc}")
            raise
    
    def validate_data(self, data: Any) -> bool:
        """Validate message data."""
        try:
            # Basic validation
            return isinstance(data, (dict, str, bytes))
        except Exception:
            return False
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform message data."""
        if direction == 'outbound':
            # Apply outbound transformations
            return self._apply_message_transformations(data, 'outbound')
        else:
            # Apply inbound transformations
            return self._apply_message_transformations(data, 'inbound')
    
    def _apply_message_transformations(self, data: Any, direction: str) -> Any:
        """Apply message-specific transformations."""
        # Add message metadata
        if direction == 'outbound' and isinstance(data, dict):
            data['timestamp'] = timezone.now().isoformat()
            data['source'] = 'engagement_system'
        
        return data


class EmailAdapter(BaseAdapter):
    """Email adapter for email integrations."""
    
    def connect(self) -> bool:
        """Connect to email service."""
        try:
            # Test email configuration
            from django.core.mail import get_connection
            from django.core.mail import EmailMessage
            
            connection = get_connection(
                backend=self.get_config_value('email_backend', 'django.core.mail.backends.smtp.EmailBackend'),
                host=self.get_config_value('smtp_host'),
                port=self.get_config_value('smtp_port', 587),
                username=self.get_config_value('smtp_username'),
                password=self.get_config_value('smtp_password'),
                use_tls=self.get_config_value('use_tls', True),
            )
            
            # Test connection
            connection.open()
            connection.close()
            
            self._is_connected = True
            return True
            
        except Exception as exc:
            self.logger.error(f"Email adapter connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close email connection."""
        self._is_connected = False
        return True
    
    def send(self, data: Any, target: str = None) -> Any:
        """Send email."""
        try:
            from django.core.mail import EmailMessage, get_connection
            
            # Transform data
            transformed_data = self.transform_data(data, 'outbound')
            
            # Create email
            email = EmailMessage(
                subject=transformed_data.get('subject', 'No Subject'),
                body=transformed_data.get('body', ''),
                to=[target or transformed_data.get('to', '')],
                from_email=transformed_data.get('from_email', settings.DEFAULT_FROM_EMAIL),
                cc=transformed_data.get('cc', []),
                bcc=transformed_data.get('bcc', []),
                reply_to=transformed_data.get('reply_to', []),
            )
            
            # Add attachments
            attachments = transformed_data.get('attachments', [])
            for attachment in attachments:
                email.attach(attachment['name'], attachment['content'], attachment['content_type'])
            
            # Send email
            connection = get_connection(
                backend=self.get_config_value('email_backend', 'django.core.mail.backends.smtp.EmailBackend'),
                host=self.get_config_value('smtp_host'),
                port=self.get_config_value('smtp_port', 587),
                username=self.get_config_value('smtp_username'),
                password=self.get_config_value('smtp_password'),
                use_tls=self.get_config_value('use_tls', True),
            )
            
            result = email.send()
            
            return {
                'success': result > 0,
                'recipients_count': len(email.to) + len(email.cc) + len(email.bcc),
                'message_id': 'email_123',  # Mock message ID
            }
            
        except Exception as exc:
            self.logger.error(f"Email adapter send failed: {exc}")
            raise
    
    def receive(self, source: str = None) -> Any:
        """Receive email (not typically used for sending)."""
        return None
    
    def validate_data(self, data: Any) -> bool:
        """Validate email data."""
        try:
            required_fields = ['to', 'subject', 'body']
            if isinstance(data, dict):
                return all(field in data for field in required_fields)
            return False
        except Exception:
            return False
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform email data."""
        if direction == 'outbound':
            # Apply outbound transformations
            return self._apply_email_transformations(data, 'outbound')
        else:
            # Apply inbound transformations
            return self._apply_email_transformations(data, 'inbound')
    
    def _apply_email_transformations(self, data: Any, direction: str) -> Any:
        """Apply email-specific transformations."""
        if direction == 'outbound' and isinstance(data, dict):
            # Add default values
            if 'from_email' not in data:
                data['from_email'] = settings.DEFAULT_FROM_EMAIL
            
            # Validate email addresses
            import re
            email_pattern = VALIDATION_RULES['email']
            
            for field in ['to', 'cc', 'bcc', 'reply_to']:
                if field in data and isinstance(data[field], str):
                    if not re.match(email_pattern, data[field]):
                        raise ValueError(f"Invalid email address in {field}")
        
        return data


class SMSAdapter(BaseAdapter):
    """SMS adapter for SMS integrations."""
    
    def connect(self) -> bool:
        """Connect to SMS service."""
        try:
            # Test SMS service connection
            api_key = self.get_config_value('api_key')
            if api_key:
                # This would test actual SMS service connection
                pass
            
            self._is_connected = True
            return True
            
        except Exception as exc:
            self.logger.error(f"SMS adapter connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close SMS connection."""
        self._is_connected = False
        return True
    
    def send(self, data: Any, target: str = None) -> Any:
        """Send SMS."""
        try:
            # Transform data
            transformed_data = self.transform_data(data, 'outbound')
            
            # Send SMS
            phone_number = target or transformed_data.get('to')
            message = transformed_data.get('message', '')
            
            # This would actually send SMS via SMS service
            result = {
                'success': True,
                'phone_number': phone_number,
                'message_length': len(message),
                'sms_id': 'sms_123',  # Mock SMS ID
                'cost': 0.05  # Mock cost
            }
            
            return result
            
        except Exception as exc:
            self.logger.error(f"SMS adapter send failed: {exc}")
            raise
    
    def receive(self, source: str = None) -> Any:
        """Receive SMS (not typically used for sending)."""
        return None
    
    def validate_data(self, data: Any) -> bool:
        """Validate SMS data."""
        try:
            required_fields = ['to', 'message']
            if isinstance(data, dict):
                return all(field in data for field in required_fields)
            return False
        except Exception:
            return False
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform SMS data."""
        if direction == 'outbound':
            # Apply outbound transformations
            return self._apply_sms_transformations(data, 'outbound')
        else:
            # Apply inbound transformations
            return self._apply_sms_transformations(data, 'inbound')
    
    def _apply_sms_transformations(self, data: Any, direction: str) -> Any:
        """Apply SMS-specific transformations."""
        if direction == 'outbound' and isinstance(data, dict):
            # Validate message length
            max_length = self.get_config_value('max_message_length', 1600)
            message = data.get('message', '')
            
            if len(message) > max_length:
                data['message'] = message[:max_length]
                data['truncated'] = True
            
            # Validate phone number
            import re
            phone_pattern = VALIDATION_RULES['phone']
            phone_number = data.get('to', '')
            
            if not re.match(phone_pattern, phone_number):
                raise ValueError(f"Invalid phone number: {phone_number}")
        
        return data


class AdapterFactory:
    """Factory for creating adapters."""
    
    _adapter_classes: Dict[AdapterType, type] = {
        AdapterType.HTTP_ADAPTER: HTTPAdapter,
        AdapterType.DATABASE_ADAPTER: DatabaseAdapter,
        AdapterType.MESSAGE_QUEUE_ADAPTER: MessageQueueAdapter,
        AdapterType.EMAIL_ADAPTER: EmailAdapter,
        AdapterType.SMS_ADAPTER: SMSAdapter,
    }
    
    @classmethod
    def create_adapter(cls, adapter_type: AdapterType, config: AdapterConfig) -> BaseAdapter:
        """Create an adapter instance."""
        adapter_class = cls._adapter_classes.get(adapter_type)
        if not adapter_class:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
        
        return adapter_class(config)
    
    @classmethod
    def register_adapter_class(cls, adapter_type: AdapterType, adapter_class: type):
        """Register an adapter class."""
        cls._adapter_classes[adapter_type] = adapter_class
    
    @classmethod
    def list_supported_types(cls) -> List[AdapterType]:
        """List supported adapter types."""
        return list(cls._adapter_classes.keys())


# Data transformation utilities
class DataTransformer:
    """Utilities for data transformation."""
    
    @staticmethod
    def transform_to_json(data: Any) -> str:
        """Transform data to JSON."""
        try:
            return json.dumps(data, default=str)
        except Exception as exc:
            logger.error(f"Failed to transform to JSON: {exc}")
            raise
    
    @staticmethod
    def transform_from_json(json_data: str) -> Any:
        """Transform JSON to data."""
        try:
            return json.loads(json_data)
        except Exception as exc:
            logger.error(f"Failed to transform from JSON: {exc}")
            raise
    
    @staticmethod
    def transform_to_xml(data: Dict[str, Any]) -> str:
        """Transform data to XML."""
        try:
            root = ET.Element('root')
            
            def dict_to_xml(parent, data):
                if isinstance(data, dict):
                    for key, value in data.items():
                        child = ET.SubElement(parent, key)
                        dict_to_xml(child, value)
                else:
                    parent.text = str(data)
            
            dict_to_xml(root, data)
            return ET.tostring(root, encoding='unicode')
        except Exception as exc:
            logger.error(f"Failed to transform to XML: {exc}")
            raise
    
    @staticmethod
    def transform_from_xml(xml_data: str) -> Dict[str, Any]:
        """Transform XML to data."""
        try:
            root = ET.fromstring(xml_data)
            
            def xml_to_dict(element):
                result = {}
                
                for child in element:
                    if len(child) > 0:
                        result[child.tag] = xml_to_dict(child)
                    else:
                        result[child.tag] = child.text
                
                return result
            
            return xml_to_dict(root)
        except Exception as exc:
            logger.error(f"Failed to transform from XML: {exc}")
            raise
    
    @staticmethod
    def transform_to_csv(data: List[Dict[str, Any]]) -> str:
        """Transform data to CSV."""
        try:
            import csv
            import io
            
            if not data:
                return ""
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            
            return output.getvalue()
        except Exception as exc:
            logger.error(f"Failed to transform to CSV: {exc}")
            raise
    
    @staticmethod
    def encode_base64(data: str) -> str:
        """Encode data to base64."""
        try:
            return base64.b64encode(data.encode()).decode()
        except Exception as exc:
            logger.error(f"Failed to encode to base64: {exc}")
            raise
    
    @staticmethod
    def decode_base64(encoded_data: str) -> str:
        """Decode base64 data."""
        try:
            return base64.b64decode(encoded_data.encode()).decode()
        except Exception as exc:
            logger.error(f"Failed to decode from base64: {exc}")
            raise
