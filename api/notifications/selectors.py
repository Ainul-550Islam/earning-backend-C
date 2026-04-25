# earning_backend/api/notifications/selectors.py
"""
Selectors — Read-only query functions (Clean Architecture / Django-styleguide pattern).

Selectors are the ONLY place that reads from the database.
They accept filter parameters and return querysets or values.
Views and services call selectors — never write raw ORM queries in views.

Pattern: selector_name(*, filter_params) → queryset | value

Reference: https://github.com/HackSoftware/Django-Styleguide
"""

import logging
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum, Avg, F
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Notification selectors
# ---------------------------------------------------------------------------

def notification_list(
    *,
    user=None,
    is_read: Optional[bool] = None,
    is_deleted: bool = False,
    is_archived: Optional[bool] = None,
    is_pinned: Optional[bool] = None,
    channel: str = '',
    priority: str = '',
    notification_type: str = '',
    status: str = '',
    campaign_id: str = '',
    search: str = '',
    date_from=None,
    date_to=None,
    order_by: str = '-created_at',
    admin_mode: bool = False,
):
    """Return a notification queryset filtered by the given parameters."""
    from api.notifications.models import Notification

    qs = Notification.objects.filter(is_deleted=is_deleted)

    if user and not admin_mode:
        qs = qs.filter(user=user)

    if is_read is not None:
        qs = qs.filter(is_read=is_read)

    if is_archived is not None:
        qs = qs.filter(is_archived=is_archived)

    if is_pinned is not None:
        qs = qs.filter(is_pinned=is_pinned)

    if channel:
        qs = qs.filter(channel=channel)

    if priority:
        qs = qs.filter(priority=priority)

    if notification_type:
        qs = qs.filter(notification_type=notification_type)

    if status:
        qs = qs.filter(status=status)

    if campaign_id:
        qs = qs.filter(campaign_id=campaign_id)

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(message__icontains=search))

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    return qs.order_by(order_by)


def notification_get(*, pk: int, user=None, allow_staff: bool = True):
    """Fetch a single Notification by pk."""
    from api.notifications.models import Notification
    qs = Notification.objects.filter(pk=pk, is_deleted=False)
    if user and not getattr(user, 'is_staff', False):
        qs = qs.filter(user=user)
    return qs.first()


def notification_unread_count(*, user) -> int:
    """Return unread notification count for a user."""
    from api.notifications.models import Notification
    from django.core.cache import cache
    cache_key = f'notif:count:{user.pk}'
    count = cache.get(cache_key)
    if count is None:
        count = Notification.objects.filter(
            user=user, is_read=False, is_deleted=False
        ).count()
        cache.set(cache_key, count, 60)
    return count


def notification_delivery_stats(*, user=None, days: int = 30) -> Dict:
    """Return delivery statistics for a user or the whole system."""
    from api.notifications.models import Notification
    cutoff = timezone.now() - timezone.timedelta(days=days)
    qs = Notification.objects.filter(created_at__gte=cutoff)
    if user:
        qs = qs.filter(user=user)
    return qs.aggregate(
        total=Count('id'),
        sent=Count('id', filter=Q(is_sent=True)),
        delivered=Count('id', filter=Q(is_delivered=True)),
        read=Count('id', filter=Q(is_read=True)),
        failed=Count('id', filter=Q(status='failed')),
        total_clicks=Sum('click_count'),
    )


# ---------------------------------------------------------------------------
# Template selectors
# ---------------------------------------------------------------------------

def template_list(
    *,
    is_active: bool = True,
    is_public: Optional[bool] = None,
    template_type: str = '',
    channel: str = '',
    category: str = '',
    search: str = '',
    order_by: str = 'name',
):
    """Return a NotificationTemplate queryset."""
    from api.notifications.models import NotificationTemplate
    qs = NotificationTemplate.objects.filter(is_active=is_active)
    if is_public is not None:
        qs = qs.filter(is_public=is_public)
    if template_type:
        qs = qs.filter(template_type=template_type)
    if channel:
        qs = qs.filter(channel=channel)
    if category:
        qs = qs.filter(category=category)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(title_en__icontains=search))
    return qs.order_by(order_by)


