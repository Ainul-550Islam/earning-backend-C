"""
Webhooks Integration

Webhook integration adapter for receiving
and sending webhook events.
"""

import logging
import hmac
import hashlib
from typing import Dict, List, Any, Optional
from django.utils import timezone
from .integ_adapter import BaseIntegrationAdapter
from .integ_constants import IntegrationType, IntegrationStatus
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class WebhookIntegration(BaseIntegrationAdapter):
    """Webhook integration adapter."""
    
    def _initialize(self):
        """Initialize webhook integration."""
        self.webhook_url = self.config.get('webhook_url')
        self.webhook_secret = self.config.get('webhook_secret')
        self.retry_count = 0
        self.last_webhook = None
        
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
        
        if not self.webhook_url:
            return {
                'success': False,
                'error': 'Webhook URL not configured'
            }
        
        try:
            # Generate signature
            signature = self._generate_signature(data)
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'OfferRouting-Webhook/1.0',
                'X-Webhook-Signature': signature
            }
            
            # Send webhook
            response = requests.post(
                self.webhook_url,
                json=data,
                headers=headers,
                timeout=30
            )
            
            # Update last webhook
            self.last_webhook = {
                'data': data,
                'response_status': response.status_code,
                'response_text': response.text,
                'timestamp': timezone.now().isoformat()
            }
            
            # Reset retry count on success
            if response.status_code == 200:
                self.retry_count = 0
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response_text': response.text,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.retry_count += 1
            logger.error(f"Error sending webhook: {e}")
            return {
                'success': False,
                'error': str(e),
                'retry_count': self.retry_count
            }
    
    def _validate_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate webhook configuration."""
        if not self.webhook_url:
            return {
                'valid': False,
                'error': 'Webhook URL not configured'
            }
        
        # Basic URL validation
        if not self.webhook_url.startswith(('http://', 'https://')):
            return {
                'valid': False,
                'error': 'Invalid webhook URL format'
            }
        
        return {
            'valid': True,
            'webhook_url': self.webhook_url,
            'configured': True
        }
    
    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate webhook signature."""
        if not self.webhook_secret:
            return ''
        
        message = str(data).encode('utf-8')
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
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
            'webhook_url': self.webhook_url,
            'webhook_configured': bool(self.webhook_url),
            'last_webhook': self.last_webhook,
            'retry_count': self.retry_count,
            'timestamp': timezone.now().isoformat()
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get webhook configuration."""
        return self.config
    
    def get_safe_config(self) -> Dict[str, Any]:
        """Get safe configuration (without secrets)."""
        safe_config = self.config.copy()
        safe_config.pop('webhook_secret', None)
        return safe_config
    
    def _enable(self) -> bool:
        """Enable webhook integration."""
        # Validate webhook before enabling
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
            'webhook_url': self.webhook_url,
            'last_webhook': self.last_webhook,
            'retry_count': self.retry_count,
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_metrics(self) -> Dict[str, Any]:
        """Get webhook metrics."""
        return {
            'webhook_url': self.webhook_url,
            'webhook_configured': bool(self.webhook_url),
            'last_webhook': self.last_webhook,
            'retry_count': self.retry_count,
            'last_signature': self._generate_signature({'test': True}) if self.webhook_secret else None
        }
