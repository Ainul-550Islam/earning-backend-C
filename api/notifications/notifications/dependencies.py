# earning_backend/api/notifications/dependencies.py
"""
Dependencies — FastAPI-style dependency injection for DRF viewsets.

Provides reusable dependency functions that viewsets can call to get
pre-validated, pre-fetched objects — eliminating boilerplate try/except
blocks in every action.

Usage in a ViewSet action:
    from .dependencies import get_notification_or_404, get_current_fatigue

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = get_notification_or_404(pk, user=request.user)
        notification.mark_as_read()
        return Response({'success': True})
"""

import logging
from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Core notification objects
# ---------------------------------------------------------------------------

def get_notification_or_404(pk, user=None, allow_staff_access: bool = True):
    """
    Fetch a Notification by pk.
    Raises NotFound if missing, PermissionDenied if user doesn't own it.
    """
    try:
        from notifications.models import Notification
        notif = Notification.objects.select_related('user').get(pk=pk, is_deleted=False)
    except Exception:
        raise NotFound(detail='Notification not found.')

    if user and notif.user != user:
        if not (allow_staff_access and getattr(user, 'is_staff', False)):
            raise PermissionDenied(detail='You do not own this notification.')

    return notif


def get_template_or_404(pk, require_active: bool = True):
    """Fetch a NotificationTemplate by pk."""
    try:
        from notifications.models import NotificationTemplate
        qs = NotificationTemplate.objects.filter(pk=pk, is_deleted=False)
        if require_active:
            qs = qs.filter(is_active=True)
        return qs.get()
    except Exception:
        raise NotFound(detail='Notification template not found.')


def get_campaign_or_404(pk, user=None, require_staff: bool = True):
    """Fetch a NotificationCampaign by pk."""
    try:
        from notifications.models import NotificationCampaign
        return NotificationCampaign.objects.get(pk=pk)
    except Exception:
        raise NotFound(detail='Campaign not found.')


def get_device_or_404(pk, user=None):
    """Fetch a DeviceToken by pk, ensuring ownership."""
    try:
        from notifications.models import DeviceToken
        device = DeviceToken.objects.get(pk=pk)
    except Exception:
        raise NotFound(detail='Device not found.')

    if user and device.user != user and not getattr(user, 'is_staff', False):
        raise PermissionDenied(detail='You do not own this device.')
    return device


def get_push_device_or_404(pk, user=None):
    """Fetch a PushDevice by pk, ensuring ownership."""
    try:
        from notifications.models.channel import PushDevice
        device = PushDevice.objects.get(pk=pk)
    except Exception:
        raise NotFound(detail='Push device not found.')

    if user and device.user != user and not getattr(user, 'is_staff', False):
        raise PermissionDenied(detail='You do not own this device.')
    return device


def get_in_app_message_or_404(pk, user=None):
    """Fetch an InAppMessage by pk, ensuring ownership."""
    try:
        from notifications.models.channel import InAppMessage
        msg = InAppMessage.objects.get(pk=pk, is_dismissed=False)
    except Exception:
        raise NotFound(detail='In-app message not found.')

    if user and msg.user != user and not getattr(user, 'is_staff', False):
        raise PermissionDenied(detail='You do not own this message.')
    return msg


def get_schedule_or_404(pk):
    """Fetch a NotificationSchedule by pk."""
    try:
        from notifications.models.schedule import NotificationSchedule
        return NotificationSchedule.objects.select_related('notification').get(pk=pk)
    except Exception:
        raise NotFound(detail='Schedule not found.')


def get_batch_or_404(pk):
    """Fetch a NotificationBatch by pk."""
    try:
        from notifications.models.schedule import NotificationBatch
        return NotificationBatch.objects.get(pk=pk)
    except Exception:
        raise NotFound(detail='Batch not found.')


def get_ab_test_or_404(pk):
    """Fetch a CampaignABTest by pk."""
    try:
        from notifications.models.campaign import CampaignABTest
        return CampaignABTest.objects.select_related('campaign').get(pk=pk)
    except Exception:
        raise NotFound(detail='A/B test not found.')


def get_rule_or_404(pk):
    """Fetch a NotificationRule by pk."""
    try:
        from notifications.models import NotificationRule
        return NotificationRule.objects.get(pk=pk)
    except Exception:
        raise NotFound(detail='Notification rule not found.')


# ---------------------------------------------------------------------------
# User state dependencies
# ---------------------------------------------------------------------------

def get_user_preference(user):
    """
    Get or create NotificationPreference for a user.
    Always returns an object — never raises.
    """
    from notifications.models import NotificationPreference
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    return pref


def get_current_fatigue(user):
    """
    Get or create NotificationFatigue record for a user.
    Returns the fatigue record.
    """
    try:
        from notifications.models.analytics import NotificationFatigue
        record, _ = NotificationFatigue.objects.get_or_create(user=user)
        return record
    except Exception:
        return None


def get_user_opt_outs(user) -> list:
    """Return list of channels the user has opted out of."""
    try:
        from notifications.services.OptOutService import opt_out_service
        return opt_out_service.get_opted_out_channels(user)
    except Exception:
        return []


