# api/offer_inventory/reporting_audit/admin_dashboard_stats.py
"""Admin dashboard real-time statistics aggregator."""
import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AdminDashboardStats:
    """Real-time stats for the admin dashboard."""

    CACHE_TTL = 60  # 1 minute

    @classmethod
    def get_live_stats(cls, tenant=None) -> dict:
        """Get current live platform statistics."""
        cache_key = f'admin_live_stats:{tenant}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        from api.offer_inventory.models import Click, Conversion, WithdrawalRequest
        now   = timezone.now()
        today = now.date()

        # Today's stats
        today_clicks = Click.objects.filter(created_at__date=today, is_fraud=False).count()
        today_convs  = Conversion.objects.filter(
            created_at__date=today, status__name='approved'
        ).aggregate(count=Count('id'), rev=Sum('payout_amount'))

        # Last hour
        since_hour = now - timedelta(hours=1)
        hour_clicks = Click.objects.filter(created_at__gte=since_hour, is_fraud=False).count()

        # Pending withdrawals
        pending_wd = WithdrawalRequest.objects.filter(status='pending').aggregate(
            count=Count('id'), total=Sum('amount')
        )

        stats = {
            'today_clicks'     : today_clicks,
            'today_conversions': today_convs['count'] or 0,
            'today_revenue'    : float(today_convs['rev'] or 0),
            'last_hour_clicks' : hour_clicks,
            'pending_withdrawals': pending_wd['count'] or 0,
            'pending_wd_amount': float(pending_wd['total'] or 0),
            'last_updated'     : now.isoformat(),
        }
        cache.set(cache_key, stats, cls.CACHE_TTL)
        return stats

    @classmethod
    def get_conversion_funnel(cls, days: int = 7) -> dict:
        """Click → Conversion funnel analysis."""
        from api.offer_inventory.models import Click, Conversion, Impression

        since = timezone.now() - timedelta(days=days)
        impressions = Impression.objects.filter(created_at__gte=since).count()
        clicks      = Click.objects.filter(created_at__gte=since, is_fraud=False).count()
        conversions = Conversion.objects.filter(
            created_at__gte=since, status__name='approved'
        ).count()

        return {
            'impressions' : impressions,
            'clicks'      : clicks,
            'conversions' : conversions,
            'ctr_pct'     : round(clicks / max(impressions, 1) * 100, 2),
            'cvr_pct'     : round(conversions / max(clicks, 1) * 100, 2),
            'days'        : days,
        }


# ─────────────────────────────────────────────────────
# audit_logs.py
# ─────────────────────────────────────────────────────

class AuditLogService:
    """Comprehensive audit log management."""

    @staticmethod
    def log_action(user, action: str, model_name: str = '',
                    object_id: str = '', changes: dict = None,
                    ip: str = '', ua: str = '') -> object:
        from api.offer_inventory.models import AuditLog
        return AuditLog.objects.create(
            user      =user,
            action    =action,
            model_name=model_name,
            object_id =str(object_id),
            changes   =changes or {},
            ip_address=ip,
            user_agent=ua[:500],
        )

    @staticmethod
    def get_user_audit_trail(user, days: int = 30, limit: int = 100) -> list:
        from api.offer_inventory.models import AuditLog
        since = timezone.now() - timedelta(days=days)
        return list(
            AuditLog.objects.filter(user=user, created_at__gte=since)
            .order_by('-created_at')
            .values('action', 'model_name', 'object_id', 'ip_address', 'created_at')
            [:limit]
        )

    @staticmethod
    def get_model_audit_trail(model_name: str, object_id: str) -> list:
        from api.offer_inventory.models import AuditLog
        return list(
            AuditLog.objects.filter(model_name=model_name, object_id=str(object_id))
            .order_by('-created_at')
            .values('user__username', 'action', 'changes', 'ip_address', 'created_at')
            [:50]
        )

    @staticmethod
    def export_audit_csv(days: int = 30):
        """Export audit logs as CSV response."""
        import csv
        from django.http import HttpResponse
        from api.offer_inventory.models import AuditLog

        since    = timezone.now() - timedelta(days=days)
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Date', 'User', 'Action', 'Model', 'Object ID', 'IP'])
        for log in AuditLog.objects.filter(created_at__gte=since).select_related('user')[:10000]:
            writer.writerow([
                log.created_at.strftime('%Y-%m-%d %H:%M'),
                log.user.username if log.user else '',
                log.action, log.model_name, log.object_id, log.ip_address,
            ])
        return response


# ─────────────────────────────────────────────────────
# real_time_monitor.py
# ─────────────────────────────────────────────────────

class RealTimeMonitor:
    """Real-time platform monitoring with alerting."""

    THRESHOLDS = {
        'fraud_rate_pct'    : 15.0,
        'error_rate_pct'    : 5.0,
        'conversion_drop_pct': 30.0,
        'response_time_ms'  : 2000.0,
    }

    @classmethod
    def check_all(cls) -> dict:
        alerts = []

        # Check fraud rate
        fr = cls._current_fraud_rate()
        if fr > cls.THRESHOLDS['fraud_rate_pct']:
            alerts.append({'type': 'fraud_spike', 'value': fr, 'threshold': cls.THRESHOLDS['fraud_rate_pct']})

        # Check error log rate
        er = cls._current_error_rate()
        if er > cls.THRESHOLDS['error_rate_pct']:
            alerts.append({'type': 'error_spike', 'value': er, 'threshold': cls.THRESHOLDS['error_rate_pct']})

        if alerts:
            cls._dispatch_alerts(alerts)

        return {'alerts': alerts, 'healthy': len(alerts) == 0, 'checked_at': timezone.now().isoformat()}

    @staticmethod
    def _current_fraud_rate() -> float:
        from api.offer_inventory.models import Click
        since = timezone.now() - timedelta(minutes=30)
        total = Click.objects.filter(created_at__gte=since).count()
        fraud = Click.objects.filter(created_at__gte=since, is_fraud=True).count()
        return round(fraud / max(total, 1) * 100, 2)

    @staticmethod
    def _current_error_rate() -> float:
        from api.offer_inventory.models import ErrorLog
        since  = timezone.now() - timedelta(minutes=30)
        errors = ErrorLog.objects.filter(created_at__gte=since, level__in=['error', 'critical']).count()
        return float(errors)

    @staticmethod
    def _dispatch_alerts(alerts: list):
        from api.offer_inventory.notifications import SlackNotifier, EmailAlertSystem
        notifier = SlackNotifier()
        for alert in alerts:
            if alert['type'] == 'fraud_spike':
                notifier.alert_fraud({'fraud_rate': alert['value']})
                EmailAlertSystem.send_fraud_spike_alert({'fraud_rate': alert['value']})


