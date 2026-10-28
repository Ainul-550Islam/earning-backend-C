# api/admin_panel/tasks/insight_tasks.py
"""
AI-powered admin insight generation tasks.
Runs daily to detect anomalies, trends, and generate recommendations.
CPAlead-style: fraud spikes, earnings anomalies, top referrers, withdrawal trends.
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def generate_insights():
    """Generate all daily admin insights."""
    generators = [
        _generate_user_growth_insight,
        _generate_withdrawal_anomaly_insight,
        _generate_fraud_detection_insight,
        _generate_referral_performance_insight,
        _generate_system_health_insight,
        _generate_revenue_trend_insight,
    ]
    generated = []
    for gen in generators:
        try:
            result = gen()
            if result:
                generated.append(result)
        except Exception as e:
            logger.error(f"Insight generator {gen.__name__} failed: {e}")

    logger.info(f"Generated {len(generated)} admin insights.")
    return {'generated': len(generated), 'insights': generated}


def _create_insight(type_: str, title: str, body: str, priority: str = 'medium',
                    data: dict = None, action_url: str = '', action_label: str = ''):
    """Helper to create an AdminInsight record."""
    try:
        from ..models.reports import AdminInsight
        insight = AdminInsight.objects.create(
            type=type_,
            title=title,
            body=body,
            priority=priority,
            data=data or {},
            action_url=action_url,
            action_label=action_label,
            expires_at=timezone.now() + timedelta(days=3),
            generated_by_task='insight_tasks.generate_insights',
        )
        return {'id': str(insight.insight_id), 'title': title}
    except Exception as e:
        logger.error(f"Failed to create insight '{title}': {e}")
        return None


def _generate_user_growth_insight():
    """Detect unusual user growth or decline."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        last_week_same = today - timedelta(days=7)

        today_count = User.objects.filter(date_joined__date=today).count()
        yesterday_count = User.objects.filter(date_joined__date=yesterday).count()
        week_ago_count = User.objects.filter(date_joined__date=last_week_same).count()

        if yesterday_count > 0:
            pct_change = ((today_count - yesterday_count) / yesterday_count) * 100
        else:
            pct_change = 0

        if abs(pct_change) >= 50:
            direction = 'spike' if pct_change > 0 else 'drop'
            priority = 'high' if abs(pct_change) >= 100 else 'medium'
            return _create_insight(
                type_='anomaly',
                title=f"User Registration {direction.title()}: {pct_change:+.0f}% vs Yesterday",
                body=(
                    f"Today's registrations ({today_count}) show a {abs(pct_change):.0f}% {direction} "
                    f"compared to yesterday ({yesterday_count}). "
                    f"One week ago same day: {week_ago_count} registrations."
                ),
                priority=priority,
                data={
                    'today': today_count,
                    'yesterday': yesterday_count,
                    'week_ago': week_ago_count,
                    'change_pct': round(pct_change, 2),
                },
                action_url='/api/admin-panel/users/',
                action_label='View Users',
            )
    except Exception as e:
        logger.debug(f"User growth insight error: {e}")
    return None


def _generate_withdrawal_anomaly_insight():
    """Detect withdrawal anomalies (high volume, large amounts)."""
    try:
        from api.withdrawals.models import Withdrawal
        from django.db.models import Sum, Count

        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        today_pending = Withdrawal.objects.filter(
            status='QUEUED', created_at__date=today
        ).aggregate(count=Count('id'), total=Sum('gross_amount'))

        yesterday_pending = Withdrawal.objects.filter(
            status='QUEUED', created_at__date=yesterday
        ).aggregate(count=Count('id'), total=Sum('gross_amount'))

        today_count = today_pending.get('count') or 0
        today_amount = float(today_pending.get('total') or 0)
        yesterday_count = yesterday_pending.get('count') or 0

        # Alert if pending withdrawals spike significantly
        if yesterday_count > 0 and today_count > yesterday_count * 2:
            return _create_insight(
                type_='anomaly',
                title=f"Withdrawal Spike: {today_count} Pending Requests Today",
                body=(
                    f"Today has {today_count} pending withdrawal requests (৳{today_amount:,.2f} total), "
                    f"compared to {yesterday_count} yesterday. "
                    f"This is a {(today_count / yesterday_count - 1) * 100:.0f}% increase. "
                    f"Consider reviewing for fraudulent activity."
                ),
                priority='high',
                data={
                    'today_count': today_count,
                    'today_amount': today_amount,
                    'yesterday_count': yesterday_count,
                },
                action_url='/api/admin-panel/withdrawals/',
                action_label='Review Withdrawals',
            )
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Withdrawal insight error: {e}")
    return None


