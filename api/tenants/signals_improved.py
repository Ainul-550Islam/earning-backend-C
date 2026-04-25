"""
Tenant Signals - Improved Version with Enhanced Security and Features

This module contains comprehensive signal handlers for tenant management
with advanced security, proper event handling, and extensive functionality.
"""

import logging
from datetime import datetime, timedelta
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from .models_improved import (
    Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
)
from .services_improved import tenant_service, tenant_security_service

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=Tenant)
def tenant_post_save(sender, instance, created, **kwargs):
    """
    Handle tenant post-save operations.
    
    This signal handler creates default related objects for new tenants
    and logs changes for existing tenants.
    """
    if created:
        # Create default related objects
        create_tenant_defaults(instance)
        
        # Send welcome notification
        send_tenant_welcome_notification(instance)
        
        # Initialize tenant cache
        initialize_tenant_cache(instance)
        
        logger.info(f"New tenant created: {instance.name} ({instance.slug})")
    else:
        # Log changes and update cache
        log_tenant_changes(instance)
        update_tenant_cache(instance)
        
        logger.debug(f"Tenant updated: {instance.name} ({instance.slug})")


@receiver(pre_save, sender=Tenant)
def tenant_pre_save(sender, instance, **kwargs):
    """
    Handle tenant pre-save operations.
    
    This signal handler validates tenant data and prepares
    it for saving.
    """
    if instance.pk:
        # Store old values for change tracking
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_values = {
                'name': old_instance.name,
                'slug': old_instance.slug,
                'domain': old_instance.domain,
                'plan': old_instance.plan,
                'status': old_instance.status,
                'is_active': old_instance.is_active,
                'is_deleted': old_instance.is_deleted,
                'is_suspended': old_instance.is_suspended,
                'max_users': old_instance.max_users,
                'admin_email': old_instance.admin_email,
            }
        except sender.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}
    
    # Validate tenant data
    validate_tenant_data(instance)


@receiver(post_delete, sender=Tenant)
def tenant_post_delete(sender, instance, **kwargs):
    """
    Handle tenant post-delete operations.
    
    This signal handler cleans up tenant-related data and
    logs the deletion.
    """
    # Clear tenant cache
    clear_tenant_cache(instance)
    
    # Log deletion
    log_tenant_deletion(instance)
    
    # Send deletion notification
    send_tenant_deletion_notification(instance)
    
    logger.info(f"Tenant deleted: {instance.name} ({instance.slug})")


@receiver(post_save, sender=TenantSettings)
def tenant_settings_post_save(sender, instance, created, **kwargs):
    """
    Handle tenant settings post-save operations.
    
    This signal handler updates tenant cache and logs
    settings changes.
    """
    if created:
        logger.info(f"Tenant settings created for: {instance.tenant.name}")
    else:
        # Log settings changes
        log_tenant_settings_changes(instance)
        
        # Update tenant cache
        update_tenant_settings_cache(instance)
        
        logger.debug(f"Tenant settings updated for: {instance.tenant.name}")


@receiver(post_save, sender=TenantBilling)
def tenant_billing_post_save(sender, instance, created, **kwargs):
    """
    Handle tenant billing post-save operations.
    
    This signal handler updates billing cache and sends
    billing notifications.
    """
    if created:
        logger.info(f"Tenant billing created for: {instance.tenant.name}")
    else:
        # Log billing changes
        log_tenant_billing_changes(instance)
        
        # Update billing cache
        update_tenant_billing_cache(instance)
        
        # Send billing notifications
        send_tenant_billing_notifications(instance)
        
        logger.debug(f"Tenant billing updated for: {instance.tenant.name}")


@receiver(post_save, sender=TenantInvoice)
def tenant_invoice_post_save(sender, instance, created, **kwargs):
    """
    Handle tenant invoice post-save operations.
    
    This signal handler sends invoice notifications and
    updates invoice cache.
    """
    if created:
        # Send invoice notification
        send_invoice_notification(instance)
        
        logger.info(f"New invoice created for tenant: {instance.tenant.name}")
    else:
        # Update invoice cache
        update_invoice_cache(instance)
        
        logger.debug(f"Invoice updated for tenant: {instance.tenant.name}")


