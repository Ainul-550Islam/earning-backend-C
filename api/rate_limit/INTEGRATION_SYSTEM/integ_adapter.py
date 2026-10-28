"""
Integration Adapter - External Service Adapter

Adapter pattern implementation for integrating with external services,
providing a unified interface for different service types and protocols.
"""

import logging
import json
import hmac
import hashlib
import requests
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin, urlparse
from django.conf import settings
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationStatus
from .integ_exceptions import IntegrationError, IntegrationTimeoutError, IntegrationAuthError
from .data_validator import DataValidator
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class AdapterType(Enum):
    """Types of integration adapters."""
    REST_API = "rest_api"
    WEBHOOK = "webhook"
    MESSAGE_QUEUE = "message_queue"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    CUSTOM = "custom"


class AuthType(Enum):
    """Authentication types for adapters."""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    HMAC = "hmac"
    CUSTOM = "custom"


@dataclass
class AdapterConfig:
    """Configuration for integration adapter."""
    name: str
    adapter_type: AdapterType
    base_url: Optional[str] = None
    auth_type: AuthType = AuthType.NONE
    auth_credentials: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    rate_limit: Optional[Dict[str, Any]] = None
    webhook_secret: Optional[str] = None
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterRequest:
    """Request data for adapter."""
    method: str = "GET"
    endpoint: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    files: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None