def template_get(*, pk: int = None, name: str = None, notification_type: str = None, channel: str = None):
    """Fetch a single NotificationTemplate."""
    from api.notifications.models import NotificationTemplate
    qs = NotificationTemplate.objects.filter(is_active=True)
    if pk:
        qs = qs.filter(pk=pk)
    if name:
        qs = qs.filter(name=name)
    if notification_type:
        qs = qs.filter(template_type=notification_type)
    if channel:
        qs = qs.filter(channel=channel)
    return qs.first()


# ---------------------------------------------------------------------------
# Device selectors
# ---------------------------------------------------------------------------

def device_list(*, user=None, is_active: bool = True, device_type: str = ''):
    """Return active DeviceToken queryset."""
    from api.notifications.models import DeviceToken
    qs = DeviceToken.objects.filter(is_active=is_active)
    if user:
        qs = qs.filter(user=user)
    if device_type:
        qs = qs.filter(device_type=device_type)
    return qs.order_by('-last_active')


def device_get_fcm_tokens(*, user_ids: List[int]) -> List[str]:
    """Return list of active FCM tokens for given user IDs."""
    from api.notifications.models import DeviceToken
    return list(
        DeviceToken.objects.filter(
            user_id__in=user_ids,
            is_active=True,
            push_enabled=True,
            device_type__in=['android', 'web'],
        ).exclude(fcm_token='').values_list('fcm_token', flat=True)
    )


def device_get_apns_tokens(*, user_ids: List[int]) -> List[str]:
    """Return list of active APNs tokens for given user IDs."""
    from api.notifications.models import DeviceToken
    return list(
        DeviceToken.objects.filter(
            user_id__in=user_ids,
            is_active=True,
            push_enabled=True,
            device_type='ios',
        ).exclude(apns_token='').values_list('apns_token', flat=True)
    )


# ---------------------------------------------------------------------------
# Campaign selectors
# ---------------------------------------------------------------------------

def campaign_list(*, status: str = '', search: str = '', order_by: str = '-created_at'):
    """Return NotificationCampaign queryset."""
    from api.notifications.models import NotificationCampaign
    qs = NotificationCampaign.objects.all()
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
    return qs.order_by(order_by)


def campaign_get(*, pk: int):
    """Fetch a single NotificationCampaign."""
    from api.notifications.models import NotificationCampaign
    return NotificationCampaign.objects.filter(pk=pk).first()


def campaign_due() -> list:
    """Return campaigns that are scheduled and due to be sent."""
    from api.notifications.models import NotificationCampaign
    return list(
        NotificationCampaign.objects.filter(
            status='scheduled',
            send_at__lte=timezone.now(),
        )
    )


# ---------------------------------------------------------------------------
# Analytics selectors
# ---------------------------------------------------------------------------

def insight_list(*, channel: str = '', date_from=None, date_to=None,
                  order_by: str = '-date'):
    """Return NotificationInsight queryset."""
    from api.notifications.models.analytics import NotificationInsight
    qs = NotificationInsight.objects.all()
    if channel:
        qs = qs.filter(channel=channel)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs.order_by(order_by)


def insight_totals(*, days: int = 30) -> Dict:
    """Return aggregated insight totals for the last N days."""
    from api.notifications.models.analytics import NotificationInsight
    cutoff = timezone.now().date() - timezone.timedelta(days=days)
    return NotificationInsight.objects.filter(date__gte=cutoff).aggregate(
        total_sent=Sum('sent'),
        total_delivered=Sum('delivered'),
        total_opened=Sum('opened'),
        total_clicked=Sum('clicked'),
        total_unsubscribed=Sum('unsubscribed'),
    )


