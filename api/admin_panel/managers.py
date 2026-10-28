# api/admin_panel/managers.py
"""
Custom Model Managers for admin_panel.
All querysets with business logic live here — models stay thin.
"""
from django.db import models
from django.utils import timezone
from django.db.models import Q, Count, Sum


class ActiveManager(models.Manager):
    """Returns only active (non-deleted, is_active=True) records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteManager(models.Manager):
    """Excludes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def deleted(self):
        return super().get_queryset().filter(is_deleted=True)

    def with_deleted(self):
        return super().get_queryset()


class AdminActivityManager(models.Manager):
    """Manager for AdminActivity logs with common filters."""

    def get_queryset(self):
        return super().get_queryset().select_related('actor')

    def by_actor(self, actor):
        return self.get_queryset().filter(actor=actor)

    def by_action(self, action: str):
        return self.get_queryset().filter(action=action)

    def recent(self, days: int = 7):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff)

    def failed(self):
        return self.get_queryset().filter(status='failed')

    def today(self):
        return self.get_queryset().filter(created_at__date=timezone.now().date())

    def summary(self, days: int = 7) -> dict:
        qs = self.recent(days)
        return {
            'total': qs.count(),
            'by_action': list(qs.values('action').annotate(count=Count('id')).order_by('-count')[:10]),
            'by_actor': list(qs.values('actor__username').annotate(count=Count('id')).order_by('-count')[:10]),
            'failed_count': qs.filter(status='failed').count(),
        }


class SystemConfigManager(models.Manager):
    """Manager for SystemConfig with cache-aware queries."""

    def get_value(self, key: str, default=None):
        from django.core.cache import cache
        cache_key = f'admin_panel:config:{key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            obj = self.get(key=key)
            val = obj.get_typed_value()
            cache.set(cache_key, val, 300)
            return val
        except self.model.DoesNotExist:
            return default

    def get_group(self, group: str) -> dict:
        from django.core.cache import cache
        cache_key = f'admin_panel:config_group:{group}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        result = {obj.key: obj.get_typed_value() for obj in self.filter(group=group)}
        cache.set(cache_key, result, 300)
        return result

    def set_value(self, key: str, value, value_type: str = 'string', group: str = 'general'):
        obj, _ = self.update_or_create(
            key=key,
            defaults={'value': str(value), 'value_type': value_type, 'group': group}
        )
        from django.core.cache import cache
        cache.delete(f'admin_panel:config:{key}')
        cache.delete(f'admin_panel:config_group:{group}')
        return obj

    def public(self):
        return self.filter(is_public=True)


class FeatureFlagManager(models.Manager):
    """Manager for FeatureFlag with rollout logic."""

    def enabled_flags(self):
        return self.filter(is_enabled=True)

    def is_enabled(self, flag_key: str) -> bool:
        from django.core.cache import cache
        cache_key = f'admin_panel:feature_flag:{flag_key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            flag = self.get(flag_key=flag_key)
            result = flag.is_enabled
            cache.set(cache_key, result, 60)
            return result
        except self.model.DoesNotExist:
            return False

    def get_all_states(self) -> dict:
        from django.core.cache import cache
        cache_key = 'admin_panel:feature_flags_all'
        cached = cache.get(cache_key)
        if cached:
            return cached
        result = {f.flag_key: f.is_enabled for f in self.all()}
        cache.set(cache_key, result, 60)
        return result


class AdminSessionManager(models.Manager):
    """Manager for AdminSession records."""

    def active(self):
        return self.filter(is_active=True, status='active')

    def for_user(self, user):
        return self.filter(user=user)

    def cleanup_expired(self, hours: int = 24) -> int:
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        expired = self.filter(is_active=False, last_seen__lt=cutoff)
        count = expired.count()
        expired.delete()
        return count


class ReportDefinitionManager(models.Manager):
    """Manager for ReportDefinition."""

    def active(self):
        return self.filter(is_active=True)

    def system_reports(self):
        return self.filter(is_system=True)

    def by_type(self, report_type: str):
        return self.filter(report_type=report_type, is_active=True)


class DashboardMetricManager(models.Manager):
    """Manager for DashboardMetric."""

    def for_period(self, period: str):
        return self.filter(period=period)

    def refresh_kpi(self, metric_key: str, value, period: str = 'daily', **kwargs):
        obj, _ = self.update_or_create(
            metric_key=metric_key,
            period=period,
            defaults={'value': value, 'cached_at': timezone.now(), **kwargs}
        )
        return obj

    def stale(self, minutes: int = 5):
        cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
        return self.filter(cached_at__lt=cutoff)