"""
Security Webhooks Module
Webhook handling for security events and notifications
"""

import logging
import hashlib
import hmac
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import models
from django.core.cache import cache
from django.urls import reverse
from django.http import HttpResponse
from rest_framework import status
import requests
from requests.exceptions import RequestException

from .models import SecurityLog, SecurityIncident
from .utils import SecurityUtils

logger = logging.getLogger('security.webhooks')


class WebhookEvent:
    """Webhook event data structure"""
    
    def __init__(self, event_type: str, data: Dict[str, Any], 
                 timestamp: Optional[datetime] = None, metadata: Optional[Dict[str, Any]] = None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or timezone.now()
        self.metadata = metadata or {}
        self.event_id = SecurityUtils.generate_secure_token(32)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'metadata': self.metadata
        }


class Webhook(models.Model):
    """Webhook configuration model"""
    
    EVENT_TYPES = [
        ('security_incident', 'Security Incident'),
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('failed_login', 'Failed Login'),
        ('password_change', 'Password Change'),
        ('account_locked', 'Account Locked'),
        ('data_breach', 'Data Breach'),
        ('system_alert', 'System Alert'),
        ('audit_log', 'Audit Log'),
        ('threat_detected', 'Threat Detected'),
        ('policy_violation', 'Policy Violation'),
        ('all', 'All Events'),
    ]
    
    name = models.CharField(max_length=100, unique=True, help_text="Webhook name")
    url = models.URLField(max_length=500, help_text="Webhook URL")
    event_types = models.JSONField(
        default=list,
        help_text="List of event types to trigger this webhook"
    )
    secret_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret key for HMAC signature"
    )
    is_active = models.BooleanField(default=True, help_text="Whether webhook is active")
    timeout = models.IntegerField(
        default=30,
        help_text="Request timeout in seconds"
    )
    retry_count = models.IntegerField(
        default=3,
        help_text="Number of retry attempts"
    )
    retry_delay = models.IntegerField(
        default=60,
        help_text="Delay between retries in seconds"
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional HTTP headers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'security_webhooks'
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.url}"
    
    def should_trigger(self, event_type: str) -> bool:
        """Check if webhook should trigger for event type"""
        return (
            self.is_active and
            ('all' in self.event_types or event_type in self.event_types)
        )
    
    def generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for payload"""
        if not self.secret_key:
            return ""
        
        return hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def send_webhook(self, event: WebhookEvent) -> bool:
        """Send webhook event"""
        try:
            payload = json.dumps(event.to_dict())
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': f'Security-Webhook/1.0',
                'X-Webhook-Event': event.event_type,
                'X-Webhook-ID': event.event_id,
                'X-Webhook-Timestamp': event.timestamp.isoformat(),
            }
            
            # Add custom headers
            headers.update(self.headers)
            
            # Add signature if secret key is configured
            if self.secret_key:
                headers['X-Webhook-Signature'] = self.generate_signature(payload)
            
            # Send request
            response = requests.post(
                self.url,
                data=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            # Update statistics
            self.last_triggered = timezone.now()
            if response.status_code < 400:
                self.success_count += 1
                logger.info(f"Webhook {self.name} delivered successfully: {event.event_type}")
                return True
            else:
                self.failure_count += 1
                logger.warning(f"Webhook {self.name} failed: {response.status_code}")
                return False
                
        except RequestException as e:
            self.failure_count += 1
            logger.error(f"Webhook {self.name} request failed: {e}")
            return False
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Webhook {self.name} unexpected error: {e}")
            return False
        finally:
            self.save(update_fields=['last_triggered', 'success_count', 'failure_count'])


class WebhookDelivery(models.Model):
    """Webhook delivery tracking"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
    ]
    
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    event_id = models.CharField(max_length=64)
    event_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attempt_count = models.IntegerField(default=0)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'security_webhook_deliveries'
        verbose_name = "Webhook Delivery"
        verbose_name_plural = "Webhook Deliveries"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', 'status']),
            models.Index(fields=['event_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} - {self.status}"


class WebhookManager:
    """Manager for webhook operations"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.retry_queue_cache_key = 'webhook_retry_queue'
    
    def trigger_event(self, event_type: str, data: Dict[str, Any], 
                    metadata: Optional[Dict[str, Any]] = None) -> int:
        """Trigger webhooks for an event"""
        event = WebhookEvent(event_type, data, metadata=metadata)
        
        # Get active webhooks for this event
        webhooks = Webhook.objects.filter(
            is_active=True
        ).filter(
            models.Q(event_types__contains=['all']) | 
            models.Q(event_types__contains=[event_type])
        )
        
        delivered_count = 0
        
        for webhook in webhooks:
            if webhook.should_trigger(event_type):
                delivery = WebhookDelivery.objects.create(
                    webhook=webhook,
                    event_id=event.event_id,
                    event_type=event_type,
                    status='pending'
                )
                
                # Send webhook
                success = webhook.send_webhook(event)
                
                if success:
                    delivery.status = 'delivered'
                    delivery.delivered_at = timezone.now()
                    delivery.response_status = 200
                    delivered_count += 1
                else:
                    delivery.status = 'failed'
                    delivery.error_message = 'Webhook delivery failed'
                
                delivery.attempt_count = 1
                delivery.save()
        
        logger.info(f"Triggered {delivered_count} webhooks for event: {event_type}")
        return delivered_count
    
    def retry_failed_deliveries(self) -> int:
        """Retry failed webhook deliveries"""
        # Get failed deliveries that haven't exceeded retry count
        failed_deliveries = WebhookDelivery.objects.filter(
            status='failed'
        ).filter(
            attempt_count__lt=models.F('webhook__retry_count')
        ).filter(
            created_at__lt=timezone.now() - timedelta(seconds=60)  # Wait at least 1 minute
        )
        
        retried_count = 0
        
        for delivery in failed_deliveries:
            webhook = delivery.webhook
            
            # Check if enough time has passed for retry
            retry_after = delivery.created_at + timedelta(
                seconds=webhook.retry_delay * delivery.attempt_count
            )
            
            if timezone.now() >= retry_after:
                # Recreate event
                event = WebhookEvent(
                    event_type=delivery.event_type,
                    data={},  # Data would need to be stored or reconstructed
                    metadata={'retry': True, 'attempt': delivery.attempt_count + 1}
                )
                
                delivery.status = 'retry'
                delivery.attempt_count += 1
                
                success = webhook.send_webhook(event)
                
                if success:
                    delivery.status = 'delivered'
                    delivery.delivered_at = timezone.now()
                    delivery.response_status = 200
                    retried_count += 1
                else:
                    delivery.status = 'failed'
                    delivery.error_message = f'Retry {delivery.attempt_count} failed'
                
                delivery.save()
        
        logger.info(f"Retried {retried_count} failed webhook deliveries")
        return retried_count
    
    def get_webhook_statistics(self) -> Dict[str, Any]:
        """Get webhook statistics"""
        webhooks = Webhook.objects.all()
        
        stats = {
            'total_webhooks': webhooks.count(),
            'active_webhooks': webhooks.filter(is_active=True).count(),
            'total_deliveries': WebhookDelivery.objects.count(),
            'successful_deliveries': WebhookDelivery.objects.filter(status='delivered').count(),
            'failed_deliveries': WebhookDelivery.objects.filter(status='failed').count(),
            'pending_deliveries': WebhookDelivery.objects.filter(status='pending').count(),
            'recent_deliveries': WebhookDelivery.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
        }
        
        # Per-webhook statistics
        webhook_stats = []
        for webhook in webhooks:
            deliveries = webhook.deliveries.all()
            webhook_stats.append({
                'name': webhook.name,
                'url': webhook.url,
                'is_active': webhook.is_active,
                'total_deliveries': deliveries.count(),
                'successful_deliveries': deliveries.filter(status='delivered').count(),
                'failed_deliveries': deliveries.filter(status='failed').count(),
                'success_rate': (
                    deliveries.filter(status='delivered').count() / deliveries.count() * 100
                    if deliveries.count() > 0 else 0
                ),
                'last_triggered': webhook.last_triggered.isoformat() if webhook.last_triggered else None,
            })
        
        stats['webhook_details'] = webhook_stats
        
        return stats
    
    def cleanup_old_deliveries(self, days: int = 30) -> int:
        """Clean up old webhook deliveries"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count = WebhookDelivery.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old webhook deliveries")
        return deleted_count


# Built-in webhook event generators
class SecurityEventGenerator:
    """Generate webhook events for security operations"""
    
    def __init__(self, webhook_manager: WebhookManager):
        self.webhook_manager = webhook_manager
    
    def on_security_incident_created(self, incident: SecurityIncident) -> None:
        """Trigger webhook for security incident creation"""
        data = {
            'incident_id': incident.id,
            'incident_type': incident.incident_type,
            'severity': incident.severity,
            'title': incident.title,
            'description': incident.description,
            'user': incident.user.username if incident.user else None,
            'affected_systems': incident.affected_systems,
            'priority': incident.priority,
            'opened_at': incident.opened_at.isoformat(),
        }
        
        metadata = {
            'model': 'SecurityIncident',
            'action': 'created',
            'user_id': incident.user.id if incident.user else None,
        }
        
        self.webhook_manager.trigger_event('security_incident', data, metadata)
    
    def on_user_login(self, user, request) -> None:
        """Trigger webhook for user login"""
        data = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'ip_address': SecurityUtils.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'timestamp': timezone.now().isoformat(),
        }
        
        metadata = {
            'model': 'User',
            'action': 'login',
            'session_id': request.session.session_key,
        }
        
        self.webhook_manager.trigger_event('user_login', data, metadata)
    
    def on_user_logout(self, user, request) -> None:
        """Trigger webhook for user logout"""
        data = {
            'user_id': user.id,
            'username': user.username,
            'ip_address': SecurityUtils.get_client_ip(request),
            'timestamp': timezone.now().isoformat(),
        }
        
        metadata = {
            'model': 'User',
            'action': 'logout',
            'session_id': getattr(request, 'session', {}).get('session_key'),
        }
        
        self.webhook_manager.trigger_event('user_logout', data, metadata)
    
    def on_failed_login(self, username, request, reason: str = '') -> None:
        """Trigger webhook for failed login"""
        data = {
            'username': username,
            'ip_address': SecurityUtils.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'reason': reason,
            'timestamp': timezone.now().isoformat(),
        }
        
        metadata = {
            'model': 'User',
            'action': 'failed_login',
            'session_id': getattr(request, 'session', {}).get('session_key'),
        }
        
        self.webhook_manager.trigger_event('failed_login', data, metadata)
    
    def on_password_change(self, user, request) -> None:
        """Trigger webhook for password change"""
        data = {
            'user_id': user.id,
            'username': user.username,
            'ip_address': SecurityUtils.get_client_ip(request),
            'timestamp': timezone.now().isoformat(),
        }
        
        metadata = {
            'model': 'User',
            'action': 'password_change',
            'session_id': request.session.session_key,
        }
        
        self.webhook_manager.trigger_event('password_change', data, metadata)
    
    def on_account_locked(self, user, reason: str) -> None:
        """Trigger webhook for account lock"""
        data = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'reason': reason,
            'timestamp': timezone.now().isoformat(),
        }
        
        metadata = {
            'model': 'User',
            'action': 'account_locked',
        }
        
        self.webhook_manager.trigger_event('account_locked', data, metadata)
    
    def on_threat_detected(self, threat_type: str, threat_data: Dict[str, Any]) -> None:
        """Trigger webhook for threat detection"""
        data = {
            'threat_type': threat_type,
            'threat_data': threat_data,
            'timestamp': timezone.now().isoformat(),
        }
        
        metadata = {
            'model': 'ThreatIntelligence',
            'action': 'threat_detected',
        }
        
        self.webhook_manager.trigger_event('threat_detected', data, metadata)


