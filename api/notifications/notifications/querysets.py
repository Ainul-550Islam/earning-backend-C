# earning_backend/api/notifications/querysets.py
"""
QuerySets — All custom QuerySet classes for the notification system.

Provides named, chainable query methods so view/service code never
writes raw .filter()/.exclude() chains.

Import pattern:
    from notifications.querysets import NotificationQS, CampaignQS
"""

from django.db import models
from django.db.models import Q, Count, Sum, Avg, F, Max, Min
from django.utils import timezone


# ---------------------------------------------------------------------------
# Notification QuerySet
# ---------------------------------------------------------------------------

class NotificationQS(models.QuerySet):
    """Full-featured queryset for the Notification model."""

    # ── Visibility ─────────────────────────────────────────────────

    def active(self):
        return self.filter(
            is_deleted=False,
        ).filter(Q(expire_date__isnull=True) | Q(expire_date__gt=timezone.now()))

    def unread(self):
        return self.filter(is_read=False, is_deleted=False)

    def read(self):
        return self.filter(is_read=True, is_deleted=False)

    def pinned(self):
        return self.filter(is_pinned=True, is_deleted=False)

    def archived(self):
        return self.filter(is_archived=True, is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def expired(self):
        return self.filter(expire_date__lt=timezone.now(), is_deleted=False)

    def not_expired(self):
        return self.filter(
            Q(expire_date__isnull=True) | Q(expire_date__gt=timezone.now())
        )

    # ── Delivery state ─────────────────────────────────────────────

    def sent(self):
        return self.filter(is_sent=True)

    def unsent(self):
        return self.filter(is_sent=False)

    def delivered(self):
        return self.filter(is_delivered=True)

    def failed(self):
        return self.filter(status='failed')

    def pending(self):
        return self.filter(status__in=('pending', 'draft'))

    def scheduled(self):
        return self.filter(status='scheduled')

    # ── Owner / scope ─────────────────────────────────────────────

    def for_user(self, user):
        return self.filter(user=user, is_deleted=False)

    def for_users(self, user_ids: list):
        return self.filter(user_id__in=user_ids)

    def for_campaign(self, campaign_id: str):
        return self.filter(campaign_id=campaign_id)

    # ── Channel / Type / Priority ─────────────────────────────────

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

    # ── Date range ────────────────────────────────────────────────

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def this_week(self):
        return self.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7))

    def this_month(self):
        return self.filter(created_at__gte=timezone.now() - timezone.timedelta(days=30))

    def date_range(self, start, end):
        return self.filter(created_at__date__range=(start, end))

    def older_than(self, days: int):
        return self.filter(created_at__lt=timezone.now() - timezone.timedelta(days=days))

    def recent(self, hours: int = 24):
        return self.filter(created_at__gte=timezone.now() - timezone.timedelta(hours=hours))

    # ── Search ────────────────────────────────────────────────────

    def search(self, query: str):
        return self.filter(Q(title__icontains=query) | Q(message__icontains=query))

    # ── Batch ops ─────────────────────────────────────────────────

    def mark_all_read(self):
        return self.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
            updated_at=timezone.now(),
        )

    def soft_delete_all(self):
        return self.update(
            is_deleted=True,
            deleted_at=timezone.now(),
            updated_at=timezone.now(),
        )

    # ── Stats ─────────────────────────────────────────────────────

    def delivery_stats(self) -> dict:
        return self.aggregate(
            total=Count('id'),
            sent=Count('id', filter=Q(is_sent=True)),
            delivered=Count('id', filter=Q(is_delivered=True)),
            read=Count('id', filter=Q(is_read=True)),
            failed=Count('id', filter=Q(status='failed')),
            total_clicks=Sum('click_count'),
            avg_clicks=Avg('click_count'),
        )

    def unread_count(self) -> int:
        return self.filter(is_read=False, is_deleted=False).count()


# ---------------------------------------------------------------------------
# DeviceToken QuerySet
# ---------------------------------------------------------------------------

class DeviceTokenQS(models.QuerySet):

    def active(self):
        return self.filter(is_active=True, push_enabled=True)

    def for_user(self, user):
        return self.filter(user=user, is_active=True)

    def android(self):
        return self.filter(device_type='android', is_active=True).exclude(fcm_token='')

    def ios(self):
        return self.filter(device_type='ios', is_active=True).exclude(apns_token='')

    def web(self):
        return self.filter(device_type='web', is_active=True)

    def stale(self, days: int = 30):
        return self.filter(
            is_active=True,
            last_active__lt=timezone.now() - timezone.timedelta(days=days),
        )

    def get_fcm_tokens(self, user_ids: list) -> list:
        return list(
            self.filter(
                user_id__in=user_ids,
                is_active=True,
                push_enabled=True,
                device_type__in=['android', 'web'],
            ).exclude(fcm_token='').values_list('fcm_token', flat=True)
        )

    def get_apns_tokens(self, user_ids: list) -> list:
        return list(
            self.filter(
                user_id__in=user_ids,
                is_active=True,
                push_enabled=True,
                device_type='ios',
            ).exclude(apns_token='').values_list('apns_token', flat=True)
        )