@receiver(pre_delete, sender=TenantInvoice)
def tenant_invoice_pre_delete(sender, instance, **kwargs):
    """
    Handle tenant invoice pre-delete operations.
    
    This signal handler logs invoice deletion.
    """
    # Log invoice deletion
    log_invoice_deletion(instance)
    
    logger.info(f"Invoice deleted for tenant: {instance.tenant.name}")


# Signal handler functions
def create_tenant_defaults(tenant):
    """
    Create default related objects for a new tenant.
    
    Args:
        tenant: Tenant instance
    """
    try:
        with transaction.atomic():
            # Create tenant settings
            settings, settings_created = TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults=get_default_tenant_settings()
            )
            
            # Create tenant billing
            billing, billing_created = TenantBilling.objects.get_or_create(
                tenant=tenant,
                defaults=get_default_tenant_billing(tenant)
            )
            
            # Log creation
            tenant.audit_log(
                action='defaults_created',
                details={
                    'settings_created': settings_created,
                    'billing_created': billing_created,
                    'trial_ends_at': billing.trial_ends_at.isoformat() if billing.trial_ends_at else None,
                }
            )
            
            logger.info(f"Default objects created for tenant: {tenant.name}")
            
    except Exception as e:
        logger.error(f"Failed to create defaults for tenant {tenant.name}: {e}")
        raise


def get_default_tenant_settings():
    """
    Get default tenant settings.
    
    Returns:
        Dictionary containing default settings
    """
    from .apps_improved import get_tenant_system_config
    
    system_config = get_tenant_system_config()
    return system_config.get('TENANT_DEFAULT_SETTINGS', {})


def get_default_tenant_billing(tenant):
    """
    Get default tenant billing configuration.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        Dictionary containing default billing settings
    """
    trial_days = getattr(settings, 'DEFAULT_TRIAL_DAYS', 14)
    
    return {
        'status': 'trial',
        'trial_ends_at': timezone.now() + timedelta(days=trial_days),
        'currency': tenant.currency_code or 'USD',
    }


def validate_tenant_data(tenant):
    """
    Validate tenant data before saving.
    
    Args:
        tenant: Tenant instance
    """
    # Validate slug uniqueness
    if tenant.slug:
        existing = Tenant.objects.filter(slug=tenant.slug)
        if tenant.pk:
            existing = existing.exclude(pk=tenant.pk)
        
        if existing.exists():
            raise ValueError(f"Tenant slug '{tenant.slug}' already exists")
    
    # Validate domain uniqueness
    if tenant.domain:
        existing = Tenant.objects.filter(domain=tenant.domain)
        if tenant.pk:
            existing = existing.exclude(pk=tenant.pk)
        
        if existing.exists():
            raise ValueError(f"Domain '{tenant.domain}' already exists")
    
    # Validate parent tenant (prevent circular references)
    if tenant.parent_tenant:
        if tenant.parent_tenant == tenant:
            raise ValueError("Tenant cannot be its own parent")
        
        # Check for circular reference
        parent = tenant.parent_tenant
        while parent:
            if parent == tenant:
                raise ValueError("Circular parent reference detected")
            parent = parent.parent_tenant


def log_tenant_changes(tenant):
    """
    Log tenant changes for audit purposes.
    
    Args:
        tenant: Tenant instance
    """
    if hasattr(tenant, '_old_values'):
        changes = {}
        for field, old_value in tenant._old_values.items():
            new_value = getattr(tenant, field, None)
            if old_value != new_value:
                changes[field] = {'old': old_value, 'new': new_value}
        
        if changes:
            tenant.audit_log(
                action='updated',
                details={'changes': changes}
            )


def log_tenant_deletion(tenant):
    """
    Log tenant deletion for audit purposes.
    
    Args:
        tenant: Tenant instance
    """
    tenant.audit_log(
        action='deleted',
        details={
            'name': tenant.name,
            'slug': tenant.slug,
            'plan': tenant.plan,
            'user_count': tenant.get_total_user_count(),
            'deleted_at': timezone.now().isoformat(),
        }
    )


