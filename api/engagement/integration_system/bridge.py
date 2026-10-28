# engagement/integration_system/bridge.py
"""
Bridge system for integration communication.
Provides bridges between different systems and protocols.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio
import threading
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_constants import (
    IntegrationType, DataType, ERROR_CODES, SUCCESS_CODES,
    DEFAULT_CONFIG, CACHE_KEYS
)

logger = logging.getLogger(__name__)


class BridgeType(Enum):
    """Types of bridges."""
    HTTP_TO_QUEUE = "http_to_queue"
    QUEUE_TO_HTTP = "queue_to_http"
    DATABASE_TO_API = "database_to_api"
    API_TO_DATABASE = "api_to_database"
    EMAIL_TO_WEBHOOK = "email_to_webhook"
    WEBHOOK_TO_EMAIL = "webhook_to_email"
    SYNC_TO_ASYNC = "sync_to_async"
    ASYNC_TO_SYNC = "async_to_sync"
    CUSTOM = "custom"


class BridgeStatus(Enum):
    """Bridge status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class BridgeConfig:
    """Configuration for a bridge."""
    id: str
    name: str
    type: BridgeType
    source_system: str
    target_system: str
    config: Dict[str, Any] = field(default_factory=dict)
    status: BridgeStatus = BridgeStatus.ACTIVE
    enabled: bool = True
    timeout: int = 30
    retry_count: int = 3
    retry_delay: int = 1
    transformation_rules: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    last_active: Optional[datetime] = None
    error_count: int = 0
    success_count: int = 0


