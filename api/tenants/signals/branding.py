"""
Branding Signal Handlers

This module contains signal handlers for branding-related models including
TenantBranding, TenantDomain, TenantEmail, and TenantSocialLink.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.branding import TenantBranding, TenantDomain, TenantEmail, TenantSocialLink
from ..models.security import TenantAuditLog
from ..models.analytics import TenantNotification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TenantBranding)
def branding_updated(sender, instance, created, **kwargs):
    """
    Handle branding updates.
    
    Signal triggered when tenant branding is updated.
    """
    if not created:
        logger.info(f"Branding updated for {instance.tenant.name}")
        
        # Log branding update
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantBranding',
            object_id=str(instance.id),
            object_repr=str(instance),
            description="Tenant branding updated",
            metadata={
                'primary_color': instance.primary_color,
                'secondary_color': instance.secondary_color,
                'font_family': instance.font_family,
                'app_name': instance.app_name,
            },
        )
        
        # Trigger signal
        from . import branding_updated
        branding_updated.send(sender=TenantBranding, branding=instance)


@receiver(pre_save, sender=TenantBranding)
def branding_pre_save(sender, instance, **kwargs):
    """
    Handle branding pre-save operations.
    
    Signal triggered before branding is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantBranding.objects.get(pk=instance.pk)
            
            # Track logo changes
            if old_instance.logo != instance.logo:
                instance._logo_changed = True
                instance._had_logo = bool(old_instance.logo)
                instance._has_logo = bool(instance.logo)
            
            # Track color changes
            color_fields = ['primary_color', 'secondary_color', 'accent_color', 'background_color', 'text_color']
            instance._colors_changed = False
            
            for field in color_fields:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)
                if old_value != new_value:
                    instance._colors_changed = True
                    break
                
        except TenantBranding.DoesNotExist:
            pass  # New branding, no changes to track


@receiver(post_save, sender=TenantBranding)
def branding_post_save(sender, instance, created, **kwargs):
    """
    Handle branding post-save operations.
    
    Signal triggered after branding is saved.
    """
    if not created:
        # Handle logo changes
        if hasattr(instance, '_logo_changed'):
            if instance._has_logo and not instance._had_logo:
                # Logo added
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantBranding',
                    object_id=str(instance.id),
                    description="Logo uploaded",
                    metadata={'logo_uploaded': True},
                )
            
            elif not instance._has_logo and instance._had_logo:
                # Logo removed
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantBranding',
                    object_id=str(instance.id),
                    description="Logo removed",
                    metadata={'logo_removed': True},
                )
        
        # Handle color changes
        if hasattr(instance, '_colors_changed') and instance._colors_changed:
            TenantAuditLog.log_action(
                tenant=instance.tenant,
                action='config_change',
                model_name='TenantBranding',
                object_id=str(instance.id),
                description="Color scheme updated",
                metadata={
                    'primary_color': instance.primary_color,
                    'secondary_color': instance.secondary_color,
                },
            )


@receiver(post_save, sender=TenantDomain)
def domain_verified(sender, instance, created, **kwargs):
    """
    Handle domain verification.
    
    Signal triggered when domain is verified.
    """
    if not created and hasattr(instance, '_dns_status_changed'):
        if instance.dns_status == 'verified' and instance._old_dns_status != 'verified':
            logger.info(f"Domain verified: {instance.domain} for {instance.tenant.name}")
            
            # Log domain verification
            TenantAuditLog.log_action(
                tenant=instance.tenant,
                action='config_change',
                model_name='TenantDomain',
                object_id=str(instance.id),
                object_repr=str(instance),
                description=f"Domain '{instance.domain}' verified",
                metadata={
                    'domain': instance.domain,
                    'dns_status': instance.dns_status,
                    'dns_verified_at': instance.dns_verified_at.isoformat(),
                },
            )
            
            # Trigger signal
            from . import domain_verified
            domain_verified.send(sender=TenantDomain, domain=instance)
            
            # Send notification
            TenantNotification.objects.create(
                tenant=instance.tenant,
                title='Domain Verified!',
                message=f'Your domain {instance.domain} has been successfully verified.',
                notification_type='system',
                priority='medium',
                send_email=True,
                send_push=True,
                action_url='/branding/domains',
                action_text='Manage Domains',
                metadata={'domain_id': str(instance.id)},
            )


