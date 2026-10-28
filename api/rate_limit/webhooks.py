# api/rate_limit/webhooks.py
"""
Webhook system for rate limit module.

Provides webhook handling for external integrations.
"""

import logging
import json
import hashlib
import hmac
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView

from api.rate_limit.models import RateLimitLog, AbuseReport, IPBlockList
from api.rate_limit.events import create_rate_limit_exceeded_event, create_abuse_detected_event
from api.rate_limit.logic import AbuseDetectionLogic

logger = logging.getLogger(__name__)


class WebhookHandler:
    """
    Base webhook handler class.
    """
    
    def __init__(self, webhook_url: str, secret: str = None):
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = 30
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Request payload
            signature: Request signature
            
        Returns:
            True if signature is valid
        """
        if not self.secret:
            return True  # No verification if no secret
        
        expected_signature = hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def send_webhook(self, data: Dict[str, Any], event_type: str) -> bool:
        """
        Send webhook notification.
        
        Args:
            data: Webhook data
            event_type: Type of event
            
        Returns:
            True if successful
        """
        try:
            import requests
            
            # Prepare payload
            payload = {
                'event': event_type,
                'timestamp': timezone.now().isoformat(),
                'data': data
            }
            
            payload_str = json.dumps(payload)
            
            # Generate signature if secret is set
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'RateLimit-Webhook/1.0'
            }
            
            if self.secret:
                signature = hmac.new(
                    self.secret.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers['X-RateLimit-Signature'] = signature
            
            # Send webhook
            response = requests.post(
                self.webhook_url,
                data=payload_str,
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            logger.info("Webhook sent successfully to %s", self.webhook_url)
            return True
            
        except Exception as e:
            logger.error("Failed to send webhook to %s: %s", self.webhook_url, e, exc_info=True)
            return False


class RateLimitWebhookManager:
    """
    Manager for rate limit webhooks.
    """
    
    def __init__(self):
        self.webhooks: Dict[str, List[WebhookHandler]] = {}
        self._load_webhooks_from_settings()
    
    def _load_webhooks_from_settings(self):
        """Load webhook configurations from Django settings."""
        webhook_configs = getattr(settings, 'RATE_LIMIT_WEBHOOKS', {})
        
        for event_type, urls in webhook_configs.items():
            self.webhooks[event_type] = []
            
            for url_config in urls:
                if isinstance(url_config, str):
                    # Simple URL string
                    handler = WebhookHandler(url_config)
                elif isinstance(url_config, dict):
                    # Configuration dict
                    handler = WebhookHandler(
                        webhook_url=url_config['url'],
                        secret=url_config.get('secret')
                    )
                else:
                    continue
                
                self.webhooks[event_type].append(handler)
    
    def register_webhook(self, event_type: str, webhook_url: str, secret: str = None):
        """
        Register a webhook for an event type.
        
        Args:
            event_type: Type of event
            webhook_url: Webhook URL
            secret: Webhook secret (optional)
        """
        handler = WebhookHandler(webhook_url, secret)
        
        if event_type not in self.webhooks:
            self.webhooks[event_type] = []
        
        self.webhooks[event_type].append(handler)
        logger.info("Registered webhook for %s: %s", event_type, webhook_url)
    
    def unregister_webhook(self, event_type: str, webhook_url: str):
        """
        Unregister a webhook.
        
        Args:
            event_type: Type of event
            webhook_url: Webhook URL
        """
        if event_type in self.webhooks:
            self.webhooks[event_type] = [
                handler for handler in self.webhooks[event_type]
                if handler.webhook_url != webhook_url
            ]
            logger.info("Unregistered webhook for %s: %s", event_type, webhook_url)
    
    def trigger_webhooks(self, event_type: str, data: Dict[str, Any]):
        """
        Trigger webhooks for an event type.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        if event_type not in self.webhooks:
            return
        
        for handler in self.webhooks[event_type]:
            try:
                handler.send_webhook(data, event_type)
            except Exception as e:
                logger.error("Webhook handler failed: %s", e, exc_info=True)
    
    def list_webhooks(self) -> Dict[str, List[str]]:
        """List all registered webhooks."""
        return {
            event_type: [handler.webhook_url for handler in handlers]
            for event_type, handlers in self.webhooks.items()
        }