# Global webhook manager and event generator
webhook_manager = WebhookManager()
event_generator = SecurityEventGenerator(webhook_manager)


# Django signal handlers for webhook events
def setup_webhook_signals():
    """Setup Django signals for webhook events"""
    from django.db.models.signals import post_save
    from django.contrib.auth.signals import user_logged_in, user_logged_out
    
    def incident_created_handler(sender, instance, created, **kwargs):
        if created and sender.__name__ == 'SecurityIncident':
            event_generator.on_security_incident_created(instance)
    
    def user_logged_in_handler(sender, request, user, **kwargs):
        event_generator.on_user_login(user, request)
    
    def user_logged_out_handler(sender, request, user, **kwargs):
        event_generator.on_user_logout(user, request)
    
    # Connect signals
    try:
        post_save.connect(incident_created_handler, sender=SecurityIncident)
        user_logged_in.connect(user_logged_in_handler)
        user_logged_out.connect(user_logged_out_handler)
    except Exception as e:
        logger.error(f"Failed to setup webhook signals: {e}")


# Management command utilities
class WebhookUtils:
    """Utility functions for webhook management"""
    
    @staticmethod
    def test_webhook(webhook_id: int) -> Dict[str, Any]:
        """Test a webhook"""
        try:
            webhook = Webhook.objects.get(id=webhook_id)
            
            # Create test event
            test_event = WebhookEvent(
                event_type='test',
                data={'message': 'Test webhook event'},
                metadata={'test': True}
            )
            
            # Send webhook
            success = webhook.send_webhook(test_event)
            
            return {
                'success': success,
                'webhook_id': webhook_id,
                'webhook_name': webhook.name,
                'event_id': test_event.event_id,
                'timestamp': test_event.timestamp.isoformat()
            }
            
        except Webhook.DoesNotExist:
            return {
                'success': False,
                'error': 'Webhook not found'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def create_webhook(name: str, url: str, event_types: List[str], 
                       secret_key: str = '', **kwargs) -> Webhook:
        """Create a new webhook"""
        webhook = Webhook.objects.create(
            name=name,
            url=url,
            event_types=event_types,
            secret_key=secret_key,
            **kwargs
        )
        
        logger.info(f"Created webhook: {webhook.name}")
        return webhook
    
    @staticmethod
    def enable_webhook(webhook_id: int) -> bool:
        """Enable a webhook"""
        try:
            webhook = Webhook.objects.get(id=webhook_id)
            webhook.is_active = True
            webhook.save()
            logger.info(f"Enabled webhook: {webhook.name}")
            return True
        except Webhook.DoesNotExist:
            return False
    
    @staticmethod
    def disable_webhook(webhook_id: int) -> bool:
        """Disable a webhook"""
        try:
            webhook = Webhook.objects.get(id=webhook_id)
            webhook.is_active = False
            webhook.save()
            logger.info(f"Disabled webhook: {webhook.name}")
            return True
        except Webhook.DoesNotExist:
            return False


# Export classes and utilities
__all__ = [
    'WebhookEvent',
    'Webhook',
    'WebhookDelivery',
    'WebhookManager',
    'SecurityEventGenerator',
    'webhook_manager',
    'event_generator',
    'setup_webhook_signals',
    'WebhookUtils'
]