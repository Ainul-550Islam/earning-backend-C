# =============================================================================
# INTEGRATION_SYSTEM/integ_adapter.py
# =============================================================================
"""
Integration Adapter System.

Provides adapters for different types of integrations (API, webhook, database, etc.).
Handles protocol-specific communication, authentication, and data transformation.
"""

from __future__ import annotations

import logging
import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .integ_constants import IntegrationStatus, IntegrationType, AuthenticationType
from .integ_exceptions import (
    IntegrationError, IntegrationTimeoutError, IntegrationConnectionError,
    IntegrationValidationError, IntegrationAuthenticationError
)
from .transformer import DataTransformer
from .versioning import VersionManager

logger = logging.getLogger(__name__)


class HttpMethod(Enum):
    """HTTP methods for API integrations."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class IntegrationConfig:
    """Configuration for integration adapters."""
    name: str
    integration_type: IntegrationType
    base_url: Optional[str] = None
    authentication_type: AuthenticationType = AuthenticationType.NONE
    credentials: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    rate_limit: Optional[int] = None
    rate_limit_window: int = 60
    version: str = "1.0"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestConfig:
    """Configuration for individual requests."""
    method: Union[HttpMethod, str]
    endpoint: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[int] = None
    retry_attempts: Optional[int] = None
    transform_request: bool = True
    transform_response: bool = True


class IntegrationAdapter(ABC):
    """
    Abstract base class for integration adapters.
    
    Provides common interface and functionality for all integration types.
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize adapter with configuration."""
        self.config = config
        self.status = IntegrationStatus.INACTIVE
        self.last_error: Optional[str] = None
        self.last_success: Optional[datetime] = None
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        
        # Components
        self.transformer = DataTransformer()
        self.version_manager = VersionManager()
        
        # Session for HTTP integrations
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"Initialized {self.__class__.__name__} for {config.name}")
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to integration.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from integration."""
        pass
    
    @abstractmethod
    async def execute(self, method: str, data: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute integration method.
        
        Args:
            method: Method to execute
            data: Method parameters
            timeout: Request timeout
            
        Returns:
            Execution result
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check result
        """
        pass
    
    async def initialize(self) -> bool:
        """
        Initialize adapter.
        
        Returns:
            True if initialization successful
        """
        try:
            if not self.config.enabled:
                self.status = IntegrationStatus.DISABLED
                return True
            
            success = await self.connect()
            if success:
                self.status = IntegrationStatus.ACTIVE
                logger.info(f"Adapter {self.config.name} initialized successfully")
            else:
                self.status = IntegrationStatus.ERROR
                logger.error(f"Failed to initialize adapter {self.config.name}")
            
            return success
            
        except Exception as e:
            self.status = IntegrationStatus.ERROR
            self.last_error = str(e)
            logger.error(f"Error initializing adapter {self.config.name}: {e}")
            return False
    
    async def cleanup(self) -> None:
        """Cleanup adapter resources."""
        try:
            await self.disconnect()
            if self.session:
                await self.session.close()
                self.session = None
            
            self.status = IntegrationStatus.INACTIVE
            logger.info(f"Cleaned up adapter {self.config.name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up adapter {self.config.name}: {e}")
    
    def update_statistics(self, success: bool) -> None:
        """Update adapter statistics."""
        self.request_count += 1
        if success:
            self.success_count += 1
            self.last_success = timezone.now()
        else:
            self.error_count += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        return {
            'name': self.config.name,
            'type': self.config.integration_type.value,
            'status': self.status.value,
            'request_count': self.request_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': (self.success_count / max(self.request_count, 1)) * 100,
            'last_success': self.last_success.isoformat() if self.last_success else None,
            'last_error': self.last_error
        }


class APIAdapter(IntegrationAdapter):
    """
    Adapter for HTTP API integrations.
    
    Handles REST API communication with authentication, retries, and rate limiting.
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize API adapter."""
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def connect(self) -> bool:
        """Establish HTTP session."""
        try:
            # Create session with timeout and connection limits
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(
                limit=100,  # Connection pool size
                limit_per_host=20,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
            
            # Prepare headers
            headers = self.config.headers.copy()
            
            # Add authentication headers
            auth_headers = await self._get_auth_headers()
            headers.update(auth_headers)
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers
            )
            
            # Test connection with health check
            health_result = await self.health_check()
            return health_result.get('status') == 'healthy'
            
        except Exception as e:
            logger.error(f"Failed to connect API adapter {self.config.name}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def execute(self, method: str, data: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute API request.
        
        Args:
            method: HTTP method and endpoint (e.g., "GET /users")
            data: Request data
            timeout: Request timeout
            
        Returns:
            Response data
        """
        if not self.session:
            raise IntegrationConnectionError("Session not established", self.config.name)
        
        # Parse method and endpoint
        parts = method.split(' ', 1)
        if len(parts) != 2:
            raise IntegrationValidationError(f"Invalid method format: {method}")
        
        http_method, endpoint = parts
        http_method = HttpMethod(http_method.upper())
        
        # Prepare request
        url = self._build_url(endpoint)
        request_timeout = timeout or self.config.timeout
        
        # Transform request data
        if self.config.metadata.get('transform_request', True):
            data = await self.transformer.transform_request(data, self.config.version)
        
        # Execute with retries
        last_exception = None
        for attempt in range(self.config.retry_attempts + 1):
            try:
                async with self.session.request(
                    method=http_method.value,
                    url=url,
                    json=data if http_method in [HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH] else None,
                    params=data if http_method == HttpMethod.GET else None,
                    timeout=aiohttp.ClientTimeout(total=request_timeout)
                ) as response:
                    
                    # Handle response
                    if response.status == 429:  # Rate limited
                        retry_after = int(response.headers.get('Retry-After', self.config.retry_delay))
                        raise IntegrationConnectionError(
                            f"Rate limited. Retry after {retry_after}s",
                            self.config.name,
                            retry_after=retry_after
                        )
                    
                    if response.status >= 400:
                        error_text = await response.text()
                        raise IntegrationError(
                            f"HTTP {response.status}: {error_text}",
                            self.config.name
                        )
                    
                    response_data = await response.json()
                    
                    # Transform response data
                    if self.config.metadata.get('transform_response', True):
                        response_data = await self.transformer.transform_response(
                            response_data, self.config.version
                        )
                    
                    self.update_statistics(True)
                    return response_data
                    
            except asyncio.TimeoutError:
                last_exception = IntegrationTimeoutError(f"Request timeout after {request_timeout}s", self.config.name)
            except aiohttp.ClientError as e:
                last_exception = IntegrationConnectionError(f"Connection error: {e}", self.config.name)
            except Exception as e:
                last_exception = IntegrationError(f"Unexpected error: {e}", self.config.name)
            
            if attempt < self.config.retry_attempts:
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
        
        # All retries failed
        self.update_statistics(False)
        self.last_error = str(last_exception)
        raise last_exception
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform API health check."""
        try:
            if not self.session:
                return {'status': 'unhealthy', 'reason': 'No session'}
            
            # Try to ping a health endpoint or root
            health_url = self._build_url('/health') or self.config.base_url + '/health'
            
            try:
                async with self.session.get(health_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status < 400:
                        return {
                            'status': 'healthy',
                            'response_time': 0.0,  # Would need actual timing
                            'endpoint': health_url
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'reason': f'HTTP {response.status}',
                            'endpoint': health_url
                        }
            except Exception:
                # If health endpoint fails, try base URL
                try:
                    async with self.session.get(self.config.base_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        return {
                            'status': 'healthy',
                            'response_time': 0.0,
                            'endpoint': self.config.base_url
                        }
                except Exception as e:
                    return {
                        'status': 'unhealthy',
                        'reason': str(e),
                        'endpoint': self.config.base_url
                    }
                    
        except Exception as e:
            return {'status': 'error', 'reason': str(e)}
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from base URL and endpoint."""
        if not self.config.base_url:
            raise IntegrationError("Base URL not configured", self.config.name)
        
        base_url = self.config.base_url.rstrip('/')
        endpoint = endpoint.lstrip('/')
        
        return f"{base_url}/{endpoint}"
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        if self.config.authentication_type == AuthenticationType.BEARER_TOKEN:
            token = self.config.credentials.get('token')
            if token:
                return {'Authorization': f'Bearer {token}'}
        
        elif self.config.authentication_type == AuthenticationType.API_KEY:
            api_key = self.config.credentials.get('api_key')
            key_header = self.config.credentials.get('key_header', 'X-API-Key')
            if api_key:
                return {key_header: api_key}
        
        elif self.config.authentication_type == AuthenticationType.BASIC_AUTH:
            username = self.config.credentials.get('username')
            password = self.config.credentials.get('password')
            if username and password:
                import base64
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                return {'Authorization': f'Basic {credentials}'}
        
        return {}


class WebhookAdapter(IntegrationAdapter):
    """
    Adapter for webhook integrations.
    
    Handles incoming and outgoing webhook processing.
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize webhook adapter."""
        super().__init__(config)
        self.webhook_handlers: Dict[str, Callable] = {}
        self.signature_secret = config.credentials.get('signature_secret')
    
    async def connect(self) -> bool:
        """Initialize webhook adapter."""
        try:
            # Webhook adapters are always "connected" - they receive events
            self.status = IntegrationStatus.ACTIVE
            return True
        except Exception as e:
            logger.error(f"Failed to connect webhook adapter {self.config.name}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect webhook adapter."""
        # Webhook adapters don't need explicit disconnection
        pass
    
    async def execute(self, method: str, data: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Send webhook event.
        
        Args:
            method: Webhook event type
            data: Event data
            timeout: Request timeout
            
        Returns:
            Response from webhook receivers
        """
        webhook_url = self.config.base_url
        if not webhook_url:
            raise IntegrationError("Webhook URL not configured", self.config.name)
        
        # Prepare webhook payload
        payload = {
            'event_type': method,
            'data': data,
            'timestamp': timezone.now().isoformat(),
            'source': self.config.name
        }
        
        # Add signature if secret is configured
        headers = {}
        if self.signature_secret:
            import hmac
            import hashlib
            
            signature = hmac.new(
                self.signature_secret.encode(),
                json.dumps(payload, sort_keys=True).encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers['X-Webhook-Signature'] = f"sha256={signature}"
        
        # Send webhook
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout or self.config.timeout)
                ) as response:
                    
                    if response.status >= 400:
                        error_text = await response.text()
                        raise IntegrationError(
                            f"Webhook failed with HTTP {response.status}: {error_text}",
                            self.config.name
                        )
                    
                    response_data = await response.json()
                    self.update_statistics(True)
                    return response_data
                    
        except Exception as e:
            self.update_statistics(False)
            self.last_error = str(e)
            raise IntegrationError(f"Webhook delivery failed: {e}", self.config.name)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check webhook adapter health."""
        return {
            'status': 'healthy',
            'webhook_url': self.config.base_url,
            'handlers_count': len(self.webhook_handlers)
        }
    
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register webhook event handler."""
        self.webhook_handlers[event_type] = handler
        logger.info(f"Registered webhook handler for {event_type}")
    
    def unregister_handler(self, event_type: str) -> None:
        """Unregister webhook event handler."""
        self.webhook_handlers.pop(event_type, None)
        logger.info(f"Unregistered webhook handler for {event_type}")
    
    async def process_webhook(self, event_type: str, data: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """
        Process incoming webhook event.
        
        Args:
            event_type: Type of webhook event
            data: Event data
            signature: Webhook signature for verification
            
        Returns:
            Processing result
        """
        # Verify signature if provided
        if signature and self.signature_secret:
            import hmac
            import hashlib
            
            expected_signature = hmac.new(
                self.signature_secret.encode(),
                json.dumps(data, sort_keys=True).encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature.replace('sha256=', ''), expected_signature):
                raise IntegrationError("Invalid webhook signature", self.config.name)
        
        # Find and execute handler
        handler = self.webhook_handlers.get(event_type)
        if not handler:
            raise IntegrationError(f"No handler for webhook event: {event_type}", self.config.name)
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(data)
            else:
                result = handler(data)
            
            self.update_statistics(True)
            return {'status': 'success', 'result': result}
            
        except Exception as e:
            self.update_statistics(False)
            self.last_error = str(e)
            raise IntegrationError(f"Webhook processing failed: {e}", self.config.name)


class DatabaseAdapter(IntegrationAdapter):
    """
    Adapter for database integrations.
    
    Handles database connections and operations.
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize database adapter."""
        super().__init__(config)
        self.connection = None
    
    async def connect(self) -> bool:
        """Establish database connection."""
        try:
            # This would be implemented based on specific database type
            # For now, just simulate connection
            self.status = IntegrationStatus.ACTIVE
            return True
        except Exception as e:
            logger.error(f"Failed to connect database adapter {self.config.name}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            # Close database connection
            self.connection = None
    
    async def execute(self, method: str, data: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute database operation.
        
        Args:
            method: Operation type (query, insert, update, delete)
            data: Operation parameters
            
        Returns:
            Operation result
        """
        # This would be implemented based on specific database type
        # For now, return mock result
        return {'status': 'success', 'affected_rows': 1}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database health."""
        return {'status': 'healthy'}


class MessageQueueAdapter(IntegrationAdapter):
    """
    Adapter for message queue integrations.
    
    Handles pub/sub messaging and queue operations.
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize message queue adapter."""
        super().__init__(config)
        self.connection = None
        self.channels: Dict[str, Any] = {}
    
    async def connect(self) -> bool:
        """Establish message queue connection."""
        try:
            # This would connect to specific message queue system
            self.status = IntegrationStatus.ACTIVE
            return True
        except Exception as e:
            logger.error(f"Failed to connect message queue adapter {self.config.name}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close message queue connection."""
        if self.connection:
            # Close connection and channels
            self.channels.clear()
            self.connection = None
    
    async def execute(self, method: str, data: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute message queue operation.
        
        Args:
            method: Operation type (publish, subscribe, acknowledge)
            data: Operation parameters
            
        Returns:
            Operation result
        """
        # This would be implemented based on specific message queue system
        return {'status': 'success'}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check message queue health."""
        return {'status': 'healthy'}


# Adapter factory
class AdapterFactory:
    """Factory for creating integration adapters."""
    
    _adapter_classes: Dict[IntegrationType, Type[IntegrationAdapter]] = {
        IntegrationType.API: APIAdapter,
        IntegrationType.WEBHOOK: WebhookAdapter,
        IntegrationType.DATABASE: DatabaseAdapter,
        IntegrationType.MESSAGE_QUEUE: MessageQueueAdapter,
    }
    
    @classmethod
    def create_adapter(cls, config: IntegrationConfig) -> IntegrationAdapter:
        """
        Create adapter instance based on configuration.
        
        Args:
            config: Integration configuration
            
        Returns:
            Adapter instance
        """
        adapter_class = cls._adapter_classes.get(config.integration_type)
        if not adapter_class:
            raise IntegrationError(f"Unsupported integration type: {config.integration_type}")
        
        return adapter_class(config)
    
    @classmethod
    def register_adapter(cls, integration_type: IntegrationType, adapter_class: Type[IntegrationAdapter]) -> None:
        """
        Register custom adapter class.
        
        Args:
            integration_type: Integration type
            adapter_class: Adapter class
        """
        cls._adapter_classes[integration_type] = adapter_class
        logger.info(f"Registered custom adapter for {integration_type}")


# Utility functions
async def create_adapter_from_config(config_dict: Dict[str, Any]) -> IntegrationAdapter:
    """
    Create adapter from configuration dictionary.
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        Initialized adapter
    """
    config = IntegrationConfig(
        name=config_dict['name'],
        integration_type=IntegrationType(config_dict['type']),
        base_url=config_dict.get('base_url'),
        authentication_type=AuthenticationType(config_dict.get('auth_type', 'none')),
        credentials=config_dict.get('credentials', {}),
        headers=config_dict.get('headers', {}),
        timeout=config_dict.get('timeout', 30),
        retry_attempts=config_dict.get('retry_attempts', 3),
        retry_delay=config_dict.get('retry_delay', 1.0),
        rate_limit=config_dict.get('rate_limit'),
        rate_limit_window=config_dict.get('rate_limit_window', 60),
        version=config_dict.get('version', '1.0'),
        enabled=config_dict.get('enabled', True),
        metadata=config_dict.get('metadata', {})
    )
    
    adapter = AdapterFactory.create_adapter(config)
    await adapter.initialize()
    
    return adapter