def delivery_rate_list(*, channel: str = '', days: int = 30):
    """Return DeliveryRate records for the last N days."""
    from api.notifications.models.analytics import DeliveryRate
    cutoff = timezone.now().date() - timezone.timedelta(days=days)
    qs = DeliveryRate.objects.filter(date__gte=cutoff)
    if channel:
        qs = qs.filter(channel=channel)
    return qs.order_by('-date', 'channel')


# ---------------------------------------------------------------------------
# Fatigue / Opt-out selectors
# ---------------------------------------------------------------------------

def fatigue_get(*, user):
    """Get NotificationFatigue record for a user."""
    from api.notifications.models.analytics import NotificationFatigue
    record, _ = NotificationFatigue.objects.get_or_create(user=user)
    return record


def opt_out_list(*, user=None, channel: str = '', is_active: bool = True):
    """Return OptOutTracking queryset."""
    from api.notifications.models.analytics import OptOutTracking
    qs = OptOutTracking.objects.filter(is_active=is_active)
    if user:
        qs = qs.filter(user=user)
    if channel:
        qs = qs.filter(channel=channel)
    return qs.order_by('-opted_out_at')


def opted_out_user_ids(*, channel: str) -> List[int]:
    """Return list of user IDs who opted out of a channel."""
    from api.notifications.models.analytics import OptOutTracking
    return list(
        OptOutTracking.objects.filter(channel=channel, is_active=True)
        .values_list('user_id', flat=True)
    )


# ---------------------------------------------------------------------------
# User preference selectors
# ---------------------------------------------------------------------------

def preference_get(*, user):
    """Get or create NotificationPreference for a user."""
    from api.notifications.models import NotificationPreference
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    return pref


def preference_list():
    """Return all NotificationPreferences."""
    from api.notifications.models import NotificationPreference
    return NotificationPreference.objects.all().select_related('user')


# ---------------------------------------------------------------------------
# In-app message selectors
# ---------------------------------------------------------------------------

def in_app_message_list(*, user, include_dismissed: bool = False,
                         include_expired: bool = False):
    """Return active in-app messages for a user."""
    from api.notifications.models.channel import InAppMessage
    qs = InAppMessage.objects.filter(user=user)
    if not include_dismissed:
        qs = qs.filter(is_dismissed=False)
    if not include_expired:
        qs = qs.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
    return qs.order_by('display_priority', '-created_at')


def in_app_message_unread_count(*, user) -> int:
    """Count unread, non-dismissed, non-expired in-app messages."""
    from api.notifications.models.channel import InAppMessage
    return InAppMessage.objects.filter(
        user=user,
        is_read=False,
        is_dismissed=False,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).count()


# ---------------------------------------------------------------------------
# Push device selectors
# ---------------------------------------------------------------------------

def push_device_list(*, user=None, is_active: bool = True, device_type: str = ''):
    """Return PushDevice queryset."""
    from api.notifications.models.channel import PushDevice
    qs = PushDevice.objects.filter(is_active=is_active)
    if user:
        qs = qs.filter(user=user)
    if device_type:
        qs = qs.filter(device_type=device_type)
    return qs.order_by('-last_used')


# ---------------------------------------------------------------------------
# Schedule selectors
# ---------------------------------------------------------------------------

def schedule_list_due():
    """Return notification schedules that are due to be sent."""
    from api.notifications.models.schedule import NotificationSchedule
    return NotificationSchedule.objects.filter(
        status='pending',
        send_at__lte=timezone.now(),
    ).select_related('notification')


def schedule_list_overdue(tolerance_minutes: int = 30):
    """Return schedules that are overdue by more than tolerance_minutes."""
    from api.notifications.models.schedule import NotificationSchedule
    cutoff = timezone.now() - timezone.timedelta(minutes=tolerance_minutes)
    return NotificationSchedule.objects.filter(
        status='pending',
        send_at__lt=cutoff,
    ).select_related('notification')
