"""
Integration Signals - Django Signal Integration

Custom Django signals for integration events, providing loose coupling
between rate limiting components and other modules.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, pre_save, post_delete
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationPriority, IntegrationStatus
from .integ_handler import integration_handler, IntegrationRequest, IntegrationMode

logger = logging.getLogger(__name__)


# Custom integration signals
rate_limit_exceeded = Signal(
)

abuse_detected = Signal(
)

ip_blocked = Signal(
)

sanction_applied = Signal(
)

rate_limit_config_updated = Signal(
)

integration_event_processed = Signal(
)

system_health_alert = Signal(
)

performance_threshold_exceeded = Signal(
)

data_integrity_violation = Signal(
)

compliance_event = Signal(
)


class IntegrationSignalManager:
    """Manager for integration signal handling and routing."""
    
    def __init__(self):
        self.active_listeners: Dict[str, int] = {}
        self.signal_stats: Dict[str, Dict[str, Any]] = {}
        self._initialize_signal_stats()
    
    def _initialize_signal_stats(self):
        """Initialize signal statistics tracking."""
        signals = [
            'rate_limit_exceeded', 'abuse_detected', 'ip_blocked',
            'sanction_applied', 'rate_limit_config_updated',
            'integration_event_processed', 'system_health_alert',
            'performance_threshold_exceeded', 'data_integrity_violation',
            'compliance_event'
        ]
        
        for signal_name in signals:
            self.signal_stats[signal_name] = {
                'total_sent': 0,
                'total_received': 0,
                'errors': 0,
                'last_sent': None,
                'last_received': None
            }
    
    def send_integration_event(self, event_type: IntegrationEvent, **kwargs):
        """Send integration event through signal system."""
        try:
            # Update stats
            signal_name = event_type.value
            self.signal_stats[signal_name]['total_sent'] += 1
            self.signal_stats[signal_name]['last_sent'] = timezone.now()
            
            # Get the corresponding signal
            signal_map = {
                IntegrationEvent.RATE_LIMIT_EXCEEDED: rate_limit_exceeded,
                IntegrationEvent.ABUSE_DETECTED: abuse_detected,
                IntegrationEvent.IP_BLOCKED: ip_blocked,
                IntegrationEvent.SANCTION_APPLIED: sanction_applied,
                IntegrationEvent.CONFIG_UPDATED: rate_limit_config_updated,
                IntegrationEvent.SYSTEM_HEALTH: system_health_alert,
                IntegrationEvent.PERFORMANCE_ALERT: performance_threshold_exceeded,
                IntegrationEvent.DATA_INTEGRITY: data_integrity_violation,
                IntegrationEvent.COMPLIANCE_EVENT: compliance_event
            }
            
            signal = signal_map.get(event_type)
            if signal:
                signal.send(sender=self.__class__, **kwargs)
            
            # Also create integration request for async processing
            request = IntegrationRequest(
                request_id=f"signal_{event_type.value}_{timezone.now().timestamp()}",
                event_type=event_type,
                source_module="signal_system",
                target_module="integration_handler",
                payload=kwargs,
                mode=IntegrationMode.ASYNC,
                priority=self._get_priority_from_event(event_type, kwargs)
            )
            
            # Process asynchronously
            import asyncio
            asyncio.create_task(integration_handler.process_request(request))
            
        except Exception as e:
            logger.error(f"Failed to send integration event: {event_type.value} - {str(e)}")
            self.signal_stats[event_type.value]['errors'] += 1
    
    def _get_priority_from_event(self, event_type: IntegrationEvent, kwargs: Dict[str, Any]) -> IntegrationPriority:
        """Determine priority from event type and context."""
        if event_type in [IntegrationEvent.ABUSE_DETECTED, IntegrationEvent.IP_BLOCKED]:
            severity = kwargs.get('severity', 3)
            if severity >= 4:
                return IntegrationPriority.HIGH
            elif severity >= 2:
                return IntegrationPriority.NORMAL
            else:
                return IntegrationPriority.LOW
        elif event_type in [IntegrationEvent.SYSTEM_HEALTH, IntegrationEvent.DATA_INTEGRITY]:
            return IntegrationPriority.HIGH
        else:
            return IntegrationPriority.NORMAL
    
    def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal statistics."""
        return self.signal_stats.copy()


# Global signal manager
signal_manager = IntegrationSignalManager()


