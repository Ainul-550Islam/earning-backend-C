"""
integ_adapter.py – Integration Adapter for postback module.

Provides comprehensive adapter functionality including:
- Request/response adaptation
- Data transformation
- Protocol handling
- Error handling and retry logic
"""
import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.utils import timezone
from django.conf import settings
import requests
import json

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException, IntegrationTimeoutException, IntegrationConnectionException
from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationType, IntegrationProtocol
from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS.transformer import DataTransformer

logger = logging.getLogger(__name__)


class AdapterStatus(Enum):
    """Adapter status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class RequestConfig:
    """Request configuration."""
    method: str = "POST"
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    verify_ssl: bool = True
    allow_redirects: bool = True
    stream: bool = False


@dataclass
class ResponseConfig:
    """Response configuration."""
    expected_status_codes: List[int] = field(default_factory=lambda: [200, 201, 202])
    response_format: str = "json"  # json, xml, text
    max_response_size: int = 10485760  # 10MB
    timeout: int = 30


class IntegrationAdapter:
    """
    Base integration adapter class.
    
    Provides common adapter functionality for different
    integration types and protocols.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config['name']
        self.type = config.get('type', IntegrationType.WEBHOOK)
        self.protocol = config.get('protocol', IntegrationProtocol.HTTP)
        self.endpoint = config.get('endpoint', '')
        self.status = AdapterStatus.ACTIVE
        
        # Request/response configuration
        self.request_config = RequestConfig(
            method=config.get('method', 'POST'),
            headers=config.get('headers', {}),
            timeout=config.get('timeout', 30),
            retry_attempts=config.get('retry_attempts', 3),
            retry_delay=config.get('retry_delay', 1.0),
            verify_ssl=config.get('verify_ssl', True),
            allow_redirects=config.get('allow_redirects', True),
            stream=config.get('stream', False),
        )
        
        self.response_config = ResponseConfig(
            expected_status_codes=config.get('expected_status_codes', [200, 201, 202]),
            response_format=config.get('response_format', 'json'),
            max_response_size=config.get('max_response_size', 10485760),
            timeout=config.get('response_timeout', 30),
        )
        
        # Data transformer
        self.transformer = DataTransformer(config.get('transformations', {}))
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.last_request_time = None
        self.last_error = None
        
        self.logger = logging.getLogger(f"adapter.{self.name}")
    
    def pre_process_request(self, request_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Pre-process request data.
        
        Args:
            request_data: Original request data
            context: Additional context
            
        Returns:
            Processed request data
        """
        context = context or {}
        
        try:
            # Apply data transformations
            processed_data = self.transformer.transform_request(request_data, context)
            
            # Add common fields
            processed_data.update({
                'timestamp': timezone.now().isoformat(),
                'adapter': self.name,
                'request_id': context.get('request_id', ''),
            })
            
            # Add authentication if configured
            if self.config.get('auth'):
                processed_data = self._add_authentication(processed_data)
            
            # Add headers if configured
            if self.config.get('additional_headers'):
                self.request_config.headers.update(self.config['additional_headers'])
            
            return processed_data
        
        except Exception as e:
            self.logger.error(f"Error pre-processing request: {str(e)}")
            raise IntegrationException(f"Request pre-processing failed: {str(e)}")
    
    def post_process_response(self, response_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Post-process response data.
        
        Args:
            response_data: Original response data
            context: Additional context
            
        Returns:
            Processed response data
        """
        context = context or {}
        
        try:
            # Apply data transformations
            processed_data = self.transformer.transform_response(response_data, context)
            
            # Add metadata
            processed_data.update({
                'adapter': self.name,
                'processed_at': timezone.now().isoformat(),
                'request_id': context.get('request_id', ''),
            })
            
            return processed_data
        
        except Exception as e:
            self.logger.error(f"Error post-processing response: {str(e)}")
            raise IntegrationException(f"Response post-processing failed: {str(e)}")
    
    def execute_request(self, request_data: Dict[str, Any], context: Dict[str, Any] = None,
                        timeout: int = None) -> Dict[str, Any]:
        """
        Execute integration request.
        
        Args:
            request_data: Request data
            context: Additional context
            timeout: Override timeout
            
        Returns:
            Response data
        """
        context = context or {}
        self.total_requests += 1
        self.last_request_time = timezone.now()
        
        try:
            # Prepare request
            processed_data = self.pre_process_request(request_data, context)
            
            # Execute based on protocol
            if self.protocol == IntegrationProtocol.HTTP:
                response = self._execute_http_request(processed_data, context, timeout)
            elif self.protocol == IntegrationProtocol.WEBSOCKET:
                response = self._execute_websocket_request(processed_data, context, timeout)
            elif self.protocol == IntegrationProtocol.GRPC:
                response = self._execute_grpc_request(processed_data, context, timeout)
            elif self.protocol == IntegrationProtocol.MESSAGE_QUEUE:
                response = self._execute_message_queue_request(processed_data, context, timeout)
            else:
                raise IntegrationException(f"Unsupported protocol: {self.protocol}")
            
            # Validate response
            if not self.validate_response(response):
                raise IntegrationException("Invalid response received")
            
            # Post-process response
            processed_response = self.post_process_response(response, context)
            
            self.successful_requests += 1
            self.last_error = None
            
            return processed_response
        
        except Exception as e:
            self.failed_requests += 1
            self.last_error = str(e)
            self.logger.error(f"Request execution failed: {str(e)}")
            raise
    
    def _execute_http_request(self, request_data: Dict[str, Any], context: Dict[str, Any],
                            timeout: int = None) -> Dict[str, Any]:
        """Execute HTTP request."""
        timeout = timeout or self.request_config.timeout
        
        # Prepare request
        url = self._build_url(context)
        method = self.request_config.method
        headers = self.request_config.headers.copy()
        
        # Add content-type if not present
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
        
        # Prepare payload
        if method in ['POST', 'PUT', 'PATCH']:
            if headers.get('Content-Type') == 'application/json':
                payload = json.dumps(request_data)
            else:
                payload = request_data
        else:
            payload = None
        
        # Execute request with retry logic
        for attempt in range(self.request_config.retry_attempts):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=payload,
                    timeout=timeout,
                    verify=self.request_config.verify_ssl,
                    allow_redirects=self.request_config.allow_redirects,
                    stream=self.request_config.stream,
                )
                
                # Check response status
                if response.status_code not in self.response_config.expected_status_codes:
                    raise IntegrationException(f"Unexpected status code: {response.status_code}")
                
                # Parse response
                if self.response_config.response_format == 'json':
                    try:
                        response_data = response.json()
                    except ValueError:
                        response_data = {'content': response.text}
                elif self.response_config.response_format == 'xml':
                    response_data = {'content': response.text}
                else:
                    response_data = {'content': response.text}
                
                # Add response metadata
                response_data.update({
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'response_time': response.elapsed.total_seconds(),
                })
                
                return response_data
            
            except requests.exceptions.Timeout:
                if attempt < self.request_config.retry_attempts - 1:
                    self.logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                    time.sleep(self.request_config.retry_delay * (2 ** attempt))
                    continue
                raise IntegrationTimeoutException(f"Request timeout after {self.request_config.retry_attempts} attempts")
            
            except requests.exceptions.ConnectionError as e:
                if attempt < self.request_config.retry_attempts - 1:
                    self.logger.warning(f"Connection error on attempt {attempt + 1}, retrying: {str(e)}")
                    time.sleep(self.request_config.retry_delay * (2 ** attempt))
                    continue
                raise IntegrationConnectionException(f"Connection failed: {str(e)}")
            
            except requests.exceptions.RequestException as e:
                raise IntegrationException(f"Request failed: {str(e)}")
    
    def _execute_websocket_request(self, request_data: Dict[str, Any], context: Dict[str, Any],
                                  timeout: int = None) -> Dict[str, Any]:
        """Execute WebSocket request."""
        # This would integrate with WebSocket library
        # For now, simulate WebSocket request
        self.logger.info(f"WebSocket request to {self.endpoint}")
        
        return {
            'status': 'success',
            'message': 'WebSocket request processed',
            'data': request_data,
        }
    
    def _execute_grpc_request(self, request_data: Dict[str, Any], context: Dict[str, Any],
                             timeout: int = None) -> Dict[str, Any]:
        """Execute gRPC request."""
        # This would integrate with gRPC library
        # For now, simulate gRPC request
        self.logger.info(f"gRPC request to {self.endpoint}")
        
        return {
            'status': 'success',
            'message': 'gRPC request processed',
            'data': request_data,
        }
    
    def _execute_message_queue_request(self, request_data: Dict[str, Any], context: Dict[str, Any],
                                      timeout: int = None) -> Dict[str, Any]:
        """Execute message queue request."""
        # This would integrate with message queue library (RabbitMQ, Kafka, etc.)
        # For now, simulate message queue request
        self.logger.info(f"Message queue request to {self.endpoint}")
        
        return {
            'status': 'success',
            'message': 'Message queue request processed',
            'data': request_data,
        }
    
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Validate response data.
        
        Args:
            response: Response data
            
        Returns:
            True if valid
        """
        try:
            # Check required fields
            if 'status' not in response:
                return False
            
            # Check status
            if response['status'] not in ['success', 'completed', 'ok']:
                return False
            
            # Check response size
            response_size = len(str(response))
            if response_size > self.response_config.max_response_size:
                return False
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error validating response: {str(e)}")
            return False
    
    def _build_url(self, context: Dict[str, Any]) -> str:
        """Build request URL."""
        url = self.endpoint
        
        # Add query parameters if configured
        if self.config.get('query_params'):
            import urllib.parse
            query_params = self.config['query_params']
            
            # Replace placeholders in query params
            for key, value in query_params.items():
                if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                    param_name = value[1:-1]
                    query_params[key] = context.get(param_name, '')
            
            url += '?' + urllib.parse.urlencode(query_params)
        
        return url
    
    def _add_authentication(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add authentication to request."""
        auth_config = self.config['auth']
        auth_type = auth_config.get('type', 'none')
        
        if auth_type == 'api_key':
            api_key = auth_config.get('api_key')
            if api_key:
                self.request_config.headers['Authorization'] = f'Bearer {api_key}'
        
        elif auth_type == 'basic':
            username = auth_config.get('username')
            password = auth_config.get('password')
            if username and password:
                import base64
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                self.request_config.headers['Authorization'] = f'Basic {credentials}'
        
        elif auth_type == 'custom':
            custom_headers = auth_config.get('headers', {})
            self.request_config.headers.update(custom_headers)
        
        return request_data
    
    def health_check(self) -> str:
        """
        Perform health check.
        
        Returns:
            Health status
        """
        try:
            # Simple health check - try to make a test request
            test_data = {'health_check': True}
            context = {'health_check': True}
            
            response = self.execute_request(test_data, context, timeout=5)
            
            if response.get('status') == 'success':
                return 'healthy'
            else:
                return 'unhealthy'
        
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return 'error'
    
    def get_status(self) -> str:
        """Get adapter status."""
        return self.status.value
    
    def set_status(self, status: AdapterStatus):
        """Set adapter status."""
        self.status = status
        self.logger.info(f"Adapter status changed to: {status.value}")
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update adapter configuration."""
        self.config.update(new_config)
        
        # Update request/response config
        if 'timeout' in new_config:
            self.request_config.timeout = new_config['timeout']
        if 'retry_attempts' in new_config:
            self.request_config.retry_attempts = new_config['retry_attempts']
        if 'headers' in new_config:
            self.request_config.headers.update(new_config['headers'])
        
        self.logger.info(f"Adapter configuration updated")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            'name': self.name,
            'type': self.type.value,
            'protocol': self.protocol.value,
            'endpoint': self.endpoint,
            'status': self.status.value,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{success_rate:.2f}%",
            'last_request_time': self.last_request_time.isoformat() if self.last_request_time else None,
            'last_error': self.last_error,
        }


class WebhookAdapter(IntegrationAdapter):
    """Specialized adapter for webhook integrations."""
    
    def __init__(self, config: Dict[str, Any]):
        config['type'] = IntegrationType.WEBHOOK
        config['protocol'] = IntegrationProtocol.HTTP
        super().__init__(config)
    
    def validate_webhook_signature(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
        """
        Validate webhook signature.
        
        Args:
            payload: Webhook payload
            signature: Received signature
            secret: Secret key
            
        Returns:
            True if signature is valid
        """
        import hmac
        import hashlib
        
        try:
            # Create expected signature
            payload_str = json.dumps(payload, sort_keys=True)
            expected_signature = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
        
        except Exception as e:
            self.logger.error(f"Error validating webhook signature: {str(e)}")
            return False


class APIAdapter(IntegrationAdapter):
    """Specialized adapter for API integrations."""
    
    def __init__(self, config: Dict[str, Any]):
        config['type'] = IntegrationType.API
        config['protocol'] = IntegrationProtocol.HTTP
        super().__init__(config)
    
    def handle_pagination(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Handle paginated responses.
        
        Args:
            response: API response
            
        Returns:
            List of paginated items
        """
        items = []
        
        if 'data' in response:
            items = response['data']
        
        # Check for pagination info
        pagination = response.get('pagination', {})
        total_pages = pagination.get('total_pages', 1)
        current_page = pagination.get('current_page', 1)
        
        # Fetch additional pages if available
        if current_page < total_pages:
            # This would implement pagination logic
            pass
        
        return items


