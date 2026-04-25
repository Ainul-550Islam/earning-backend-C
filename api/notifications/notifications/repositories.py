# earning_backend/api/notifications/repositories.py
"""
Repositories — Database write operations (Clean Architecture pattern).

Repositories are the ONLY place that writes to the database.
Selectors read. Repositories write. Use cases orchestrate both.

Each repository method:
  - Has a clear name: create_notification, update_notification_status, etc.
  - Returns the saved model instance or a result dict
  - Handles the DB transaction boundary
"""
import logging
from typing import Dict, List, Optional
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class NotificationRepository:
    """Write operations for the Notification model."""

    def create(self, *, user, title: str, message: str, notification_type: str = 'announcement',
               channel: str = 'in_app', priority: str = 'medium', **kwargs):
        from api.notifications.models import Notification
        return Notification.objects.create(
            user=user, title=title, message=message,
            notification_type=notification_type,
            channel=channel, priority=priority, **kwargs
        )

    def mark_read(self, *, pk: int, user) -> bool:
        from api.notifications.models import Notification
        count = Notification.objects.filter(pk=pk, user=user, is_read=False).update(
            is_read=True, read_at=timezone.now(), updated_at=timezone.now()
        )
        return count > 0

    def mark_all_read(self, *, user) -> int:
        from api.notifications.models import Notification
        return Notification.objects.filter(user=user, is_read=False, is_deleted=False).update(
            is_read=True, read_at=timezone.now(), updated_at=timezone.now()
        )

    def soft_delete(self, *, pk: int, user) -> bool:
        from api.notifications.models import Notification
        count = Notification.objects.filter(pk=pk, user=user, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now(), updated_at=timezone.now()
        )
        return count > 0

    def mark_sent(self, *, pk: int, sent_at=None) -> bool:
        from api.notifications.models import Notification
        count = Notification.objects.filter(pk=pk).update(
            is_sent=True, sent_at=sent_at or timezone.now(),
            status='sent', updated_at=timezone.now()
        )
        return count > 0

    def mark_delivered(self, *, pk: int) -> bool:
        from api.notifications.models import Notification
        count = Notification.objects.filter(pk=pk).update(
            is_delivered=True, delivered_at=timezone.now(),
            status='delivered', updated_at=timezone.now()
        )
        return count > 0

    def mark_failed(self, *, pk: int, error: str = '') -> bool:
        from api.notifications.models import Notification
        count = Notification.objects.filter(pk=pk).update(
            status='failed', failure_reason=error, updated_at=timezone.now()
        )
        return count > 0

    def increment_click(self, *, pk: int):
        from api.notifications.models import Notification
        from django.db.models import F
        Notification.objects.filter(pk=pk).update(
            click_count=F('click_count') + 1, updated_at=timezone.now()
        )

    def bulk_create(self, notifications: list) -> List:
        from api.notifications.models import Notification
        return Notification.objects.bulk_create(notifications, batch_size=500)

    def cleanup_expired(self, *, days: int = 90) -> int:
        from api.notifications.models import Notification
        cutoff = timezone.now() - timezone.timedelta(days=days)
        count, _ = Notification.objects.filter(
            is_deleted=True, deleted_at__lt=cutoff
        ).delete()
        return count


class DeviceRepository:
    """Write operations for DeviceToken."""

    def create_or_update(self, *, user, device_type: str, fcm_token: str = '',
                          apns_token: str = '', **kwargs):
        from api.notifications.models import DeviceToken
        device, created = DeviceToken.objects.update_or_create(
            user=user, device_type=device_type,
            defaults={
                'fcm_token': fcm_token, 'apns_token': apns_token,
                'is_active': True, 'last_active': timezone.now(), **kwargs
            }
        )
        return device, created

    def deactivate(self, *, pk: int) -> bool:
        from api.notifications.models import DeviceToken
        return DeviceToken.objects.filter(pk=pk).update(is_active=False, updated_at=timezone.now()) > 0

    def deactivate_tokens(self, *, tokens: list):
        from api.notifications.models import DeviceToken
        return DeviceToken.objects.filter(fcm_token__in=tokens).update(is_active=False)

    def update_last_active(self, *, user):
        from api.notifications.models import DeviceToken
        DeviceToken.objects.filter(user=user, is_active=True).update(last_active=timezone.now())


class CampaignRepository:
    """Write operations for NotificationCampaign."""

    def create(self, *, name: str, template_id: int, created_by, **kwargs):
        from api.notifications.models import NotificationCampaign
        return NotificationCampaign.objects.create(
            name=name, template_id=template_id, created_by=created_by,
            status='draft', **kwargs
        )

    def update_status(self, *, pk: int, status: str, **kwargs) -> bool:
        from api.notifications.models import NotificationCampaign
        return NotificationCampaign.objects.filter(pk=pk).update(
            status=status, updated_at=timezone.now(), **kwargs
        ) > 0

    def increment_sent(self, *, pk: int, count: int = 1):
        from api.notifications.models import NotificationCampaign
        from django.db.models import F
        NotificationCampaign.objects.filter(pk=pk).update(
            sent_count=F('sent_count') + count, updated_at=timezone.now()
        )

    def increment_failed(self, *, pk: int, count: int = 1):
        from api.notifications.models import NotificationCampaign
        from django.db.models import F
        NotificationCampaign.objects.filter(pk=pk).update(
            failed_count=F('failed_count') + count, updated_at=timezone.now()
        )


class OptOutRepository:
    """Write operations for OptOutTracking."""

    def opt_out(self, *, user, channel: str, reason: str = 'user_request', notes: str = ''):
        from api.notifications.models.analytics import OptOutTracking
        record, _ = OptOutTracking.objects.update_or_create(
            user=user, channel=channel,
            defaults={
                'is_active': True, 'reason': reason, 'notes': notes,
                'opted_out_at': timezone.now(), 'triggered_by': 'user',
            }
        )
        return record

    def resubscribe(self, *, user, channel: str) -> bool:
        from api.notifications.models.analytics import OptOutTracking
        return OptOutTracking.objects.filter(user=user, channel=channel).update(
            is_active=False, opted_in_at=timezone.now(), updated_at=timezone.now()
        ) > 0


class FatigueRepository:
    """Write operations for NotificationFatigue."""

    def get_or_create(self, *, user):
        from api.notifications.models.analytics import NotificationFatigue
        record, _ = NotificationFatigue.objects.get_or_create(user=user)
        return record

    def increment(self, *, user):
        from api.notifications.models.analytics import NotificationFatigue
        from django.db.models import F
        NotificationFatigue.objects.filter(user=user).update(
            sent_today=F('sent_today') + 1,
            sent_this_week=F('sent_this_week') + 1,
            sent_this_month=F('sent_this_month') + 1,
            updated_at=timezone.now(),
        )

    def reset_daily(self):
        from api.notifications.models.analytics import NotificationFatigue
        return NotificationFatigue.objects.all().update(
            sent_today=0, is_fatigued=False,
            daily_reset_at=timezone.now(), updated_at=timezone.now()
        )

    def reset_weekly(self):
        from api.notifications.models.analytics import NotificationFatigue
        return NotificationFatigue.objects.all().update(
            sent_this_week=0, weekly_reset_at=timezone.now(), updated_at=timezone.now()
        )


# Singletons
notification_repo = NotificationRepository()
device_repo = DeviceRepository()
campaign_repo = CampaignRepository()
opt_out_repo = OptOutRepository()
fatigue_repo = FatigueRepository()
