"""
Webhook management for alerts app
"""
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class WebhookManager:
    """Manages webhook configuration and delivery"""
    
    def __init__(self):
        self.webhooks = {}
        self.delivery_queue = []
        self.retry_queue = []
    
    def register_webhook(self, webhook_id: str, config: Dict[str, Any]):
        """Register a webhook"""
        self.webhooks[webhook_id] = {
            'id': webhook_id,
            'url': config['url'],
            'secret': config.get('secret', ''),
            'events': config.get('events', ['*']),
            'active': config.get('active', True),
            'retry_count': 0,
            'max_retries': config.get('max_retries', 3),
            'timeout': config.get('timeout', 30),
            'headers': config.get('headers', {}),
            'created_at': timezone.now(),
            'last_delivery': None,
            'delivery_count': 0,
            'failure_count': 0
        }
        logger.info(f"Registered webhook: {webhook_id}")
    
    def unregister_webhook(self, webhook_id: str):
        """Unregister a webhook"""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info(f"Unregistered webhook: {webhook_id}")
    
    def get_webhook(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook configuration"""
        return self.webhooks.get(webhook_id)
    
    def get_all_webhooks(self) -> Dict[str, Dict[str, Any]]:
        """Get all webhooks"""
        return self.webhooks.copy()
    
    def deliver_webhook(self, webhook_id: str, event_type: str, data: Dict[str, Any]) -> bool:
        """Deliver event to webhook"""
        webhook = self.get_webhook(webhook_id)
        if not webhook or not webhook['active']:
            return False
        
        # Check if webhook is interested in this event
        if '*' not in webhook['events'] and event_type not in webhook['events']:
            return True  # Not interested, but not a failure
        
        # Prepare payload
        payload = {
            'event': event_type,
            'data': data,
            'timestamp': timezone.now().isoformat(),
            'webhook_id': webhook_id
        }
        
        # Add signature if secret is configured
        if webhook['secret']:
            payload['signature'] = self._generate_signature(
                json.dumps(payload, sort_keys=True),
                webhook['secret']
            )
        
        try:
            import requests
            from .validators import validate_webhook_url as _validate_outbound_url
            check = _validate_outbound_url(webhook['url'])
            if not check.get('valid', False):
                webhook['failure_count'] += 1
                logger.error(f"Webhook delivery blocked (unsafe URL): {webhook_id}: {check.get('errors')}")
                return False
            
            response = requests.post(  # nosec B113 - timeout comes from the webhook config (default 30s)
                webhook['url'],
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'AlertSystem-Webhook/1.0',
                    'X-Webhook-ID': webhook_id,
                    'X-Event-Type': event_type,
                    **webhook['headers']
                },
                timeout=webhook['timeout'],
                allow_redirects=False,  # a redirect could bounce us to an internal address
            )
            
            # Update webhook stats
            webhook['last_delivery'] = timezone.now()
            webhook['delivery_count'] += 1
            
            if 200 <= response.status_code < 300:
                webhook['retry_count'] = 0
                logger.info(f"Webhook delivered successfully: {webhook_id}")
                return True
            else:
                webhook['failure_count'] += 1
                logger.error(f"Webhook delivery failed: {webhook_id}, status: {response.status_code}")
                
                # Add to retry queue
                if webhook['retry_count'] < webhook['max_retries']:
                    self.retry_queue.append({
                        'webhook_id': webhook_id,
                        'event_type': event_type,
                        'data': data,
                        'retry_count': webhook['retry_count'] + 1,
                        'retry_after': timezone.now() + timedelta(minutes=2 ** webhook['retry_count'])
                    })
                
                return False
        
        except Exception as e:
            webhook['failure_count'] += 1
            logger.error(f"Webhook delivery error: {webhook_id}, error: {e}")
            
            # Add to retry queue
            if webhook['retry_count'] < webhook['max_retries']:
                self.retry_queue.append({
                    'webhook_id': webhook_id,
                    'event_type': event_type,
                    'data': data,
                    'retry_count': webhook['retry_count'] + 1,
                    'retry_after': timezone.now() + timedelta(minutes=2 ** webhook['retry_count'])
                })
            
            return False
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature"""
        expected_signature = self._generate_signature(payload, secret)
        return hmac.compare_digest(expected_signature, signature)
    
    def process_retry_queue(self):
        """Process webhook retry queue"""
        current_time = timezone.now()
        remaining_retries = []
        
        for retry_item in self.retry_queue:
            if retry_item['retry_after'] <= current_time:
                webhook = self.get_webhook(retry_item['webhook_id'])
                if webhook:
                    webhook['retry_count'] = retry_item['retry_count']
                    self.deliver_webhook(
                        retry_item['webhook_id'],
                        retry_item['event_type'],
                        retry_item['data']
                    )
            else:
                remaining_retries.append(retry_item)
        
        self.retry_queue = remaining_retries
    
    def get_webhook_stats(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook delivery statistics"""
        webhook = self.get_webhook(webhook_id)
        if not webhook:
            return None
        
        success_rate = 0
        total_deliveries = webhook['delivery_count']
        if total_deliveries > 0:
            success_rate = ((total_deliveries - webhook['failure_count']) / total_deliveries) * 100
        
        return {
            'webhook_id': webhook_id,
            'active': webhook['active'],
            'delivery_count': total_deliveries,
            'failure_count': webhook['failure_count'],
            'success_rate': round(success_rate, 2),
            'last_delivery': webhook['last_delivery'].isoformat() if webhook['last_delivery'] else None,
            'retry_count': webhook['retry_count'],
            'created_at': webhook['created_at'].isoformat()
        }


class AlertWebhookManager(WebhookManager):
    """Specialized webhook manager for alert events"""
    
    def __init__(self):
        super().__init__()
        self._load_alert_webhooks()
    
    def _load_alert_webhooks(self):
        """Load alert webhooks from configuration"""
        webhook_configs = getattr(settings, 'ALERT_WEBHOOKS', {})
        
        for webhook_id, config in webhook_configs.items():
            self.register_webhook(webhook_id, config)
    
    def trigger_alert_webhooks(self, alert_log):
        """Trigger webhooks for alert event"""
        event_data = {
            'alert_id': alert_log.id,
            'rule_id': alert_log.rule.id,
            'rule_name': alert_log.rule.name,
            'severity': alert_log.rule.severity,
            'message': alert_log.message,
            'trigger_value': alert_log.trigger_value,
            'threshold_value': alert_log.threshold_value,
            'triggered_at': alert_log.triggered_at.isoformat(),
            'details': alert_log.details,
            'is_resolved': alert_log.is_resolved,
            'resolved_at': alert_log.resolved_at.isoformat() if alert_log.resolved_at else None
        }
        
        # Deliver to all relevant webhooks
        for webhook_id in self.webhooks:
            self.deliver_webhook(webhook_id, 'alert.triggered', event_data)
    
    def trigger_resolution_webhooks(self, alert_log):
        """Trigger webhooks for alert resolution"""
        event_data = {
            'alert_id': alert_log.id,
            'rule_id': alert_log.rule.id,
            'rule_name': alert_log.rule.name,
            'severity': alert_log.rule.severity,
            'resolved_at': alert_log.resolved_at.isoformat(),
            'resolved_by': alert_log.resolved_by.username if alert_log.resolved_by else None,
            'resolution_note': alert_log.resolution_note,
            'time_to_resolve_minutes': (
                (alert_log.resolved_at - alert_log.triggered_at).total_seconds() / 60
                if alert_log.resolved_at else 0
            )
        }
        
        for webhook_id in self.webhooks:
            self.deliver_webhook(webhook_id, 'alert.resolved', event_data)
    
    def trigger_escalation_webhooks(self, alert_log, escalation_level):
        """Trigger webhooks for alert escalation"""
        event_data = {
            'alert_id': alert_log.id,
            'rule_id': alert_log.rule.id,
            'rule_name': alert_log.rule.name,
            'severity': alert_log.rule.severity,
            'escalation_level': escalation_level,
            'escalated_at': timezone.now().isoformat(),
            'time_since_trigger_minutes': (
                (timezone.now() - alert_log.triggered_at).total_seconds() / 60
            )
        }
        
        for webhook_id in self.webhooks:
            self.deliver_webhook(webhook_id, 'alert.escalated', event_data)


# Global webhook manager instances
webhook_manager = WebhookManager()
alert_webhook_manager = AlertWebhookManager()


def get_webhook_manager() -> WebhookManager:
    """Get global webhook manager"""
    return webhook_manager


def get_alert_webhook_manager() -> AlertWebhookManager:
    """Get global alert webhook manager"""
    return alert_webhook_manager


# Django views for webhook management
@csrf_exempt
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def webhook_endpoint(request, webhook_id=None):
    """Generic webhook endpoint"""
    # Management verbs (info / update / delete) are staff-only; POST stays signature-checked.
    if request.method != 'POST':
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated and user.is_staff):
            return JsonResponse({'error': 'Forbidden'}, status=403)
    if request.method == 'GET':
        return handle_webhook_info(request, webhook_id)
    elif request.method == 'POST':
        return handle_incoming_webhook(request, webhook_id)
    elif request.method == 'PUT':
        return handle_webhook_update(request, webhook_id)
    elif request.method == 'DELETE':
        return handle_webhook_delete(request, webhook_id)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


def handle_webhook_info(request, webhook_id):
    """Handle webhook info request"""
    webhook = webhook_manager.get_webhook(webhook_id)
    if not webhook:
        return JsonResponse({'error': 'Webhook not found'}, status=404)
    
    stats = webhook_manager.get_webhook_stats(webhook_id)
    return JsonResponse(stats)


def handle_incoming_webhook(request, webhook_id):
    """Handle incoming webhook"""
    webhook = webhook_manager.get_webhook(webhook_id)
    if not webhook:
        return JsonResponse({'error': 'Webhook not found'}, status=404)
    
    try:
        # Get request body
        payload = request.body.decode('utf-8')
        data = json.loads(payload)
        
        # Verify signature if secret is configured
        if webhook['secret']:
            signature = request.headers.get('X-Signature', '')
            if not webhook_manager.verify_signature(payload, signature, webhook['secret']):
                return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Process the webhook event
        event_type = data.get('event', 'unknown')
        event_data = data.get('data', {})
        
        # Log the webhook
        logger.info(f"Received webhook {event_type} for {webhook_id}")
        
        # Process based on event type
        if event_type == 'alert.triggered':
            process_alert_webhook_event(event_data)
        elif event_type == 'system.health':
            process_system_health_webhook_event(event_data)
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
        
        return JsonResponse({'status': 'received', 'event': event_type})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def handle_webhook_update(request, webhook_id):
    """Handle webhook configuration update"""
    webhook = webhook_manager.get_webhook(webhook_id)
    if not webhook:
        return JsonResponse({'error': 'Webhook not found'}, status=404)
    
    try:
        data = json.loads(request.body)
        
        # Update webhook configuration
        updates = {}
        if 'url' in data:
            if not validate_webhook_url(data['url']):
                return JsonResponse({'error': 'Invalid or unsafe webhook URL'}, status=400)
            updates['url'] = data['url']
        if 'events' in data:
            updates['events'] = data['events']
        if 'active' in data:
            updates['active'] = data['active']
        if 'secret' in data:
            updates['secret'] = data['secret']
        
        # Apply updates
        for key, value in updates.items():
            webhook[key] = value
        
        logger.info(f"Updated webhook {webhook_id}")
        return JsonResponse({'status': 'updated', 'webhook_id': webhook_id})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error updating webhook: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def handle_webhook_delete(request, webhook_id):
    """Handle webhook deletion"""
    webhook = webhook_manager.get_webhook(webhook_id)
    if not webhook:
        return JsonResponse({'error': 'Webhook not found'}, status=404)
    
    webhook_manager.unregister_webhook(webhook_id)
    logger.info(f"Deleted webhook {webhook_id}")
    
    return JsonResponse({'status': 'deleted', 'webhook_id': webhook_id})


def process_alert_webhook_event(event_data):
    """Process alert webhook event"""
    try:
        alert_id = event_data.get('alert_id')
        if not alert_id:
            logger.warning("Webhook event missing alert_id")
            return
        
        from .models import AlertLog
        try:
            alert = AlertLog.objects.get(id=alert_id)
            
            # Update alert based on webhook data
            if 'is_resolved' in event_data:
                alert.is_resolved = event_data['is_resolved']
                if event_data['is_resolved'] and 'resolved_at' in event_data:
                    alert.resolved_at = datetime.fromisoformat(event_data['resolved_at'])
                    alert.resolved_by = None  # Would need user lookup
            
            if 'resolution_note' in event_data:
                alert.resolution_note = event_data['resolution_note']
            
            alert.save()
            logger.info(f"Updated alert {alert_id} from webhook")
        
        except AlertLog.DoesNotExist:
            logger.error(f"Alert {alert_id} not found")
    
    except Exception as e:
        logger.error(f"Error processing alert webhook event: {e}")


def process_system_health_webhook_event(event_data):
    """Process system health webhook event"""
    try:
        from .models import SystemHealthCheck
        
        check_name = event_data.get('check_name')
        if not check_name:
            logger.warning("Webhook event missing check_name")
            return
        
        # Create or update health check
        health_check, created = SystemHealthCheck.objects.update_or_create(
            check_name=check_name,
            defaults={
                'check_type': event_data.get('check_type', 'external'),
                'status': event_data.get('status', 'unknown'),
                'status_message': event_data.get('message', ''),
                'response_time_ms': event_data.get('response_time_ms', 0),
                'checked_at': timezone.now(),
                'is_active': True
            }
        )
        
        if not created:
            # Update existing check
            health_check.status = event_data.get('status', 'unknown')
            health_check.status_message = event_data.get('message', '')
            health_check.response_time_ms = event_data.get('response_time_ms', 0)
            health_check.checked_at = timezone.now()
            health_check.save()
        
        logger.info(f"Updated health check {check_name} from webhook")
    
    except Exception as e:
        logger.error(f"Error processing system health webhook event: {e}")


# Utility functions
def create_webhook_config(url: str, events: List[str] = None, secret: str = None, **kwargs) -> Dict[str, Any]:
    """Create webhook configuration"""
    return {
        'url': url,
        'events': events or ['*'],
        'secret': secret or '',
        'active': kwargs.get('active', True),
        'max_retries': kwargs.get('max_retries', 3),
        'timeout': kwargs.get('timeout', 30),
        'headers': kwargs.get('headers', {})
    }


def validate_webhook_url(url: str) -> bool:
    """Validate webhook URL (scheme, host and SSRF checks)"""
    try:
        from .validators import validate_webhook_url as _validate
        return bool(_validate(url).get('valid'))
    except Exception:
        return False


def generate_webhook_secret(length: int = 32) -> str:
    """Generate secure webhook secret"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# Task for processing retry queue
def process_webhook_retries():
    """Process webhook retry queue (for Celery task)"""
    webhook_manager.process_retry_queue()


# Task for triggering alert webhooks
def trigger_alert_webhooks_task(alert_log_id):
    """Trigger alert webhooks (for Celery task)"""
    try:
        from .models import AlertLog
        alert_log = AlertLog.objects.get(id=alert_log_id)
        alert_webhook_manager.trigger_alert_webhooks(alert_log)
    except Exception as e:
        logger.error(f"Error in trigger_alert_webhooks_task: {e}")


# Task for triggering resolution webhooks
def trigger_resolution_webhooks_task(alert_log_id):
    """Trigger resolution webhooks (for Celery task)"""
    try:
        from .models import AlertLog
        alert_log = AlertLog.objects.get(id=alert_log_id)
        alert_webhook_manager.trigger_resolution_webhooks(alert_log)
    except Exception as e:
        logger.error(f"Error in trigger_resolution_webhooks_task: {e}")