# ---------------------------------------------------------------------------
# NotificationTemplate QuerySet
# ---------------------------------------------------------------------------

class TemplateQS(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def public(self):
        return self.filter(is_public=True, is_active=True)

    def for_type(self, notification_type: str):
        return self.filter(template_type=notification_type)

    def for_channel(self, channel: str):
        return self.filter(channel=channel)

    def search(self, query: str):
        return self.filter(Q(name__icontains=query) | Q(description__icontains=query))

    def most_used(self, limit: int = 10):
        return self.order_by('-usage_count')[:limit]


# ---------------------------------------------------------------------------
# Campaign QuerySet
# ---------------------------------------------------------------------------

class CampaignQS(models.QuerySet):

    def active(self):
        return self.filter(status__in=('running', 'scheduled'))

    def draft(self):
        return self.filter(status='draft')

    def running(self):
        return self.filter(status='running')

    def completed(self):
        return self.filter(status='completed')

    def due(self):
        return self.filter(status='scheduled', send_at__lte=timezone.now())

    def recently_completed(self, days: int = 7):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(status='completed', completed_at__gte=cutoff)

    def with_progress(self):
        return self.annotate(
            progress_pct=F('sent_count') * 100.0 / (F('total_count') + 1)
        )


# ---------------------------------------------------------------------------
# NotificationSchedule QuerySet
# ---------------------------------------------------------------------------

class ScheduleQS(models.QuerySet):

    def pending(self):
        return self.filter(status='pending')

    def due(self):
        return self.filter(status='pending', send_at__lte=timezone.now())

    def overdue(self, tolerance_minutes: int = 30):
        cutoff = timezone.now() - timezone.timedelta(minutes=tolerance_minutes)
        return self.filter(status='pending', send_at__lt=cutoff)

    def sent(self):
        return self.filter(status='sent')

    def failed(self):
        return self.filter(status='failed')

    def for_notification(self, notification_id: int):
        return self.filter(notification_id=notification_id)


# ---------------------------------------------------------------------------
# NotificationInsight QuerySet
# ---------------------------------------------------------------------------

class InsightQS(models.QuerySet):

    def for_channel(self, channel: str):
        return self.filter(channel=channel)

    def date_range(self, start, end):
        return self.filter(date__range=(start, end))

    def last_n_days(self, n: int = 30):
        return self.filter(date__gte=timezone.now().date() - timezone.timedelta(days=n))

    def totals(self) -> dict:
        return self.aggregate(
            total_sent=Sum('sent'),
            total_delivered=Sum('delivered'),
            total_opened=Sum('opened'),
            total_clicked=Sum('clicked'),
            total_unsubscribed=Sum('unsubscribed'),
        )

    def avg_delivery_rate(self) -> float:
        result = self.aggregate(
            avg=Avg(F('delivered') * 100.0 / (F('sent') + 1))
        )
        return round(result.get('avg') or 0, 2)


# ---------------------------------------------------------------------------
# OptOutTracking QuerySet
# ---------------------------------------------------------------------------

class OptOutQS(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def for_user(self, user):
        return self.filter(user=user)

    def for_channel(self, channel: str):
        return self.filter(channel=channel, is_active=True)

    def opted_out_ids(self, channel: str) -> list:
        return list(self.for_channel(channel).values_list('user_id', flat=True))


# ---------------------------------------------------------------------------
# NotificationFatigue QuerySet
# ---------------------------------------------------------------------------

class FatigueQS(models.QuerySet):

    def fatigued(self):
        return self.filter(is_fatigued=True)

    def not_fatigued(self):
        return self.filter(is_fatigued=False)

    def for_user(self, user):
        return self.filter(user=user)

    def above_daily_limit(self, limit: int = 10):
        return self.filter(sent_today__gte=limit)

    def reset_daily(self):
        return self.update(
            sent_today=0,
            is_fatigued=False,
            daily_reset_at=timezone.now(),
            updated_at=timezone.now(),
        )

    def reset_weekly(self):
        return self.update(
            sent_this_week=0,
            weekly_reset_at=timezone.now(),
            updated_at=timezone.now(),
        )


# ---------------------------------------------------------------------------
# InAppMessage QuerySet
# ---------------------------------------------------------------------------

class InAppMessageQS(models.QuerySet):

    def active(self):
        return self.filter(
            is_dismissed=False,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

    def for_user(self, user):
        return self.filter(user=user)

    def unread(self):
        return self.filter(is_read=False, is_dismissed=False)

    def dismissed(self):
        return self.filter(is_dismissed=True)

    def expired(self):
        return self.filter(expires_at__lt=timezone.now())

    def by_priority(self):
        return self.order_by('display_priority', '-created_at')
