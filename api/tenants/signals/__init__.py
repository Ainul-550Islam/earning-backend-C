"""
api/tenants/signals/__init__.py
All tenant signals — defined here to avoid circular imports.
"""
from django.dispatch import Signal

# ── Core signals ──────────────────────────────────
tenant_created = Signal()
tenant_updated = Signal()
tenant_deleted = Signal()
tenant_settings_updated = Signal()
tenant_billing_updated = Signal()
tenant_invoice_created = Signal()
tenant_invoice_updated = Signal()

# ── Plan signals ──────────────────────────────────
plan_created = Signal()
plan_updated = Signal()
plan_deleted = Signal()
plan_usage_recorded = Signal()
plan_quota_exceeded = Signal()

# ── User signals ──────────────────────────────────
tenant_user_added = Signal()
tenant_user_removed = Signal()
tenant_user_role_changed = Signal()

# ── Onboarding signals ────────────────────────────
onboarding_completed = Signal()
onboarding_step_completed = Signal()

# ── Branding signals ──────────────────────────────
ssl_certificate_updated = Signal()
domain_verified = Signal()

# ── Connect signal handlers ───────────────────────
try:
    from .core import *  # noqa
except (ImportError, Exception) as e:
    import logging
    logging.getLogger(__name__).warning(f"tenants.signals.core: {e}")

try:
    from .plan import *  # noqa
except (ImportError, Exception) as e:
    import logging
    logging.getLogger(__name__).warning(f"tenants.signals.plan: {e}")

try:
    from .onboarding import *  # noqa
except (ImportError, Exception) as e:
    import logging
    logging.getLogger(__name__).warning(f"tenants.signals.onboarding: {e}")

try:
    from .branding import *  # noqa
except (ImportError, Exception) as e:
    import logging
    logging.getLogger(__name__).warning(f"tenants.signals.branding: {e}")

__all__ = [
    'tenant_created', 'tenant_updated', 'tenant_deleted',
    'tenant_settings_updated', 'tenant_billing_updated',
    'tenant_invoice_created', 'tenant_invoice_updated',
    'plan_created', 'plan_updated', 'plan_deleted',
    'plan_usage_recorded', 'plan_quota_exceeded',
    'tenant_user_added', 'tenant_user_removed', 'tenant_user_role_changed',
    'onboarding_completed', 'onboarding_step_completed',
    'ssl_certificate_updated', 'domain_verified',
]