def log_tenant_settings_changes(settings):
    """
    Log tenant settings changes for audit purposes.
    
    Args:
        settings: TenantSettings instance
    """
    # Get changed fields
    changes = {}
    for field in settings._meta.fields:
        field_name = field.name
        if field_name not in ['id', 'tenant', 'created_at', 'updated_at']:
            old_value = getattr(settings, f'_{field_name}', None)
            new_value = getattr(settings, field_name, None)
            if old_value != new_value:
                changes[field_name] = {'old': old_value, 'new': new_value}
    
    if changes:
        settings.tenant.audit_log(
            action='settings_updated',
            details={'changes': changes}
        )


def log_tenant_billing_changes(billing):
    """
    Log tenant billing changes for audit purposes.
    
    Args:
        billing: TenantBilling instance
    """
    # Get changed fields
    changes = {}
    for field in billing._meta.fields:
        field_name = field.name
        if field_name not in ['id', 'tenant', 'created_at', 'updated_at']:
            old_value = getattr(billing, f'_{field_name}', None)
            new_value = getattr(billing, field_name, None)
            if old_value != new_value:
                changes[field_name] = {'old': old_value, 'new': new_value}
    
    if changes:
        billing.tenant.audit_log(
            action='billing_updated',
            details={'changes': changes}
        )


def log_invoice_deletion(invoice):
    """
    Log invoice deletion for audit purposes.
    
    Args:
        invoice: TenantInvoice instance
    """
    invoice.tenant.audit_log(
        action='invoice_deleted',
        details={
            'invoice_number': invoice.invoice_number,
            'amount': float(invoice.total_amount),
            'status': invoice.status,
            'deleted_at': timezone.now().isoformat(),
        }
    )


def send_tenant_welcome_notification(tenant):
    """
    Send welcome notification to tenant owner.
    
    Args:
        tenant: Tenant instance
    """
    try:
        subject = _('Welcome to Your New Tenant!')
        
        context = {
            'tenant': tenant,
            'owner': tenant.owner,
            'trial_ends_at': tenant.trial_ends_at,
            'login_url': getattr(settings, 'TENANT_LOGIN_URL', '/login'),
            'admin_url': getattr(settings, 'TENANT_ADMIN_URL', '/admin'),
        }
        
        html_message = render_to_string('tenants/welcome_notification.html', context)
        text_message = render_to_string('tenants/welcome_notification.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[tenant.admin_email],
            html_message=html_message,
            fail_silently=True
        )
        
        logger.info(f"Welcome notification sent to: {tenant.admin_email}")
        
    except Exception as e:
        logger.error(f"Failed to send welcome notification to {tenant.admin_email}: {e}")


def send_tenant_deletion_notification(tenant):
    """
    Send deletion notification to tenant owner.
    
    Args:
        tenant: Tenant instance
    """
    try:
        subject = _('Your Tenant Has Been Deleted')
        
        context = {
            'tenant': tenant,
            'owner': tenant.owner,
            'deleted_at': timezone.now(),
            'contact_email': getattr(settings, 'SUPPORT_EMAIL', 'support@example.com'),
        }
        
        html_message = render_to_string('tenants/deletion_notification.html', context)
        text_message = render_to_string('tenants/deletion_notification.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[tenant.admin_email],
            html_message=html_message,
            fail_silently=True
        )
        
        logger.info(f"Deletion notification sent to: {tenant.admin_email}")
        
    except Exception as e:
        logger.error(f"Failed to send deletion notification to {tenant.admin_email}: {e}")


def send_tenant_billing_notifications(billing):
    """
    Send billing notifications based on billing status.
    
    Args:
        billing: TenantBilling instance
    """
    try:
        # Check if notification should be sent
        if billing.status == 'past_due':
            send_past_due_notification(billing)
        elif billing.status == 'cancelled':
            send_cancellation_notification(billing)
        elif billing.status == 'active' and billing.subscription_ends_at:
            # Check if subscription is expiring soon
            days_until_expiry = billing.days_until_expiry
            if days_until_expiry and days_until_expiry <= 7:
                send_expiry_notification(billing)
        
    except Exception as e:
        logger.error(f"Failed to send billing notification for {billing.tenant.name}: {e}")