@receiver(pre_save, sender=TenantDomain)
def domain_pre_save(sender, instance, **kwargs):
    """
    Handle domain pre-save operations.
    
    Signal triggered before domain is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantDomain.objects.get(pk=instance.pk)
            
            # Track DNS status changes
            if old_instance.dns_status != instance.dns_status:
                instance._dns_status_changed = True
                instance._old_dns_status = old_instance.dns_status
                instance._new_dns_status = instance.dns_status
            
            # Track SSL status changes
            if old_instance.ssl_status != instance.ssl_status:
                instance._ssl_status_changed = True
                instance._old_ssl_status = old_instance.ssl_status
                instance._new_ssl_status = old_instance.ssl_status
                
        except TenantDomain.DoesNotExist:
            pass  # New domain, no changes to track


@receiver(post_save, sender=TenantDomain)
def domain_updated(sender, instance, created, **kwargs):
    """
    Handle domain updates.
    
    Signal triggered when domain is updated.
    """
    if not created:
        # Handle SSL status changes
        if hasattr(instance, '_ssl_status_changed'):
            if instance._new_ssl_status == 'verified' and instance._old_ssl_status != 'verified':
                logger.info(f"SSL certificate verified: {instance.domain} for {instance.tenant.name}")
                
                # Log SSL verification
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantDomain',
                    object_id=str(instance.id),
                    description=f"SSL certificate verified for domain '{instance.domain}'",
                    metadata={
                        'domain': instance.domain,
                        'ssl_status': instance.ssl_status,
                        'ssl_expires_at': instance.ssl_expires_at.isoformat() if instance.ssl_expires_at else None,
                    },
                )
                
                # Trigger signal
                from . import ssl_certificate_updated
                ssl_certificate_updated.send(sender=TenantDomain, domain=instance)
                
                # Send notification
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='SSL Certificate Verified!',
                    message=f'SSL certificate for {instance.domain} has been successfully installed.',
                    notification_type='system',
                    priority='medium',
                    send_email=True,
                    send_push=True,
                    action_url='/branding/domains',
                    action_text='Manage Domains',
                    metadata={'domain_id': str(instance.id)},
                )
            
            elif instance._new_ssl_status == 'expired' and instance._old_ssl_status != 'expired':
                logger.warning(f"SSL certificate expired: {instance.domain} for {instance.tenant.name}")
                
                # Log SSL expiration
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantDomain',
                    object_id=str(instance.id),
                    description=f"SSL certificate expired for domain '{instance.domain}'",
                    metadata={
                        'domain': instance.domain,
                        'ssl_status': instance.ssl_status,
                        'ssl_expires_at': instance.ssl_expires_at.isoformat() if instance.ssl_expires_at else None,
                    },
                    severity='high',
                )
                
                # Send alert
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='SSL Certificate Expired',
                    message=f'SSL certificate for {instance.domain} has expired. Please renew it.',
                    notification_type='security',
                    priority='high',
                    send_email=True,
                    send_push=True,
                    action_url='/branding/domains',
                    action_text='Renew SSL',
                    metadata={'domain_id': str(instance.id)},
                )


@receiver(post_save, sender=TenantEmail)
def email_configuration_updated(sender, instance, created, **kwargs):
    """
    Handle email configuration updates.
    
    Signal triggered when email configuration is updated.
    """
    if not created:
        logger.info(f"Email configuration updated for {instance.tenant.name}")
        
        # Log email configuration update
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='config_change',
            model_name='TenantEmail',
            object_id=str(instance.id),
            description="Email configuration updated",
            metadata={
                'provider': instance.provider,
                'from_email': instance.from_email,
                'is_verified': instance.is_verified,
            },
        )
        
        # Trigger signal
        from . import email_configuration_updated
        email_configuration_updated.send(sender=TenantEmail, email_config=instance)


@receiver(pre_save, sender=TenantEmail)
def email_config_pre_save(sender, instance, **kwargs):
    """
    Handle email configuration pre-save operations.
    
    Signal triggered before email configuration is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantEmail.objects.get(pk=instance.pk)
            
            # Track verification status changes
            if old_instance.is_verified != instance.is_verified:
                instance._verification_changed = True
                instance._old_verified = old_instance.is_verified
                instance._new_verified = instance.is_verified
                
        except TenantEmail.DoesNotExist:
            pass  # New email config, no changes to track


@receiver(post_save, sender=TenantEmail)
def email_config_post_save(sender, instance, created, **kwargs):
    """
    Handle email configuration post-save operations.
    
    Signal triggered after email configuration is saved.
    """
    if not created:
        # Handle verification changes
        if hasattr(instance, '_verification_changed'):
            if instance._new_verified and not instance._old_verified:
                # Email verified
                TenantAuditLog.log_action(
                    tenant=instance.tenant,
                    action='config_change',
                    model_name='TenantEmail',
                    object_id=str(instance.id),
                    description="Email configuration verified",
                    metadata={
                        'provider': instance.provider,
                        'from_email': instance.from_email,
                    },
                )
                
                # Send notification
                TenantNotification.objects.create(
                    tenant=instance.tenant,
                    title='Email Configuration Verified',
                    message=f'Your email configuration has been verified and is ready to use.',
                    notification_type='system',
                    priority='low',
                    send_email=True,
                    send_push=True,
                    action_url='/branding/email',
                    action_text='Manage Email',
                    metadata={'email_config_id': str(instance.id)},
                )


