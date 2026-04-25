"""
Integration Adapter

Adapter pattern for integrating external systems
with the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Protocol
from abc import ABC, abstractmethod
from django.utils import timezone
from .integ_constants import IntegrationType, IntegrationStatus
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class IntegrationAdapter(Protocol):
    """Protocol for integration adapters."""
    
    def execute(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute integration action."""
        ...
    
    def get_status(self) -> Dict[str, Any]:
        """Get integration status."""
        ...
    
    def get_config(self) -> Dict[str, Any]:
        """Get integration configuration."""
        ...


class BaseIntegrationAdapter(ABC):
    """Base class for all integration adapters."""
    
    def __init__(self, integration_id: str, config: Dict[str, Any]):
        self.integration_id = integration_id
        self.config = config
        self.status = IntegrationStatus.INACTIVE
        self.last_sync = None
        self.error_count = 0
        self.last_error = None
        
        # Initialize adapter
        self._initialize()
    
    @abstractmethod
    def _initialize(self):
        """Initialize the integration adapter."""
        pass
    
    @abstractmethod
    def execute(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute integration action."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get integration status."""
        pass
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Get integration configuration."""
        pass
    
    def enable(self) -> bool:
        """Enable the integration."""
        try:
            if self.status == IntegrationStatus.ACTIVE:
                return True
            
            # Perform enable logic
            result = self._enable()
            
            if result:
                self.status = IntegrationStatus.ACTIVE
                logger.info(f"Enabled integration {self.integration_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error enabling integration {self.integration_id}: {e}")
            return False
    
    def disable(self) -> bool:
        """Disable the integration."""
        try:
            if self.status == IntegrationStatus.INACTIVE:
                return True
            
            # Perform disable logic
            result = self._disable()
            
            if result:
                self.status = IntegrationStatus.INACTIVE
                logger.info(f"Disabled integration {self.integration_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error disabling integration {self.integration_id}: {e}")
            return False
    
    def sync(self) -> Dict[str, Any]:
        """Synchronize integration data."""
        try:
            # Perform sync logic
            result = self._sync()
            
            self.last_sync = timezone.now()
            
            if result.get('success', False):
                self.error_count = 0
                self.last_error = None
                logger.info(f"Successfully synced integration {self.integration_id}")
            else:
                self.error_count += 1
                self.last_error = result.get('error', 'Unknown error')
                logger.error(f"Failed to sync integration {self.integration_id}: {self.last_error}")
            
            return result
            
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"Error syncing integration {self.integration_id}: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            # Perform health check logic
            result = self._health_check()
            
            # Add common health info
            result.update({
                'integration_id': self.integration_id,
                'status': self.status,
                'last_sync': self.last_sync,
                'error_count': self.error_count,
                'last_error': self.last_error,
                'timestamp': timezone.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in health check for {self.integration_id}: {e}")
            
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get integration metrics."""
        try:
            # Get metrics from implementation
            metrics = self._get_metrics()
            
            # Add common metrics
            metrics.update({
                'integration_id': self.integration_id,
                'status': self.status,
                'error_count': self.error_count,
                'last_error': self.last_error,
                'last_sync': self.last_sync,
                'uptime_percentage': self._calculate_uptime(),
                'timestamp': timezone.now().isoformat()
            })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting metrics for {self.integration_id}: {e}")
            
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _calculate_uptime(self) -> float:
        """Calculate uptime percentage."""
        # This would be calculated based on historical data
        # For now, return a placeholder
        return 95.0
    
    @abstractmethod
    def _enable(self) -> bool:
        """Enable integration implementation."""
        pass
    
    @abstractmethod
    def _disable(self) -> bool:
        """Disable integration implementation."""
        pass
    
    @abstractmethod
    def _sync(self) -> Dict[str, Any]:
        """Sync implementation."""
        pass
    
    @abstractmethod
    def _health_check(self) -> Dict[str, Any]:
        """Health check implementation."""
        pass
    
    @abstractmethod
    def _get_metrics(self) -> Dict[str, Any]:
        """Get metrics implementation."""
        pass


class WebhookIntegrationAdapter(BaseIntegrationAdapter):
    """Webhook integration adapter."""
    
    def _initialize(self):
        """Initialize webhook integration."""
        logger.info(f"Initialized webhook integration {self.integration_id}")
    
    def execute(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute webhook action."""
        try:
            if action == 'send_webhook':
                return self._send_webhook(data)
            elif action == 'validate_webhook':
                return self._validate_webhook(data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown action: {action}'
                }
                
        except Exception as e:
            logger.error(f"Error executing webhook action {action}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send webhook data."""
        import requests
        
        webhook_url = self.config.get('webhook_url')
        webhook_secret = self.config.get('webhook_secret')
        
        if not webhook_url:
            return {
                'success': False,
                'error': 'Webhook URL not configured'
            }
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'OfferRouting-Webhook/1.0'
            }
            
            if webhook_secret:
                headers['X-Webhook-Signature'] = self._generate_signature(data, webhook_secret)
            
            response = requests.post(
                webhook_url,
                json=data,
                headers=headers,
                timeout=30
            )
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response_text': response.text,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate webhook configuration."""
        webhook_url = self.config.get('webhook_url')
        
        if not webhook_url:
            return {
                'valid': False,
                'error': 'Webhook URL not configured'
            }
        
        # Basic URL validation
        if not webhook_url.startswith(('http://', 'https://')):
            return {
                'valid': False,
                'error': 'Invalid webhook URL format'
            }
        
        return {
            'valid': True,
            'webhook_url': webhook_url
        }
    
    def _generate_signature(self, data: Dict[str, Any], secret: str) -> str:
        """Generate webhook signature."""
        import hmac
        import hashlib
        
        message = str(data).encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_status(self) -> Dict[str, Any]:
        """Get webhook integration status."""
        return {
            'integration_id': self.integration_id,
            'type': IntegrationType.WEBHOOK.value,
            'status': self.status,
            'config': self.get_safe_config(),
            'last_sync': self.last_sync,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'timestamp': timezone.now().isoformat()
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get webhook configuration."""
        return self.config
    
    def get_safe_config(self) -> Dict[str, Any]:
        """Get safe configuration (without secrets)."""
        safe_config = self.config.copy()
        
        # Remove sensitive fields
        safe_config.pop('webhook_secret', None)
        safe_config.pop('api_key', None)
        
        return safe_config
    
    def _enable(self) -> bool:
        """Enable webhook integration."""
        # Validate webhook URL
        validation = self._validate_webhook({})
        
        if not validation['valid']:
            logger.error(f"Cannot enable webhook integration: {validation['error']}")
            return False
        
        return True
    
    def _disable(self) -> bool:
        """Disable webhook integration."""
        # No specific disable logic needed for webhooks
        return True
    
    def _sync(self) -> Dict[str, Any]:
        """Sync webhook integration."""
        # Webhooks don't need syncing
        return {
            'success': True,
            'message': 'Webhook integration does not require syncing',
            'timestamp': timezone.now().isoformat()
        }
    
    def _health_check(self) -> Dict[str, Any]:
        """Health check for webhook integration."""
        validation = self._validate_webhook({})
        
        return {
            'status': 'healthy' if validation['valid'] else 'unhealthy',
            'webhook_url_valid': validation['valid'],
            'webhook_url': self.config.get('webhook_url'),
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_metrics(self) -> Dict[str, Any]:
        """Get webhook metrics."""
        return {
            'webhook_url': self.config.get('webhook_url'),
            'webhook_configured': bool(self.config.get('webhook_url')),
            'last_validation': self.last_sync
        }


class APIIntegrationAdapter(BaseIntegrationAdapter):
    """API integration adapter."""
    
    def _initialize(self):
        """Initialize API integration."""
        logger.info(f"Initialized API integration {self.integration_id}")
    
    def execute(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API action."""
        try:
            if action == 'make_request':
                return self._make_api_request(data)
            elif action == 'validate_credentials':
                return self._validate_credentials(data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown action: {action}'
                }
                
        except Exception as e:
            logger.error(f"Error executing API action {action}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _make_api_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request."""
        import requests
        
        api_url = self.config.get('api_url')
        api_key = self.config.get('api_key')
        method = data.get('method', 'POST')
        endpoint = data.get('endpoint', '/')
        request_data = data.get('data', {})
        
        if not api_url or not api_key:
            return {
                'success': False,
                'error': 'API URL or key not configured'
            }
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'User-Agent': 'OfferRouting-API/1.0'
            }
            
            url = f"{api_url.rstrip('/')}/{endpoint.lstrip('/')}"
            
            response = requests.request(
                method=method,
                url=url,
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            return {
                'success': 200 <= response.status_code < 300,
                'status_code': response.status_code,
                'response_data': response.json() if response.headers.get('Content-Type', '').startswith('application/json') else response.text,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_credentials(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API credentials."""
        api_url = self.config.get('api_url')
        api_key = self.config.get('api_key')
        
        if not api_url or not api_key:
            return {
                'valid': False,
                'error': 'API URL or key not configured'
            }
        
        # Test API connection
        test_result = self._make_api_request({
            'method': 'GET',
            'endpoint': '/health',
            'data': {}
        })
        
        return {
            'valid': test_result['success'],
            'api_url': api_url,
            'test_status_code': test_result.get('status_code'),
            'timestamp': timezone.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get API integration status."""
        return {
            'integration_id': self.integration_id,
            'type': IntegrationType.API.value,
            'status': self.status,
            'config': self.get_safe_config(),
            'last_sync': self.last_sync,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'timestamp': timezone.now().isoformat()
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get API configuration."""
        return self.config
    
    def get_safe_config(self) -> Dict[str, Any]:
        """Get safe configuration (without secrets)."""
        safe_config = self.config.copy()
        
        # Remove sensitive fields
        safe_config.pop('api_key', None)
        safe_config.pop('api_secret', None)
        
        return safe_config
    
    def _enable(self) -> bool:
        """Enable API integration."""
        # Validate API credentials
        validation = self._validate_credentials({})
        
        if not validation['valid']:
            logger.error(f"Cannot enable API integration: {validation['error']}")
            return False
        
        return True
    
    def _disable(self) -> bool:
        """Disable API integration."""
        # No specific disable logic needed for APIs
        return True
    
    def _sync(self) -> Dict[str, Any]:
        """Sync API integration."""
        # APIs don't need syncing
        return {
            'success': True,
            'message': 'API integration does not require syncing',
            'timestamp': timezone.now().isoformat()
        }
    
    def _health_check(self) -> Dict[str, Any]:
        """Health check for API integration."""
        validation = self._validate_credentials({})
        
        return {
            'status': 'healthy' if validation['valid'] else 'unhealthy',
            'api_url_valid': validation['valid'],
            'api_url': self.config.get('api_url'),
            'test_status_code': validation.get('test_status_code'),
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_metrics(self) -> Dict[str, Any]:
        """Get API metrics."""
        return {
            'api_url': self.config.get('api_url'),
            'api_configured': bool(self.config.get('api_url')),
            'last_validation': self.last_sync
        }


# Factory function for creating adapters
def create_adapter(integration_type: str, integration_id: str, 
                 config: Dict[str, Any]) -> Optional[BaseIntegrationAdapter]:
    """Create integration adapter based on type."""
    
    if integration_type == IntegrationType.WEBHOOK.value:
        return WebhookIntegrationAdapter(integration_id, config)
    elif integration_type == IntegrationType.API.value:
        return APIIntegrationAdapter(integration_id, config)
    else:
        logger.error(f"Unknown integration type: {integration_type}")
        return None
