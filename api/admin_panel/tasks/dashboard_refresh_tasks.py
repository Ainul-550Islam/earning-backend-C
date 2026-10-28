# api/admin_panel/tasks/dashboard_refresh_tasks.py
"""
Dashboard KPI refresh tasks.
Runs every 5 minutes via Celery Beat.
"""
import logging
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Sum, Avg
from datetime import timedelta

logger = logging.getLogger(__name__)


def refresh_all_metrics():
    """
    Refresh all dashboard KPI metrics and persist to DashboardMetric.
    Called by the periodic task every 5 minutes.
    """
    results = {}
    metrics = [
        _refresh_user_metrics,
        _refresh_revenue_metrics,
        _refresh_withdrawal_metrics,
        _refresh_earning_metrics,
        _refresh_activity_metrics,
    ]
    for fn in metrics:
        try:
            key, value = fn()
            results[key] = value
        except Exception as e:
            logger.error(f"Dashboard metric refresh error in {fn.__name__}: {e}")

    cache.set('admin_panel:dashboard_last_refresh', timezone.now().isoformat(), 600)
    logger.info(f"Dashboard KPIs refreshed: {list(results.keys())}")
    return results


def _upsert_metric(key: str, label: str, value, unit: str = '', period: str = 'daily', metadata: dict = None):
    """Upsert a DashboardMetric record."""
    try:
        from ..models.dashboard import DashboardMetric
        existing = DashboardMetric.objects.filter(metric_key=key, period=period).first()
        prev_value = float(existing.value) if existing else None

        DashboardMetric.objects.update_or_create(
            metric_key=key,
            period=period,
            defaults={
                'label': label,
                'value': value,
                'previous_value': prev_value,
                'unit': unit,
                'metadata': metadata or {},
                'cached_at': timezone.now(),
            }
        )
    except Exception as e:
        logger.error(f"Failed to upsert DashboardMetric '{key}': {e}")


def _refresh_user_metrics():
    """Refresh user-related KPIs."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    last_30 = timezone.now() - timedelta(days=30)

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    new_today = User.objects.filter(date_joined__date=today).count()
    new_yesterday = User.objects.filter(date_joined__date=yesterday).count()
    new_30d = User.objects.filter(date_joined__gte=last_30).count()

    _upsert_metric(
        'total_users', 'Total Users', total_users, 'users', 'realtime',
        {'active': active_users, 'inactive': total_users - active_users}
    )
    _upsert_metric('new_users_today', 'New Users Today', new_today, 'users', 'daily',
                   {'yesterday': new_yesterday})
    _upsert_metric('new_users_30d', 'New Users (30 Days)', new_30d, 'users', 'monthly')

    return 'user_metrics', {'total': total_users, 'today': new_today}


def _refresh_revenue_metrics():
    """Refresh revenue/payment KPIs."""
    try:
        from api.transactions.models import Transaction
        from django.db.models import Sum

        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        total_revenue = Transaction.objects.filter(
            transaction_type='earning', status='completed'
        ).aggregate(total=Sum('gross_amount'))['total'] or 0

        today_revenue = Transaction.objects.filter(
            transaction_type='earning', status='completed', created_at__date=today
        ).aggregate(total=Sum('gross_amount'))['total'] or 0

        yesterday_revenue = Transaction.objects.filter(
            transaction_type='earning', status='completed', created_at__date=yesterday
        ).aggregate(total=Sum('gross_amount'))['total'] or 0

        _upsert_metric('total_revenue', 'Total Revenue', float(total_revenue), 'BDT', 'realtime')
        _upsert_metric('daily_revenue', 'Daily Revenue', float(today_revenue), 'BDT', 'daily',
                       {'yesterday': float(yesterday_revenue)})

        return 'revenue_metrics', {'total': float(total_revenue), 'today': float(today_revenue)}
    except ImportError:
        logger.debug("Transaction model not available for revenue metrics.")
        return 'revenue_metrics', {}


def _refresh_withdrawal_metrics():
    """Refresh withdrawal KPIs."""
    try:
        from api.withdrawals.models import Withdrawal
        from django.db.models import Sum, Count

        pending_count = Withdrawal.objects.filter(status='QUEUED').count()
        pending_amount = Withdrawal.objects.filter(
            status='QUEUED'
        ).aggregate(total=Sum('gross_amount'))['total'] or 0

        today = timezone.now().date()
        today_paid = Withdrawal.objects.filter(
            status='SUCCESS', updated_at__date=today
        ).aggregate(total=Sum('gross_amount'))['total'] or 0

        _upsert_metric('pending_withdrawals', 'Pending Withdrawals', pending_count, 'requests', 'realtime',
                       {'amount': float(pending_amount)})
        _upsert_metric('today_paid_out', 'Paid Out Today', float(today_paid), 'BDT', 'daily')

        return 'withdrawal_metrics', {'pending': pending_count, 'pending_amount': float(pending_amount)}
    except ImportError:
        logger.debug("Withdrawal model not available.")
        return 'withdrawal_metrics', {}


def _refresh_earning_metrics():
    """Refresh earning/points KPIs."""
    try:
        from api.users.models import UserProfile
        from django.db.models import Sum

        total_points = UserProfile.objects.aggregate(
            total=Sum('total_points')
        )['total'] or 0

        _upsert_metric('total_points_issued', 'Total Points Issued', total_points, 'pts', 'realtime')
        return 'earning_metrics', {'total_points': total_points}
    except ImportError:
        logger.debug("UserProfile model not available for earning metrics.")
        return 'earning_metrics', {}


def _refresh_activity_metrics():
    """Refresh admin activity metrics."""
    try:
        from ..models.activity import AdminActivity, AdminSession
        today = timezone.now().date()

        today_actions = AdminActivity.objects.filter(created_at__date=today).count()
        active_sessions = AdminSession.objects.filter(is_active=True).count()

        _upsert_metric('admin_actions_today', 'Admin Actions Today', today_actions, 'actions', 'daily')
        _upsert_metric('active_admin_sessions', 'Active Admin Sessions', active_sessions, 'sessions', 'realtime')

        return 'activity_metrics', {'actions_today': today_actions, 'active_sessions': active_sessions}
    except Exception as e:
        logger.debug(f"Activity metrics: {e}")
        return 'activity_metrics', {}


@shared_task(name='admin_panel.tasks.dashboard_refresh_tasks.refresh_dashboard_kpis')
def refresh_dashboard_kpis_task():
    """Celery periodic task — refresh dashboard KPIs every 5 minutes."""
    return refresh_all_metrics()