# Signal receivers
@receiver(rate_limit_exceeded)
def handle_rate_limit_exceeded_signal(sender, **kwargs):
    """Handle rate limit exceeded signals."""
    try:
        # Update stats
        signal_manager.signal_stats['rate_limit_exceeded']['total_received'] += 1
        signal_manager.signal_stats['rate_limit_exceeded']['last_received'] = timezone.now()
        
        # Log the event
        logger.warning(f"Rate limit exceeded signal: {kwargs}")
        
        # Trigger additional actions if needed
        severity = kwargs.get('severity', 'normal')
        if severity == 'high':
            # Trigger immediate IP blocking for high severity
            from api.rate_limit.services.IPBlockService import IPBlockService
            ip_service = IPBlockService()
            
            ip_service.block_ip(
                ip_address=kwargs.get('ip_address'),
                reason='High severity rate limit exceeded',
                duration_days=1
            )
    
    except Exception as e:
        logger.error(f"Error handling rate limit exceeded signal: {str(e)}")
        signal_manager.signal_stats['rate_limit_exceeded']['errors'] += 1


@receiver(abuse_detected)
def handle_abuse_detected_signal(sender, **kwargs):
    """Handle abuse detection signals."""
    try:
        # Update stats
        signal_manager.signal_stats['abuse_detected']['total_received'] += 1
        signal_manager.signal_stats['abuse_detected']['last_received'] = timezone.now()
        
        # Log the event
        logger.warning(f"Abuse detected signal: {kwargs}")
        
        # Create abuse report if not already created
        from api.rate_limit.models.AbuseReport import AbuseReport
        
        # Check if report already exists for this IP/time window
        recent_reports = AbuseReport.objects.filter(
            ip_address=kwargs.get('ip_address'),
            created_at__gte=timezone.now() - timezone.timedelta(hours=1)
        )
        
        if not recent_reports.exists():
            AbuseReport.objects.create(
                ip_address=kwargs.get('ip_address'),
                user_id=kwargs.get('user_id'),
                abuse_type=kwargs.get('abuse_type'),
                severity=kwargs.get('severity', 3),
                details=kwargs.get('details', {}),
                is_investigated=False
            )
    
    except Exception as e:
        logger.error(f"Error handling abuse detected signal: {str(e)}")
        signal_manager.signal_stats['abuse_detected']['errors'] += 1