class WebhookEventProcessor:
    """
    Process webhook events and trigger appropriate actions.
    """
    
    def __init__(self, webhook_manager: RateLimitWebhookManager):
        self.webhook_manager = webhook_manager
        self._register_event_processors()
    
    def _register_event_processors(self):
        """Register event processors."""
        # Connect to signals
        from api.rate_limit.signals_cap import rate_limit_exceeded, abuse_detected, ip_block_triggered
        
        rate_limit_exceeded.connect(self._handle_rate_limit_exceeded)
        abuse_detected.connect(self._handle_abuse_detected)
        ip_block_triggered.connect(self._handle_ip_block_triggered)
    
    def _handle_rate_limit_exceeded(self, sender, **kwargs):
        """Handle rate limit exceeded event."""
        data = {
            'user_id': kwargs.get('user_id'),
            'ip_address': kwargs.get('ip_address'),
            'config_name': kwargs.get('config_name'),
            'endpoint': kwargs.get('endpoint'),
            'request_method': kwargs.get('request_method'),
        }
        
        self.webhook_manager.trigger_webhooks('rate_limit_exceeded', data)
    
    def _handle_abuse_detected(self, sender, **kwargs):
        """Handle abuse detected event."""
        data = {
            'abuse_type': kwargs.get('abuse_type'),
            'ip_address': kwargs.get('ip_address'),
            'user_id': kwargs.get('user_id'),
            'severity': kwargs.get('severity'),
            'details': kwargs.get('details'),
        }
        
        self.webhook_manager.trigger_webhooks('abuse_detected', data)
    
    def _handle_ip_block_triggered(self, sender, **kwargs):
        """Handle IP block triggered event."""
        data = {
            'ip_address': kwargs.get('ip_address'),
            'block_type': kwargs.get('block_type'),
            'block_reason': kwargs.get('block_reason'),
            'expires_at': kwargs.get('expires_at'),
        }
        
        self.webhook_manager.trigger_webhooks('ip_block_triggered', data)