@dataclass
class AdapterResponse:
    """Response data from adapter."""
    status_code: int
    data: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    success: bool = False
    error_message: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntegrationAdapter:
    """Base integration adapter for external services."""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.validator = DataValidator()
        self.circuit_breaker = CircuitBreaker(
            integration_name=config.name,
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=IntegrationError
        )
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """Setup session with authentication and headers."""
        # Set default headers
        self.session.headers.update(self.config.headers)
        
        # Setup authentication
        if self.config.auth_type == AuthType.API_KEY:
            key_name = self.config.auth_credentials.get('key_name', 'X-API-Key')
            self.session.headers[key_name] = self.config.auth_credentials.get('api_key')
        
        elif self.config.auth_type == AuthType.BEARER_TOKEN:
            self.session.headers['Authorization'] = f"Bearer {self.config.auth_credentials.get('token')}"
        
        elif self.config.auth_type == AuthType.BASIC_AUTH:
            self.session.auth = (
                self.config.auth_credentials.get('username'),
                self.config.auth_credentials.get('password')
            )
        
        elif self.config.auth_type == AuthType.OAUTH2:
            token = self._get_oauth2_token()
            self.session.headers['Authorization'] = f"Bearer {token}"
    
    def _get_oauth2_token(self) -> str:
        """Get OAuth2 token."""
        # Implementation would vary based on OAuth2 provider
        # This is a placeholder for OAuth2 token retrieval
        token_url = self.config.auth_credentials.get('token_url')
        client_id = self.config.auth_credentials.get('client_id')
        client_secret = self.config.auth_credentials.get('client_secret')
        
        try:
            response = requests.post(
                token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': client_id,
                    'client_secret': client_secret
                }
            )
            
            if response.status_code == 200:
                return response.json().get('access_token')
            else:
                raise IntegrationAuthError(f"OAuth2 token request failed: {response.status_code}")
        
        except Exception as e:
            raise IntegrationAuthError(f"OAuth2 authentication failed: {str(e)}")
    
    def _sign_request(self, request_data: str) -> str:
        """Sign request with HMAC."""
        if self.config.auth_type == AuthType.HMAC and self.config.webhook_secret:
            signature = hmac.new(
                self.config.webhook_secret.encode(),
                request_data.encode(),
                hashlib.sha256
            ).hexdigest()
            return signature
        return ""
    
    async def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        """Execute request through adapter."""
        start_time = timezone.now()
        
        try:
            # Validate request data
            self.validator.validate_request_data(request.data)
            
            # Execute through circuit breaker
            response = await self.circuit_breaker.call(
                self._execute_request_internal, request
            )
            
            # Calculate execution time
            response.execution_time = (timezone.now() - start_time).total_seconds()
            
            return response
            
        except Exception as e:
            logger.error(f"Adapter request failed: {str(e)}")
            return AdapterResponse(
                status_code=500,
                success=False,
                error_message=str(e),
                execution_time=(timezone.now() - start_time).total_seconds()
            )
    
    async def _execute_request_internal(self, request: AdapterRequest) -> AdapterResponse:
        """Execute request internally."""
        try:
            # Prepare request
            url = urljoin(self.config.base_url, request.endpoint) if self.config.base_url else request.endpoint
            
            # Merge headers
            headers = {**self.session.headers, **request.headers}
            
            # Add HMAC signature if configured
            if self.config.auth_type == AuthType.HMAC:
                request_data = json.dumps(request.data, sort_keys=True)
                signature = self._sign_request(request_data)
                if signature:
                    headers['X-Signature'] = signature
            
            # Make request
            response = self.session.request(
                method=request.method,
                url=url,
                params=request.params,
                json=request.data if request.data else None,
                files=request.files,
                headers=headers,
                timeout=request.timeout or self.config.timeout
            )
            
            # Parse response
            try:
                response_data = response.json()
            except ValueError:
                response_data = {'content': response.text}
            
            return AdapterResponse(
                status_code=response.status_code,
                data=response_data,
                headers=dict(response.headers),
                success=response.status_code < 400,
                metadata={
                    'url': url,
                    'method': request.method,
                    'adapter': self.config.name
                }
            )
            
        except requests.exceptions.Timeout:
            raise IntegrationTimeoutError(f"Request timeout: {request.endpoint}")
        except requests.exceptions.RequestException as e:
            raise IntegrationError(f"Request failed: {str(e)}")
    
    async def send_webhook(self, event_type: str, payload: Dict[str, Any]) -> AdapterResponse:
        """Send webhook event."""
        request = AdapterRequest(
            method="POST",
            endpoint=self.config.custom_settings.get('webhook_endpoint', ''),
            data={
                'event_type': event_type,
                'payload': payload,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        return await self.execute_request(request)
    
    async def get_data(self, endpoint: str, params: Dict[str, Any] = None) -> AdapterResponse:
        """Get data from external service."""
        request = AdapterRequest(
            method="GET",
            endpoint=endpoint,
            params=params or {}
        )
        
        return await self.execute_request(request)
    
    async def post_data(self, endpoint: str, data: Dict[str, Any]) -> AdapterResponse:
        """Post data to external service."""
        request = AdapterRequest(
            method="POST",
            endpoint=endpoint,
            data=data
        )
        
        return await self.execute_request(request)
    
    async def put_data(self, endpoint: str, data: Dict[str, Any]) -> AdapterResponse:
        """Put data to external service."""
        request = AdapterRequest(
            method="PUT",
            endpoint=endpoint,
            data=data
        )
        
        return await self.execute_request(request)
    
    async def delete_data(self, endpoint: str) -> AdapterResponse:
        """Delete data from external service."""
        request = AdapterRequest(
            method="DELETE",
            endpoint=endpoint
        )
        
        return await self.execute_request(request)


class RestAPIAdapter(IntegrationAdapter):
    """REST API adapter for HTTP-based integrations."""
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.config.adapter_type = AdapterType.REST_API


class WebhookAdapter(IntegrationAdapter):
    """Webhook adapter for outbound webhook integrations."""
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.config.adapter_type = AdapterType.WEBHOOK
    
    async def send_event(self, event_type: str, payload: Dict[str, Any]) -> AdapterResponse:
        """Send webhook event with proper formatting."""
        webhook_data = {
            'event': event_type,
            'data': payload,
            'timestamp': timezone.now().isoformat(),
            'source': 'rate_limit_system'
        }
        
        return await self.send_webhook(event_type, webhook_data)


class MessageQueueAdapter(IntegrationAdapter):
    """Message queue adapter for async messaging."""
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.config.adapter_type = AdapterType.MESSAGE_QUEUE
    
    async def publish_message(self, topic: str, message: Dict[str, Any]) -> AdapterResponse:
        """Publish message to queue."""
        request = AdapterRequest(
            method="POST",
            endpoint=f"/topics/{topic}/messages",
            data={
                'message': message,
                'timestamp': timezone.now().isoformat(),
                'source': 'rate_limit_system'
            }
        )
        
        return await self.execute_request(request)
    
    async def consume_messages(self, topic: str, callback: Callable) -> None:
        """Consume messages from queue (implementation depends on queue type)."""
        # This would be implemented based on the specific message queue system
        # For now, it's a placeholder for the interface
        pass


class DatabaseAdapter(IntegrationAdapter):
    """Database adapter for external database integrations."""
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.config.adapter_type = AdapterType.DATABASE
    
    async def query_data(self, query: str, params: Dict[str, Any] = None) -> AdapterResponse:
        """Execute database query."""
        request = AdapterRequest(
            method="POST",
            endpoint="/query",
            data={
                'query': query,
                'params': params or {}
            }
        )
        
        return await self.execute_request(request)
    
    async def insert_data(self, table: str, data: Dict[str, Any]) -> AdapterResponse:
        """Insert data into table."""
        request = AdapterRequest(
            method="POST",
            endpoint=f"/tables/{table}/insert",
            data=data
        )
        
        return await self.execute_request(request)
    
    async def update_data(self, table: str, condition: Dict[str, Any], data: Dict[str, Any]) -> AdapterResponse:
        """Update data in table."""
        request = AdapterRequest(
            method="PUT",
            endpoint=f"/tables/{table}/update",
            data={
                'condition': condition,
                'data': data
            }
        )
        
        return await self.execute_request(request)


class AdapterFactory:
    """Factory for creating integration adapters."""
    
    @staticmethod
    def create_adapter(config: AdapterConfig) -> IntegrationAdapter:
        """Create adapter based on configuration."""
        if config.adapter_type == AdapterType.REST_API:
            return RestAPIAdapter(config)
        elif config.adapter_type == AdapterType.WEBHOOK:
            return WebhookAdapter(config)
        elif config.adapter_type == AdapterType.MESSAGE_QUEUE:
            return MessageQueueAdapter(config)
        elif config.adapter_type == AdapterType.DATABASE:
            return DatabaseAdapter(config)
        else:
            return IntegrationAdapter(config)
    
    @staticmethod
    def create_webhook_adapter(name: str, webhook_url: str, secret: str = None) -> WebhookAdapter:
        """Create webhook adapter with common configuration."""
        config = AdapterConfig(
            name=name,
            adapter_type=AdapterType.WEBHOOK,
            base_url=webhook_url,
            auth_type=AuthType.HMAC if secret else AuthType.NONE,
            webhook_secret=secret,
            custom_settings={'webhook_endpoint': webhook_url}
        )
        
        return WebhookAdapter(config)
    
    @staticmethod
    def create_api_adapter(name: str, base_url: str, api_key: str = None, 
                          key_name: str = 'X-API-Key') -> RestAPIAdapter:
        """Create REST API adapter with common configuration."""
        auth_type = AuthType.API_KEY if api_key else AuthType.NONE
        auth_credentials = {'api_key': api_key, 'key_name': key_name} if api_key else {}
        
        config = AdapterConfig(
            name=name,
            adapter_type=AdapterType.REST_API,
            base_url=base_url,
            auth_type=auth_type,
            auth_credentials=auth_credentials
        )
        
        return RestAPIAdapter(config)


# Pre-configured adapters for common integrations
class PreconfiguredAdapters:
    """Pre-configured adapters for common external services."""
    
    @staticmethod
    def get_slack_webhook_adapter(webhook_url: str) -> WebhookAdapter:
        """Get Slack webhook adapter."""
        return AdapterFactory.create_webhook_adapter(
            name='slack_webhook',
            webhook_url=webhook_url
        )
    
    @staticmethod
    def get_discord_webhook_adapter(webhook_url: str) -> WebhookAdapter:
        """Get Discord webhook adapter."""
        return AdapterFactory.create_webhook_adapter(
            name='discord_webhook',
            webhook_url=webhook_url
        )
    
    @staticmethod
    def get_email_service_adapter(base_url: str, api_key: str) -> RestAPIAdapter:
        """Get email service adapter."""
        return AdapterFactory.create_api_adapter(
            name='email_service',
            base_url=base_url,
            api_key=api_key
        )
    
    @staticmethod
    def get_analytics_service_adapter(base_url: str, api_key: str) -> RestAPIAdapter:
        """Get analytics service adapter."""
        return AdapterFactory.create_api_adapter(
            name='analytics_service',
            base_url=base_url,
            api_key=api_key
        )
