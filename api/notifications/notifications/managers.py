# earning_backend/api/notifications/managers.py
"""
Managers — Custom QuerySet and Manager classes for all Notification models.

Every model gets a tailored manager so views and services never write
raw ORM filter chains — they call named, tested methods instead.
"""

from django.db import models
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, F


# ---------------------------------------------------------------------------
# Notification QuerySet & Manager
# ---------------------------------------------------------------------------

class NotificationQuerySet(models.QuerySet):

    # ── Visibility filters ───────────────────────────────────────────

    def active(self):
        """Exclude soft-deleted and expired notifications."""
        return self.filter(
            is_deleted=False,
        ).filter(
            Q(expire_date__isnull=True) | Q(expire_date__gt=timezone.now())
        )

    def deleted(self):
        return self.filter(is_deleted=True)

    def expired(self):
        return self.filter(expire_date__lt=timezone.now(), is_deleted=False)

    # ── Read state ───────────────────────────────────────────────────

    def unread(self):
        return self.filter(is_read=False, is_deleted=False)

    def read(self):
        return self.filter(is_read=True)

    def mark_all_read(self):
        return self.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
            updated_at=timezone.now(),
        )

    # ── State filters ────────────────────────────────────────────────

    def pinned(self):
        return self.filter(is_pinned=True, is_deleted=False)

    def archived(self):
        return self.filter(is_archived=True, is_deleted=False)

    def sent(self):
        return self.filter(is_sent=True)

    def delivered(self):
        return self.filter(is_delivered=True)

    def failed(self):
        return self.filter(status='failed')

    def pending(self):
        return self.filter(status__in=('pending', 'draft'))

    # ── Channel / Type ───────────────────────────────────────────────

    def for_channel(self, channel: str):
        return self.filter(channel=channel)

    def for_type(self, notification_type: str):
        return self.filter(notification_type=notification_type)

    def for_priority(self, priority: str):
        return self.filter(priority=priority)

    def high_priority(self):
        return self.filter(priority__in=('high', 'urgent', 'critical'))

    def critical(self):
        return self.filter(priority='critical')

    # ── User / Ownership ─────────────────────────────────────────────

    def for_user(self, user):
        return self.filter(user=user, is_deleted=False)

    def for_users(self, user_ids: list):
        return self.filter(user_id__in=user_ids)

    # ── Date range ───────────────────────────────────────────────────

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def this_week(self):
        cutoff = timezone.now() - timezone.timedelta(days=7)
        return self.filter(created_at__gte=cutoff)

    def date_range(self, start, end):
        return self.filter(created_at__date__range=(start, end))

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)

    # ── Search ───────────────────────────────────────────────────────

    def search(self, query: str):
        return self.filter(
            Q(title__icontains=query) | Q(message__icontains=query)
        )

    # ── Campaign ─────────────────────────────────────────────────────

    def for_campaign(self, campaign_id: str):
        return self.filter(campaign_id=campaign_id)

    # ── Aggregation helpers ──────────────────────────────────────────

    def unread_count(self) -> int:
        return self.filter(is_read=False, is_deleted=False).count()

    def delivery_stats(self) -> dict:
        return self.aggregate(
            total=Count('id'),
            sent=Count('id', filter=Q(is_sent=True)),
            delivered=Count('id', filter=Q(is_delivered=True)),
            read=Count('id', filter=Q(is_read=True)),
            failed=Count('id', filter=Q(status='failed')),
            clicks=Sum('click_count'),
        )

    # ── Cleanup ──────────────────────────────────────────────────────

    def older_than(self, days: int):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__lt=cutoff)

    def cleanup_expired(self):
        """Hard-delete expired + soft-deleted records older than 30 days."""
        cutoff = timezone.now() - timezone.timedelta(days=30)
        return self.filter(
            Q(is_deleted=True, deleted_at__lt=cutoff) |
            Q(expire_date__lt=cutoff)
        ).delete()


class NotificationManager(models.Manager):
    def get_queryset(self):
        return NotificationQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def unread(self):
        return self.get_queryset().unread()

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def high_priority(self):
        return self.get_queryset().high_priority()

    def search(self, query: str):
        return self.get_queryset().search(query)

    def create_for_user(self, user, **kwargs):
        """Shortcut: create a notification for a user with defaults."""
        kwargs.setdefault('channel', 'in_app')
        kwargs.setdefault('priority', 'medium')
        return self.create(user=user, **kwargs)


