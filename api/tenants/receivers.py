"""
Tenant Receivers - Django Signal Receivers

This module contains Django signal receivers for tenant-related events
including user management, billing updates, and system integration.
"""

import logging
from datetime import datetime, timedelta
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db.models import Count, Sum, Avg

from .models_improved import Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
from .services_improved import tenant_service, tenant_security_service
from .tasks_improved import (
    send_welcome_email_task, send_trial_expiry_notification_task,
    update_tenant_usage_stats_task, cleanup_old_audit_logs_task
)

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save_receiver(sender, instance, created, **kwargs):
    """
    Handle user post-save operations.
    
    Updates tenant user counts and sends notifications for new users.
    """
    try:
        # Check if user belongs to a tenant
        if hasattr(instance, 'tenant') and instance.tenant:
            tenant = instance.tenant
            
            # Update user count cache
            update_tenant_user_count_cache(tenant)
            
            # Log user activity
            if created:
                tenant.audit_log(
                    action='user_added',
                    details={
                        'user_id': instance.id,
                        'user_email': instance.email,
                        'created_at': instance.created_at.isoformat(),
                    },
                    user=instance
                )
                
                # Send welcome email asynchronously
                send_welcome_email_task.delay(tenant.id, instance.id)
                
                logger.info(f"New user {instance.email} added to tenant {tenant.name}")
            else:
                # Log user update
                tenant.audit_log(
                    action='user_updated',
                    details={
                        'user_id': instance.id,
                        'user_email': instance.email,
                        'updated_at': instance.updated_at.isoformat(),
                    },
                    user=instance
                )
                
    except Exception as e:
        logger.error(f"Failed to handle user post-save: {e}")


@receiver(post_delete, sender=User)
def user_post_delete_receiver(sender, instance, **kwargs):
    """
    Handle user post-delete operations.
    
    Updates tenant user counts and logs user deletion.
    """
    try:
        # Check if user belonged to a tenant
        if hasattr(instance, 'tenant') and instance.tenant:
            tenant = instance.tenant
            
            # Update user count cache
            update_tenant_user_count_cache(tenant)
            
            # Log user deletion
            tenant.audit_log(
                action='user_removed',
                details={
                    'user_id': instance.id,
                    'user_email': instance.email,
                    'deleted_at': datetime.now().isoformat(),
                }
            )
            
            logger.info(f"User {instance.email} removed from tenant {tenant.name}")
            
    except Exception as e:
        logger.error(f"Failed to handle user post-delete: {e}")


@receiver(post_save, sender=Tenant)
def tenant_post_save_receiver(sender, instance, created, **kwargs):
    """
    Handle tenant post-save operations.
    
    Creates default related objects and updates caches.
    """
    try:
        if created:
            # Create default settings and billing if they don't exist
            tenant_service.create_tenant_defaults(instance)
            
            # Log tenant creation
            instance.audit_log(
                action='created',
                details={
                    'tenant_name': instance.name,
                    'tenant_slug': instance.slug,
                    'plan': instance.plan,
                    'created_at': instance.created_at.isoformat(),
                }
            )
            
            # Schedule trial expiry notification
            if instance.trial_ends_at:
                schedule_trial_expiry_notification(instance)
            
            logger.info(f"New tenant created: {instance.name}")
        else:
            # Update caches
            update_tenant_caches(instance)
            
            # Log tenant update
            instance.audit_log(
                action='updated',
                details={
                    'tenant_name': instance.name,
                    'updated_at': instance.updated_at.isoformat(),
                }
            )
            
    except Exception as e:
        logger.error(f"Failed to handle tenant post-save: {e}")


@receiver(pre_save, sender=Tenant)
def tenant_pre_save_receiver(sender, instance, **kwargs):
    """
    Handle tenant pre-save operations.
    
    Validates tenant data and tracks changes.
    """
    try:
        if instance.pk:
            # Store old values for change tracking
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_values = {
                'name': old_instance.name,
                'slug': old_instance.slug,
                'domain': old_instance.domain,
                'plan': old_instance.plan,
                'status': old_instance.status,
                'is_active': old_instance.is_active,
                'is_suspended': old_instance.is_suspended,
                'max_users': old_instance.max_users,
                'admin_email': old_instance.admin_email,
            }
        else:
            instance._old_values = {}
        
        # Validate tenant data
        validate_tenant_data(instance)
        
    except Exception as e:
        logger.error(f"Failed to handle tenant pre-save: {e}")


@receiver(post_save, sender=TenantSettings)
def tenant_settings_post_save_receiver(sender, instance, created, **kwargs):
    """
    Handle tenant settings post-save operations.
    
    Updates feature caches and logs changes.
    """
    try:
        tenant = instance.tenant
        
        # Update feature cache
        update_tenant_feature_cache(tenant)
        
        # Log settings change
        action = 'settings_created' if created else 'settings_updated'
        tenant.audit_log(
            action=action,
            details={
                'settings_id': instance.id,
                'updated_at': instance.updated_at.isoformat(),
            }
        )
        
        # Update usage stats asynchronously
        update_tenant_usage_stats_task.delay(tenant.id)
        
        logger.debug(f"Tenant settings updated for: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to handle tenant settings post-save: {e}")