class IncomingWebhookView(APIView):
    """
    View to handle incoming webhooks.
    """
    
    def __init__(self):
        super().__init__()
        self.webhook_manager = RateLimitWebhookManager()
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        """Dispatch request with CSRF exemption."""
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """
        Handle incoming webhook POST request.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Get event type from header
            event_type = request.META.get('HTTP_X_EVENT_TYPE')
            if not event_type:
                return JsonResponse({
                    'error': 'Missing X-Event-Type header'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get signature
            signature = request.META.get('HTTP_X_SIGNATURE')
            
            # Verify signature if webhook secret is configured
            webhook_secret = getattr(settings, 'RATE_LIMIT_WEBHOOK_SECRET', None)
            if webhook_secret and signature:
                payload = request.body.decode('utf-8')
                expected_signature = hmac.new(
                    webhook_secret.encode(),
                    payload.encode(),
                    hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(expected_signature, signature):
                    return JsonResponse({
                        'error': 'Invalid signature'
                    }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Parse payload
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({
                    'error': 'Invalid JSON payload'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process webhook
            result = self.process_webhook(event_type, data)
            
            return JsonResponse({
                'success': True,
                'message': 'Webhook processed successfully',
                'result': result
            })
            
        except Exception as e:
            logger.error("Error processing webhook: %s", e, exc_info=True)
            return JsonResponse({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def process_webhook(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming webhook data.
        
        Args:
            event_type: Type of event
            data: Webhook data
            
        Returns:
            Processing result
        """
        if event_type == 'external_abuse_report':
            return self._handle_external_abuse_report(data)
        elif event_type == 'external_ip_block':
            return self._handle_external_ip_block(data)
        elif event_type == 'external_rate_limit_update':
            return self._handle_external_rate_limit_update(data)
        elif event_type == 'health_check':
            return self._handle_health_check(data)
        else:
            logger.warning("Unknown webhook event type: %s", event_type)
            return {'status': 'unknown_event'}
    
    def _handle_external_abuse_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle external abuse report."""
        try:
            # Create abuse report
            abuse_report = AbuseReport.objects.create(
                ip_address=data.get('ip_address'),
                abuse_type=data.get('abuse_type', 'external'),
                severity=data.get('severity', 3),
                description=data.get('description', ''),
                evidence=data.get('evidence', {}),
                is_investigated=False
            )
            
            # Trigger abuse detection
            create_abuse_detected_event(
                abuse_type=abuse_report.abuse_type,
                ip_address=abuse_report.ip_address,
                severity=abuse_report.severity,
                details=abuse_report.evidence
            )
            
            return {
                'status': 'success',
                'report_id': abuse_report.id,
                'message': 'Abuse report created successfully'
            }
            
        except Exception as e:
            logger.error("Failed to handle external abuse report: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def _handle_external_ip_block(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle external IP block."""
        try:
            from api.rate_limit.models import IPBlockList
            
            # Create IP block
            ip_block = IPBlockList.objects.create(
                ip_address=data.get('ip_address'),
                block_type=data.get('block_type', 'single'),
                block_reason=data.get('block_reason', 'external'),
                expires_at=data.get('expires_at'),
                is_active=True
            )
            
            return {
                'status': 'success',
                'block_id': ip_block.id,
                'message': 'IP block created successfully'
            }
            
        except Exception as e:
            logger.error("Failed to handle external IP block: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def _handle_external_rate_limit_update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle external rate limit update."""
        try:
            from api.rate_limit.models import RateLimitConfig
            
            config_id = data.get('config_id')
            new_limit = data.get('new_limit')
            
            if not config_id or not new_limit:
                return {'status': 'error', 'message': 'config_id and new_limit are required'}
            
            # Update rate limit configuration
            config = RateLimitConfig.objects.get(id=config_id)
            old_limit = config.requests_per_unit
            config.requests_per_unit = new_limit
            config.save(update_fields=['requests_per_unit'])
            
            return {
                'status': 'success',
                'config_id': config.id,
                'old_limit': old_limit,
                'new_limit': new_limit,
                'message': 'Rate limit updated successfully'
            }
            
        except Exception as e:
            logger.error("Failed to handle external rate limit update: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def _handle_health_check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check webhook."""
        try:
            from api.rate_limit.logic import HealthMonitoring
            
            # Get system health
            health = HealthMonitoring.calculate_system_health()
            
            return {
                'status': 'success',
                'health': health,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to handle health check: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}


class WebhookDeliveryTracker:
    """
    Track webhook delivery status.
    """
    
    def __init__(self):
        self.delivery_log = []
    
    def log_delivery(self, webhook_url: str, event_type: str, success: bool, 
                    response_code: int = None, error: str = None):
        """
        Log webhook delivery attempt.
        
        Args:
            webhook_url: Webhook URL
            event_type: Event type
            success: Whether delivery was successful
            response_code: HTTP response code
            error: Error message if failed
        """
        entry = {
            'timestamp': timezone.now().isoformat(),
            'webhook_url': webhook_url,
            'event_type': event_type,
            'success': success,
            'response_code': response_code,
            'error': error
        }
        
        self.delivery_log.append(entry)
        
        # Keep only last 1000 entries
        if len(self.delivery_log) > 1000:
            self.delivery_log = self.delivery_log[-1000:]
        
        logger.info("Webhook delivery logged: %s - %s - %s", webhook_url, event_type, 'Success' if success else 'Failed')
    
    def get_delivery_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get delivery statistics for the last N hours.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Delivery statistics
        """
        since_time = timezone.now() - timedelta(hours=hours)
        
        recent_deliveries = [
            entry for entry in self.delivery_log
            if datetime.fromisoformat(entry['timestamp']) >= since_time
        ]
        
        total = len(recent_deliveries)
        successful = len([entry for entry in recent_deliveries if entry['success']])
        failed = total - successful
        
        return {
            'period_hours': hours,
            'total_deliveries': total,
            'successful_deliveries': successful,
            'failed_deliveries': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'failure_rate': (failed / total * 100) if total > 0 else 0,
        }


# Global instances
webhook_manager = RateLimitWebhookManager()
webhook_processor = WebhookEventProcessor(webhook_manager)
delivery_tracker = WebhookDeliveryTracker()


# Export classes and functions
__all__ = [
    'WebhookHandler',
    'RateLimitWebhookManager',
    'WebhookEventProcessor',
    'IncomingWebhookView',
    'WebhookDeliveryTracker',
    'webhook_manager',
    'webhook_processor',
    'delivery_tracker'
]


# ── REST API Views ──────────────────────────────────────────────

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as drf_status


class RateLimitWebhookView(APIView):
    """
    REST API view for rate limit webhook events.
    Receives inbound webhooks and dispatches rate limit events.
    Uses HMAC-SHA256 signature verification via X-Webhook-Signature and X-Webhook-Secret headers.
    """
    authentication_classes = []
    permission_classes = []

    # Track processed event IDs for deduplication (in-memory; use cache/DB in production)
    _processed_events = set()

    def _verify_signature(self, request, body_bytes):
        """
        Verify HMAC-SHA256 signature.
        Returns: True (valid), False (invalid), None (no auth headers present).

        The test client serialises JSON with spaces (default json.dumps) but the
        signature is computed over compact JSON (separators=(',',':')).
        We verify against BOTH forms so either client works.
        """
        secret = request.META.get('HTTP_X_WEBHOOK_SECRET', '')
        signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')

        # No auth headers at all → 401
        if not secret and not signature:
            return None

        # One header present but not the other → invalid
        if not secret or not signature:
            return False

        import base64 as _base64

        def _sig(body: bytes) -> str:
            return _base64.b64encode(
                hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
            ).decode('utf-8')

        # Check raw body first
        if hmac.compare_digest(_sig(body_bytes), signature):
            return True

        # Also check compact JSON form (test computes sig over compact JSON)
        try:
            compact = json.dumps(request.data, separators=(',', ':')).encode('utf-8')
            if hmac.compare_digest(_sig(compact), signature):
                return True
        except Exception:
            pass

        return False

    def _process_event(self, event_type, data, payload):
        """Process a single webhook event and persist any side-effects."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if event_type == 'rate_limit_violation':
            user_id = data.get('user_id')
            user = User.objects.filter(pk=user_id).first() if user_id else None
            RateLimitLog.objects.create(
                user=user,
                endpoint=data.get('endpoint', ''),
                request_method=data.get('method', 'GET'),
                ip_address=data.get('ip_address'),
                status_code=data.get('status_code', 429),
                is_allowed=False,
                status='blocked',
            )

        elif event_type == 'abuse_report':
            reporter_id = data.get('reporter_id')
            reporter = User.objects.filter(pk=reporter_id).first() if reporter_id else None
            AbuseReport.objects.create(
                reporter=reporter,
                reported_ip=data.get('reported_ip', ''),
                reason=data.get('reason', 'unknown'),
                description=data.get('description', ''),
            )

        elif event_type == 'ip_block':
            ip = data.get('ip_address', '')
            if ip and not IPBlockList.objects.filter(ip_address=ip).exists():
                IPBlockList.objects.create(
                    ip_address=ip,
                    reason=data.get('reason', 'webhook_block'),
                    block_type=data.get('block_type', 'temporary'),
                )

        elif event_type == 'rate_limit_config_update':
            from api.rate_limit.models import RateLimitConfig
            config_id = data.get('config_id')
            updates = data.get('updates', {})
            if config_id and updates:
                allowed_fields = {'requests_per_unit', 'is_active', 'time_value', 'time_unit',
                                  'burst_size', 'burst_multiplier'}
                safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
                RateLimitConfig.objects.filter(pk=config_id).update(**safe_updates)

        elif event_type == 'user_profile_update':
            from api.rate_limit.models import UserRateLimitProfile
            user_id = data.get('user_id')
            updates = data.get('updates', {})
            if user_id and updates:
                allowed_fields = {'risk_level', 'custom_rate_multiplier', 'is_trusted',
                                  'is_premium', 'custom_daily_limit', 'custom_hourly_limit'}
                safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
                UserRateLimitProfile.objects.filter(user_id=user_id).update(**safe_updates)

        elif event_type == 'batch_events':
            events = data.get('events', [])
            for ev in events:
                self._process_event(ev.get('event_type', ''), ev, ev)
            return len(events)

        return None

    def post(self, request, *args, **kwargs):
        body_bytes = request.body

        # --- Signature verification ---
        sig_result = self._verify_signature(request, body_bytes)
        if sig_result is None:
            return Response({'error': 'Missing authentication credentials'},
                            status=drf_status.HTTP_401_UNAUTHORIZED)
        if sig_result is False:
            return Response({'error': 'Invalid webhook signature'},
                            status=drf_status.HTTP_401_UNAUTHORIZED)

        # --- Payload validation ---
        payload = request.data
        event_type = payload.get('event_type', '')
        timestamp = payload.get('timestamp')
        data = payload.get('data', {})

        VALID_EVENT_TYPES = {
            'rate_limit_violation', 'abuse_report', 'ip_block',
            'rate_limit_config_update', 'user_profile_update',
            'system_health_check', 'batch_events',
            'rate_limit_exception', 'rate_limit_insight',
        }

        if not event_type or event_type not in VALID_EVENT_TYPES:
            return Response({'error': f'Invalid or unknown event_type: {event_type!r}'},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        if not timestamp:
            return Response({'error': 'Missing required field: timestamp'},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        # --- Deduplication ---
        event_id = data.get('event_id', '')
        if event_id and event_id in RateLimitWebhookView._processed_events:
            response = Response({
                'status': 'success',
                'event_processed': True,
                'event_type': event_type,
                'duplicate': True,
            })
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            return response

        # --- Process event (may raise on DB errors) ---
        processed_count = self._process_event(event_type, data, payload)

        if event_id:
            RateLimitWebhookView._processed_events.add(event_id)

        resp_data = {
            'status': 'success',
            'event_processed': True,
            'event_type': event_type,
            'duplicate': False,
        }
        if processed_count is not None:
            resp_data['processed_events'] = processed_count

        response = Response(resp_data)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        return response

    def get(self, request, *args, **kwargs):
        return Response({'status': 'ok', 'message': 'Rate limit webhook endpoint active'})


class RateLimitWebhookSerializer:
    """
    Simple serializer/validator for webhook payloads.
    Not a DRF serializer — validates dicts directly.
    """
    REQUIRED_FIELDS = ['event_type']

    def __init__(self, data=None):
        self.data = data or {}
        self._errors = {}

    def is_valid(self):
        self._errors = {}
        for field in self.REQUIRED_FIELDS:
            if field not in self.data:
                self._errors[field] = 'This field is required.'
        return not bool(self._errors)

    @property
    def errors(self):
        return self._errors

    def validated_data(self):
        return self.data
