"""
Tenant Signals Module

This module contains all Django signal handlers for the tenant management system,
including signals for models, user actions, and system events.
"""

from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import Signal
from django.contrib.auth import get_user_model

from .core import (
    tenant_created, tenant_updated, tenant_deleted,
    tenant_settings_updated, tenant_billing_updated,
    tenant_invoice_created, tenant_invoice_updated,
)

from .plan import (
    plan_created, plan_updated, plan_deleted,
    plan_usage_recorded, plan_quota_exceeded,
)

from .security import (
    api_key_created, api_key_used, api_key_revoked,
    webhook_triggered, audit_log_created,
    security_event_detected,
)

from .onboarding import (
    onboarding_started, onboarding_step_completed,
    onboarding_completed, trial_extension_requested,
)

from .analytics import (
    metric_recorded, health_score_updated,
    feature_flag_toggled, notification_created,
)

from .branding import (
    branding_updated, domain_verified, ssl_certificate_updated,
    email_configuration_updated,
)

from .reseller import (
    reseller_created, commission_calculated,
)

# Custom signals
tenant_suspended = Signal()
tenant_unsuspended = Signal()
trial_extended = Signal()
quota_warning = Signal()
payment_processed = Signal()
webhook_delivered = Signal()
backup_completed = Signal()

__all__ = [
    # Core signals
    'tenant_created', 'tenant_updated', 'tenant_deleted',
    'tenant_settings_updated', 'tenant_billing_updated',
    'tenant_invoice_created', 'tenant_invoice_updated',
    'tenant_suspended', 'tenant_unsuspended', 'trial_extended',
    
    # Plan signals
    'plan_created', 'plan_updated', 'plan_deleted',
    'plan_usage_recorded', 'plan_quota_exceeded',
    
    # Security signals
    'api_key_created', 'api_key_used', 'api_key_revoked',
    'webhook_triggered', 'webhook_delivered', 'audit_log_created',
    'security_event_detected',
    
    # Onboarding signals
    'onboarding_started', 'onboarding_step_completed',
    'onboarding_completed', 'trial_extension_requested',
    
    # Analytics signals
    'metric_recorded', 'health_score_updated',
    'feature_flag_toggled', 'notification_created',
    
    # Branding signals
    'branding_updated', 'domain_verified', 'ssl_certificate_updated',
    'email_configuration_updated',
    
    # Reseller signals
    'reseller_created', 'commission_calculated',
    
    # System signals
    'quota_warning', 'payment_processed', 'backup_completed',
]
