"""
tasks/export_tasks.py
Async data export Celery tasks:
  - export_task_history       — export UserTaskCompletion to CSV/Excel
  - export_user_earnings      — per-user earnings export
  - export_admin_ledger       — AdminLedger export
  - export_withdrawal_history — withdrawal records export
  - export_referral_report    — referral + commission export
  - notify_export_ready       — notify user when export is ready
"""
import logging
import csv
import io
import os
import uuid
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

EXPORT_DIR = getattr(settings, 'EXPORT_DIR', '/tmp/task_exports/')


def _ensure_export_dir():
    """Create the export directory if it doesn't exist."""
    os.makedirs(EXPORT_DIR, exist_ok=True)


def _save_csv(rows: list, headers: list, filename: str) -> str:
    """Write rows to a CSV file and return the file path."""
    _ensure_export_dir()
    filepath = os.path.join(EXPORT_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return filepath


# ─────────────────────────────────────────────
# export_task_history
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name='tasks.export_tasks.export_task_history',
)
def export_task_history(
    self,
    user_id: int = None,
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    requester_user_id: int = None,
) -> dict:
    """
    Export UserTaskCompletion records to CSV.
    Filters by user_id, date range, and/or status.
    Saves the file to EXPORT_DIR and stores the file path in cache
    so the user can download it.

    Args:
        user_id:           Filter by user (None = all users, admin only)
        start_date:        ISO date string 'YYYY-MM-DD'
        end_date:          ISO date string 'YYYY-MM-DD'
        status:            Filter by completion status
        requester_user_id: Who requested the export (for cache key + notification)
    """
    try:
        from datetime import datetime, timedelta
        logger.info(f"📤 Exporting task history (user={user_id}, start={start_date}, end={end_date})...")

        try:
            from api.tasks.models import UserTaskCompletion

            qs = UserTaskCompletion.objects.select_related('user', 'task').all()

            if user_id:
                qs = qs.filter(user_id=user_id)

            if start_date:
                dt = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
                qs = qs.filter(completed_at__gte=dt)

            if end_date:
                dt = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d')) + timedelta(days=1)
                qs = qs.filter(completed_at__lt=dt)

            if status:
                qs = qs.filter(status=status)

            headers = [
                'id', 'user_id', 'username', 'task_id', 'task_name',
                'status', 'reward_amount', 'admin_revenue_received',
                'completed_at', 'created_at',
            ]

            rows = []
            for obj in qs.iterator(chunk_size=500):
                rows.append({
                    'id': obj.pk,
                    'user_id': obj.user_id,
                    'username': obj.user.username if obj.user else '',
                    'task_id': obj.task.task_id if obj.task else '',
                    'task_name': obj.task.name if obj.task else '',
                    'status': obj.status,
                    'reward_amount': str(obj.reward_amount or Decimal('0')),
                    'admin_revenue_received': str(obj.admin_revenue_received or Decimal('0')),
                    'completed_at': obj.completed_at.isoformat() if obj.completed_at else '',
                    'created_at': obj.created_at.isoformat() if obj.created_at else '',
                })

            filename    = f"task_history_{uuid.uuid4().hex[:8]}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath    = _save_csv(rows, headers, filename)
            export_key  = f'export_task_history_{requester_user_id or user_id}_{timezone.now().strftime("%Y%m%d")}'

            export_info = {
                'filename': filename,
                'filepath': filepath,
                'row_count': len(rows),
                'generated_at': timezone.now().isoformat(),
            }
            cache.set(export_key, export_info, timeout=86400)

            # Notify requester
            if requester_user_id:
                notify_export_ready.apply_async(
                    kwargs={
                        'user_id': requester_user_id,
                        'export_type': 'task_history',
                        'filename': filename,
                        'row_count': len(rows),
                    }
                )

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")
            rows = []
            filename = ''
            filepath = ''

        result = {
            'status': 'success',
            'filename': filename,
            'row_count': len(rows),
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Task history exported: {len(rows)} rows → {filename}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] export_task_history failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# export_user_earnings
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.export_tasks.export_user_earnings',
)
def export_user_earnings(
    self,
    start_date: str = None,
    end_date: str = None,
    requester_user_id: int = None,
) -> dict:
    """
    Export aggregated per-user earnings for a date range.
    Columns: user_id, username, email, total_earned, total_completions, avg_reward.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Sum, Count, Avg

        logger.info(f"📤 Exporting user earnings ({start_date} to {end_date})...")

        rows = []
        filename = ''

        try:
            from api.tasks.models import UserTaskCompletion

            qs = UserTaskCompletion.objects.filter(status='completed')

            if start_date:
                dt = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
                qs = qs.filter(completed_at__gte=dt)

            if end_date:
                dt = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d')) + timedelta(days=1)
                qs = qs.filter(completed_at__lt=dt)

            earnings = qs.values(
                'user_id', 'user__username', 'user__email'
            ).annotate(
                total_earned=Sum('reward_amount'),
                total_completions=Count('id'),
                avg_reward=Avg('reward_amount'),
            ).order_by('-total_earned')

            headers = [
                'user_id', 'username', 'email',
                'total_earned', 'total_completions', 'avg_reward',
            ]

            for row in earnings:
                rows.append({
                    'user_id': row['user_id'],
                    'username': row['user__username'],
                    'email': row['user__email'],
                    'total_earned': str(row['total_earned'] or Decimal('0')),
                    'total_completions': row['total_completions'],
                    'avg_reward': str(row['avg_reward'] or Decimal('0')),
                })

            filename = f"user_earnings_{uuid.uuid4().hex[:8]}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            _save_csv(rows, headers, filename)

            if requester_user_id:
                notify_export_ready.apply_async(
                    kwargs={
                        'user_id': requester_user_id,
                        'export_type': 'user_earnings',
                        'filename': filename,
                        'row_count': len(rows),
                    }
                )

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'filename': filename,
            'row_count': len(rows),
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] User earnings exported: {len(rows)} rows → {filename}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] export_user_earnings failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# export_admin_ledger
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.export_tasks.export_admin_ledger',
)
def export_admin_ledger(
    self,
    start_date: str = None,
    end_date: str = None,
    source_type: str = None,
    requester_user_id: int = None,
) -> dict:
    """
    Export AdminLedger records to CSV.
    """
    try:
        from datetime import datetime, timedelta
        logger.info(f"📤 Exporting admin ledger ({start_date} to {end_date})...")

        rows = []
        filename = ''

        try:
            from api.tasks.models import AdminLedger

            qs = AdminLedger.objects.select_related('task', 'user', 'completion').all()

            if start_date:
                dt = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
                qs = qs.filter(created_at__gte=dt)

            if end_date:
                dt = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d')) + timedelta(days=1)
                qs = qs.filter(created_at__lt=dt)

            if source_type:
                qs = qs.filter(source_type=source_type)

            headers = [
                'id', 'amount', 'source', 'source_type',
                'task_id', 'user_id', 'completion_id',
                'description', 'created_at',
            ]

            for obj in qs.iterator(chunk_size=500):
                rows.append({
                    'id': obj.pk,
                    'amount': str(obj.amount or Decimal('0')),
                    'source': obj.source or '',
                    'source_type': obj.source_type or '',
                    'task_id': obj.task.task_id if obj.task else '',
                    'user_id': obj.user_id or '',
                    'completion_id': obj.completion_id or '',
                    'description': obj.description or '',
                    'created_at': obj.created_at.isoformat() if obj.created_at else '',
                })

            filename = f"admin_ledger_{uuid.uuid4().hex[:8]}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            _save_csv(rows, headers, filename)

            if requester_user_id:
                notify_export_ready.apply_async(
                    kwargs={
                        'user_id': requester_user_id,
                        'export_type': 'admin_ledger',
                        'filename': filename,
                        'row_count': len(rows),
                    }
                )

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'filename': filename,
            'row_count': len(rows),
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Admin ledger exported: {len(rows)} rows → {filename}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] export_admin_ledger failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# export_withdrawal_history
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.export_tasks.export_withdrawal_history',
)
def export_withdrawal_history(
    self,
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    requester_user_id: int = None,
) -> dict:
    """
    Export wallet Withdrawal records to CSV.
    """
    try:
        from datetime import datetime, timedelta
        logger.info(f"📤 Exporting withdrawal history ({start_date} to {end_date})...")

        rows = []
        filename = ''

        try:
            from wallet.models import Withdrawal

            qs = Withdrawal.objects.select_related('user', 'gateway').all()

            if start_date:
                dt = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
                qs = qs.filter(created_at__gte=dt)

            if end_date:
                dt = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d')) + timedelta(days=1)
                qs = qs.filter(created_at__lt=dt)

            if status:
                qs = qs.filter(status=status)

            headers = [
                'id', 'user_id', 'username', 'amount', 'status',
                'gateway', 'gateway_txn_id', 'failure_reason',
                'created_at', 'completed_at',
            ]

            for obj in qs.iterator(chunk_size=500):
                rows.append({
                    'id': obj.pk,
                    'user_id': obj.user_id,
                    'username': obj.user.username if obj.user else '',
                    'amount': str(obj.amount or Decimal('0')),
                    'status': obj.status or '',
                    'gateway': obj.gateway.name if obj.gateway else '',
                    'gateway_txn_id': obj.gateway_txn_id or '',
                    'failure_reason': obj.failure_reason or '',
                    'created_at': obj.created_at.isoformat() if obj.created_at else '',
                    'completed_at': obj.completed_at.isoformat() if obj.completed_at else '',
                })

            filename = f"withdrawals_{uuid.uuid4().hex[:8]}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            _save_csv(rows, headers, filename)

            if requester_user_id:
                notify_export_ready.apply_async(
                    kwargs={
                        'user_id': requester_user_id,
                        'export_type': 'withdrawal_history',
                        'filename': filename,
                        'row_count': len(rows),
                    }
                )

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'filename': filename,
            'row_count': len(rows),
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Withdrawal history exported: {len(rows)} rows → {filename}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] export_withdrawal_history failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# export_referral_report
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.export_tasks.export_referral_report',
)
def export_referral_report(
    self,
    start_date: str = None,
    end_date: str = None,
    requester_user_id: int = None,
) -> dict:
    """
    Export referral and commission data to CSV.
    """
    try:
        from datetime import datetime, timedelta
        logger.info(f"📤 Exporting referral report ({start_date} to {end_date})...")

        rows = []
        filename = ''

        try:
            from referrals.models import Referral, ReferralCommission
            from django.db.models import Sum

            qs = Referral.objects.select_related('referrer', 'referred_user').all()

            if start_date:
                dt = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
                qs = qs.filter(created_at__gte=dt)

            if end_date:
                dt = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d')) + timedelta(days=1)
                qs = qs.filter(created_at__lt=dt)

            headers = [
                'id', 'referrer_id', 'referrer_username',
                'referred_user_id', 'referred_username',
                'bonus_paid', 'bonus_amount', 'created_at',
            ]

            for obj in qs.iterator(chunk_size=500):
                rows.append({
                    'id': obj.pk,
                    'referrer_id': obj.referrer_id,
                    'referrer_username': obj.referrer.username if obj.referrer else '',
                    'referred_user_id': obj.referred_user_id,
                    'referred_username': obj.referred_user.username if obj.referred_user else '',
                    'bonus_paid': obj.bonus_paid,
                    'bonus_amount': str(obj.bonus_amount or Decimal('0')),
                    'created_at': obj.created_at.isoformat() if obj.created_at else '',
                })

            filename = f"referral_report_{uuid.uuid4().hex[:8]}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            _save_csv(rows, headers, filename)

            if requester_user_id:
                notify_export_ready.apply_async(
                    kwargs={
                        'user_id': requester_user_id,
                        'export_type': 'referral_report',
                        'filename': filename,
                        'row_count': len(rows),
                    }
                )

        except ImportError as e:
            logger.warning(f"[WARN] Referral models not available: {e}")

        result = {
            'status': 'success',
            'filename': filename,
            'row_count': len(rows),
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Referral report exported: {len(rows)} rows → {filename}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] export_referral_report failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# notify_export_ready
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    name='tasks.export_tasks.notify_export_ready',
)
def notify_export_ready(
    self,
    user_id: int,
    export_type: str,
    filename: str,
    row_count: int = 0,
) -> dict:
    """
    Notify a user that their export is ready for download.
    Sends an in-app notification and an email.
    """
    try:
        logger.info(f"📧 Notifying user {user_id} that export is ready: {filename}")

        title   = 'Export Ready for Download 📊'
        message = (
            f'Your {export_type.replace("_", " ").title()} export is ready. '
            f'{row_count} records exported. '
            f'File: {filename}'
        )

        try:
            from api.tasks.notification_tasks import dispatch_in_app_notification, send_email_notification

            dispatch_in_app_notification.apply_async(
                kwargs={
                    'user_id': user_id,
                    'title': title,
                    'message': message,
                    'notification_type': 'info',
                    'action_url': f'/exports/{filename}',
                    'metadata': {
                        'export_type': export_type,
                        'filename': filename,
                        'row_count': row_count,
                    },
                }
            )

            send_email_notification.apply_async(
                kwargs={
                    'user_id': user_id,
                    'subject': f'Your {export_type} export is ready',
                    'message': message,
                }
            )

        except ImportError as e:
            logger.warning(f"[WARN] Notification tasks not available: {e}")

        return {
            'status': 'success',
            'user_id': user_id,
            'export_type': export_type,
            'filename': filename,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] notify_export_ready failed: {exc}")
        raise self.retry(exc=exc)
