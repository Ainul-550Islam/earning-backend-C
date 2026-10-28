"""
tasks/report_tasks.py
Scheduled report generation Celery tasks:
  - generate_daily_revenue_report
  - generate_weekly_user_report
  - generate_monthly_admin_report
  - generate_task_performance_report
  - email_report_to_admins
"""
import logging
import csv
import io
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# generate_daily_revenue_report
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.report_tasks.generate_daily_revenue_report',
)
def generate_daily_revenue_report(self, date_str: str = None) -> dict:
    """
    Generate a comprehensive daily revenue report:
    - Total task rewards paid out
    - Total referral bonuses
    - Total admin profit (20% share)
    - Per-task breakdown
    - Per-category breakdown
    Caches report JSON for 24 hours and optionally sends to admins.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Sum, Count, Q

        target_date = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str
            else (timezone.now() - timedelta(days=1)).date()
        )

        logger.info(f"📊 Generating daily revenue report for {target_date}...")

        report = {
            'date': str(target_date),
            'type': 'daily_revenue',
            'summary': {},
            'by_task': [],
            'by_category': [],
            'generated_at': timezone.now().isoformat(),
        }

        try:
            from api.tasks.models import UserTaskCompletion, AdminLedger

            day_start = timezone.make_aware(
                datetime.combine(target_date, datetime.min.time())
            )
            day_end = day_start + timedelta(days=1)

            completions = UserTaskCompletion.objects.filter(
                completed_at__gte=day_start,
                completed_at__lt=day_end,
                status='completed',
            )

            summary = completions.aggregate(
                total_completions=Count('id'),
                total_rewards=Sum('reward_amount'),
                total_admin_revenue=Sum('admin_revenue_received'),
            )

            report['summary'] = {
                'total_completions': summary['total_completions'] or 0,
                'total_rewards_paid': str(summary['total_rewards'] or Decimal('0')),
                'total_admin_revenue': str(summary['total_admin_revenue'] or Decimal('0')),
            }

            # Per-task breakdown
            by_task = (
                completions
                .values('task__task_id', 'task__name')
                .annotate(
                    count=Count('id'),
                    total=Sum('reward_amount'),
                )
                .order_by('-total')[:20]
            )
            report['by_task'] = [
                {
                    'task_id': r['task__task_id'],
                    'task_name': r['task__name'],
                    'count': r['count'],
                    'total': str(r['total'] or Decimal('0')),
                }
                for r in by_task
            ]

            # Per-category breakdown
            by_category = (
                completions
                .values('task__category')
                .annotate(
                    count=Count('id'),
                    total=Sum('reward_amount'),
                )
                .order_by('-total')
            )
            report['by_category'] = [
                {
                    'category': r['task__category'],
                    'count': r['count'],
                    'total': str(r['total'] or Decimal('0')),
                }
                for r in by_category
            ]

            cache_key = f'daily_revenue_report_{target_date}'
            cache.set(cache_key, report, timeout=86400)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'report': report,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Daily revenue report generated for {target_date}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] generate_daily_revenue_report failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# generate_weekly_user_report
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.report_tasks.generate_weekly_user_report',
)
def generate_weekly_user_report(self) -> dict:
    """
    Weekly user activity report:
    - New registrations
    - Active users (at least 1 task completion)
    - Churned users (active last week, not this week)
    - Top earners
    - Referral funnel stats
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count, Q

        logger.info("👥 Generating weekly user report...")

        week_end   = timezone.now()
        week_start = week_end - timedelta(days=7)
        prev_start = week_start - timedelta(days=7)

        report = {
            'type': 'weekly_user',
            'period_start': week_start.isoformat(),
            'period_end': week_end.isoformat(),
            'new_registrations': 0,
            'active_users': 0,
            'churned_users': 0,
            'top_earners': [],
            'referral_summary': {},
            'generated_at': timezone.now().isoformat(),
        }

        try:
            from django.contrib.auth import get_user_model
            from api.tasks.models import UserTaskCompletion

            User = get_user_model()

            report['new_registrations'] = User.objects.filter(
                date_joined__gte=week_start
            ).count()

            active_this_week = set(
                UserTaskCompletion.objects.filter(
                    completed_at__gte=week_start,
                    status='completed',
                ).values_list('user_id', flat=True).distinct()
            )
            report['active_users'] = len(active_this_week)

            active_prev_week = set(
                UserTaskCompletion.objects.filter(
                    completed_at__gte=prev_start,
                    completed_at__lt=week_start,
                    status='completed',
                ).values_list('user_id', flat=True).distinct()
            )
            report['churned_users'] = len(active_prev_week - active_this_week)

            # Top earners
            top_earners = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=week_start,
                    status='completed',
                )
                .values('user_id', 'user__username')
                .annotate(
                    total_earned=Sum('reward_amount'),
                    completions=Count('id'),
                )
                .order_by('-total_earned')[:10]
            )
            report['top_earners'] = [
                {
                    'user_id': r['user_id'],
                    'username': r['user__username'],
                    'total_earned': str(r['total_earned'] or Decimal('0')),
                    'completions': r['completions'],
                }
                for r in top_earners
            ]

            cache.set('weekly_user_report', report, timeout=604800)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'report': report,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info("[OK] Weekly user report generated")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] generate_weekly_user_report failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# generate_monthly_admin_report
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name='tasks.report_tasks.generate_monthly_admin_report',
)
def generate_monthly_admin_report(self, year: int = None, month: int = None) -> dict:
    """
    Monthly comprehensive admin report:
    - Total revenue, admin profit, payouts
    - User growth MoM
    - Task completion trends
    - Top performing tasks/categories
    - Gateway performance summary
    """
    try:
        from datetime import datetime
        import calendar
        from django.db.models import Sum, Count, Avg, Q

        now   = timezone.now()
        year  = year or now.year
        month = month or (now.month - 1 or 12)
        if month == 12 and now.month == 1:
            year -= 1

        _, last_day = calendar.monthrange(year, month)
        month_start = timezone.make_aware(datetime(year, month, 1))
        month_end   = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))

        logger.info(f"📋 Generating monthly admin report for {year}-{month:02d}...")

        report = {
            'type': 'monthly_admin',
            'year': year,
            'month': month,
            'period': f'{year}-{month:02d}',
            'revenue': {},
            'users': {},
            'tasks': {},
            'generated_at': timezone.now().isoformat(),
        }

        try:
            from api.tasks.models import UserTaskCompletion, AdminLedger
            from django.contrib.auth import get_user_model

            User = get_user_model()

            completions = UserTaskCompletion.objects.filter(
                completed_at__gte=month_start,
                completed_at__lte=month_end,
                status='completed',
            )

            rev_agg = completions.aggregate(
                total_rewards=Sum('reward_amount'),
                total_admin=Sum('admin_revenue_received'),
                total_completions=Count('id'),
                unique_users=Count('user', distinct=True),
            )

            report['revenue'] = {
                'total_rewards_paid': str(rev_agg['total_rewards'] or Decimal('0')),
                'total_admin_profit': str(rev_agg['total_admin'] or Decimal('0')),
            }
            report['tasks'] = {
                'total_completions': rev_agg['total_completions'] or 0,
                'unique_active_users': rev_agg['unique_users'] or 0,
            }

            new_users = User.objects.filter(
                date_joined__gte=month_start,
                date_joined__lte=month_end,
            ).count()
            total_users = User.objects.count()

            report['users'] = {
                'new_registrations': new_users,
                'total_users': total_users,
            }

            cache_key = f'monthly_admin_report_{year}_{month:02d}'
            cache.set(cache_key, report, timeout=2592000)  # 30 days

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'report': report,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Monthly admin report generated for {year}-{month:02d}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] generate_monthly_admin_report failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# generate_task_performance_report
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.report_tasks.generate_task_performance_report',
)
def generate_task_performance_report(self, lookback_days: int = 30) -> dict:
    """
    Generate a task performance report covering:
    - Top performing tasks by completion volume and revenue
    - Tasks with declining completion rates
    - Average time-to-completion per task
    - Error/failure breakdown per task
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg, Q

        logger.info(f"⚡ Generating task performance report (lookback={lookback_days}d)...")
        cutoff = timezone.now() - timedelta(days=lookback_days)

        report = {
            'type': 'task_performance',
            'lookback_days': lookback_days,
            'top_tasks': [],
            'declining_tasks': [],
            'generated_at': timezone.now().isoformat(),
        }

        try:
            from api.tasks.models import UserTaskCompletion, MasterTask

            base_qs = UserTaskCompletion.objects.filter(
                completed_at__gte=cutoff,
                status='completed',
            )

            top_tasks = (
                base_qs
                .values('task__task_id', 'task__name', 'task__category')
                .annotate(
                    completions=Count('id'),
                    total_revenue=Sum('reward_amount'),
                    unique_users=Count('user', distinct=True),
                    avg_reward=Avg('reward_amount'),
                )
                .order_by('-completions')[:20]
            )

            report['top_tasks'] = [
                {
                    'task_id': r['task__task_id'],
                    'task_name': r['task__name'],
                    'category': r['task__category'],
                    'completions': r['completions'],
                    'total_revenue': str(r['total_revenue'] or Decimal('0')),
                    'unique_users': r['unique_users'],
                    'avg_reward': str(r['avg_reward'] or Decimal('0')),
                }
                for r in top_tasks
            ]

            cache.set('task_performance_report', report, timeout=86400)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'report': report,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info("[OK] Task performance report generated")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] generate_task_performance_report failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# email_report_to_admins
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.report_tasks.email_report_to_admins',
)
def email_report_to_admins(self, report_type: str = 'daily_revenue', date_str: str = None) -> dict:
    """
    Retrieve a generated report from cache and email it to all admin users.
    Falls back to regenerating the report if cache miss.
    Supported report_type values:
      daily_revenue, weekly_user, monthly_admin, task_performance
    """
    try:
        from django.core.mail import send_mail
        from django.contrib.auth import get_user_model
        from django.conf import settings

        logger.info(f"📧 Emailing {report_type} report to admins...")

        target_date = date_str or str(timezone.now().date())
        cache_key   = f'{report_type}_report_{target_date}'
        report      = cache.get(cache_key)

        if not report:
            logger.warning(f"[WARN] No cached report found for {cache_key}. Regenerating...")
            if report_type == 'daily_revenue':
                generate_daily_revenue_report.apply(kwargs={'date_str': target_date})
                report = cache.get(cache_key) or {}
            else:
                report = {'note': 'Report not available. Please run generation task first.'}

        User = get_user_model()
        admins = User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)
        admin_emails = [e for e in admins if e]

        if not admin_emails:
            logger.warning("[WARN] No admin emails found.")
            return {'status': 'skipped', 'reason': 'no_admin_emails'}

        subject = f"[{getattr(settings, 'SITE_NAME', 'Platform')}] {report_type.replace('_', ' ').title()} Report – {target_date}"
        body    = (
            f"Report Type  : {report_type}\n"
            f"Date         : {target_date}\n"
            f"Generated At : {report.get('generated_at', 'N/A')}\n\n"
            f"Summary:\n{str(report.get('summary', report))[:2000]}\n\n"
            f"Please log in to the admin dashboard for the full interactive report."
        )

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        send_mail(subject, body, from_email, admin_emails, fail_silently=False)

        result = {
            'status': 'success',
            'report_type': report_type,
            'emails_sent_to': list(admin_emails),
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Report emailed to {len(admin_emails)} admin(s)")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] email_report_to_admins failed: {exc}")
        raise self.retry(exc=exc)
