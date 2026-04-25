"""
Security Signal Handlers

This module contains signal handlers for security-related models including
TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, and TenantAuditLog.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.security import TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, TenantAuditLog
from ..models.analytics import TenantNotification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TenantAPIKey)
def api_key_created(sender, instance, created, **kwargs):
    """
    Handle API key creation.
    
    Signal triggered when a new API key is created.
    """
    if created:
        logger.info(f"API key created for {instance.tenant.name}: {instance.name}")
        
        # Log API key creation
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='create',
            model_name='TenantAPIKey',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"API key '{instance.name}' created",
            metadata={
                'key_prefix': instance.key_prefix,
                'scopes': instance.scopes,
                'rate_limit_per_minute': instance.rate_limit_per_minute,
                'expires_at': instance.expires_at.isoformat() if instance.expires_at else None,
            },
            severity='medium',
        )
        
        # Trigger signal
        from . import api_key_created
        api_key_created.send(sender=TenantAPIKey, api_key=instance)


@receiver(pre_save, sender=TenantAPIKey)
def api_key_pre_save(sender, instance, **kwargs):
    """
    Handle API key pre-save operations.
    
    Signal triggered before API key is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantAPIKey.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
                instance._new_status = instance.status
                
        except TenantAPIKey.DoesNotExist:
            pass  # New API key, no changes to track


@receiver(post_save, sender=TenantAPIKey)
def api_key_updated(sender, instance, created, **kwargs):
    """
    Handle API key updates.
    
    Signal triggered when API key is updated.
    """
    if not created:
        logger.info(f"API key updated for {instance.tenant.name}: {instance.name} - Status: {instance.status}")
        
        # Handle status changes
        if hasattr(instance, '_status_changed'):
            if instance._new_status == 'revoked':
                # Log revocation
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantAPIKey',
                    object_id=str(instance.id),
                    object_repr=str(instance),
                    description=f"API key '{instance.name}' revoked",
                    changes={
                        'status': {'old': instance._old_status, 'new': instance._new_status}
                    },
                    severity='high',
                )
                
                # Trigger signal
                from . import api_key_revoked
                api_key_revoked.send(sender=TenantAPIKey, api_key=instance)
                
                # Send notification
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='API Key Revoked',
                    message=f'API key "{instance.name}" has been revoked.',
                    notification_type='security',
                    priority='high',
                    send_email=True,
                    send_push=True,
                    action_url='/security/api-keys',
                    action_text='Manage API Keys',
                    metadata={'api_key_id': str(instance.id)},
                )


@receiver(post_save, sender=TenantWebhookConfig)
def webhook_config_created(sender, instance, created, **kwargs):
    """
    Handle webhook configuration creation.
    
    Signal triggered when a webhook configuration is created.
    """
    if created:
        logger.info(f"Webhook config created for {instance.tenant.name}: {instance.name}")
        
        # Log webhook creation
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='create',
            model_name='TenantWebhookConfig',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Webhook configuration '{instance.name}' created",
            metadata={
                'url': instance.url,
                'events': instance.events,
                'auth_type': instance.auth_type,
            },
            severity='low',
        )


@receiver(post_save, sender=TenantWebhookConfig)
def webhook_triggered(sender, instance, created, **kwargs):
    """
    Handle webhook trigger events.
    
    This would be called when a webhook is triggered.
    """
    if not created:
        # This would be called by the webhook delivery system
        # For now, just log that it would be triggered
        pass


@receiver(post_save, sender=TenantIPWhitelist)
def ip_whitelist_created(sender, instance, created, **kwargs):
    """
    Handle IP whitelist entry creation.
    
    Signal triggered when an IP whitelist entry is created.
    """
    if created:
        logger.info(f"IP whitelist entry created for {instance.tenant.name}: {instance.ip_range}")
        
        # Log IP whitelist creation
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='create',
            model_name='TenantIPWhitelist',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"IP whitelist entry '{instance.ip_range}' created",
            metadata={
                'ip_range': instance.ip_range,
                'label': instance.label,
                'is_active': instance.is_active,
            },
            severity='low',
        )


@receiver(post_save, sender=TenantAuditLog)
def audit_log_created(sender, instance, created, **kwargs):
    """
    Handle audit log creation.
    
    Signal triggered when an audit log is created.
    """
    if created:
        logger.debug(f"Audit log created for {instance.tenant.name}: {instance.action}")
        
        # Check for high-severity events
        if instance.severity in ['high', 'critical']:
            # Send security alert
            if instance.action == 'security_event':
                # Trigger security event signal
                from . import security_event_detected
                security_event_detected.send(
                    sender=TenantAuditLog,
                    tenant=instance.tenant,
                    audit_log=instance,
                )
                
                # Send immediate notification
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='Security Event Detected',
                    message=instance.description,
                    notification_type='security',
                    priority='urgent' if instance.severity == 'critical' else 'high',
                    send_email=True,
                    send_push=True,
                    action_url='/security/audit',
                    action_text='View Security Log',
                    metadata={'audit_log_id': str(instance.id)},
                )
        
        # Trigger signal
        from . import audit_log_created
        audit_log_created.send(sender=TenantAuditLog, audit_log=instance)


