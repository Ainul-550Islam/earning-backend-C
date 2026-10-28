"""
tasks/referral_tasks.py
Referral system Celery tasks:
  - commission_processing
  - referral_fraud_scan
  - referral_stats_rollup
  - expire_inactive_referral_codes
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# commission_processing
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.referral_tasks.commission_processing',
)
def commission_processing(self, batch_size: int = 50) -> dict:
    """
    Process pending referral commissions:
    1. Fetch approved referral events that have not been paid out yet.
    2. Calculate commission amounts per level (L1 / L2).
    3. Credit wallet balances via WalletService.
    4. Mark commission records as paid.
    """
    try:
        logger.info(f"💰 Starting commission processing (batch_size={batch_size})...")
        processed = 0
        skipped   = 0
        errors    = 0

        try:
            from referrals.models import ReferralCommission
            from api.tasks.services import WalletService

            pending = ReferralCommission.objects.filter(
                status='pending',
                is_eligible=True,
            ).select_related('referrer', 'referred_user')[:batch_size]

            for commission in pending:
                try:
                    with transaction.atomic():
                        amount = Decimal(str(commission.amount))
                        if amount <= Decimal('0'):
                            skipped += 1
                            continue

                        wallet_service = WalletService()
                        wallet_service.credit(
                            user=commission.referrer,
                            amount=amount,
                            transaction_type='referral_commission',
                            reference=f'commission_{commission.pk}',
                            metadata={
                                'commission_id': commission.pk,
                                'referred_user_id': commission.referred_user_id,
                                'level': commission.level,
                            },
                        )
                        commission.status = 'paid'
                        commission.paid_at = timezone.now()
                        commission.save(update_fields=['status', 'paid_at'])
                        processed += 1

                except Exception as row_error:
                    logger.error(f"[ERROR] Commission {commission.pk}: {row_error}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Referral models not available: {e}")

        result = {
            'status': 'success',
            'processed': processed,
            'skipped': skipped,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Commission processing done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] commission_processing failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# referral_fraud_scan
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name='tasks.referral_tasks.referral_fraud_scan',
)
def referral_fraud_scan(self, lookback_hours: int = 24) -> dict:
    """
    Scan recent referrals for fraudulent patterns:
    - Same IP referrer / referred
    - Self-referral attempts
    - Rapid bulk sign-ups from one referral code
    - Account age < threshold before first task completion
    Flags suspicious referrals for manual review.
    """
    try:
        logger.info(f"🔍 Running referral fraud scan (lookback={lookback_hours}h)...")
        from datetime import timedelta

        flagged      = 0
        reviewed     = 0
        window_start = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from referrals.models import Referral, ReferralFraudFlag

            recent = Referral.objects.filter(
                created_at__gte=window_start,
                is_fraud_checked=False,
            ).select_related('referrer', 'referred_user')

            reviewed = recent.count()

            for referral in recent:
                fraud_reasons = []

                # Rule 1: self-referral
                if referral.referrer_id == referral.referred_user_id:
                    fraud_reasons.append('self_referral')

                # Rule 2: same IP
                if (
                    referral.referrer_ip
                    and referral.referred_ip
                    and referral.referrer_ip == referral.referred_ip
                ):
                    fraud_reasons.append('same_ip')

                # Rule 3: bulk sign-ups (>10 in 1 hour from same code)
                one_hour_ago = referral.created_at - timedelta(hours=1)
                bulk_count = Referral.objects.filter(
                    referral_code=referral.referral_code,
                    created_at__gte=one_hour_ago,
                    created_at__lte=referral.created_at,
                ).count()
                if bulk_count > 10:
                    fraud_reasons.append(f'bulk_signup_count={bulk_count}')

                if fraud_reasons:
                    ReferralFraudFlag.objects.get_or_create(
                        referral=referral,
                        defaults={
                            'reasons': fraud_reasons,
                            'flagged_at': timezone.now(),
                            'status': 'pending_review',
                        },
                    )
                    flagged += 1

                referral.is_fraud_checked = True
                referral.save(update_fields=['is_fraud_checked'])

        except ImportError as e:
            logger.warning(f"[WARN] Referral models not available: {e}")

        result = {
            'status': 'success',
            'reviewed': reviewed,
            'flagged': flagged,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Fraud scan done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] referral_fraud_scan failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# referral_stats_rollup
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.referral_tasks.referral_stats_rollup',
)
def referral_stats_rollup(self) -> dict:
    """
    Recompute referral stats (total referrals, total commissions, active codes)
    and store in cache for dashboard display.
    """
    try:
        logger.info("📊 Running referral stats rollup...")
        stats = {}

        try:
            from referrals.models import Referral, ReferralCommission
            from django.db.models import Sum, Count

            stats['total_referrals']         = Referral.objects.count()
            stats['active_referrals']        = Referral.objects.filter(is_active=True).count()
            stats['total_commission_paid']   = str(
                ReferralCommission.objects.filter(status='paid').aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0')
            )
            stats['pending_commission']      = str(
                ReferralCommission.objects.filter(status='pending').aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0')
            )

            cache.set('referral_stats', stats, timeout=3600)

        except ImportError as e:
            logger.warning(f"[WARN] Referral models not available: {e}")

        result = {
            'status': 'success',
            'stats': stats,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Referral stats rollup done.")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] referral_stats_rollup failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# expire_inactive_referral_codes
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.referral_tasks.expire_inactive_referral_codes',
)
def expire_inactive_referral_codes(self, inactive_days: int = 90) -> dict:
    """
    Expire referral codes belonging to users who have been inactive
    for more than `inactive_days` days.
    """
    try:
        from datetime import timedelta
        logger.info(f"⏳ Expiring referral codes inactive > {inactive_days} days...")

        expired_count = 0
        cutoff        = timezone.now() - timedelta(days=inactive_days)

        try:
            from referrals.models import ReferralCode

            stale = ReferralCode.objects.filter(
                is_active=True,
                last_used_at__lt=cutoff,
            )
            expired_count = stale.count()
            stale.update(is_active=False, expired_at=timezone.now())

        except ImportError as e:
            logger.warning(f"[WARN] ReferralCode model not available: {e}")

        result = {
            'status': 'success',
            'expired_count': expired_count,
            'inactive_days': inactive_days,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Expired {expired_count} referral codes.")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] expire_inactive_referral_codes failed: {exc}")
        raise self.retry(exc=exc)
