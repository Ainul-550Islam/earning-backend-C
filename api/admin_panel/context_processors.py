# api/admin_panel/context_processors.py
"""
Django context processors for admin_panel templates.
Injects admin data into every template context.
"""
from django.core.cache import cache
from django.utils import timezone


def admin_panel_context(request):
    """Add admin_panel data to all template contexts."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    # Maintenance status
    maintenance = bool(cache.get('admin_panel:maintenance_mode_active'))

    # Unread alerts count
    try:
        from api.alerts.models import AlertLog
        alert_count = AlertLog.objects.filter(status='active').count()
    except Exception:
        alert_count = 0

    # Pending withdrawals
    try:
        from api.payout_queue.models import PayoutItem
        pending_withdrawals = PayoutItem.objects.filter(status='QUEUED').count()
    except Exception:
        pending_withdrawals = 0

    # Pending KYC
    try:
        from api.kyc.models import KYC
        pending_kyc = KYC.objects.filter(status='QUEUED').count()
    except Exception:
        pending_kyc = 0

    # Admin role
    try:
        role = request.user.admin_profile.role
    except Exception:
        role = 'superadmin' if request.user.is_superuser else 'admin'

    return {
        'admin_maintenance_active': maintenance,
        'admin_alert_count': alert_count,
        'admin_pending_withdrawals': pending_withdrawals,
        'admin_pending_kyc': pending_kyc,
        'admin_role': role,
        'admin_panel_version': '1.0.0',
        'current_timestamp': timezone.now().isoformat(),
    }