# ─────────────────────────────────────────────────────
# error_tracker.py
# ─────────────────────────────────────────────────────

class ErrorTracker:
    """Application error tracking and grouping."""

    @staticmethod
    def log(level: str, message: str, traceback: str = '',
             request=None, user=None) -> object:
        from api.offer_inventory.models import ErrorLog
        ip = ''
        if request:
            xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
            ip  = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')

        return ErrorLog.objects.create(
            level       =level,
            message     =message[:1000],
            traceback   =traceback[:5000],
            request_path=request.path if request else '',
            user        =user or (request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None),
            ip_address  =ip or None,
        )

    @staticmethod
    def get_error_summary(hours: int = 24) -> dict:
        from api.offer_inventory.models import ErrorLog
        from django.db.models import Count
        since = timezone.now() - timedelta(hours=hours)
        return dict(
            ErrorLog.objects.filter(created_at__gte=since)
            .values_list('level')
            .annotate(count=Count('id'))
        )

    @staticmethod
    def get_top_errors(limit: int = 10) -> list:
        from api.offer_inventory.models import ErrorLog
        from django.db.models import Count
        since = timezone.now() - timedelta(days=7)
        return list(
            ErrorLog.objects.filter(created_at__gte=since, is_resolved=False)
            .values('message')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )


# ─────────────────────────────────────────────────────
# export_manager.py
# ─────────────────────────────────────────────────────

class ExportManager:
    """Centralized export manager for all platform data."""

    AVAILABLE_EXPORTS = [
        'revenue_report',
        'conversion_report',
        'withdrawal_report',
        'fraud_report',
        'user_earnings',
        'network_comparison',
        'audit_log',
    ]

    @classmethod
    def export(cls, export_type: str, days: int = 30,
                format: str = 'csv', **kwargs):
        """Dispatch to the correct export function."""
        from api.offer_inventory.business.reporting_suite import ReportingEngine

        handlers = {
            'revenue_report'    : lambda: ReportingEngine.revenue_report(days=days, format=format),
            'conversion_report' : lambda: ReportingEngine.conversion_report(days=days, format=format),
            'withdrawal_report' : lambda: ReportingEngine.withdrawal_report(days=days, format=format),
            'fraud_report'      : lambda: ReportingEngine.fraud_report(days=days),
            'user_earnings'     : lambda: ReportingEngine.user_earnings_report(days=days, format=format),
            'network_comparison': lambda: ReportingEngine.network_comparison(days=days),
            'audit_log'         : lambda: AuditLogService.export_audit_csv(days=days),
        }

        handler = handlers.get(export_type)
        if not handler:
            raise ValueError(f'Unknown export type: {export_type}. Available: {cls.AVAILABLE_EXPORTS}')

        return handler()


# ─────────────────────────────────────────────────────
# performance_analytics.py
# ─────────────────────────────────────────────────────

class PerformanceAnalytics:
    """API and system performance analytics."""

    @staticmethod
    def record_request(endpoint: str, method: str, elapsed_ms: float,
                        error_rate: float = 0.0):
        """Record an API request performance metric."""
        from api.offer_inventory.models import PerformanceMetric
        PerformanceMetric.objects.create(
            endpoint     =endpoint[:255],
            method       =method[:6],
            avg_ms       =elapsed_ms,
            p95_ms       =elapsed_ms * 1.2,
            p99_ms       =elapsed_ms * 1.5,
            error_rate   =error_rate,
            request_count=1,
            recorded_at  =timezone.now(),
        )

    @staticmethod
    def get_slow_endpoints(threshold_ms: float = 1000.0, limit: int = 20) -> list:
        """Get endpoints with average response time above threshold."""
        from api.offer_inventory.models import PerformanceMetric
        from django.db.models import Avg, Count
        since = timezone.now() - timedelta(hours=24)
        return list(
            PerformanceMetric.objects.filter(recorded_at__gte=since)
            .values('endpoint', 'method')
            .annotate(avg=Avg('avg_ms'), requests=Count('id'))
            .filter(avg__gt=threshold_ms)
            .order_by('-avg')[:limit]
        )

    @staticmethod
    def get_error_prone_endpoints(limit: int = 10) -> list:
        """Get endpoints with highest error rates."""
        from api.offer_inventory.models import PerformanceMetric
        from django.db.models import Avg, Count
        since = timezone.now() - timedelta(hours=24)
        return list(
            PerformanceMetric.objects.filter(recorded_at__gte=since, error_rate__gt=0)
            .values('endpoint', 'method')
            .annotate(avg_error=Avg('error_rate'), requests=Count('id'))
            .order_by('-avg_error')[:limit]
        )
