# api/admin_panel/viewsets/DashboardViewSet.py
"""
DashboardViewSet — real-time KPIs, widget data, system health.
Extends original AdminPanelViewSet logic.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone

from ..dashboard.DashboardService import DashboardService
from ..dashboard.DataExporter import DataExporter
from ..pagination import AdminPagination


class DashboardViewSet(viewsets.ViewSet):
    """
    Dashboard ViewSet.
    Provides KPIs, stats, revenue, system health, metrics.
    All original AdminPanelViewSet actions preserved.
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """General dashboard stats (original action)."""
        cache_key = 'admin_panel:dashboard_stats:general'
        cached = cache.get(cache_key)
        if cached is None:
            cached = DashboardService.get_dashboard_stats()
            cache.set(cache_key, cached, 300)
        return Response({'success': True, 'data': cached})

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Alias for stats (backward-compat with original AdminPanelViewSet)."""
        return self.stats(request)

    @action(detail=False, methods=['get'])
    def user_stats(self, request):
        """User statistics (original action)."""
        stats = DashboardService.get_user_statistics()
        return Response({'success': True, 'data': stats})

    @action(detail=False, methods=['get'])
    def revenue_stats(self, request):
        """Revenue statistics (original action)."""
        stats = DashboardService.get_revenue_statistics()
        return Response({'success': True, 'data': stats})

    @action(detail=False, methods=['post'])
    def export_data(self, request):
        """Export dashboard data (original action)."""
        export_type = request.data.get('type', 'users')
        file_path = DataExporter.export_data(export_type)
        return Response({'success': True, 'data': {'file_path': file_path},
                         'message': 'Data exported successfully'})

    @action(detail=False, methods=['get'])
    def kpis(self, request):
        """
        Real-time KPI metrics from DashboardMetric table.
        Returns cached values; refreshed every 5 min by background task.
        """
        period = request.query_params.get('period', 'daily')
        try:
            from ..models.dashboard import DashboardMetric
            metrics = DashboardMetric.objects.filter(period=period)
            data = []
            for m in metrics:
                data.append({
                    'key': m.metric_key,
                    'label': m.label,
                    'value': float(m.value),
                    'previous_value': float(m.previous_value) if m.previous_value else None,
                    'change_percentage': m.change_percentage,
                    'unit': m.unit,
                    'period': m.period,
                    'cached_at': m.cached_at.isoformat(),
                    'is_stale': m.is_stale,
                })
            return Response({'success': True, 'data': data, 'period': period})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """System health check (cache + live)."""
        cached = cache.get('admin_panel:system_health')
        if cached:
            return Response({'success': True, 'data': cached, 'source': 'cache'})

        from ..utils import get_full_system_health
        health = get_full_system_health()
        cache.set('admin_panel:system_health', health, 60)
        return Response({'success': True, 'data': health, 'source': 'live'})

    @action(detail=False, methods=['post'])
    def refresh_kpis(self, request):
        """Manually trigger KPI refresh."""
        try:
            from ..tasks import refresh_dashboard_kpis
            refresh_dashboard_kpis.delay()
            return Response({'success': True, 'message': 'KPI refresh queued.'})
        except Exception as e:
            from ..tasks.dashboard_refresh_tasks import refresh_all_metrics
            result = refresh_all_metrics()
            return Response({'success': True, 'data': result, 'message': 'KPIs refreshed synchronously.'})

    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """Get active dashboard alerts."""
        try:
            from ..models.dashboard import DashboardAlert
            alerts = DashboardAlert.objects.filter(is_active=True).select_related('metric')
            data = []
            for alert in alerts:
                data.append({
                    'id': alert.pk,
                    'label': alert.label,
                    'metric_key': alert.metric.metric_key,
                    'metric_value': float(alert.metric.value),
                    'threshold': float(alert.threshold),
                    'operator': alert.operator,
                    'is_triggered': alert.check_condition(alert.metric.value),
                    'last_triggered': alert.last_triggered.isoformat() if alert.last_triggered else None,
                    'trigger_count': alert.trigger_count,
                })
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def quick_actions(self, request):
        """Get active quick actions for the dashboard."""
        try:
            from ..models.dashboard import QuickAction
            actions = QuickAction.objects.filter(is_active=True).order_by('sort_order')
            data = [{
                'id': a.pk,
                'label': a.label,
                'description': a.description,
                'icon': a.icon,
                'url': a.url,
                'color': a.color,
                'open_in_new_tab': a.open_in_new_tab,
                'permission_required': a.permission_required,
            } for a in actions if not a.permission_required
              or request.user.has_perm(a.permission_required)]
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})