class MessageQueueAdapter(IntegrationAdapter):
    """Specialized adapter for message queue integrations."""
    
    def __init__(self, config: Dict[str, Any]):
        config['type'] = IntegrationType.MESSAGE_QUEUE
        config['protocol'] = IntegrationProtocol.MESSAGE_QUEUE
        super().__init__(config)
    
    def publish_message(self, topic: str, message: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """
        Publish message to queue.
        
        Args:
            topic: Message topic
            message: Message data
            context: Additional context
            
        Returns:
            Message ID
        """
        context = context or {}
        context['topic'] = topic
        
        response = self.execute_request(message, context)
        
        return response.get('message_id', '')
    
    def consume_messages(self, topic: str, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Consume messages from queue.
        
        Args:
            topic: Message topic
            max_messages: Maximum messages to consume
            
        Returns:
            List of messages
        """
        # This would implement message consumption logic
        return []


# Factory function
def create_adapter(config: Dict[str, Any]) -> IntegrationAdapter:
    """
    Create integration adapter based on configuration.
    
    Args:
        config: Adapter configuration
        
    Returns:
        Integration adapter instance
    """
    adapter_type = config.get('type', IntegrationType.WEBHOOK)
    
    if adapter_type == IntegrationType.WEBHOOK:
        return WebhookAdapter(config)
    elif adapter_type == IntegrationType.API:
        return APIAdapter(config)
    elif adapter_type == IntegrationType.MESSAGE_QUEUE:
        return MessageQueueAdapter(config)
    else:
        return IntegrationAdapter(config)