# ---------------------------------------------------------------------------
# SoftDelete Manager  (used by any model with is_deleted)
# ---------------------------------------------------------------------------

class SoftDeleteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def delete(self):
        """Soft-delete all records in the queryset."""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(is_deleted=False, deleted_at=None)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return SoftDeleteQuerySet(self.model, using=self._db).deleted()


# ---------------------------------------------------------------------------
# NotificationTemplate Manager
# ---------------------------------------------------------------------------

class NotificationTemplateQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True, is_deleted=False)

    def public(self):
        return self.filter(is_public=True, is_active=True)

    def for_type(self, notification_type: str):
        return self.filter(template_type=notification_type)

    def for_channel(self, channel: str):
        return self.filter(channel=channel)

    def for_category(self, category: str):
        return self.filter(category=category)

    def search(self, query: str):
        return self.filter(
            Q(name__icontains=query) |
            Q(title_en__icontains=query) |
            Q(description__icontains=query)
        )

    def most_used(self, limit: int = 10):
        return self.order_by('-usage_count')[:limit]

    def increment_usage(self, pk: int):
        self.filter(pk=pk).update(usage_count=F('usage_count') + 1)


class NotificationTemplateManager(models.Manager):
    def get_queryset(self):
        return NotificationTemplateQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def public(self):
        return self.get_queryset().public()

    def get_for_type(self, notification_type: str, channel: str = 'in_app'):
        return self.get_queryset().active().filter(
            template_type=notification_type,
            channel=channel,
        ).first()


# ---------------------------------------------------------------------------
# DeviceToken Manager
# ---------------------------------------------------------------------------

class DeviceTokenQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True, push_enabled=True)

    def for_user(self, user):
        return self.filter(user=user, is_active=True)

    def for_platform(self, platform: str):
        return self.filter(platform=platform, is_active=True)

    def android(self):
        return self.filter(device_type='android', is_active=True).exclude(fcm_token='')

    def ios(self):
        return self.filter(device_type='ios', is_active=True).exclude(apns_token='')

    def web(self):
        return self.filter(device_type='web', is_active=True)

    def fcm_tokens_for_users(self, user_ids: list) -> list:
        return list(
            self.filter(
                user_id__in=user_ids,
                is_active=True,
                push_enabled=True,
                device_type__in=['android', 'web'],
            ).exclude(fcm_token='').values_list('fcm_token', flat=True)
        )

    def stale(self, days: int = 30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(is_active=True, last_active__lt=cutoff)

    def high_failure_rate(self, threshold: float = 0.8):
        return self.filter(
            is_active=True,
            push_sent__gt=5,
        ).annotate(
            failure_rate=F('push_failed') * 1.0 / F('push_sent')
        ).filter(failure_rate__gte=threshold)

    def deactivate_invalid(self, tokens: list):
        return self.filter(fcm_token__in=tokens).update(
            is_active=False,
            updated_at=timezone.now(),
        )


class DeviceTokenManager(models.Manager):
    def get_queryset(self):
        return DeviceTokenQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def get_fcm_tokens(self, user_ids: list) -> list:
        return self.get_queryset().fcm_tokens_for_users(user_ids)


# ---------------------------------------------------------------------------
# NotificationCampaign Manager
# ---------------------------------------------------------------------------

class CampaignQuerySet(models.QuerySet):

    def active(self):
        return self.filter(status__in=('running', 'scheduled'))

    def draft(self):
        return self.filter(status='draft')

    def running(self):
        return self.filter(status='running')

    def scheduled(self):
        return self.filter(status='scheduled')

    def completed(self):
        return self.filter(status='completed')

    def due(self):
        """Campaigns that are scheduled and their send_at has passed."""
        return self.filter(
            status='scheduled',
            send_at__lte=timezone.now(),
        )

    def for_template(self, template_id: int):
        return self.filter(template_id=template_id)

    def with_stats(self):
        return self.annotate(
            success_rate=F('sent_count') * 100.0 / (F('total_count') + 1),
        )


class CampaignManager(models.Manager):
    def get_queryset(self):
        return CampaignQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def due(self):
        return self.get_queryset().due()


# ---------------------------------------------------------------------------
# NotificationLog Manager
# ---------------------------------------------------------------------------

class NotificationLogQuerySet(models.QuerySet):

    def for_notification(self, notification_id: int):
        return self.filter(notification_id=notification_id)

    def for_user(self, user):
        return self.filter(notification__user=user)

    def errors(self):
        return self.filter(log_level__in=('error', 'critical'))

    def for_type(self, log_type: str):
        return self.filter(log_type=log_type)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)

    def date_range(self, start, end):
        return self.filter(created_at__date__range=(start, end))