def get_user_devices(user) -> list:
    """Return list of active push devices for a user."""
    try:
        from notifications.models import DeviceToken
        return list(DeviceToken.objects.filter(user=user, is_active=True))
    except Exception:
        return []


def get_notification_status(user) -> dict:
    """
    Full notification status summary for a user.
    Used by the user-facing dashboard endpoint.
    """
    try:
        from notifications.models import Notification
        from notifications.models.analytics import NotificationFatigue, OptOutTracking
        from notifications.models import DeviceToken

        unread = Notification.objects.filter(user=user, is_read=False, is_deleted=False).count()
        fatigue = NotificationFatigue.objects.filter(user=user).first()
        opted_out = list(
            OptOutTracking.objects.filter(user=user, is_active=True)
            .values_list('channel', flat=True)
        )
        active_devices = DeviceToken.objects.filter(user=user, is_active=True).count()

        return {
            'unread_count': unread,
            'is_fatigued': getattr(fatigue, 'is_fatigued', False),
            'sent_today': getattr(fatigue, 'sent_today', 0),
            'sent_this_week': getattr(fatigue, 'sent_this_week', 0),
            'opted_out_channels': opted_out,
            'active_devices': active_devices,
        }
    except Exception as exc:
        logger.warning(f'get_notification_status: {exc}')
        return {
            'unread_count': 0,
            'is_fatigued': False,
            'sent_today': 0,
            'sent_this_week': 0,
            'opted_out_channels': [],
            'active_devices': 0,
        }


# ---------------------------------------------------------------------------
# Service singletons (lazy-loaded)
# ---------------------------------------------------------------------------

def get_notification_service():
    """Return the notification service singleton."""
    from notifications.services.NotificationService import notification_service
    return notification_service


def get_campaign_service():
    """Return the campaign service singleton."""
    from notifications.services.CampaignService import campaign_service
    return campaign_service


def get_fatigue_service():
    """Return the fatigue service singleton."""
    from notifications.services.FatigueService import fatigue_service
    return fatigue_service


def get_opt_out_service():
    """Return the opt-out service singleton."""
    from notifications.services.OptOutService import opt_out_service
    return opt_out_service


def get_segment_service():
    """Return the segment service singleton."""
    from notifications.services.SegmentService import segment_service
    return segment_service


def get_ab_test_service():
    """Return the A/B test service singleton."""
    from notifications.services.ABTestService import ab_test_service
    return ab_test_service


def get_journey_service():
    """Return the journey service singleton."""
    from notifications.services.JourneyService import journey_service
    return journey_service


def get_smart_send_time_service():
    """Return the smart send time service singleton."""
    from notifications.services.SmartSendTimeService import smart_send_time_service
    return smart_send_time_service


# ---------------------------------------------------------------------------
# Pagination dependency
# ---------------------------------------------------------------------------

def get_pagination_class(size: str = 'default'):
    """Return the appropriate pagination class."""
    from notifications.pagination import (
        NotificationPagination, LargeNotificationPagination,
        InAppMessagePagination, AnalyticsPagination,
    )
    return {
        'default': NotificationPagination,
        'large': LargeNotificationPagination,
        'in_app': InAppMessagePagination,
        'analytics': AnalyticsPagination,
    }.get(size, NotificationPagination)


# ---------------------------------------------------------------------------
# Validation dependencies
# ---------------------------------------------------------------------------

def validate_notification_data(data: dict) -> dict:
    """
    Validate notification creation data.
    Raises DRF ValidationError with field-level errors.
    """
    errors = {}

    title = data.get('title', '')
    if not title:
        errors['title'] = 'Title is required.'
    elif len(title) > 255:
        errors['title'] = 'Title must be 255 characters or fewer.'

    message = data.get('message', '')
    if not message:
        errors['message'] = 'Message is required.'
    elif len(message) > 2000:
        errors['message'] = 'Message must be 2000 characters or fewer.'

    from notifications.choices import CHANNEL_CHOICES, PRIORITY_CHOICES
    valid_channels = [c[0] for c in CHANNEL_CHOICES]
    valid_priorities = [p[0] for p in PRIORITY_CHOICES]

    channel = data.get('channel', 'in_app')
    if channel not in valid_channels:
        errors['channel'] = f'Invalid channel. Choose from: {valid_channels}'

    priority = data.get('priority', 'medium')
    if priority not in valid_priorities:
        errors['priority'] = f'Invalid priority. Choose from: {valid_priorities}'

    if errors:
        raise ValidationError(errors)

    return data


def validate_bulk_user_ids(user_ids) -> list:
    """
    Validate a list of user IDs.
    Returns cleaned list of integers.
    """
    if not isinstance(user_ids, (list, tuple)):
        raise ValidationError({'user_ids': 'Must be a list.'})
    if len(user_ids) > 100_000:
        raise ValidationError({'user_ids': 'Cannot target more than 100,000 users at once.'})
    try:
        return [int(uid) for uid in user_ids]
    except (TypeError, ValueError):
        raise ValidationError({'user_ids': 'All user IDs must be integers.'})
