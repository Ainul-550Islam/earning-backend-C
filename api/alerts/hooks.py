"""
Webhook system for alerts app - handles incoming and outgoing webhooks
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
import logging

logger = logging.getLogger(__name__)


class WebhookManager:
    """Manages webhook processing and validation"""
    
    @staticmethod
    def verify_signature(payload, signature, secret):
        """Verify webhook signature (fails closed: no secret means nothing can be verified)"""
        if not secret or not isinstance(signature, str):
            return False
        if signature.lower().startswith('sha256='):
            signature = signature.split('=', 1)[1]
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    @staticmethod
    def process_webhook_event(event_type, data, source='external'):
        """Process incoming webhook event"""
        try:
            logger.info(f"Processing webhook event: {event_type} from {source}")
            
            # Route to appropriate handler
            if event_type == 'alert.triggered':
                return WebhookManager._handle_alert_triggered(data)
            elif event_type == 'system.health':
                return WebhookManager._handle_system_health(data)
            elif event_type == 'metric.update':
                return WebhookManager._handle_metric_update(data)
            elif event_type == 'incident.created':
                return WebhookManager._handle_incident_created(data)
            else:
                logger.warning(f"Unknown webhook event type: {event_type}")
                return {'status': 'unknown_event', 'message': f'Event type {event_type} not recognized'}
        
        except Exception as e:
            logger.error(f"Error processing webhook event {event_type}: {e}")
            return {'status': 'error', 'message': 'Operation failed'}
    
    @staticmethod
    def _handle_alert_triggered(data):
        """Handle alert triggered webhook"""
        from .services import LegacyAlertProcessorService as AlertProcessorService
        
        rule_id = data.get('rule_id')
        trigger_value = data.get('trigger_value')
        message = data.get('message')
        details = data.get('details', {})
        
        if not all([rule_id, trigger_value, message]):
            return {'status': 'error', 'message': 'Missing required fields'}
        
        alert_log = AlertProcessorService.process_alert(
            rule_id=rule_id,
            trigger_value=trigger_value,
            message=message,
            details=details
        )
        
        if alert_log:
            return {
                'status': 'success',
                'alert_id': alert_log.id,
                'message': 'Alert processed successfully'
            }
        else:
            return {'status': 'error', 'message': 'Failed to process alert'}
    
    @staticmethod
    def _handle_system_health(data):
        """Handle system health webhook"""
        from .models import SystemHealthCheck, SystemMetrics
        
        check_name = data.get('check_name')
        status = data.get('status')
        response_time = data.get('response_time_ms', 0)
        message = data.get('message', '')
        
        if not all([check_name, status]):
            return {'status': 'error', 'message': 'Missing required fields'}
        
        # Update or create health check
        health_check, created = SystemHealthCheck.objects.update_or_create(
            check_name=check_name,
            defaults={
                'status': status,
                'response_time_ms': response_time,
                'status_message': message,
                'checked_at': timezone.now()
            }
        )
        
        return {
            'status': 'success',
            'health_check_id': health_check.id,
            'created': created
        }
    
    @staticmethod
    def _handle_metric_update(data):
        """Handle metric update webhook"""
        from .models import SystemMetrics
        
        metric_data = {
            'cpu_usage_percent': data.get('cpu_usage', 0),
            'memory_usage_percent': data.get('memory_usage', 0),
            'disk_usage_percent': data.get('disk_usage', 0),
            'total_users': data.get('total_users', 0),
            'active_users_1h': data.get('active_users_1h', 0),
            'total_earnings_1h': data.get('total_earnings_1h', 0),
            'fraud_indicators_1h': data.get('fraud_indicators_1h', 0),
            'data_source': 'webhook'
        }
        
        metrics = SystemMetrics.objects.create(**metric_data)
        
        return {
            'status': 'success',
            'metrics_id': metrics.id
        }
    
    @staticmethod
    def _handle_incident_created(data):
        """Handle incident created webhook"""
        from .models import Incident
        
        incident_data = {
            'title': data.get('title'),
            'description': data.get('description', ''),
            'severity': data.get('severity', 'medium'),
            'status': data.get('status', 'investigating'),
            'detected_at': timezone.now(),
            'data_source': 'webhook'
        }
        
        incident = Incident.objects.create(**incident_data)
        
        return {
            'status': 'success',
            'incident_id': incident.id
        }


class OutgoingWebhookManager:
    """Manages outgoing webhooks to external systems"""
    
    @staticmethod
    def send_webhook(url, payload, secret=None, event_type='alert.triggered'):
        """Send webhook to external system"""
        try:
            import requests
            from .validators import validate_webhook_url as _validate_outbound_url
            check = _validate_outbound_url(url) if url else {'valid': False, 'errors': ['missing url']}
            if not check.get('valid', False):
                logger.error(f"Webhook blocked (unsafe or missing URL): {check.get('errors')}")
                return {'status': 'error', 'message': 'Webhook URL rejected'}
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'AlertSystem/1.0',
                'X-Event-Type': event_type
            }
            
            # Add signature if secret provided
            if secret:
                payload_str = json.dumps(payload)
                signature = hmac.new(
                    secret.encode('utf-8'),
                    payload_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers['X-Signature'] = signature
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
                allow_redirects=False,
            )
            
            if 200 <= response.status_code < 300:
                logger.info(f"Webhook sent successfully to {url}")
                return {'status': 'success', 'response': response.text}
            else:
                logger.error(f"Webhook failed to {url}: {response.status_code}")
                return {'status': 'error', 'response': response.text}
        
        except Exception as e:
            logger.error(f"Error sending webhook to {url}: {e}")
            return {'status': 'error', 'message': 'Operation failed'}
    
    @staticmethod
    def send_alert_webhook(alert_log):
        """Send alert webhook to configured endpoints"""
        from .models import AlertChannel
        
        # Get webhook channels
        webhook_channels = AlertChannel.objects.filter(
            channel_type='webhook',
            is_enabled=True
        )
        
        payload = {
            'event_type': 'alert.triggered',
            'alert_id': alert_log.id,
            'rule_name': alert_log.rule.name,
            'severity': alert_log.rule.severity,
            'message': alert_log.message,
            'trigger_value': alert_log.trigger_value,
            'threshold_value': alert_log.threshold_value,
            'triggered_at': alert_log.triggered_at.isoformat(),
            'details': alert_log.details
        }
        
        results = []
        for channel in webhook_channels:
            result = OutgoingWebhookManager.send_webhook(
                url=channel.config.get('webhook_url'),
                payload=payload,
                secret=channel.config.get('webhook_secret'),
                event_type='alert.triggered'
            )
            results.append({
                'channel_id': channel.id,
                'channel_name': channel.name,
                'result': result
            })
        
        return results


# Django views for webhook endpoints
@csrf_exempt
@require_http_methods(["POST"])
def incoming_webhook(request, webhook_id=None):
    """Handle incoming webhooks"""
    try:
        # Get request data
        payload = request.body.decode('utf-8')
        data = json.loads(payload)
        
        # Get event type from headers
        event_type = request.headers.get('X-Event-Type', 'unknown')
        signature = request.headers.get('X-Signature', '')
        
        # Inbound events must be tied to a registered webhook with a signing secret
        if not webhook_id:
            return JsonResponse({'error': 'webhook_id required'}, status=400)
        secret = None
        if webhook_id:
            from .models import AlertChannel
            try:
                webhook = AlertChannel.objects.get(id=webhook_id, channel_type='webhook')
                secret = webhook.config.get('webhook_secret')
            except AlertChannel.DoesNotExist:
                return JsonResponse({'error': 'Webhook not found'}, status=404)
        
        # Verify signature
        if not WebhookManager.verify_signature(payload, signature, secret):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Process the webhook
        result = WebhookManager.process_webhook_event(event_type, data)
        
        return JsonResponse(result)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in incoming webhook: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["GET"])
def webhook_status(request):
    """Get webhook system status"""
    try:
        from .models import AlertChannel
        
        webhook_channels = AlertChannel.objects.filter(channel_type='webhook')
        
        status_data = {
            'total_webhooks': webhook_channels.count(),
            'active_webhooks': webhook_channels.filter(is_enabled=True).count(),
            'recent_webhooks': [],  # Add recent webhook logs if needed
        }
        
        return JsonResponse(status_data)
    
    except Exception:
        logger.exception("Unhandled error in webhook_status")
        return JsonResponse({'error': 'Internal server error'}, status=500)


class WebhookEventLogger:
    """Logs webhook events for auditing and debugging"""
    
    @staticmethod
    def log_incoming_webhook(event_type, source, payload, result):
        """Log incoming webhook"""
        from .models import WebhookLog
        
        WebhookLog.objects.create(
            event_type=event_type,
            direction='incoming',
            source=source,
            payload=payload,
            result=result,
            created_at=timezone.now()
        )
    
    @staticmethod
    def log_outgoing_webhook(event_type, target, payload, result):
        """Log outgoing webhook"""
        from .models import WebhookLog
        
        WebhookLog.objects.create(
            event_type=event_type,
            direction='outgoing',
            source='alert_system',
            target=target,
            payload=payload,
            result=result,
            created_at=timezone.now()
        )
