"""
tasks/kyc_tasks.py
KYC (Know Your Customer) & identity verification Celery tasks:
  - check_kyc_verification_status  — poll KYC provider for status updates
  - auto_approve_basic_kyc         — auto-approve low-risk accounts
  - remind_kyc_incomplete          — remind users with pending KYC
  - expire_failed_kyc              — expire KYC attempts past deadline
  - update_kyc_limits              — adjust withdrawal limits by KYC tier
  - run_enhanced_due_diligence     — EDD for high-value accounts
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

KYC_STATUS_CACHE_TTL = 3600

# KYC tiers → withdrawal limits
KYC_WITHDRAWAL_LIMITS = {
    'none':     Decimal('10'),
    'basic':    Decimal('100'),
    'standard': Decimal('500'),
    'full':     Decimal('5000'),
}


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='tasks.kyc_tasks.check_kyc_verification_status')
def check_kyc_verification_status(self, batch_size: int = 50) -> dict:
    """
    Poll the KYC provider API for status updates on pending verifications.
    Updates local KYC records and adjusts user limits accordingly.
    """
    try:
        from django.conf import settings
        logger.info("📋 Checking KYC verification status...")

        updated  = 0
        approved = 0
        rejected = 0

        try:
            from users.models import KYCVerification

            pending = KYCVerification.objects.filter(
                status='pending',
                provider_reference__isnull=False,
            ).exclude(provider_reference='')[:batch_size]

            for kyc in pending:
                try:
                    # Poll provider (Jumio, Onfido, Sumsub, etc.)
                    provider = getattr(settings, 'KYC_PROVIDER', 'sumsub')
                    status   = _poll_kyc_provider(kyc.provider_reference, provider)

                    if status == 'approved':
                        kyc.status      = 'approved'
                        kyc.approved_at = timezone.now()
                        kyc.save(update_fields=['status', 'approved_at'])
                        _apply_kyc_limits(kyc.user, 'standard')
                        approved += 1

                    elif status == 'rejected':
                        kyc.status      = 'rejected'
                        kyc.rejected_at = timezone.now()
                        kyc.save(update_fields=['status', 'rejected_at'])
                        rejected += 1

                    updated += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] KYC check for {kyc.pk}: {row_err}")

        except ImportError as e:
            logger.warning(f"[WARN] KYC models not available: {e}")

        result = {
            'status': 'success',
            'message': 'KYC check completed',
            'timestamp': timezone.now().isoformat(),
            'updated': updated,
            'approved': approved,
            'rejected': rejected,
        }
        logger.info(f"[OK] KYC check done: {approved} approved, {rejected} rejected")
        return result

    except Exception as e:
        logger.error(f"[ERROR] check_kyc_verification_status: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.kyc_tasks.auto_approve_basic_kyc')
def auto_approve_basic_kyc(self) -> dict:
    """
    Auto-approve basic KYC for low-risk accounts that meet criteria:
    - Account age > 7 days
    - At least 5 task completions
    - No fraud flags
    - Email verified
    """
    try:
        from datetime import timedelta
        from django.db.models import Count
        from django.contrib.auth import get_user_model
        logger.info("✅ Running auto-approve basic KYC...")

        User      = get_user_model()
        approved  = 0
        cutoff    = timezone.now() - timedelta(days=7)

        try:
            from users.models import KYCVerification
            from api.tasks.models import UserTaskCompletion

            # Users with 'none' KYC tier, old enough account, email verified
            candidates = User.objects.filter(
                date_joined__lt=cutoff,
                is_active=True,
                emailaddress__verified=True,
            ).annotate(
                completion_count=Count('usertaskcompletion', filter=(
                    __import__('django.db.models', fromlist=['Q'])
                    .Q(usertaskcompletion__status='completed')
                ))
            ).filter(completion_count__gte=5)

            for user in candidates.iterator(chunk_size=100):
                # Check no fraud flag
                fraud_score = cache.get(f'fraud_score_{user.pk}', 0)
                if fraud_score >= 40:
                    continue

                kyc_qs = KYCVerification.objects.filter(user=user)
                if not kyc_qs.exists():
                    KYCVerification.objects.create(
                        user=user,
                        status='approved',
                        tier='basic',
                        approved_at=timezone.now(),
                        method='auto',
                    )
                    _apply_kyc_limits(user, 'basic')
                    approved += 1

        except ImportError as e:
            logger.warning(f"[WARN] KYC/User models not available: {e}")

        result = {
            'status': 'success',
            'approved': approved,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Auto-approve KYC done: {approved} approved")
        return result

    except Exception as e:
        logger.error(f"[ERROR] auto_approve_basic_kyc: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.kyc_tasks.remind_kyc_incomplete')
def remind_kyc_incomplete(self, reminder_days: int = 3) -> dict:
    """
    Send reminder notifications to users who started but haven't completed KYC.
    Only reminds once every reminder_days days.
    """
    try:
        from datetime import timedelta
        logger.info(f"📧 Sending KYC reminder notifications (reminder_days={reminder_days})...")

        reminded = 0
        cutoff   = timezone.now() - timedelta(days=reminder_days)

        try:
            from users.models import KYCVerification
            from api.tasks.notification_tasks import send_email_notification, dispatch_in_app_notification

            incomplete = KYCVerification.objects.filter(
                status__in=['pending', 'started'],
                last_reminder_at__lt=cutoff,
            ).select_related('user')

            for kyc in incomplete:
                title   = 'Complete Your KYC Verification 🔐'
                message = (
                    'Your identity verification is incomplete. '
                    'Complete it now to unlock higher withdrawal limits.'
                )
                dispatch_in_app_notification.apply_async(kwargs={
                    'user_id': kyc.user_id,
                    'title': title,
                    'message': message,
                    'notification_type': 'warning',
                    'action_url': '/account/kyc/',
                })
                send_email_notification.apply_async(kwargs={
                    'user_id': kyc.user_id,
                    'subject': title,
                    'message': message,
                })
                kyc.last_reminder_at = timezone.now()
                kyc.save(update_fields=['last_reminder_at'])
                reminded += 1

        except ImportError as e:
            logger.warning(f"[WARN] KYC models not available: {e}")

        result = {
            'status': 'success',
            'reminded': reminded,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] KYC reminders sent: {reminded}")
        return result

    except Exception as e:
        logger.error(f"[ERROR] remind_kyc_incomplete: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.kyc_tasks.expire_failed_kyc')
def expire_failed_kyc(self, expiry_days: int = 30) -> dict:
    """Expire KYC verification attempts older than expiry_days without approval."""
    try:
        from datetime import timedelta
        logger.info(f"⏰ Expiring stale KYC verifications (>{expiry_days} days)...")
        expired = 0
        cutoff  = timezone.now() - timedelta(days=expiry_days)

        try:
            from users.models import KYCVerification
            stale = KYCVerification.objects.filter(
                status='pending',
                created_at__lt=cutoff,
            )
            expired = stale.update(status='expired', expired_at=timezone.now())
        except ImportError as e:
            logger.warning(f"[WARN] KYC model not available: {e}")

        result = {
            'status': 'success',
            'expired': expired,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Expired {expired} stale KYC verifications")
        return result

    except Exception as e:
        logger.error(f"[ERROR] expire_failed_kyc: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.kyc_tasks.update_kyc_limits')
def update_kyc_limits(self) -> dict:
    """
    Sync all user withdrawal limits with their current KYC tier.
    Runs nightly to correct any drift.
    """
    try:
        logger.info("🔄 Updating KYC-based withdrawal limits...")
        updated = 0

        try:
            from users.models import KYCVerification
            from wallet.models import Wallet

            for kyc in KYCVerification.objects.filter(status='approved').select_related('user'):
                tier  = getattr(kyc, 'tier', 'basic')
                limit = KYC_WITHDRAWAL_LIMITS.get(tier, Decimal('100'))
                Wallet.objects.filter(user=kyc.user).update(
                    daily_withdrawal_limit=limit
                )
                updated += 1

        except ImportError as e:
            logger.warning(f"[WARN] KYC/Wallet models not available: {e}")

        result = {
            'status': 'success',
            'updated': updated,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] KYC limits updated for {updated} users")
        return result

    except Exception as e:
        logger.error(f"[ERROR] update_kyc_limits: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='tasks.kyc_tasks.run_enhanced_due_diligence')
def run_enhanced_due_diligence(self, lookback_days: int = 7) -> dict:
    """
    Run Enhanced Due Diligence (EDD) for high-value accounts:
    - Users with large total withdrawals
    - Users flagged by fraud detection
    Flags accounts for manual review by compliance team.
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum
        logger.info("🔬 Running Enhanced Due Diligence (EDD)...")

        flagged  = 0
        reviewed = 0
        cutoff   = timezone.now() - timedelta(days=lookback_days)

        try:
            from wallet.models import Withdrawal
            from django.db.models import Sum

            high_value = (
                Withdrawal.objects.filter(
                    created_at__gte=cutoff, status='completed'
                )
                .values('user_id')
                .annotate(total=Sum('amount'))
                .filter(total__gt=Decimal('500'))
            )

            for row in high_value:
                reviewed += 1
                fraud_score = cache.get(f'fraud_score_{row["user_id"]}', 0)
                if fraud_score >= 30:
                    flagged += 1
                    logger.warning(
                        f"[EDD] User {row['user_id']} flagged: "
                        f"total_withdrawal={row['total']} fraud_score={fraud_score}"
                    )

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'reviewed': reviewed,
            'flagged': flagged,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] EDD done: {reviewed} reviewed, {flagged} flagged")
        return result

    except Exception as e:
        logger.error(f"[ERROR] run_enhanced_due_diligence: {e}")
        raise self.retry(exc=e)