@receiver(ip_blocked)
def handle_ip_blocked_signal(sender, **kwargs):
    """Handle IP blocking signals."""
    try:
        # Update stats
        signal_manager.signal_stats['ip_blocked']['total_received'] += 1
        signal_manager.signal_stats['ip_blocked']['last_received'] = timezone.now()
        
        # Log the event
        logger.info(f"IP blocked signal: {kwargs}")
        
        # Clear cache for blocked IP
        from django.core.cache import cache
        ip_address = kwargs.get('ip_address')
        cache.delete(f"rl:ip:{ip_address}")
        
        # Send webhook notification
        from api.rate_limit.webhooks import WebhookManager
        webhook_manager = WebhookManager()
        
        webhook_manager.send_webhook(
            event_type='ip_blocked',
            payload={
                'ip_address': ip_address,
                'reason': kwargs.get('reason'),
                'duration': kwargs.get('duration'),
                'timestamp': timezone.now().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"Error handling IP blocked signal: {str(e)}")
        signal_manager.signal_stats['ip_blocked']['errors'] += 1


@receiver(sanction_applied)
def handle_sanction_applied_signal(sender, **kwargs):
    """Handle sanction applied signals."""
    try:
        # Update stats
        signal_manager.signal_stats['sanction_applied']['total_received'] += 1
        signal_manager.signal_stats['sanction_applied']['last_received'] = timezone.now()
        
        # Log the event
        logger.info(f"Sanction applied signal: {kwargs}")
        
        # Update user profile if applicable
        user_id = kwargs.get('target')
        if user_id and isinstance(user_id, int):
            from api.rate_limit.models.UserRateLimitProfile import UserRateLimitProfile
            try:
                profile = UserRateLimitProfile.objects.get(user_id=user_id)
                profile.suspicion_score = min(100, profile.suspicion_score + 10)
                profile.save()
            except UserRateLimitProfile.DoesNotExist:
                pass
        
        # Log compliance event
        from api.rate_limit.compliance import ComplianceAuditTrail
        audit_trail = ComplianceAuditTrail()
        audit_trail.log_action(
            action='sanction_applied',
            user_id=user_id if isinstance(user_id, int) else None,
            ip_address=kwargs.get('ip_address'),
            details=kwargs,
            compliance_relevant=True
        )
    
    except Exception as e:
        logger.error(f"Error handling sanction applied signal: {str(e)}")
        signal_manager.signal_stats['sanction_applied']['errors'] += 1


@receiver(rate_limit_config_updated)
def handle_rate_limit_config_updated_signal(sender, **kwargs):
    """Handle rate limit config update signals."""
    try:
        # Update stats
        signal_manager.signal_stats['rate_limit_config_updated']['total_received'] += 1
        signal_manager.signal_stats['rate_limit_config_updated']['last_received'] = timezone.now()
        
        # Log the event
        logger.info(f"Rate limit config updated signal: {kwargs}")
        
        # Clear relevant cache
        from django.core.cache import cache
        cache.delete_many_pattern("rl:config:*")
        
        # Sync with Redis
        from api.rate_limit.management.commands.sync_rate_configs import ConfigSyncManager
        sync_manager = ConfigSyncManager()
        sync_manager.sync_single_config(kwargs.get('config_id'))
    
    except Exception as e:
        logger.error(f"Error handling rate limit config updated signal: {str(e)}")
        signal_manager.signal_stats['rate_limit_config_updated']['errors'] += 1


@receiver(system_health_alert)
def handle_system_health_alert_signal(sender, **kwargs):
    """Handle system health alert signals."""
    try:
        # Update stats
        signal_manager.signal_stats['system_health_alert']['total_received'] += 1
        signal_manager.signal_stats['system_health_alert']['last_received'] = timezone.now()
        
        # Log the event
        logger.warning(f"System health alert signal: {kwargs}")
        
        # Send admin notification
        from django.core.mail import mail_admins
        component = kwargs.get('component', 'unknown')
        status = kwargs.get('status', 'unknown')
        message = kwargs.get('message', '')
        
        mail_admins(
            subject=f'Rate Limit System Health Alert: {component}',
            message=f'Component: {component}\nStatus: {status}\nMessage: {message}\nTime: {timezone.now()}'
        )
    
    except Exception as e:
        logger.error(f"Error handling system health alert signal: {str(e)}")
        signal_manager.signal_stats['system_health_alert']['errors'] += 1


@receiver(data_integrity_violation)
def handle_data_integrity_violation_signal(sender, **kwargs):
    """Handle data integrity violation signals."""
    try:
        # Update stats
        signal_manager.signal_stats['data_integrity_violation']['total_received'] += 1
        signal_manager.signal_stats['data_integrity_violation']['last_received'] = timezone.now()
        
        # Log the event
        logger.error(f"Data integrity violation signal: {kwargs}")
        
        # Send security alert
        from django.core.mail import mail_admins
        model = kwargs.get('model', 'unknown')
        record_id = kwargs.get('record_id', 'unknown')
        
        mail_admins(
            subject='CRITICAL: Rate Limit Data Integrity Violation',
            message=f'Model: {model}\nRecord ID: {record_id}\nTime: {timezone.now()}\nThis requires immediate investigation!'
        )
        
        # Create security event log
        from api.rate_limit.models.RateLimitException import RateLimitException
        RateLimitException.objects.create(
            exception_type='INTEGRITY_VIOLATION',
            details=kwargs,
            severity=5,
            is_resolved=False
        )
    
    except Exception as e:
        logger.error(f"Error handling data integrity violation signal: {str(e)}")
        signal_manager.signal_stats['data_integrity_violation']['errors'] += 1


# Model signal receivers for integration events
@receiver(post_save, sender=None)
def handle_model_post_save(sender, instance, created, **kwargs):
    """Handle model post-save events for integration."""
    try:
        # Only process rate limit models
        if hasattr(instance, '_meta') and instance._meta.app_label == 'rate_limit':
            model_name = instance._meta.model_name
            
            if model_name == 'ratelimitlog' and instance.status == 'blocked':
                signal_manager.send_integration_event(
                    IntegrationEvent.RATE_LIMIT_EXCEEDED,
                    ip_address=instance.ip_address,
                    endpoint=instance.endpoint,
                    method=instance.request_method,
                    payload={'log_id': instance.id}
                )
            elif model_name == 'abusereport' and created:
                signal_manager.send_integration_event(
                    IntegrationEvent.ABUSE_DETECTED,
                    ip_address=instance.ip_address,
                    user_id=instance.user_id,
                    abuse_type=instance.abuse_type,
                    severity=instance.severity,
                    details=instance.details
                )
            elif model_name == 'ipblocklist' and created:
                signal_manager.send_integration_event(
                    IntegrationEvent.IP_BLOCKED,
                    ip_address=instance.ip_address,
                    reason=instance.reason,
                    duration=instance.duration_days,
                    block_type=instance.block_type
                )
    
    except Exception as e:
        logger.error(f"Error in model post-save integration: {str(e)}")


@receiver(pre_save, sender=None)
def handle_model_pre_save(sender, instance, **kwargs):
    """Handle model pre-save events for integrity checking."""
    try:
        # Check integrity for HashChainedModel instances
        if hasattr(instance, 'verify_integrity'):
            if not instance.verify_integrity():
                signal_manager.send_integration_event(
                    IntegrationEvent.DATA_INTEGRITY,
                    model=instance._meta.model_name,
                    record_id=instance.id,
                    expected_hash=instance.integrity_hash,
                    actual_hash='verification_failed'
                )
    
    except Exception as e:
        logger.error(f"Error in model pre-save integration: {str(e)}")