def send_past_due_notification(billing):
    """
    Send past due notification.
    
    Args:
        billing: TenantBilling instance
    """
    subject = _('Your Payment is Past Due')
    
    context = {
        'tenant': billing.tenant,
        'billing': billing,
        'next_payment': billing.next_payment_at,
        'payment_url': getattr(settings, 'TENANT_PAYMENT_URL', '/billing'),
    }
    
    send_billing_email(billing.tenant, subject, 'past_due_notification', context)


def send_cancellation_notification(billing):
    """
    Send cancellation notification.
    
    Args:
        billing: TenantBilling instance
    """
    subject = _('Your Subscription Has Been Cancelled')
    
    context = {
        'tenant': billing.tenant,
        'billing': billing,
        'cancelled_at': billing.cancelled_at,
        'reactivate_url': getattr(settings, 'TENANT_REACTIVATE_URL', '/billing/reactivate'),
    }
    
    send_billing_email(billing.tenant, subject, 'cancellation_notification', context)


def send_expiry_notification(billing):
    """
    Send subscription expiry notification.
    
    Args:
        billing: TenantBilling instance
    """
    days_until_expiry = billing.days_until_expiry
    subject = _('Your Subscription Expires Soon')
    
    context = {
        'tenant': billing.tenant,
        'billing': billing,
        'days_until_expiry': days_until_expiry,
        'renewal_url': getattr(settings, 'TENANT_RENEWAL_URL', '/billing/renew'),
    }
    
    send_billing_email(billing.tenant, subject, 'expiry_notification', context)


def send_invoice_notification(invoice):
    """
    Send invoice notification.
    
    Args:
        invoice: TenantInvoice instance
    """
    subject = _('New Invoice Generated')
    
    context = {
        'tenant': invoice.tenant,
        'invoice': invoice,
        'payment_url': getattr(settings, 'TENANT_PAYMENT_URL', '/billing/pay'),
    }
    
    send_billing_email(invoice.tenant, subject, 'invoice_notification', context)


def send_billing_email(tenant, subject, template_name, context):
    """
    Send billing email to tenant.
    
    Args:
        tenant: Tenant instance
        subject: Email subject
        template_name: Template name
        context: Email context
    """
    try:
        html_message = render_to_string(f'tenants/{template_name}.html', context)
        text_message = render_to_string(f'tenants/{template_name}.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[tenant.admin_email],
            html_message=html_message,
            fail_silently=True
        )
        
        logger.info(f"Billing email sent to: {tenant.admin_email}")
        
    except Exception as e:
        logger.error(f"Failed to send billing email to {tenant.admin_email}: {e}")


# Cache management functions
def initialize_tenant_cache(tenant):
    """
    Initialize cache for a new tenant.
    
    Args:
        tenant: Tenant instance
    """
    try:
        # Cache tenant object
        cache.set(f'tenant_{tenant.slug}', tenant, timeout=300)
        cache.set(f'tenant_{tenant.id}', tenant, timeout=300)
        
        # Cache tenant settings
        settings = tenant.get_settings()
        cache.set(f'tenant_settings_{tenant.id}', settings, timeout=600)
        
        # Cache tenant billing
        billing = tenant.get_billing()
        cache.set(f'tenant_billing_{tenant.id}', billing, timeout=300)
        
        # Cache tenant features
        features = tenant.get_feature_flags()
        cache.set(f'tenant_features_{tenant.id}', features, timeout=300)
        
        logger.debug(f"Cache initialized for tenant: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to initialize cache for tenant {tenant.name}: {e}")


def update_tenant_cache(tenant):
    """
    Update cache for an existing tenant.
    
    Args:
        tenant: Tenant instance
    """
    try:
        # Update tenant cache
        cache.set(f'tenant_{tenant.slug}', tenant, timeout=300)
        cache.set(f'tenant_{tenant.id}', tenant, timeout=300)
        
        # Clear related caches
        cache.delete(f'tenant_settings_{tenant.id}')
        cache.delete(f'tenant_billing_{tenant.id}')
        cache.delete(f'tenant_features_{tenant.id}')
        
        logger.debug(f"Cache updated for tenant: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update cache for tenant {tenant.name}: {e}")