@receiver(post_save, sender=TenantBilling)
def tenant_billing_post_save_receiver(sender, instance, created, **kwargs):
    """
    Handle tenant billing post-save operations.
    
    Updates billing caches and sends notifications.
    """
    try:
        tenant = instance.tenant
        
        # Update billing cache
        update_tenant_billing_cache(tenant)
        
        # Log billing change
        action = 'billing_created' if created else 'billing_updated'
        tenant.audit_log(
            action=action,
            details={
                'billing_id': instance.id,
                'status': instance.status,
                'updated_at': instance.updated_at.isoformat(),
            }
        )
        
        # Check for billing events
        handle_billing_events(instance, created)
        
        logger.debug(f"Tenant billing updated for: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to handle tenant billing post-save: {e}")


@receiver(post_save, sender=TenantInvoice)
def tenant_invoice_post_save_receiver(sender, instance, created, **kwargs):
    """
    Handle tenant invoice post-save operations.
    
    Sends invoice notifications and updates caches.
    """
    try:
        tenant = instance.tenant
        
        # Log invoice creation/update
        action = 'invoice_created' if created else 'invoice_updated'
        tenant.audit_log(
            action=action,
            details={
                'invoice_id': instance.id,
                'invoice_number': instance.invoice_number,
                'amount': float(instance.total_amount),
                'status': instance.status,
                'updated_at': instance.updated_at.isoformat(),
            }
        )
        
        # Handle invoice events
        handle_invoice_events(instance, created)
        
        logger.debug(f"Invoice processed for tenant: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to handle tenant invoice post-save: {e}")


@receiver(post_delete, sender=TenantInvoice)
def tenant_invoice_post_delete_receiver(sender, instance, **kwargs):
    """
    Handle tenant invoice post-delete operations.
    
    Logs invoice deletion and updates caches.
    """
    try:
        tenant = instance.tenant
        
        # Log invoice deletion
        tenant.audit_log(
            action='invoice_deleted',
            details={
                'invoice_id': instance.id,
                'invoice_number': instance.invoice_number,
                'amount': float(instance.total_amount),
                'deleted_at': datetime.now().isoformat(),
            }
        )
        
        logger.info(f"Invoice deleted for tenant: {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to handle tenant invoice post-delete: {e}")


# Utility functions for receivers
def update_tenant_user_count_cache(tenant):
    """Update tenant user count cache."""
    try:
        user_count = tenant.get_active_user_count()
        cache_key = f'tenant_user_count_{tenant.id}'
        cache.set(cache_key, user_count, timeout=300)  # 5 minutes
        
        logger.debug(f"Updated user count cache for tenant {tenant.name}: {user_count}")
        
    except Exception as e:
        logger.error(f"Failed to update user count cache: {e}")


def update_tenant_caches(tenant):
    """Update all tenant-related caches."""
    try:
        cache_keys = [
            f'tenant_{tenant.id}',
            f'tenant_{tenant.slug}',
        ]
        
        # Clear existing caches
        for key in cache_keys:
            cache.delete(key)
        
        # Update user count
        update_tenant_user_count_cache(tenant)
        
        # Update feature cache
        update_tenant_feature_cache(tenant)
        
        # Update billing cache
        update_tenant_billing_cache(tenant)
        
        logger.debug(f"Updated all caches for tenant {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update tenant caches: {e}")


def update_tenant_feature_cache(tenant):
    """Update tenant feature cache."""
    try:
        features = tenant.get_feature_flags()
        cache_key = f'tenant_features_{tenant.id}'
        cache.set(cache_key, features, timeout=600)  # 10 minutes
        
        logger.debug(f"Updated feature cache for tenant {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update feature cache: {e}")


def update_tenant_billing_cache(tenant):
    """Update tenant billing cache."""
    try:
        billing = tenant.get_billing()
        cache_key = f'tenant_billing_{tenant.id}'
        cache.set(cache_key, billing, timeout=300)  # 5 minutes
        
        logger.debug(f"Updated billing cache for tenant {tenant.name}")
        
    except Exception as e:
        logger.error(f"Failed to update billing cache: {e}")


def validate_tenant_data(tenant):
    """Validate tenant data before saving."""
    try:
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
        
    except Exception as e:
        logger.error(f"Tenant validation failed: {e}")
        raise


def schedule_trial_expiry_notification(tenant):
    """Schedule trial expiry notification."""
    try:
        if tenant.trial_ends_at:
            # Schedule notification for 3 days before expiry
            notification_date = tenant.trial_ends_at - timedelta(days=3)
            
            if notification_date > timezone.now():
                from .celery_beat_config import CELERY_BEAT_SCHEDULE
                from celery import current_app
                
                # This would be handled by Celery Beat in production
                logger.info(f"Scheduled trial expiry notification for tenant {tenant.name} on {notification_date}")
                
    except Exception as e:
        logger.error(f"Failed to schedule trial expiry notification: {e}")


