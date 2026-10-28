# api/admin_panel/querysets.py
"""
Custom QuerySets for admin_panel models.
All complex DB queries live here — keeps models and views clean.
"Do not summarize or skip any logic. Provide the full code."
"""
from __future__ import annotations
from django.db import models
from django.db.models import (
    Q, Count, Sum, Avg, Max, Min, F, Value, Case, When,
    OuterRef, Subquery, Prefetch, ExpressionWrapper, FloatField,
    DecimalField, IntegerField, BooleanField, CharField,
    DurationField, DateTimeField,
)
from django.db.models.functions import (
    TruncDate, TruncHour, TruncMinute, TruncMonth, TruncWeek,
    Coalesce, Now, ExtractHour, ExtractDay, ExtractMonth,
    Greatest, Least, Abs,
)
from django.utils import timezone
from datetime import timedelta


# ==================== AdminActivity QuerySet ====================

class AdminActivityQuerySet(models.QuerySet):
    """QuerySet for AdminActivity model."""

    def by_actor(self, actor):
        return self.filter(actor=actor)

    def by_action(self, action: str):
        return self.filter(action=action)

    def by_model(self, model_name: str):
        return self.filter(model_name=model_name)

    def recent(self, days: int = 7):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def last_hour(self):
        return self.filter(created_at__gte=timezone.now() - timedelta(hours=1))

    def failed(self):
        return self.filter(status='failed')

    def successful(self):
        return self.filter(status='success')

    def by_ip(self, ip: str):
        return self.filter(ip=ip)

    def actions_summary(self, days: int = 7):
        """Group by action, return counts."""
        return (
            self.recent(days)
            .values('action')
            .annotate(
                count=Count('id'),
                failed=Count('id', filter=Q(status='failed')),
                last_seen=Max('created_at'),
            )
            .order_by('-count')
        )

    def actors_summary(self, days: int = 7):
        """Group by actor, return activity counts."""
        return (
            self.recent(days)
            .values('actor__username', 'actor__id')
            .annotate(
                action_count=Count('id'),
                failed_count=Count('id', filter=Q(status='failed')),
                last_action=Max('created_at'),
            )
            .order_by('-action_count')
        )

    def hourly_breakdown(self, days: int = 1):
        """Hourly activity breakdown."""
        cutoff = timezone.now() - timedelta(days=days)
        return (
            self.filter(created_at__gte=cutoff)
            .annotate(hour=TruncHour('created_at'))
            .values('hour')
            .annotate(total=Count('id'), failed=Count('id', filter=Q(status='failed')))
            .order_by('hour')
        )

    def with_actor(self):
        return self.select_related('actor')

    def risky_ips(self, threshold: int = 5, hours: int = 1):
        """IPs with many failed actions."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return (
            self.filter(created_at__gte=cutoff, status='failed')
            .exclude(ip='')
            .values('ip')
            .annotate(fail_count=Count('id'))
            .filter(fail_count__gte=threshold)
            .order_by('-fail_count')
        )


# ==================== SystemConfig QuerySet ====================

class SystemConfigQuerySet(models.QuerySet):
    """QuerySet for SystemConfig model."""

    def by_group(self, group: str):
        return self.filter(group=group)

    def public(self):
        return self.filter(is_public=True)

    def private(self):
        return self.filter(is_public=False)

    def writable(self):
        return self.filter(is_readonly=False)

    def readonly(self):
        return self.filter(is_readonly=True)

    def encrypted(self):
        return self.filter(is_encrypted=True)

    def by_type(self, value_type: str):
        return self.filter(value_type=value_type)

    def search(self, q: str):
        return self.filter(Q(key__icontains=q) | Q(label__icontains=q) | Q(description__icontains=q))

    def groups_summary(self):
        """Count configs per group."""
        return (
            self.values('group')
            .annotate(
                total=Count('id'),
                public=Count('id', filter=Q(is_public=True)),
                encrypted=Count('id', filter=Q(is_encrypted=True)),
            )
            .order_by('group')
        )

    def recently_updated(self, days: int = 7):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(updated_at__gte=cutoff).order_by('-updated_at')


# ==================== FeatureFlag QuerySet ====================

class FeatureFlagQuerySet(models.QuerySet):
    """QuerySet for FeatureFlag model."""

    def enabled(self):
        return self.filter(is_enabled=True)

    def disabled(self):
        return self.filter(is_enabled=False)

    def full_rollout(self):
        return self.filter(is_enabled=True, rollout_pct=100)

    def partial_rollout(self):
        return self.filter(is_enabled=True, rollout_pct__gt=0, rollout_pct__lt=100)

    def by_key(self, flag_key: str):
        return self.filter(flag_key=flag_key).first()

    def search(self, q: str):
        return self.filter(Q(flag_key__icontains=q) | Q(label__icontains=q))

    def rollout_summary(self):
        """Summary: enabled, disabled, partial rollout counts."""
        return {
            'total': self.count(),
            'enabled': self.enabled().count(),
            'disabled': self.disabled().count(),
            'full_rollout': self.full_rollout().count(),
            'partial_rollout': self.partial_rollout().count(),
        }

    def recently_changed(self, days: int = 7):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(updated_at__gte=cutoff).order_by('-updated_at')


# ==================== AdminSession QuerySet ====================

class AdminSessionQuerySet(models.QuerySet):
    """QuerySet for AdminSession model."""

    def active(self):
        return self.filter(is_active=True, status='active')

    def for_user(self, user):
        return self.filter(user=user)

    def by_ip(self, ip: str):
        return self.filter(ip=ip)

    def expired(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(last_seen__lt=cutoff, is_active=True)

    def force_logged_out(self):
        return self.filter(status='force_logout')

    def concurrent_sessions(self, user):
        """Return concurrent active sessions for a user (multi-device)."""
        return self.filter(user=user, is_active=True).count()

    def session_stats(self):
        """Session statistics."""
        return {
            'total_active': self.active().count(),
            'total': self.count(),
            'by_status': list(
                self.values('status').annotate(count=Count('id')).order_by('-count')
            ),
            'unique_users': self.active().values('user').distinct().count(),
        }

    def with_users(self):
        return self.select_related('user', 'force_logout_by')


# ==================== DashboardMetric QuerySet ====================

class DashboardMetricQuerySet(models.QuerySet):
    """QuerySet for DashboardMetric model."""

    def for_period(self, period: str):
        return self.filter(period=period)

    def realtime(self):
        return self.filter(period='realtime')

    def daily(self):
        return self.filter(period='daily')

    def stale(self, minutes: int = 5):
        cutoff = timezone.now() - timedelta(minutes=minutes)
        return self.filter(cached_at__lt=cutoff)

    def fresh(self, minutes: int = 5):
        cutoff = timezone.now() - timedelta(minutes=minutes)
        return self.filter(cached_at__gte=cutoff)

    def with_trend(self):
        """Annotate with trend direction (up/down/neutral)."""
        return self.annotate(
            trend=Case(
                When(previous_value__isnull=True, then=Value('neutral')),
                When(value__gt=F('previous_value'), then=Value('up')),
                When(value__lt=F('previous_value'), then=Value('down')),
                default=Value('neutral'),
                output_field=CharField(),
            )
        )

    def change_pct(self):
        """Annotate with percentage change from previous value."""
        return self.annotate(
            change_percentage=Case(
                When(
                    previous_value__isnull=False,
                    previous_value__gt=0,
                    then=ExpressionWrapper(
                        (F('value') - F('previous_value')) / F('previous_value') * 100,
                        output_field=FloatField(),
                    )
                ),
                default=Value(None),
                output_field=FloatField(),
            )
        )


# ==================== AdminInsight QuerySet ====================

class AdminInsightQuerySet(models.QuerySet):
    """QuerySet for AdminInsight model."""

    def unread(self):
        return self.filter(is_read=False, is_dismissed=False)

    def active(self):
        return self.filter(is_dismissed=False).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

    def expired(self):
        return self.filter(expires_at__lt=timezone.now())

    def by_priority(self, priority: str):
        return self.filter(priority=priority)

    def critical(self):
        return self.filter(priority='critical', is_dismissed=False)

    def high_priority(self):
        return self.filter(priority__in=['critical', 'high'], is_dismissed=False)

    def by_type(self, insight_type: str):
        return self.filter(type=insight_type)

    def unread_count(self) -> int:
        return self.unread().count()

    def mark_all_read(self) -> int:
        return self.unread().update(is_read=True)

    def dismiss_expired(self) -> int:
        return self.expired().update(is_dismissed=True)


# ==================== ReportDefinition QuerySet ====================

class ReportDefinitionQuerySet(models.QuerySet):
    """QuerySet for ReportDefinition model."""

    def active(self):
        return self.filter(is_active=True)

    def system_reports(self):
        return self.filter(is_system=True, is_active=True)

    def user_reports(self):
        return self.filter(is_system=False, is_active=True)

    def by_type(self, report_type: str):
        return self.filter(report_type=report_type)

    def with_schedules(self):
        return self.prefetch_related('schedules')

    def with_exports(self):
        return self.prefetch_related('exports')

    def popular(self, limit: int = 10):
        """Most-scheduled reports."""
        return (
            self.active()
            .annotate(schedule_count=Count('schedules'))
            .order_by('-schedule_count')[:limit]
        )


# ==================== DataExport QuerySet ====================

class DataExportQuerySet(models.QuerySet):
    """QuerySet for DataExport model."""

    def queued(self):
        return self.filter(status='queued')

    def processing(self):
        return self.filter(status='PROCESSING')

    def ready(self):
        return self.filter(status='ready')

    def failed(self):
        return self.filter(status='failed')

    def expired(self):
        return self.filter(expires_at__lt=timezone.now())

    def for_user(self, user):
        return self.filter(requested_by=user)

    def by_model(self, model_name: str):
        return self.filter(model_name=model_name)

    def cleanup_expired(self) -> int:
        """Mark expired exports as expired status."""
        return self.expired().exclude(status='expired').update(status='expired')

    def total_size_mb(self) -> float:
        """Total file size of ready exports in MB."""
        total = self.ready().aggregate(total=Sum('file_size_bytes'))['total'] or 0
        return round(total / (1024 * 1024), 2)

    def stats(self) -> dict:
        return {
            'queued':     self.queued().count(),
            'processing': self.processing().count(),
            'ready':      self.ready().count(),
            'failed':     self.failed().count(),
            'expired':    self.expired().count(),
            'total_size_mb': self.total_size_mb(),
        }


# ==================== MaintenanceWindow QuerySet ====================

class MaintenanceWindowQuerySet(models.QuerySet):
    """QuerySet for MaintenanceWindow model."""

    def active(self):
        return self.filter(is_active=True)

    def currently_active(self):
        now = timezone.now()
        return self.filter(is_active=True, start_at__lte=now, end_at__gte=now)

    def upcoming(self, hours: int = 24):
        cutoff = timezone.now() + timedelta(hours=hours)
        return self.filter(
            is_active=False,
            start_at__gte=timezone.now(),
            start_at__lte=cutoff,
        )

    def past(self):
        return self.filter(end_at__lt=timezone.now())

    def should_activate(self):
        """Windows that should be activated now."""
        now = timezone.now()
        return self.filter(is_active=False, start_at__lte=now, end_at__gte=now)

    def should_deactivate(self):
        """Windows that should end now."""
        return self.filter(is_active=True, end_at__lt=timezone.now())

    def by_type(self, maintenance_type: str):
        return self.filter(maintenance_type=maintenance_type)

    def upcoming_notify(self, minutes: int = 60):
        """Windows that need user notification soon."""
        now = timezone.now()
        threshold = now + timedelta(minutes=minutes)
        return self.filter(
            notify_users=True,
            start_at__gte=now,
            start_at__lte=threshold,
        )


# ==================== DashboardWidget QuerySet ====================

class DashboardWidgetQuerySet(models.QuerySet):
    """QuerySet for DashboardWidget model."""

    def visible(self):
        return self.filter(is_visible=True)

    def for_user(self, user):
        return self.filter(user=user)

    def by_type(self, widget_type: str):
        return self.filter(widget_type=widget_type)

    def ordered(self):
        return self.order_by('position')

    def stats_cards(self):
        return self.filter(widget_type='stat_card', is_visible=True)

    def charts(self):
        return self.filter(widget_type__in=['line_chart', 'bar_chart', 'pie_chart',
                                             'donut_chart', 'area_chart'], is_visible=True)


# ==================== SiteNotification QuerySet ====================

class SiteNotificationQuerySet(models.QuerySet):
    """QuerySet for SiteNotification model."""

    def active(self):
        now = timezone.now()
        return self.filter(
            is_active=True,
            start_date__lte=now,
        ).filter(Q(end_date__gte=now) | Q(end_date__isnull=True))

    def login_popups(self):
        return self.active().filter(show_on_login=True)

    def by_type(self, notification_type: str):
        return self.filter(notification_type=notification_type)

    def high_priority(self):
        return self.active().order_by('-priority')

    def expired(self):
        return self.filter(end_date__lt=timezone.now())

    def deactivate_expired(self) -> int:
        return self.expired().filter(is_active=True).update(is_active=False)


# ==================== SiteContent QuerySet ====================

class SiteContentQuerySet(models.QuerySet):
    """QuerySet for SiteContent model."""

    def active(self):
        return self.filter(is_active=True)

    def by_language(self, language: str = 'en'):
        return self.filter(language=language)

    def by_type(self, content_type: str):
        return self.filter(content_type=content_type)

    def by_identifier(self, identifier: str, language: str = 'en'):
        return self.filter(identifier=identifier, language=language, is_active=True).first()

    def ordered(self):
        return self.order_by('order', 'title')

    def for_public(self, language: str = 'en'):
        return self.active().by_language(language).ordered()


# ==================== AdminProfile QuerySet ====================

class AdminProfileQuerySet(models.QuerySet):
    """QuerySet for AdminProfile model."""

    def by_role(self, role: str):
        return self.filter(role=role)

    def superadmins(self):
        return self.filter(role='superadmin')

    def active_users(self):
        return self.filter(user__is_active=True)

    def recently_seen(self, hours: int = 24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(last_seen__gte=cutoff)

    def who_receive_digest(self):
        return self.filter(receive_digest=True, user__is_active=True)

    def who_receive_alerts(self):
        return self.filter(receive_alerts=True, user__is_active=True)

    def role_distribution(self):
        return (
            self.values('role')
            .annotate(count=Count('id'))
            .order_by('role')
        )

    def with_user(self):
        return self.select_related('user')


# ==================== MANAGER CLASSES USING CUSTOM QUERYSETS ====================

class AdminActivityManager(models.Manager):
    def get_queryset(self):
        return AdminActivityQuerySet(self.model, using=self._db)

    def recent(self, days=7):
        return self.get_queryset().recent(days)

    def today(self):
        return self.get_queryset().today()

    def by_actor(self, actor):
        return self.get_queryset().by_actor(actor)

    def summary(self, days=7):
        return self.get_queryset().actions_summary(days)


class SystemConfigManager(models.Manager):
    def get_queryset(self):
        return SystemConfigQuerySet(self.model, using=self._db)

    def public(self):
        return self.get_queryset().public()

    def by_group(self, group):
        return self.get_queryset().by_group(group)


class FeatureFlagManager(models.Manager):
    def get_queryset(self):
        return FeatureFlagQuerySet(self.model, using=self._db)

    def enabled(self):
        return self.get_queryset().enabled()

    def disabled(self):
        return self.get_queryset().disabled()