def update_tenant_settings_cache(settings):
    """
    Update tenant settings cache.
    
    Args:
        settings: TenantSettings instance
    """
    try:
        cache.set(f'tenant_settings_{settings.tenant.id}', settings, timeout=600)
        cache.delete(f'tenant_features_{settings.tenant.id}')  # Features may have changed
        
        logger.debug(f"Settings cache updated for tenant: {settings.tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update settings cache for tenant {settings.tenant.name}: {e}")


def update_tenant_billing_cache(billing):
    """
    Update tenant billing cache.
    
    Args:
        billing: TenantBilling instance
    """
    try:
        cache.set(f'tenant_billing_{billing.tenant.id}', billing, timeout=300)
        
        logger.debug(f"Billing cache updated for tenant: {billing.tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update billing cache for tenant {billing.tenant.name}: {e}")


def update_invoice_cache(invoice):
    """
    Update invoice cache.
    
    Args:
        invoice: TenantInvoice instance
    """
    try:
        cache.set(f'invoice_{invoice.id}', invoice, timeout=300)
        
        logger.debug(f"Invoice cache updated: {invoice.invoice_number}")
        
    except Exception as e:
        logger.error(f"Failed to update invoice cache for {invoice.invoice_number}: {e}")


def clear_tenant_cache(tenant):
    """
    Clear all cache entries for a tenant.
    
    Args:
        tenant: Tenant instance
    """
    try:
        cache_keys = [
            f'tenant_{tenant.slug}',
            f'tenant_{tenant.id}',
            f'tenant_settings_{tenant.id}',
            f'tenant_billing_{tenant.id}',
            f'tenant_features_{tenant.id}',
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        logger.debug(f"Cache cleared for tenant: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to clear cache for tenant {tenant.name}: {e}")


# User-related signal handlers
@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Handle user post-save operations related to tenants.
    
    This signal handler updates tenant user counts and
    sends user notifications.
    """
    if created:
        # Check if user belongs to a tenant
        if hasattr(instance, 'tenant') and instance.tenant:
            update_tenant_user_count(instance.tenant)
            send_user_welcome_notification(instance)
    else:
        # Check if tenant association changed
        if hasattr(instance, 'tenant') and instance.tenant:
            update_tenant_user_count(instance.tenant)


@receiver(post_delete, sender=User)
def user_post_delete(sender, instance, **kwargs):
    """
    Handle user post-delete operations related to tenants.
    
    This signal handler updates tenant user counts.
    """
    if hasattr(instance, 'tenant') and instance.tenant:
        update_tenant_user_count(instance.tenant)


def update_tenant_user_count(tenant):
    """
    Update tenant user count cache.
    
    Args:
        tenant: Tenant instance
    """
    try:
        user_count = tenant.get_active_user_count()
        cache.set(f'tenant_user_count_{tenant.id}', user_count, timeout=300)
        
        logger.debug(f"User count updated for tenant: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update user count for tenant {tenant.name}: {e}")


def send_user_welcome_notification(user):
    """
    Send welcome notification to new user.
    
    Args:
        user: User instance
    """
    try:
        subject = _('Welcome to the Platform!')
        
        context = {
            'user': user,
            'tenant': user.tenant,
            'login_url': getattr(settings, 'TENANT_LOGIN_URL', '/login'),
        }
        
        html_message = render_to_string('tenants/user_welcome.html', context)
        text_message = render_to_string('tenants/user_welcome.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True
        )
        
        logger.info(f"Welcome notification sent to user: {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send welcome notification to user {user.email}: {e}")


# Export signal handlers
__all__ = [
    'tenant_post_save',
    'tenant_pre_save',
    'tenant_post_delete',
    'tenant_settings_post_save',
    'tenant_billing_post_save',
    'tenant_invoice_post_save',
    'tenant_invoice_pre_delete',
    'user_post_save',
    'user_post_delete',
]