def handle_billing_events(billing, created):
    """Handle billing-related events."""
    try:
        tenant = billing.tenant
        
        if created:
            # New billing created
            if billing.status == 'trial':
                # Trial started
                logger.info(f"Trial started for tenant {tenant.name}")
            elif billing.status == 'active':
                # Subscription activated
                logger.info(f"Subscription activated for tenant {tenant.name}")
        else:
            # Billing updated
            old_status = getattr(billing, '_old_status', None)
            if old_status and old_status != billing.status:
                # Status changed
                handle_billing_status_change(billing, old_status)
        
        # Check for subscription expiry
        if billing.subscription_ends_at:
            days_until_expiry = billing.days_until_expiry
            if days_until_expiry and days_until_expiry <= 7:
                # Schedule expiry notification
                send_trial_expiry_notification_task.delay(tenant.id)
                
    except Exception as e:
        logger.error(f"Failed to handle billing events: {e}")


def handle_billing_status_change(billing, old_status):
    """Handle billing status change."""
    try:
        tenant = billing.tenant
        new_status = billing.status
        
        # Log status change
        tenant.audit_log(
            action='billing_status_changed',
            details={
                'billing_id': billing.id,
                'old_status': old_status,
                'new_status': new_status,
                'changed_at': datetime.now().isoformat(),
            }
        )
        
        # Handle specific status changes
        if old_status == 'trial' and new_status == 'active':
            # Trial converted to paid
            logger.info(f"Trial converted to paid for tenant {tenant.name}")
        elif old_status == 'active' and new_status == 'cancelled':
            # Subscription cancelled
            logger.info(f"Subscription cancelled for tenant {tenant.name}")
        elif new_status == 'past_due':
            # Payment overdue
            logger.warning(f"Payment overdue for tenant {tenant.name}")
            
    except Exception as e:
        logger.error(f"Failed to handle billing status change: {e}")


def handle_invoice_events(invoice, created):
    """Handle invoice-related events."""
    try:
        tenant = invoice.tenant
        
        if created:
            # New invoice created
            logger.info(f"New invoice created for tenant {tenant.name}: {invoice.invoice_number}")
            
            # Send invoice notification (this would be handled by a task)
            # send_invoice_notification_task.delay(invoice.id)
        else:
            # Invoice updated
            old_status = getattr(invoice, '_old_status', None)
            if old_status and old_status != invoice.status:
                # Status changed
                handle_invoice_status_change(invoice, old_status)
        
        # Check for overdue invoices
        if invoice.status == 'overdue':
            logger.warning(f"Invoice overdue for tenant {tenant.name}: {invoice.invoice_number}")
            
    except Exception as e:
        logger.error(f"Failed to handle invoice events: {e}")


def handle_invoice_status_change(invoice, old_status):
    """Handle invoice status change."""
    try:
        tenant = invoice.tenant
        new_status = invoice.status
        
        # Log status change
        tenant.audit_log(
            action='invoice_status_changed',
            details={
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'old_status': old_status,
                'new_status': new_status,
                'changed_at': datetime.now().isoformat(),
            }
        )
        
        # Handle specific status changes
        if old_status != 'paid' and new_status == 'paid':
            # Invoice paid
            logger.info(f"Invoice paid for tenant {tenant.name}: {invoice.invoice_number}")
            
            # Update tenant billing
            billing = tenant.get_billing()
            if billing:
                billing.last_payment_at = timezone.now()
                billing.save()
                
        elif new_status == 'overdue':
            # Invoice overdue
            logger.warning(f"Invoice overdue for tenant {tenant.name}: {invoice.invoice_number}")
            
    except Exception as e:
        logger.error(f"Failed to handle invoice status change: {e}")


# System maintenance receivers
def schedule_maintenance_tasks():
    """Schedule periodic maintenance tasks."""
    try:
        from celery.schedules import crontab
        from django_celery_beat.models import PeriodicTask, CrontabSchedule
        
        # Schedule daily usage stats update
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='1',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        PeriodicTask.objects.get_or_create(
            name='update_tenant_usage_stats',
            crontab=schedule,
            task='tenants.tasks.update_tenant_usage_stats',
        )
        
        # Schedule weekly audit log cleanup
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='2',
            day_of_week='0',  # Sunday
            day_of_month='*',
            month_of_year='*',
        )
        
        PeriodicTask.objects.get_or_create(
            name='cleanup_old_audit_logs',
            crontab=schedule,
            task='tenants.tasks.cleanup_old_audit_logs',
        )
        
        logger.info("Maintenance tasks scheduled successfully")
        
    except Exception as e:
        logger.error(f"Failed to schedule maintenance tasks: {e}")


# Initialize receivers
def initialize_receivers():
    """Initialize all receivers."""
    try:
        # Schedule maintenance tasks
        schedule_maintenance_tasks()
        
        logger.info("Tenant receivers initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize receivers: {e}")


# Auto-initialize when module is imported
initialize_receivers()
