"""
Integration Webhooks - Webhook integration for alerts system
Provides safe webhook integration with existing alerts architecture
"""
import logging
import json
import hashlib
import hmac
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import (
    validate_alert_rule_condition, 
    validate_threshold_value, 
    validate_channel_config,
    validate_cron_expression,
    validate_webhook_url
)
from api.alerts.services.channels.WebhookAlertService import WebhookAlertService
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_constants import (
    HASH_ALGORITHM,
    SECRET_MIN_LENGTH
)

logger = logging.getLogger(__name__)


class IntegrationWebhookManager:
    """
    Manages webhook integrations with safe architectural integration
    """
    
    def __init__(self):
        self.webhook_service = WebhookAlertService()
        self.registered_webhooks = {}
        self.webhook_stats = {
            'total_received': 0,
            'successful_processed': 0,
            'failed_processed': 0,
            'last_received': None
        }
    
    def register_webhook(self, webhook_id: str, url: str, secret: str = None, 
                        config: Dict[str, Any] = None) -> bool:
        """
        Register webhook with validation
        Validates webhook configuration using existing validators
        """
        try:
            # Validate webhook URL
            url_validation = validate_webhook_url(url)
            if not url_validation['valid']:
                logger.error(f"Invalid webhook URL for {webhook_id}: {url_validation['errors']}")
                return False
            
            # Validate secret if provided
            if secret and len(secret) < SECRET_MIN_LENGTH:
                logger.error(f"Webhook secret too short for {webhook_id}")
                return False
            
            # Validate configuration
            if config:
                config_validation = validate_channel_config(config, 'webhook')
                if not config_validation['valid']:
                    logger.error(f"Invalid webhook config for {webhook_id}: {config_validation['errors']}")
                    return False
            
            # Register webhook
            webhook_data = {
                'id': webhook_id,
                'url': url,
                'secret': secret,
                'config': config or {},
                'created_at': django_tz.now().isoformat(),
                'stats': {
                    'total_received': 0,
                    'successful_processed': 0,
                    'failed_processed': 0,
                    'last_received': None
                }
            }
            
            self.registered_webhooks[webhook_id] = webhook_data
            
            logger.info(f"Registered webhook: {webhook_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering webhook {webhook_id}: {e}")
            return False
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister webhook
        """
        try:
            if webhook_id in self.registered_webhooks:
                del self.registered_webhooks[webhook_id]
                logger.info(f"Unregistered webhook: {webhook_id}")
                return True
            else:
                logger.warning(f"Webhook not found: {webhook_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error unregistering webhook {webhook_id}: {e}")
            return False
    
    def process_incoming_webhook(self, webhook_id: str, request: HttpRequest) -> JsonResponse:
        """
        Process incoming webhook request
        Validates signature and processes data
        """
        try:
            # Get webhook configuration
            webhook = self.registered_webhooks.get(webhook_id)
            if not webhook:
                return JsonResponse({
                    'success': False,
                    'error': f'Webhook not found: {webhook_id}'
                }, status=404)
            
            # Update stats
            webhook['stats']['total_received'] += 1
            webhook['stats']['last_received'] = django_tz.now().isoformat()
            self.webhook_stats['total_received'] += 1
            self.webhook_stats['last_received'] = django_tz.now().isoformat()
            
            # Verify signature if secret is configured
            if webhook['secret']:
                if not self._verify_signature(request, webhook['secret']):
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid signature'
                    }, status=401)
            
            # Parse request data
            try:
                if request.content_type == 'application/json':
                    data = json.loads(request.body.decode('utf-8'))
                else:
                    data = json.loads(request.POST.get('payload', '{}'))
            except json.JSONDecodeError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid JSON: {str(e)}'
                }, status=400)
            
            # Validate webhook data
            validation_result = self._validate_webhook_data(data)
            if not validation_result['valid']:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid webhook data',
                    'validation_errors': validation_result['errors']
                }, status=400)
            
            # Process webhook data
            result = self._process_webhook_data(data, webhook)
            
            if result.get('success', False):
                webhook['stats']['successful_processed'] += 1
                self.webhook_stats['successful_processed'] += 1
                
                return JsonResponse({
                    'success': True,
                    'message': 'Webhook processed successfully',
                    'result': result
                })
            else:
                webhook['stats']['failed_processed'] += 1
                self.webhook_stats['failed_processed'] += 1
                
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Webhook processing failed')
                }, status=500)
            
        except Exception as e:
            logger.error(f"Error processing webhook {webhook_id}: {e}")
            webhook['stats']['failed_processed'] += 1
            self.webhook_stats['failed_processed'] += 1
            
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    def _verify_signature(self, request: HttpRequest, secret: str) -> bool:
        """
        Verify webhook signature
        Uses existing SHA-256 logic from WebhookAlertService
        """
        try:
            # Get signature from header
            signature = request.META.get('HTTP_X_ALERT_SIGNATURE', '')
            if not signature:
                signature = request.META.get('HTTP_X_SIGNATURE', '')
            
            if not signature:
                logger.warning("No signature found in webhook request")
                return False
            
            # Strip prefix if present
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            # Generate expected signature
            body = request.body.decode('utf-8')
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def _validate_webhook_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate webhook data using existing validators
        """
        try:
            errors = []
            
            # Validate alert data if present
            if 'alert' in data:
                alert_data = data['alert']
                
                # Validate condition if present
                if 'condition' in alert_data:
                    condition_validation = validate_alert_rule_condition(alert_data['condition'])
                    if not condition_validation['valid']:
                        errors.extend(condition_validation['errors'])
                
                # Validate threshold if present
                if 'threshold' in alert_data:
                    threshold_validation = validate_threshold_value(alert_data['threshold'])
                    if not threshold_validation['valid']:
                        errors.extend(threshold_validation['errors'])
            
            # Validate integration data if present
            if 'integration' in data:
                integration_data = data['integration']
                
                # Validate webhook URL if present
                if 'webhook_url' in integration_data:
                    webhook_validation = validate_webhook_url(integration_data['webhook_url'])
                    if not webhook_validation['valid']:
                        errors.extend(webhook_validation['errors'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating webhook data: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def _process_webhook_data(self, data: Dict[str, Any], webhook: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process webhook data through integration handler
        """
        try:
            # Extract alert data
            alert_data = data.get('alert', {})
            integration_data = data.get('integration', {})
            
            # Combine data
            combined_data = {
                **alert_data,
                **integration_data,
                'source': 'webhook',
                'webhook_id': webhook['id']
            }
            
            # Process through integration handler
            result = integration_handler.process_alert_data(combined_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing webhook data: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def send_webhook(self, webhook_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send webhook to registered endpoint
        """
        try:
            webhook = self.registered_webhooks.get(webhook_id)
            if not webhook:
                return {
                    'success': False,
                    'error': f'Webhook not found: {webhook_id}'
                }
            
            # Use existing webhook service
            result = self.webhook_service.send_webhook(
                url=webhook['url'],
                data=data,
                config=webhook['config']
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending webhook {webhook_id}: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def get_webhook_stats(self, webhook_id: str = None) -> Dict[str, Any]:
        """
        Get webhook statistics
        """
        try:
            if webhook_id:
                webhook = self.registered_webhooks.get(webhook_id)
                if webhook:
                    return webhook['stats']
                else:
                    return {'error': f'Webhook not found: {webhook_id}'}
            else:
                return {
                    'global_stats': self.webhook_stats,
                    'webhook_count': len(self.registered_webhooks),
                    'webhooks': {
                        webhook_id: webhook['stats']
                        for webhook_id, webhook in self.registered_webhooks.items()
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting webhook stats: {e}")
            return {'error': 'Operation failed'}
    
    def get_all_webhooks(self) -> List[Dict[str, Any]]:
        """
        Get all registered webhooks
        """
        try:
            webhooks = []
            for webhook_id, webhook_data in self.registered_webhooks.items():
                webhooks.append({
                    'id': webhook_id,
                    'url': webhook_data['url'],
                    'has_secret': bool(webhook_data['secret']),
                    'created_at': webhook_data['created_at'],
                    'stats': webhook_data['stats']
                })
            
            return webhooks
            
        except Exception as e:
            logger.error(f"Error getting all webhooks: {e}")
            return []


# Global webhook manager instance
integration_webhook_manager = IntegrationWebhookManager()


# Django view functions for webhook endpoints
@csrf_exempt
@require_http_methods(["POST"])
def integration_webhook_receiver(request, webhook_id: str):
    """
    Django view for receiving webhooks
    """
    return integration_webhook_manager.process_incoming_webhook(webhook_id, request)


@require_http_methods(["GET"])
def webhook_stats_view(request, webhook_id: str = None):
    """
    Django view for webhook statistics
    """
    stats = integration_webhook_manager.get_webhook_stats(webhook_id)
    return JsonResponse(stats)


@require_http_methods(["GET"])
def webhooks_list_view(request):
    """
    Django view for listing webhooks
    """
    webhooks = integration_webhook_manager.get_all_webhooks()
    return JsonResponse({'webhooks': webhooks})


# Utility functions
def register_integration_webhook(webhook_id: str, url: str, secret: str = None, 
                               config: Dict[str, Any] = None) -> bool:
    """
    Register integration webhook
    """
    return integration_webhook_manager.register_webhook(webhook_id, url, secret, config)


def send_integration_webhook(webhook_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send integration webhook
    """
    return integration_webhook_manager.send_webhook(webhook_id, data)


def get_webhook_statistics(webhook_id: str = None) -> Dict[str, Any]:
    """
    Get webhook statistics
    """
    return integration_webhook_manager.get_webhook_stats(webhook_id)


# Webhook event handlers
def handle_alert_webhook(alert_id: int, webhook_data: Dict[str, Any]) -> bool:
    """
    Handle alert webhook event
    """
    try:
        # Get alert log
        alert_log = AlertLog.objects.get(id=alert_id)
        
        # Prepare webhook data
        webhook_payload = {
            'alert': {
                'id': alert_log.id,
                'title': alert_log.title,
                'severity': alert_log.severity,
                'message': alert_log.message,
                'timestamp': alert_log.triggered_at.isoformat()
            },
            'integration': webhook_data
        }
        
        # Send webhook
        result = integration_webhook_manager.send_webhook(
            webhook_data.get('webhook_id'),
            webhook_payload
        )
        
        return result.get('success', False)
        
    except AlertLog.DoesNotExist:
        logger.error(f"Alert log not found: {alert_id}")
        return False
    except Exception as e:
        logger.error(f"Error handling alert webhook: {e}")
        return False


# URL patterns for webhook endpoints
"""
Add to urls.py:

from api.alerts.integration.webhooks_integration import (
    integration_webhook_receiver,
    webhook_stats_view,
    webhooks_list_view
)

urlpatterns = [
    path('api/integration/webhook/<str:webhook_id>/', integration_webhook_receiver, name='integration_webhook_receiver'),
    path('api/integration/webhook/stats/<str:webhook_id>/', webhook_stats_view, name='webhook_stats'),
    path('api/integration/webhook/stats/', webhook_stats_view, name='all_webhook_stats'),
    path('api/integration/webhooks/', webhooks_list_view, name='webhooks_list'),
]
"""