@receiver(post_save, sender=TenantSocialLink)
def social_link_created(sender, instance, created, **kwargs):
    """
    Handle social link creation.
    
    Signal triggered when social link is created.
    """
    if created:
        logger.info(f"Social link created for {instance.tenant.name}: {instance.platform}")
        
        # Log social link creation
        TenantAuditLog.log_action(
            tenant=instance.tenant,
            action='create',
            model_name='TenantSocialLink',
            object_id=str(instance.id),
            object_repr=str(instance),
            description=f"Social link '{instance.platform}' created",
            metadata={
                'platform': instance.platform,
                'url': instance.url,
                'is_visible': instance.is_visible,
            },
        )


@receiver(pre_save, sender=TenantSocialLink)
def social_link_pre_save(sender, instance, **kwargs):
    """
    Handle social link pre-save operations.
    
    Signal triggered before social link is saved.
    """
    # Check if this is an update
    if instance.pk:
        try:
            old_instance = TenantSocialLink.objects.get(pk=instance.pk)
            
            # Track visibility changes
            if old_instance.is_visible != instance.is_visible:
                instance._visibility_changed = True
                instance._old_visible = old_instance.is_visible
                instance._new_visible = instance.is_visible
                
        except TenantSocialLink.DoesNotExist:
            pass  # New social link, no changes to track


@receiver(post_save, sender=TenantSocialLink)
def social_link_updated(sender, instance, created, **kwargs):
    """
    Handle social link updates.
    
    Signal triggered when social link is updated.
    """
    if not created:
        # Handle visibility changes
        if hasattr(instance, '_visibility_changed'):
            visibility_text = 'shown' if instance._new_visible else 'hidden'
            
            # Log visibility change
            TenantAuditLog.log_action(
                tenant=instance.tenant,
                action='config_change',
                model_name='TenantSocialLink',
                object_id=str(instance.id),
                description=f"Social link '{instance.platform}' {visibility_text}",
                changes={
                    'is_visible': {'old': instance._old_visible, 'new': instance._new_visible}
                },
            )


def track_domain_health_check(tenant, domain, health_score):
    """
    Track domain health check results.
    
    Args:
        tenant: Tenant instance
        domain: Domain instance
        health_score: Health score (0-100)
    """
    try:
        # Log health check
        TenantAuditLog.log_action(
            tenant=tenant,
            action='config_change',
            model_name='TenantDomain',
            object_id=str(domain.id),
            description=f"Domain health check: {health_score}/100",
            metadata={
                'domain': domain.domain,
                'health_score': health_score,
                'dns_status': domain.dns_status,
                'ssl_status': domain.ssl_status,
            },
            severity='medium' if health_score < 70 else 'low',
        )
        
        # Send alert if health is poor
        if health_score < 50:
            TenantNotification.objects.create(
                tenant=tenant,
                title='Domain Health Alert',
                message=f'Domain {domain.domain} health score is {health_score}/100. Please check configuration.',
                notification_type='system',
                priority='high',
                send_email=True,
                send_push=True,
                action_url='/branding/domains',
                action_text='Fix Issues',
                metadata={'domain_id': str(domain.id)},
            )
        
    except Exception as e:
        logger.error(f"Failed to track domain health for {tenant.name}: {str(e)}")


def log_ssl_renewal_attempt(tenant, domain, success, error=None):
    """
    Log SSL renewal attempt.
    
    Args:
        tenant: Tenant instance
        domain: Domain instance
        success: Whether renewal was successful
        error: Error message if failed
    """
    try:
        if success:
            TenantAuditLog.log_action(
                tenant=tenant,
                action='config_change',
                model_name='TenantDomain',
                object_id=str(domain.id),
                description=f"SSL certificate renewed for domain '{domain.domain}'",
                metadata={
                    'domain': domain.domain,
                    'renewal_success': True,
                },
            )
        else:
            TenantAuditLog.log_action(
                tenant=tenant,
                action='config_change',
                model_name='TenantDomain',
                object_id=str(domain.id),
                description=f"SSL certificate renewal failed for domain '{domain.domain}'",
                metadata={
                    'domain': domain.domain,
                    'renewal_success': False,
                    'error': error,
                },
                severity='high',
            )
    
    except Exception as e:
        logger.error(f"Failed to log SSL renewal for {tenant.name}: {str(e)}")
