# api/admin_panel/services/AdminDashboardService.py
"""
AdminDashboardService — builds complete dashboard data for any admin role.
Aggregates KPIs, metrics, alerts, quick actions, and insights.
"""
import logging
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class AdminDashboardService:
    """Build full dashboard data payload for a given admin user and role."""

    CACHE_TTL = 300  # 5 minutes

    @classmethod
    def get_dashboard_data(cls, user, period: str = 'daily') -> dict:
        """
        Build complete dashboard data for a user.
        Returns: kpis, metrics, alerts, insights, quick_actions, system_health, activity_feed
        """
        cache_key = f'admin_panel:dashboard_full:{user.pk}:{period}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = {
            'user': cls._get_user_context(user),
            'kpis': cls._get_kpis(period),
            'alerts': cls._get_active_alerts(),
            'insights': cls._get_recent_insights(),
            'quick_actions': cls._get_quick_actions(user),
            'system_health': cls._get_system_health(),
            'activity_feed': cls._get_activity_feed(limit=10),
            'generated_at': timezone.now().isoformat(),
            'period': period,
        }

        cache.set(cache_key, data, cls.CACHE_TTL)
        return data

    @classmethod
    def _get_user_context(cls, user) -> dict:
        ctx = {
            'id': user.pk,
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name(),
            'is_superuser': user.is_superuser,
            'role': 'superadmin' if user.is_superuser else 'admin',
        }
        try:
            profile = user.admin_profile
            ctx.update({
                'role': profile.role,
                'avatar': profile.avatar.url if profile.avatar else None,
                'theme': profile.theme,
                'permissions': profile.get_display_name(),
            })
        except Exception:
            pass
        return ctx

    @classmethod
    def _get_kpis(cls, period: str) -> list:
        try:
            from ..models.dashboard import DashboardMetric
            metrics = DashboardMetric.objects.filter(period=period).order_by('metric_key')
            return [
                {
                    'key': m.metric_key,
                    'label': m.label,
                    'value': float(m.value),
                    'previous_value': float(m.previous_value) if m.previous_value else None,
                    'change_percentage': m.change_percentage,
                    'unit': m.unit,
                    'is_stale': m.is_stale,
                }
                for m in metrics
            ]
        except Exception as e:
            logger.debug(f"KPI fetch error: {e}")
            return []

    @classmethod
    def _get_active_alerts(cls) -> list:
        try:
            from ..models.dashboard import DashboardAlert
            alerts = DashboardAlert.objects.filter(is_active=True).select_related('metric')
            return [
                {
                    'id': a.pk,
                    'label': a.label,
                    'metric_key': a.metric.metric_key,
                    'metric_value': float(a.metric.value),
                    'threshold': float(a.threshold),
                    'operator': a.operator,
                    'is_triggered': a.check_condition(a.metric.value),
                    'last_triggered': a.last_triggered.isoformat() if a.last_triggered else None,
                }
                for a in alerts
            ]
        except Exception as e:
            logger.debug(f"Alert fetch error: {e}")
            return []

    @classmethod
    def _get_recent_insights(cls, limit: int = 5) -> list:
        try:
            from ..models.reports import AdminInsight
            from django.db.models import Q
            insights = AdminInsight.objects.filter(
                is_dismissed=False,
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
            ).order_by('-created_at')[:limit]
            return [
                {
                    'id': str(i.insight_id),
                    'type': i.type,
                    'title': i.title,
                    'priority': i.priority,
                    'priority_color': i.priority_color,
                    'is_read': i.is_read,
                    'action_url': i.action_url,
                    'action_label': i.action_label,
                    'created_at': i.created_at.isoformat(),
                }
                for i in insights
            ]
        except Exception as e:
            logger.debug(f"Insights fetch error: {e}")
            return []

    @classmethod
    def _get_quick_actions(cls, user) -> list:
        try:
            from ..models.dashboard import QuickAction
            actions = QuickAction.objects.filter(is_active=True).order_by('sort_order')
            return [
                {
                    'id': a.pk,
                    'label': a.label,
                    'icon': a.icon,
                    'url': a.url,
                    'color': a.color,
                    'open_in_new_tab': a.open_in_new_tab,
                }
                for a in actions
                if not a.permission_required or user.has_perm(a.permission_required)
            ]
        except Exception as e:
            logger.debug(f"Quick actions fetch error: {e}")
            return []

    @classmethod
    def _get_system_health(cls) -> dict:
        cached = cache.get('admin_panel:system_health')
        if cached:
            return cached
        try:
            from ..utils import get_full_system_health
            health = get_full_system_health()
            cache.set('admin_panel:system_health', health, 60)
            return health
        except Exception:
            return {'overall': 'unknown', 'checks': {}}

    @classmethod
    def _get_activity_feed(cls, limit: int = 10) -> list:
        try:
            from ..models.activity import AdminActivity
            activities = AdminActivity.objects.select_related('actor').order_by('-created_at')[:limit]
            return [
                {
                    'id': a.pk,
                    'actor': a.actor.username if a.actor else 'System',
                    'action': a.action,
                    'model': a.model_name,
                    'object_id': a.object_id,
                    'status': a.status,
                    'created_at': a.created_at.isoformat(),
                }
                for a in activities
            ]
        except Exception as e:
            logger.debug(f"Activity feed error: {e}")
            return []