# ── Private helpers ────────────────────────────────────────────────────────

def _poll_kyc_provider(reference: str, provider: str) -> str:
    """Poll KYC provider API for verification status. Returns 'approved'|'rejected'|'pending'."""
    try:
        import requests
        from django.conf import settings

        if provider == 'sumsub':
            url     = f"https://api.sumsub.com/resources/applicants/{reference}/requiredIdDocsStatus"
            headers = {'X-App-Token': getattr(settings, 'SUMSUB_APP_TOKEN', '')}
            resp    = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('reviewStatus', 'pending')

        elif provider == 'onfido':
            url     = f"https://api.onfido.com/v3.5/checks/{reference}"
            headers = {'Authorization': f"Token token={getattr(settings, 'ONFIDO_API_TOKEN', '')}"}
            resp    = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data   = resp.json()
                result = data.get('result', 'clear')
                return 'approved' if result == 'clear' else 'rejected'

    except Exception as e:
        logger.debug(f"[DEBUG] KYC provider poll: {e}")

    return 'pending'


def _apply_kyc_limits(user, tier: str) -> None:
    """Apply withdrawal limits to a user based on their KYC tier."""
    limit = KYC_WITHDRAWAL_LIMITS.get(tier, Decimal('100'))
    try:
        from wallet.models import Wallet
        Wallet.objects.filter(user=user).update(daily_withdrawal_limit=limit)
    except ImportError:
        pass
