# api/support/admin_actions.py
"""
Custom Django admin bulk actions for support.
Register in admin.py: actions = [bulk_resolve_tickets, ...]
"""
import logging
from django.contrib import messages
from django.utils import timezone

logger = logging.getLogger(__name__)


def bulk_resolve_tickets(modeladmin, request, queryset):
    """Bulk-resolve selected tickets."""
    if not request.user.is_staff:
        modeladmin.message_user(request, 'Permission denied.', messages.ERROR)
        return
    open_qs = queryset.filter(status__in=['open', 'in_progress', 'waiting_user'])
    count   = open_qs.count()
    open_qs.update(
        status='resolved',
        resolved_at=timezone.now(),
        admin_response='Resolved by admin.',
    )
    modeladmin.message_user(request, f'Resolved {count} tickets.', messages.SUCCESS)
bulk_resolve_tickets.short_description = '✅ Bulk resolve selected tickets'


def bulk_close_tickets(modeladmin, request, queryset):
    """Bulk-close selected resolved tickets."""
    count = queryset.filter(status='resolved').update(status='closed')
    modeladmin.message_user(request, f'Closed {count} tickets.', messages.SUCCESS)
bulk_close_tickets.short_description = '🔒 Bulk close selected tickets'


def bulk_assign_to_me(modeladmin, request, queryset):
    """Assign selected tickets to the current admin user."""
    count = queryset.filter(assigned_to__isnull=True).update(assigned_to=request.user)
    modeladmin.message_user(request, f'Assigned {count} tickets to you.', messages.SUCCESS)
bulk_assign_to_me.short_description = '👤 Assign to me'


def mark_spam(modeladmin, request, queryset):
    """Mark selected tickets as spam."""
    count = queryset.update(status='spam')
    modeladmin.message_user(request, f'Marked {count} tickets as spam.', messages.WARNING)
mark_spam.short_description = '🚫 Mark as spam'


def bulk_escalate(modeladmin, request, queryset):
    """Bulk escalate selected tickets."""
    count = queryset.filter(escalated=False).update(
        escalated=True, escalated_at=timezone.now(), priority='urgent'
    )
    modeladmin.message_user(request, f'Escalated {count} tickets.', messages.WARNING)
bulk_escalate.short_description = '🔴 Bulk escalate selected tickets'