class BaseBridge(ABC):
    """Base bridge class."""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._is_connected = False
        self._lock = threading.Lock()
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish bridge connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close bridge connection."""
        pass
    
    @abstractmethod
    def send_data(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """Send data through bridge."""
        pass
    
    @abstractmethod
    def receive_data(self, context: Dict[str, Any] = None) -> Any:
        """Receive data through bridge."""
        pass
    
    @abstractmethod
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform data format."""
        pass
    
    @abstractmethod
    def validate_data(self, data: Any, direction: str = 'outbound') -> bool:
        """Validate data format."""
        pass
    
    def is_connected(self) -> bool:
        """Check if bridge is connected."""
        return self._is_connected
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.config.get(key, default)
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration."""
        with self._lock:
            self.config.config.update(updates)
            self.config.updated_at = timezone.now()
    
    def increment_success(self):
        """Increment success count."""
        self.config.success_count += 1
        self.config.last_active = timezone.now()
    
    def increment_error(self):
        """Increment error count."""
        self.config.error_count += 1
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        total = self.config.success_count + self.config.error_count
        if total == 0:
            return 0.0
        return (self.config.success_count / total) * 100


class HttpToQueueBridge(BaseBridge):
    """Bridge from HTTP to message queue."""
    
    def connect(self) -> bool:
        """Connect to HTTP and message queue systems."""
        try:
            # Test HTTP connectivity
            import requests
            test_url = self.get_config_value('test_url')
            if test_url:
                response = requests.get(test_url, timeout=5)
                if response.status_code >= 400:
                    raise Exception(f"HTTP test failed: {response.status_code}")
            
            # Test queue connectivity
            # This would test message queue connection
            # For now, assume success
            
            self._is_connected = True
            return True
            
        except Exception as exc:
            self.logger.error(f"HttpToQueueBridge connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close connections."""
        self._is_connected = False
        return True
    
    def send_data(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """Send HTTP request to message queue."""
        try:
            # Validate and transform data
            if not self.validate_data(data, 'outbound'):
                raise ValueError("Invalid data format")
            
            transformed_data = self.transform_data(data, 'outbound')
            
            # Send to message queue
            queue_name = self.get_config_value('queue_name', 'default')
            message_id = self._send_to_queue(transformed_data, queue_name)
            
            return {
                'success': True,
                'message_id': message_id,
                'queue': queue_name,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"HttpToQueueBridge send_data failed: {exc}")
            raise
    
    def receive_data(self, context: Dict[str, Any] = None) -> Any:
        """Receive data from message queue to HTTP."""
        try:
            # Receive from message queue
            queue_name = self.get_config_value('queue_name', 'default')
            message = self._receive_from_queue(queue_name)
            
            if not message:
                return None
            
            # Validate and transform data
            if not self.validate_data(message, 'inbound'):
                raise ValueError("Invalid data format")
            
            transformed_data = self.transform_data(message, 'inbound')
            
            # Send HTTP request
            http_url = self.get_config_value('http_url')
            http_method = self.get_config_value('http_method', 'POST')
            
            response = self._send_http_request(transformed_data, http_url, http_method)
            
            return {
                'success': True,
                'http_status': response.status_code,
                'http_response': response.json() if response.content else None,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"HttpToQueueBridge receive_data failed: {exc}")
            raise
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform data between HTTP and queue formats."""
        transformation_rules = self.config.transformation_rules
        
        if direction == 'outbound':
            # HTTP to queue transformation
            if transformation_rules.get('add_queue_metadata', True):
                if isinstance(data, dict):
                    data.update({
                        'source': 'http',
                        'timestamp': timezone.now().isoformat(),
                        'bridge_id': self.config.id
                    })
            
            # Apply field mappings
            field_mappings = transformation_rules.get('field_mappings', {})
            if field_mappings and isinstance(data, dict):
                transformed_data = {}
                for old_field, new_field in field_mappings.items():
                    if old_field in data:
                        transformed_data[new_field] = data[old_field]
                data = transformed_data
        
        else:
            # Queue to HTTP transformation
            if transformation_rules.get('add_http_metadata', True):
                if isinstance(data, dict):
                    data.update({
                        'source': 'queue',
                        'timestamp': timezone.now().isoformat(),
                        'bridge_id': self.config.id
                    })
        
        return data
    
    def validate_data(self, data: Any, direction: str = 'outbound') -> bool:
        """Validate data format."""
        try:
            if direction == 'outbound':
                # Validate HTTP data
                return isinstance(data, (dict, str, bytes))
            else:
                # Validate queue data
                return isinstance(data, (dict, str, bytes))
        except Exception:
            return False
    
    def _send_to_queue(self, data: Any, queue_name: str) -> str:
        """Send data to message queue."""
        # This would actually send to message queue system
        # For now, return mock message ID
        return f"msg_{timezone.now().timestamp()}"
    
    def _receive_from_queue(self, queue_name: str) -> Any:
        """Receive data from message queue."""
        # This would actually receive from message queue system
        # For now, return mock data
        return {
            'id': 'test_message',
            'content': 'test data',
            'timestamp': timezone.now().isoformat()
        }
    
    def _send_http_request(self, data: Any, url: str, method: str):
        """Send HTTP request."""
        import requests
        
        if method == 'GET':
            return requests.get(url, params=data, timeout=self.config.timeout)
        elif method == 'POST':
            return requests.post(url, json=data, timeout=self.config.timeout)
        elif method == 'PUT':
            return requests.put(url, json=data, timeout=self.config.timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")


class DatabaseToApiBridge(BaseBridge):
    """Bridge from database to API."""
    
    def connect(self) -> bool:
        """Connect to database and API systems."""
        try:
            # Test database connection
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Test API connectivity
            import requests
            test_url = self.get_config_value('api_test_url')
            if test_url:
                response = requests.get(test_url, timeout=5)
                if response.status_code >= 400:
                    raise Exception(f"API test failed: {response.status_code}")
            
            self._is_connected = True
            return True
            
        except Exception as exc:
            self.logger.error(f"DatabaseToApiBridge connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close connections."""
        self._is_connected = False
        return True
    
    def send_data(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """Send database data to API."""
        try:
            # Validate and transform data
            if not self.validate_data(data, 'outbound'):
                raise ValueError("Invalid data format")
            
            transformed_data = self.transform_data(data, 'outbound')
            
            # Send to API
            api_url = self.get_config_value('api_url')
            api_method = self.get_config_value('api_method', 'POST')
            api_headers = self.get_config_value('api_headers', {})
            
            response = self._send_api_request(transformed_data, api_url, api_method, api_headers)
            
            return {
                'success': True,
                'api_status': response.status_code,
                'api_response': response.json() if response.content else None,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"DatabaseToApiBridge send_data failed: {exc}")
            raise
    
    def receive_data(self, context: Dict[str, Any] = None) -> Any:
        """Receive API data and save to database."""
        try:
            # Receive from API
            api_url = self.get_config_value('api_url')
            api_method = self.get_config_value('api_method', 'GET')
            api_headers = self.get_config_value('api_headers', {})
            
            response = self._send_api_request({}, api_url, api_method, api_headers)
            
            if not response.content:
                return None
            
            api_data = response.json()
            
            # Validate and transform data
            if not self.validate_data(api_data, 'inbound'):
                raise ValueError("Invalid data format")
            
            transformed_data = self.transform_data(api_data, 'inbound')
            
            # Save to database
            table_name = self.get_config_value('table_name')
            record_id = self._save_to_database(transformed_data, table_name)
            
            return {
                'success': True,
                'record_id': record_id,
                'table': table_name,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"DatabaseToApiBridge receive_data failed: {exc}")
            raise
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform data between database and API formats."""
        transformation_rules = self.config.transformation_rules
        
        if direction == 'outbound':
            # Database to API transformation
            if transformation_rules.get('add_api_metadata', True):
                if isinstance(data, dict):
                    data.update({
                        'source': 'database',
                        'timestamp': timezone.now().isoformat(),
                        'bridge_id': self.config.id
                    })
            
            # Apply field mappings
            field_mappings = transformation_rules.get('field_mappings', {})
            if field_mappings and isinstance(data, dict):
                transformed_data = {}
                for old_field, new_field in field_mappings.items():
                    if old_field in data:
                        transformed_data[new_field] = data[old_field]
                data = transformed_data
        
        else:
            # API to database transformation
            if transformation_rules.get('add_db_metadata', True):
                if isinstance(data, dict):
                    data.update({
                        'source': 'api',
                        'timestamp': timezone.now().isoformat(),
                        'bridge_id': self.config.id
                    })
        
        return data
    
    def validate_data(self, data: Any, direction: str = 'outbound') -> bool:
        """Validate data format."""
        try:
            if direction == 'outbound':
                # Validate database data
                return isinstance(data, (dict, list))
            else:
                # Validate API data
                return isinstance(data, (dict, list))
        except Exception:
            return False
    
    def _send_api_request(self, data: Any, url: str, method: str, headers: Dict[str, str]):
        """Send API request."""
        import requests
        
        if method == 'GET':
            return requests.get(url, params=data, headers=headers, timeout=self.config.timeout)
        elif method == 'POST':
            return requests.post(url, json=data, headers=headers, timeout=self.config.timeout)
        elif method == 'PUT':
            return requests.put(url, json=data, headers=headers, timeout=self.config.timeout)
        elif method == 'DELETE':
            return requests.delete(url, headers=headers, timeout=self.config.timeout)
        else:
            raise ValueError(f"Unsupported API method: {method}")
    
    def _save_to_database(self, data: Any, table_name: str) -> str:
        """Save data to database."""
        # This would actually save to database
        # For now, return mock record ID
        return f"record_{timezone.now().timestamp()}"


class EmailToWebhookBridge(BaseBridge):
    """Bridge from email to webhook."""
    
    def connect(self) -> bool:
        """Connect to email and webhook systems."""
        try:
            # Test email configuration
            from django.core.mail import get_connection
            connection = get_connection(
                backend=self.get_config_value('email_backend', 'django.core.mail.backends.smtp.EmailBackend'),
                host=self.get_config_value('smtp_host'),
                port=self.get_config_value('smtp_port', 587),
                username=self.get_config_value('smtp_username'),
                password=self.get_config_value('smtp_password'),
                use_tls=self.get_config_value('use_tls', True),
            )
            connection.open()
            connection.close()
            
            # Test webhook connectivity
            import requests
            test_url = self.get_config_value('webhook_test_url')
            if test_url:
                response = requests.get(test_url, timeout=5)
                if response.status_code >= 400:
                    raise Exception(f"Webhook test failed: {response.status_code}")
            
            self._is_connected = True
            return True
            
        except Exception as exc:
            self.logger.error(f"EmailToWebhookBridge connection failed: {exc}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close connections."""
        self._is_connected = False
        return True
    
    def send_data(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """Send email data to webhook."""
        try:
            # Validate and transform data
            if not self.validate_data(data, 'outbound'):
                raise ValueError("Invalid data format")
            
            transformed_data = self.transform_data(data, 'outbound')
            
            # Send to webhook
            webhook_url = self.get_config_value('webhook_url')
            webhook_method = self.get_config_value('webhook_method', 'POST')
            webhook_headers = self.get_config_value('webhook_headers', {})
            
            response = self._send_webhook_request(transformed_data, webhook_url, webhook_method, webhook_headers)
            
            return {
                'success': True,
                'webhook_status': response.status_code,
                'webhook_response': response.json() if response.content else None,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"EmailToWebhookBridge send_data failed: {exc}")
            raise
    
    def receive_data(self, context: Dict[str, Any] = None) -> Any:
        """Receive webhook data and send email."""
        try:
            # Receive webhook data
            webhook_data = context.get('webhook_data')
            
            if not webhook_data:
                return None
            
            # Validate and transform data
            if not self.validate_data(webhook_data, 'inbound'):
                raise ValueError("Invalid data format")
            
            transformed_data = self.transform_data(webhook_data, 'inbound')
            
            # Send email
            email_to = self.get_config_value('email_to')
            email_subject = self.get_config_value('email_subject', 'Webhook Notification')
            email_body = self.get_config_value('email_body_template', 'Webhook data: {data}')
            
            email_id = self._send_email(transformed_data, email_to, email_subject, email_body)
            
            return {
                'success': True,
                'email_id': email_id,
                'recipient': email_to,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"EmailToWebhookBridge receive_data failed: {exc}")
            raise
    
    def transform_data(self, data: Any, direction: str = 'outbound') -> Any:
        """Transform data between email and webhook formats."""
        transformation_rules = self.config.transformation_rules
        
        if direction == 'outbound':
            # Email to webhook transformation
            if transformation_rules.get('add_webhook_metadata', True):
                if isinstance(data, dict):
                    data.update({
                        'source': 'email',
                        'timestamp': timezone.now().isoformat(),
                        'bridge_id': self.config.id
                    })
            
            # Apply field mappings
            field_mappings = transformation_rules.get('field_mappings', {})
            if field_mappings and isinstance(data, dict):
                transformed_data = {}
                for old_field, new_field in field_mappings.items():
                    if old_field in data:
                        transformed_data[new_field] = data[old_field]
                data = transformed_data
        
        else:
            # Webhook to email transformation
            if transformation_rules.get('add_email_metadata', True):
                if isinstance(data, dict):
                    data.update({
                        'source': 'webhook',
                        'timestamp': timezone.now().isoformat(),
                        'bridge_id': self.config.id
                    })
        
        return data
    
    def validate_data(self, data: Any, direction: str = 'outbound') -> bool:
        """Validate data format."""
        try:
            if direction == 'outbound':
                # Validate email data
                return isinstance(data, (dict, str))
            else:
                # Validate webhook data
                return isinstance(data, (dict, str))
        except Exception:
            return False
    
    def _send_webhook_request(self, data: Any, url: str, method: str, headers: Dict[str, str]):
        """Send webhook request."""
        import requests
        
        if method == 'POST':
            return requests.post(url, json=data, headers=headers, timeout=self.config.timeout)
        elif method == 'PUT':
            return requests.put(url, json=data, headers=headers, timeout=self.config.timeout)
        else:
            raise ValueError(f"Unsupported webhook method: {method}")
    
    def _send_email(self, data: Any, to: str, subject: str, body_template: str) -> str:
        """Send email."""
        from django.core.mail import EmailMessage, get_connection
        
        # Format email body
        body = body_template.format(data=str(data))
        
        # Create email
        email = EmailMessage(
            subject=subject,
            body=body,
            to=[to],
            from_email=self.get_config_value('from_email', settings.DEFAULT_FROM_EMAIL),
        )
        
        # Send email
        connection = get_connection(
            backend=self.get_config_value('email_backend', 'django.core.mail.backends.smtp.EmailBackend'),
            host=self.get_config_value('smtp_host'),
            port=self.get_config_value('smtp_port', 587),
            username=self.get_config_value('smtp_username'),
            password=self.get_config_value('smtp_password'),
            use_tls=self.get_config_value('use_tls', True),
        )
        
        result = email.send(connection=connection)
        
        return f"email_{timezone.now().timestamp()}"


class BridgeManager:
    """Manager for bridge operations."""
    
    def __init__(self):
        self._bridges: Dict[str, BaseBridge] = {}
        self._configs: Dict[str, BridgeConfig] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def register_bridge(self, bridge: BaseBridge, config: BridgeConfig) -> bool:
        """Register a bridge."""
        try:
            with self._lock:
                # Check if bridge already exists
                if config.id in self._bridges:
                    self.logger.warning(f"Bridge {config.id} already registered, updating...")
                    self.unregister_bridge(config.id)
                
                # Connect bridge
                if not bridge.connect():
                    self.logger.error(f"Failed to connect bridge {config.id}")
                    return False
                
                # Register bridge
                self._bridges[config.id] = bridge
                self._configs[config.id] = config
                
                self.logger.info(f"Successfully registered bridge {config.id}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to register bridge {config.id}: {exc}")
            return False
    
    def unregister_bridge(self, bridge_id: str) -> bool:
        """Unregister a bridge."""
        try:
            with self._lock:
                if bridge_id not in self._bridges:
                    self.logger.warning(f"Bridge {bridge_id} not found")
                    return False
                
                bridge = self._bridges[bridge_id]
                
                # Disconnect bridge
                bridge.disconnect()
                
                # Remove from registry
                del self._bridges[bridge_id]
                del self._configs[bridge_id]
                
                self.logger.info(f"Successfully unregistered bridge {bridge_id}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to unregister bridge {bridge_id}: {exc}")
            return False
    
    def get_bridge(self, bridge_id: str) -> Optional[BaseBridge]:
        """Get bridge by ID."""
        return self._bridges.get(bridge_id)
    
    def get_config(self, bridge_id: str) -> Optional[BridgeConfig]:
        """Get bridge configuration by ID."""
        return self._configs.get(bridge_id)
    
    def list_bridges(self, status: BridgeStatus = None, 
                    bridge_type: BridgeType = None) -> List[BridgeConfig]:
        """List bridges with optional filtering."""
        configs = list(self._configs.values())
        
        if status:
            configs = [c for c in configs if c.status == status]
        
        if bridge_type:
            configs = [c for c in configs if c.type == bridge_type]
        
        return configs
    
    def execute_bridge(self, bridge_id: str, data: Any, 
                       direction: str = 'send', context: Dict[str, Any] = None) -> Any:
        """Execute bridge operation."""
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            raise ValueError(f"Bridge {bridge_id} not found")
        
        config = self.get_config(bridge_id)
        if not config.enabled:
            raise ValueError(f"Bridge {bridge_id} is not enabled")
        
        try:
            if direction == 'send':
                result = bridge.send_data(data, context)
            else:
                result = bridge.receive_data(context)
            
            bridge.increment_success()
            return result
            
        except Exception as exc:
            bridge.increment_error()
            self.logger.error(f"Bridge execution failed for {bridge_id}: {exc}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        with self._lock:
            total_bridges = len(self._bridges)
            status_counts = {}
            type_counts = {}
            total_success = 0
            total_errors = 0
            
            for config in self._configs.values():
                # Count by status
                status = config.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Count by type
                bridge_type = config.type.value
                type_counts[bridge_type] = type_counts.get(bridge_type, 0) + 1
                
                # Count successes and errors
                total_success += config.success_count
                total_errors += config.error_count
            
            success_rate = (total_success / (total_success + total_errors) * 100) if (total_success + total_errors) > 0 else 0
            
            return {
                'total_bridges': total_bridges,
                'status_counts': status_counts,
                'type_counts': type_counts,
                'total_success': total_success,
                'total_errors': total_errors,
                'success_rate': success_rate,
                'last_updated': timezone.now().isoformat(),
            }


class BridgeFactory:
    """Factory for creating bridges."""
    
    _bridge_classes: Dict[BridgeType, type] = {
        BridgeType.HTTP_TO_QUEUE: HttpToQueueBridge,
        BridgeType.QUEUE_TO_HTTP: HttpToQueueBridge,
        BridgeType.DATABASE_TO_API: DatabaseToApiBridge,
        BridgeType.API_TO_DATABASE: DatabaseToApiBridge,
        BridgeType.EMAIL_TO_WEBHOOK: EmailToWebhookBridge,
        BridgeType.WEBHOOK_TO_EMAIL: EmailToWebhookBridge,
    }
    
    @classmethod
    def create_bridge(cls, bridge_type: BridgeType, config: BridgeConfig) -> BaseBridge:
        """Create a bridge instance."""
        bridge_class = cls._bridge_classes.get(bridge_type)
        if not bridge_class:
            raise ValueError(f"Unknown bridge type: {bridge_type}")
        
        return bridge_class(config)
    
    @classmethod
    def register_bridge_class(cls, bridge_type: BridgeType, bridge_class: type):
        """Register a bridge class."""
        cls._bridge_classes[bridge_type] = bridge_class
    
    @classmethod
    def list_supported_types(cls) -> List[BridgeType]:
        """List supported bridge types."""
        return list(cls._bridge_classes.keys())


# Global bridge manager instance
bridge_manager = BridgeManager()
