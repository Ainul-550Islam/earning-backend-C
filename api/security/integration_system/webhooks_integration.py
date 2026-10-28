"""
Webhooks Integration Module
Webhook integration for security system
"""

import logging
import hashlib
import hmac
import json
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_handler import BaseIntegrationHandler
from .integ_constants import *
from .circuit_breaker import circuit_breaker_protected

User = get_user_model()
logger = logging.getLogger('security.integration.webhooks')


class WebhookIntegration(BaseIntegrationHandler):
    """Webhook integration handler"""
    
    def __init__(self):
        super().__init__("webhook_integration")
        self.webhooks = {}
        self.signature_algorithms = {
            'sha256': hashlib.sha256,
            'sha1': hashlib.sha1,
            'md5': hashlib.md5
        }
        self.retry_attempts = 3
        self.retry_delay = 5  # seconds
        self.timeout = 30  # seconds
        self.user_agent = 'Security-Webhook-Integration/1.0'
    
    def configure(self, config: Dict[str, Any]):
        """Configure webhook integration"""
        super().configure(config)
        
        self.webhooks = config.get('webhooks', {})
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 5)
        self.timeout = config.get('timeout', 30)
        self.user_agent = config.get('user_agent', self.user_agent)
    
    def initialize(self) -> bool:
        """Initialize webhook integration"""
        try:
            # Validate webhook configurations
            for webhook_name, webhook_config in self.webhooks.items():
                if not self._validate_webhook_config(webhook_config):
                    logger.error(f"Invalid webhook configuration: {webhook_name}")
                    return False
            
            self.initialized = True
            self.health_status = 'healthy'
            return True
            
        except Exception as e:
            logger.error(f"Error initializing webhook integration: {e}")
            self.health_status = 'unhealthy'
            return False
    
    def handle(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle webhook event"""
        try:
            results = []
            
            # Determine which webhooks to trigger
            target_webhooks = self._get_target_webhooks(event_data)
            
            for webhook_name in target_webhooks:
                webhook_config = self.webhooks[webhook_name]
                result = self._send_webhook(webhook_name, webhook_config, event_data)
                results.append(result)
            
            return {
                'status': 'success',
                'webhooks_triggered': len(target_webhooks),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error handling webhook event: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _validate_webhook_config(self, config: Dict[str, Any]) -> bool:
        """Validate webhook configuration"""
        required_fields = ['url', 'events']
        
        for field in required_fields:
            if field not in config:
                return False
        
        # Validate URL
        url = config['url']
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Validate events
        events = config['events']
        if not isinstance(events, list) or not events:
            return False
        
        return True
    
    def _get_target_webhooks(self, event_data: Dict[str, Any]) -> List[str]:
        """Get target webhooks for event"""
        target_webhooks = []
        event_type = event_data.get('event_type', '')
        
        for webhook_name, webhook_config in self.webhooks.items():
            events = webhook_config.get('events', [])
            
            # Check if webhook handles this event type
            if event_type in events or '*' in events:
                # Check filters
                if self._passes_filters(event_data, webhook_config.get('filters', {})):
                    target_webhooks.append(webhook_name)
        
        return target_webhooks
    
    def _passes_filters(self, event_data: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if event passes webhook filters"""
        for field, filter_config in filters.items():
            if field in event_data:
                event_value = event_data[field]
                
                # Check include filter
                if 'include' in filter_config:
                    if event_value not in filter_config['include']:
                        return False
                
                # Check exclude filter
                if 'exclude' in filter_config:
                    if event_value in filter_config['exclude']:
                        return False
                
                # Check range filter
                if 'range' in filter_config:
                    range_config = filter_config['range']
                    min_val = range_config.get('min')
                    max_val = range_config.get('max')
                    
                    if min_val is not None and event_value < min_val:
                        return False
                    if max_val is not None and event_value > max_val:
                        return False
        
        return True
    
    @circuit_breaker_protected('webhook_sender')
    def _send_webhook(self, webhook_name: str, webhook_config: Dict[str, Any], 
                      event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send webhook with retry logic"""
        import requests
        
        url = webhook_config['url']
        method = webhook_config.get('method', 'POST')
        headers = webhook_config.get('headers', {})
        secret = webhook_config.get('secret')
        signature_algorithm = webhook_config.get('signature_algorithm', 'sha256')
        
        # Prepare payload
        payload = {
            'id': SecurityUtils.generate_uuid(),
            'timestamp': timezone.now().isoformat(),
            'event': event_data,
            'webhook': webhook_name
        }
        
        # Add signature if secret provided
        if secret:
            signature = self._generate_signature(payload, secret, signature_algorithm)
            headers['X-Signature'] = signature
        
        # Add user agent
        headers['User-Agent'] = self.user_agent
        
        # Set content type
        headers['Content-Type'] = 'application/json'
        
        # Send webhook with retries
        for attempt in range(self.retry_attempts + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code in [200, 201, 202]:
                    return {
                        'status': 'success',
                        'webhook': webhook_name,
                        'status_code': response.status_code,
                        'attempt': attempt + 1
                    }
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"Webhook {webhook_name} failed (attempt {attempt + 1}): {error_msg}")
                    
                    if attempt < self.retry_attempts:
                        time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    else:
                        return {
                            'status': 'error',
                            'webhook': webhook_name,
                            'error': error_msg,
                            'status_code': response.status_code,
                            'attempts': attempt + 1
                        }
            
            except requests.exceptions.RequestException as e:
                logger.warning(f"Webhook {webhook_name} failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.retry_attempts:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    return {
                        'status': 'error',
                        'webhook': webhook_name,
                        'error': str(e),
                        'attempts': attempt + 1
                    }
    
    def _generate_signature(self, payload: Dict[str, Any], secret: str, 
                          algorithm: str = 'sha256') -> str:
        """Generate webhook signature"""
        algorithm_func = self.signature_algorithms.get(algorithm, hashlib.sha256)
        
        # Create signature
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            algorithm_func
        ).hexdigest()
        
        return f"{algorithm}={signature}"
    
    def verify_signature(self, payload: Dict[str, Any], signature: str, 
                        secret: str, algorithm: str = 'sha256') -> bool:
        """Verify webhook signature"""
        try:
            expected_signature = self._generate_signature(payload, secret, algorithm)
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False
    
    def add_webhook(self, webhook_name: str, url: str, events: List[str], 
                    secret: str = None, **kwargs):
        """Add webhook configuration"""
        webhook_config = {
            'url': url,
            'events': events,
            'secret': secret,
            'method': kwargs.get('method', 'POST'),
            'headers': kwargs.get('headers', {}),
            'signature_algorithm': kwargs.get('signature_algorithm', 'sha256'),
            'filters': kwargs.get('filters', {}),
            'timeout': kwargs.get('timeout', self.timeout),
            'retry_attempts': kwargs.get('retry_attempts', self.retry_attempts),
            'retry_delay': kwargs.get('retry_delay', self.retry_delay)
        }
        
        self.webhooks[webhook_name] = webhook_config
        logger.info(f"Added webhook: {webhook_name}")
    
    def remove_webhook(self, webhook_name: str):
        """Remove webhook configuration"""
        if webhook_name in self.webhooks:
            del self.webhooks[webhook_name]
            logger.info(f"Removed webhook: {webhook_name}")
    
    def update_webhook(self, webhook_name: str, **kwargs):
        """Update webhook configuration"""
        if webhook_name in self.webhooks:
            webhook_config = self.webhooks[webhook_name]
            webhook_config.update(kwargs)
            logger.info(f"Updated webhook: {webhook_name}")
    
    def get_webhook_status(self, webhook_name: str) -> Dict[str, Any]:
        """Get webhook status"""
        if webhook_name not in self.webhooks:
            return {'error': f'Webhook not found: {webhook_name}'}
        
        webhook_config = self.webhooks[webhook_name]
        
        # Test webhook connectivity
        connectivity_status = self._test_webhook_connectivity(webhook_config)
        
        return {
            'name': webhook_name,
            'url': webhook_config['url'],
            'events': webhook_config['events'],
            'connectivity': connectivity_status,
            'has_secret': bool(webhook_config.get('secret')),
            'signature_algorithm': webhook_config.get('signature_algorithm', 'sha256'),
            'timeout': webhook_config.get('timeout', self.timeout),
            'retry_attempts': webhook_config.get('retry_attempts', self.retry_attempts)
        }
    
    def _test_webhook_connectivity(self, webhook_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test webhook connectivity"""
        try:
            import requests
            
            # Send test ping
            test_payload = {
                'test': True,
                'timestamp': timezone.now().isoformat()
            }
            
            headers = webhook_config.get('headers', {})
            headers['User-Agent'] = self.user_agent
            headers['Content-Type'] = 'application/json'
            
            response = requests.post(
                webhook_config['url'],
                json=test_payload,
                headers=headers,
                timeout=10
            )
            
            return {
                'status': 'connected',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_all_webhooks_status(self) -> Dict[str, Any]:
        """Get status of all webhooks"""
        return {
            'total_webhooks': len(self.webhooks),
            'webhooks': {
                name: self.get_webhook_status(name)
                for name in self.webhooks.keys()
            }
        }
    
    def cleanup(self):
        """Clean up webhook integration"""
        self.webhooks.clear()
        super().cleanup()


class WebhookReceiver(APIView):
    """API view for receiving webhooks"""
    
    def __init__(self):
        super().__init__()
        self.received_webhooks = []
        self.max_history = 1000
        self.secret_keys = {}
    
    def add_secret_key(self, webhook_name: str, secret: str):
        """Add secret key for webhook verification"""
        self.secret_keys[webhook_name] = secret
    
    def remove_secret_key(self, webhook_name: str):
        """Remove secret key"""
        if webhook_name in self.secret_keys:
            del self.secret_keys[webhook_name]
    
    @method_decorator(csrf_exempt)
    def post(self, request, webhook_name: str):
        """Receive webhook"""
        try:
            # Get request body
            body = request.body.decode('utf-8')
            
            # Parse JSON
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return Response(
                    {'error': 'Invalid JSON'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify signature if secret key exists
            signature = request.META.get('HTTP_X_SIGNATURE')
            if webhook_name in self.secret_keys and signature:
                secret = self.secret_keys[webhook_name]
                
                if not self._verify_webhook_signature(payload, signature, secret):
                    return Response(
                        {'error': 'Invalid signature'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            
            # Record webhook
            webhook_record = {
                'webhook_name': webhook_name,
                'payload': payload,
                'headers': dict(request.headers),
                'received_at': timezone.now(),
                'ip_address': self._get_client_ip(request)
            }
            
            self.received_webhooks.append(webhook_record)
            
            # Maintain history size
            if len(self.received_webhooks) > self.max_history:
                self.received_webhooks.pop(0)
            
            # Process webhook
            result = self._process_webhook(webhook_record)
            
            # Log webhook receipt
            SecurityLog.objects.create(
                security_type='webhook_received',
                severity='info',
                description=f"Webhook received: {webhook_name}",
                metadata={
                    'webhook_name': webhook_name,
                    'payload_id': payload.get('id'),
                    'event_type': payload.get('event', {}).get('event_type', 'unknown')
                }
            )
            
            return Response({
                'status': 'received',
                'processed': result['success'],
                'message': result.get('message', 'Webhook processed successfully')
            })
            
        except Exception as e:
            logger.error(f"Error receiving webhook {webhook_name}: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _verify_webhook_signature(self, payload: Dict[str, Any], signature: str, 
                                  secret: str) -> bool:
        """Verify webhook signature"""
        try:
            if '=' in signature:
                algorithm, signature_value = signature.split('=', 1)
            else:
                algorithm = 'sha256'
                signature_value = signature
            
            webhook_integration = WebhookIntegration()
            return webhook_integration.verify_signature(payload, signature_value, secret, algorithm)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def _process_webhook(self, webhook_record: Dict[str, Any]) -> Dict[str, Any]:
        """Process received webhook"""
        try:
            payload = webhook_record['payload']
            event_data = payload.get('event', {})
            
            if not event_data:
                return {'success': False, 'message': 'No event data in payload'}
            
            # Create security log entry
            SecurityLog.objects.create(
                security_type='webhook_event',
                severity='info',
                description=f"Webhook event: {event_data.get('event_type', 'unknown')}",
                metadata={
                    'webhook_name': webhook_record['webhook_name'],
                    'event_data': event_data,
                    'payload_id': payload.get('id')
                }
            )
            
            # Handle specific event types
            event_type = event_data.get('event_type')
            
            if event_type == 'security_alert':
                return self._handle_security_alert(event_data)
            elif event_type == 'threat_detected':
                return self._handle_threat_detected(event_data)
            elif event_type == 'incident_created':
                return self._handle_incident_created(event_data)
            else:
                return {'success': True, 'message': 'Event processed'}
                
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return {'success': False, 'message': str(e)}
    
    def _handle_security_alert(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle security alert event"""
        try:
            # Create security incident for high severity alerts
            severity = event_data.get('severity', 'medium')
            
            if severity in ['high', 'critical']:
                SecurityIncident.objects.create(
                    title=f"Webhook Security Alert: {event_data.get('title', 'Unknown')}",
                    incident_type='webhook_alert',
                    severity=severity,
                    priority='high',
                    description=event_data.get('description', 'Security alert received via webhook'),
                    metadata={
                        'webhook_source': True,
                        'original_event': event_data
                    }
                )
            
            return {'success': True, 'message': 'Security alert processed'}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _handle_threat_detected(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle threat detected event"""
        try:
            # Create threat intelligence record
            from ..models import ThreatIntelligence
            
            ThreatIntelligence.objects.update_or_create(
                indicator=event_data.get('indicator', ''),
                defaults={
                    'threat_type': event_data.get('threat_type', 'unknown'),
                    'indicator_type': event_data.get('indicator_type', 'unknown'),
                    'severity': event_data.get('severity', 'medium'),
                    'source': 'webhook',
                    'description': event_data.get('description', 'Threat detected via webhook'),
                    'is_active': True
                }
            )
            
            return {'success': True, 'message': 'Threat processed'}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _handle_incident_created(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incident created event"""
        try:
            # Create security incident
            SecurityIncident.objects.create(
                title=event_data.get('title', 'Webhook Incident'),
                incident_type=event_data.get('incident_type', 'webhook_incident'),
                severity=event_data.get('severity', 'medium'),
                priority=event_data.get('priority', 'medium'),
                description=event_data.get('description', 'Incident created via webhook'),
                metadata={
                    'webhook_source': True,
                    'original_event': event_data
                }
            )
            
            return {'success': True, 'message': 'Incident created'}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or '0.0.0.0'
    
    def get_received_webhooks(self, webhook_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get received webhooks"""
        webhooks = self.received_webhooks
        
        if webhook_name:
            webhooks = [w for w in webhooks if w['webhook_name'] == webhook_name]
        
        return webhooks[-limit:]


# Global webhook receiver
webhook_receiver = WebhookReceiver()


# Export symbols
__all__ = [
    'WebhookIntegration',
    'WebhookReceiver',
    'webhook_receiver'
]