def _generate_fraud_detection_insight():
    """Detect potential fraud patterns."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Flag users with suspicious activity (is_active=False, many account bans)
        last_24h = timezone.now() - timedelta(hours=24)
        recently_banned = User.objects.filter(
            is_active=False,
            date_joined__gte=last_24h
        ).count()

        if recently_banned >= 5:
            return _create_insight(
                type_='alert',
                title=f"Fraud Alert: {recently_banned} Accounts Deactivated in Last 24h",
                body=(
                    f"{recently_banned} user accounts have been deactivated in the last 24 hours. "
                    "This may indicate a coordinated fraud attempt or bot registration wave. "
                    "Review the accounts and check for shared IPs or device fingerprints."
                ),
                priority='critical' if recently_banned >= 20 else 'high',
                data={'recently_banned': recently_banned},
                action_url='/api/admin-panel/users/?is_active=false',
                action_label='Review Banned Users',
            )
    except Exception as e:
        logger.debug(f"Fraud detection insight error: {e}")
    return None


def _generate_referral_performance_insight():
    """Analyze referral system performance."""
    try:
        from api.users.models import UserProfile
        from django.db.models import Count

        last_7d = timezone.now() - timedelta(days=7)
        referral_signups = UserProfile.objects.filter(
            created_at__gte=last_7d,
            referred_by__isnull=False,
        ).count() if hasattr(UserProfile, 'referred_by') else 0

        total_signups = UserProfile.objects.filter(
            created_at__gte=last_7d
        ).count()

        if total_signups > 0:
            referral_rate = (referral_signups / total_signups) * 100
            if referral_rate >= 40:
                priority = 'low'
                body_msg = f"Excellent! {referral_rate:.1f}% of new users came via referral."
                insight_type = 'performance'
            elif referral_rate < 10:
                priority = 'medium'
                body_msg = f"Low referral conversion: only {referral_rate:.1f}% of new users came via referral."
                insight_type = 'recommendation'
            else:
                return None

            return _create_insight(
                type_=insight_type,
                title=f"Referral Rate: {referral_rate:.1f}% (Last 7 Days)",
                body=body_msg,
                priority=priority,
                data={
                    'referral_signups': referral_signups,
                    'total_signups': total_signups,
                    'referral_rate': round(referral_rate, 2),
                },
                action_url='/api/admin-panel/users/',
                action_label='View Users',
            )
    except (ImportError, Exception) as e:
        logger.debug(f"Referral insight error: {e}")
    return None


def _generate_system_health_insight():
    """Check system health and create critical alerts if degraded."""
    try:
        from ..utils import get_full_system_health
        health = get_full_system_health()
        if health['overall'] in ('down', 'degraded'):
            failing = [k for k, v in health['checks'].items() if v['status'] != 'healthy']
            return _create_insight(
                type_='alert',
                title=f"System Health: {health['overall'].upper()} — {', '.join(failing)} affected",
                body=(
                    f"System health check detected issues: {', '.join(failing)}. "
                    f"Overall status: {health['overall']}. "
                    "Investigate immediately to prevent service disruption."
                ),
                priority='critical' if health['overall'] == 'down' else 'high',
                data=health,
                action_url='/api/admin-panel/dashboard/system-health/',
                action_label='View Health Status',
            )
    except Exception as e:
        logger.debug(f"System health insight error: {e}")
    return None


def _generate_revenue_trend_insight():
    """Analyze revenue trend vs previous period."""
    try:
        from ..models.dashboard import DashboardMetric
        metric = DashboardMetric.objects.filter(metric_key='daily_revenue').first()
        if metric and metric.change_percentage is not None:
            change = metric.change_percentage
            if abs(change) >= 20:
                direction = 'increase' if change > 0 else 'decrease'
                priority = 'low' if change > 0 else 'medium'
                return _create_insight(
                    type_='trend',
                    title=f"Revenue {direction.title()}: {change:+.1f}% vs Yesterday",
                    body=(
                        f"Today's revenue shows a {abs(change):.1f}% {direction} vs yesterday. "
                        f"Current: ৳{float(metric.value):,.2f}. "
                        f"Previous: ৳{float(metric.previous_value):,.2f}."
                    ),
                    priority=priority,
                    data={
                        'current': float(metric.value),
                        'previous': float(metric.previous_value),
                        'change_pct': change,
                    },
                    action_url='/api/admin-panel/reports/',
                    action_label='View Reports',
                )
    except Exception as e:
        logger.debug(f"Revenue trend insight error: {e}")
    return None


@shared_task(name='admin_panel.tasks.insight_tasks.generate_daily_insights_task')
def generate_daily_insights_task():
    """Celery periodic task — generate daily insights."""
    return generate_insights()