class NotificationLogManager(models.Manager):
    def get_queryset(self):
        return NotificationLogQuerySet(self.model, using=self._db)

    def log(self, notification, log_type: str, message: str,
            log_level: str = 'info', source: str = 'system'):
        return self.create(
            notification=notification,
            log_type=log_type,
            message=message,
            log_level=log_level,
            source=source,
        )

    def log_sent(self, notification, source: str = 'system'):
        return self.log(notification, 'sent', f'Notification sent via {notification.channel}', source=source)

    def log_failed(self, notification, error: str, source: str = 'system'):
        return self.log(notification, 'failed', error, log_level='error', source=source)

    def log_click(self, notification):
        return self.log(notification, 'click', 'Notification clicked', source='frontend')


# ---------------------------------------------------------------------------
# InAppMessage Manager
# ---------------------------------------------------------------------------

class InAppMessageQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(user=user, is_dismissed=False)

    def unread(self):
        return self.filter(is_read=False, is_dismissed=False)

    def not_expired(self):
        return self.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

    def active_for_user(self, user):
        return self.for_user(user).not_expired()

    def by_priority(self):
        return self.order_by('display_priority', '-created_at')


class InAppMessageManager(models.Manager):
    def get_queryset(self):
        return InAppMessageQuerySet(self.model, using=self._db)

    def active_for_user(self, user):
        return self.get_queryset().active_for_user(user).by_priority()

    def unread_count(self, user) -> int:
        return self.get_queryset().for_user(user).not_expired().filter(is_read=False).count()


# ---------------------------------------------------------------------------
# NotificationInsight Manager
# ---------------------------------------------------------------------------

class InsightQuerySet(models.QuerySet):

    def for_channel(self, channel: str):
        return self.filter(channel=channel)

    def date_range(self, start, end):
        return self.filter(date__range=(start, end))

    def last_n_days(self, n: int = 30):
        cutoff = timezone.now().date() - timezone.timedelta(days=n)
        return self.filter(date__gte=cutoff)

    def totals(self) -> dict:
        return self.aggregate(
            total_sent=Sum('sent'),
            total_delivered=Sum('delivered'),
            total_opened=Sum('opened'),
            total_clicked=Sum('clicked'),
            total_unsubscribed=Sum('unsubscribed'),
        )

    def avg_rates(self) -> dict:
        return self.aggregate(
            avg_delivery_rate=Avg(
                F('delivered') * 100.0 / (F('sent') + 1)
            ),
            avg_open_rate=Avg(
                F('opened') * 100.0 / (F('delivered') + 1)
            ),
        )


class InsightManager(models.Manager):
    def get_queryset(self):
        return InsightQuerySet(self.model, using=self._db)

    def for_channel(self, channel: str):
        return self.get_queryset().for_channel(channel)

    def last_n_days(self, n: int = 30):
        return self.get_queryset().last_n_days(n)


# ---------------------------------------------------------------------------
# OptOutTracking Manager
# ---------------------------------------------------------------------------

class OptOutQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def for_user(self, user):
        return self.filter(user=user)

    def for_channel(self, channel: str):
        return self.filter(channel=channel, is_active=True)

    def opted_out_user_ids(self, channel: str) -> list:
        return list(
            self.filter(channel=channel, is_active=True)
            .values_list('user_id', flat=True)
        )


class OptOutManager(models.Manager):
    def get_queryset(self):
        return OptOutQuerySet(self.model, using=self._db)

    def is_opted_out(self, user, channel: str) -> bool:
        return self.get_queryset().for_user(user).for_channel(channel).exists()

    def opted_out_ids(self, channel: str) -> list:
        return self.get_queryset().opted_out_user_ids(channel)