def log_api_access(tenant, user, endpoint, ip_address, user_agent, request_id=None):
    """
    Log API access for audit purposes.
    
    Args:
        tenant: Tenant instance
        user: User instance
        endpoint: API endpoint
        ip_address: Client IP address
        user_agent: User agent string
        request_id: Request ID for tracking
    """
    # Create audit log entry
    audit_log = TenantAuditLog.objects.create(
        tenant=tenant,
        action='api_access',
        actor=user,
        model_name='API',
        description=f"API access: {endpoint}",
        metadata={
            'endpoint': endpoint,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'request_id': request_id,
        },
        severity='low',
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    
    # Update API key usage if applicable
    # This would update the last_used_at and usage_count for the API key
    
    # Trigger signal
    from . import api_key_used
    api_key_used.send(
        sender=None,
        tenant=tenant,
        user=user,
        endpoint=endpoint,
        ip_address=ip_address,
    )


def log_security_event(tenant, event_type, description, severity='medium', 
                      actor=None, ip_address=None, metadata=None):
    """
    Log security event.
    
    Args:
        tenant: Tenant instance
        event_type: Type of security event
        description: Event description
        severity: Event severity
        actor: User who triggered the event
        ip_address: IP address
        metadata: Additional metadata
    """
    # Create audit log entry
    audit_log = TenantAuditLog.objects.create(
        tenant=tenant,
        action='security_event',
        actor=actor,
        model_name='SecurityEvent',
        object_repr=event_type,
        description=description,
        metadata=metadata or {},
        severity=severity,
        ip_address=ip_address,
    )
    
    # Trigger signal
    from . import security_event_detected
    security_event_detected.send(
        sender=TenantAuditLog,
        tenant=tenant,
        event_type=event_type,
        audit_log=audit_log,
    )


@receiver(pre_save, sender=TenantWebhookConfig)
def webhook_config_pre_save(sender, instance, **kwargs):
    """
    Handle webhook configuration pre-save operations.
    
    Signal triggered before webhook config is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantWebhookConfig.objects.get(pk=instance.pk)
            
            # Track status changes
            if old_instance.is_active != instance.is_active:
                instance._status_changed = True
                instance._old_status = old_instance.is_active
                instance._new_status = instance.is_active
                
        except TenantWebhookConfig.DoesNotExist:
            pass  # New webhook config, no changes to track


@receiver(post_save, sender=TenantWebhookConfig)
def webhook_config_updated(sender, instance, created, **kwargs):
    """
    Handle webhook configuration updates.
    
    Signal triggered when webhook configuration is updated.
    """
    if not created:
        logger.info(f"Webhook config updated for {instance.tenant.name}: {instance.name}")
        
        # Handle status changes
        if hasattr(instance, '_status_changed'):
            status_text = 'activated' if instance._new_status else 'deactivated'
            
            # Log status change
            TenantAuditLog.log_action(
                tenant=instance.tenant,
                action='config_change',
                model_name='TenantWebhookConfig',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Webhook configuration '{instance.name}' {status_text}",
                changes={
                    'is_active': {'old': instance._old_status, 'new': instance._new_status}
                },
            )


def detect_anomalous_activity(tenant, activity_type, data):
    """
    Detect anomalous activity and trigger appropriate responses.
    
    Args:
        tenant: Tenant instance
        activity_type: Type of activity
        data: Activity data
    """
    # This would implement anomaly detection logic
    # For now, just log the detection
    
    if activity_type == 'unusual_api_usage':
        log_security_event(
            tenant=tenant,
            event_type='unusual_api_usage',
            description=f"Unusual API usage detected: {data}",
            severity='medium',
            metadata=data,
        )
    
    elif activity_type == 'multiple_ip_access':
        log_security_event(
            tenant=tenant,
            event_type='multiple_ip_access',
            description=f"API access from multiple IPs detected: {data}",
            severity='medium',
            metadata=data,
        )
    
    elif activity_type == 'failed_login_attempts':
        log_security_event(
            tenant=tenant,
            event_type='failed_login_attempts',
            description=f"Multiple failed login attempts: {data}",
            severity='high',
            metadata=data,
        )
