# =============================================================================
# api/promotions/tasks.py
# Celery Async Tasks — Background jobs
# =============================================================================

import logging
from decimal import Decimal
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

logger = logging.getLogger('promotions.tasks')


# =============================================================================
# ── CURRENCY RATES ────────────────────────────────────────────────────────────
# =============================================================================

@shared_task(
    name='promotions.tasks.sync_currency_rates',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='default',
)
def sync_currency_rates(self):
    """প্রতিদিন currency rates sync করে। Cron: daily at midnight UTC।"""
    from .models import CurrencyRate
    from .choices import RateSource
    import requests

    TARGET_CURRENCIES = ['BDT', 'INR', 'EUR', 'GBP', 'PKR', 'NPR', 'LKR']

    try:
        # OpenExchangeRates বা Fixer.io থেকে rates fetch করো
        # Demo: https://open.er-api.com/v6/latest/USD (free tier)
        response = requests.get(
            'https://open.er-api.com/v6/latest/USD',
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        rates = data.get('rates', {})

        created_count = 0
        for currency in TARGET_CURRENCIES:
            if currency in rates:
                CurrencyRate.objects.create(
                    from_currency='USD',
                    to_currency=currency,
                    rate=Decimal(str(rates[currency])),
                    source=RateSource.OPEN_EXCHANGE,
                )
                created_count += 1

        logger.info(f'Currency rates synced: {created_count} rates updated.')
        return {'synced': created_count, 'timestamp': str(timezone.now())}

    except requests.RequestException as exc:
        logger.error(f'Currency rate fetch failed: {exc}')
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception(f'Unexpected error syncing currency rates: {exc}')
        raise


# =============================================================================
# ── CAMPAIGN MANAGEMENT ───────────────────────────────────────────────────────
# =============================================================================

@shared_task(
    name='promotions.tasks.expire_old_campaigns',
    bind=True,
    queue='default',
)
def expire_old_campaigns(self):
    """Scheduled end_at পার হলে campaign auto-complete করে। Cron: every 15 mins।"""
    from .models import Campaign, CampaignSchedule
    from .choices import CampaignStatus

    now = timezone.now()
    expired_campaigns = Campaign.objects.filter(
        status=CampaignStatus.ACTIVE,
        schedule__end_at__lte=now,
    ).select_related('schedule')

    count = 0
    for campaign in expired_campaigns:
        try:
            with transaction.atomic():
                campaign.status = CampaignStatus.COMPLETED
                campaign.save(update_fields=['status', 'updated_at'])
                count += 1
                logger.info(f'Campaign #{campaign.pk} auto-completed (scheduled end).')
        except Exception as e:
            logger.exception(f'Error expiring campaign #{campaign.pk}: {e}')

    # Budget exhausted campaign pause করো
    budget_exhausted = Campaign.objects.filter(
        status=CampaignStatus.ACTIVE,
        schedule__auto_pause_on_budget_exhaust=True,
    ).filter(
        spent_usd__gte=F('total_budget_usd')
    )

    paused_count = 0
    for campaign in budget_exhausted:
        try:
            with transaction.atomic():
                campaign.status = CampaignStatus.PAUSED
                campaign.save(update_fields=['status', 'updated_at'])
                paused_count += 1
                logger.info(f'Campaign #{campaign.pk} auto-paused (budget exhausted).')
        except Exception as e:
            logger.exception(f'Error pausing campaign #{campaign.pk}: {e}')

    return {'expired': count, 'paused': paused_count}


@shared_task(
    name='promotions.tasks.activate_scheduled_campaigns',
    bind=True,
    queue='default',
)
def activate_scheduled_campaigns(self):
    """start_at পার হলে campaign auto-activate করে। Cron: every 5 mins।"""
    from .models import Campaign
    from .choices import CampaignStatus

    now = timezone.now()
    pending_campaigns = Campaign.objects.filter(
        status=CampaignStatus.PENDING,
        schedule__start_at__lte=now,
    )

    count = 0
    for campaign in pending_campaigns:
        try:
            with transaction.atomic():
                campaign.status = CampaignStatus.ACTIVE
                campaign.save(update_fields=['status', 'updated_at'])
                count += 1
                logger.info(f'Campaign #{campaign.pk} auto-activated.')
        except Exception as e:
            logger.exception(f'Error activating campaign #{campaign.pk}: {e}')

    return {'activated': count}


# =============================================================================
# ── USER REPUTATION ───────────────────────────────────────────────────────────
# =============================================================================

@shared_task(
    name='promotions.tasks.recalculate_user_reputation',
    bind=True,
    max_retries=3,
    queue='low_priority',
)
def recalculate_user_reputation(self, user_id: int):
    """User এর reputation এবং trust score recalculate করে।"""
    from .models import UserReputation, TaskSubmission
    from .choices import SubmissionStatus

    try:
        stats = TaskSubmission.objects.filter(worker_id=user_id).aggregate(
            total=Sum('id') - Sum('id') + F('id').count() if False else None,
        )
        # Simple count-based aggregation
        from django.db.models import Count
        counts = TaskSubmission.objects.filter(worker_id=user_id).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status=SubmissionStatus.APPROVED)),
            rejected=Count('id', filter=Q(status=SubmissionStatus.REJECTED)),
            disputed=Count('id', filter=Q(status=SubmissionStatus.DISPUTED)),
        )

        total    = counts['total'] or 0
        approved = counts['approved'] or 0
        rejected = counts['rejected'] or 0
        disputed = counts['disputed'] or 0

        # Success rate
        success_rate = Decimal('0')
        if total > 0:
            success_rate = (Decimal(approved) / Decimal(total) * 100).quantize(Decimal('0.01'))

        # Trust score algorithm (0-100)
        # Base score: success rate weighted
        base_score = float(success_rate) * 0.7
        # Volume bonus: max 15 points
        volume_bonus = min(total / 100 * 15, 15)
        # Dispute penalty
        dispute_penalty = min(disputed * 2, 20)
        trust_score = max(0, min(100, int(base_score + volume_bonus - dispute_penalty)))

        # Level calculation (1-100)
        level = max(1, min(100, total // 10 + 1))

        with transaction.atomic():
            reputation, created = UserReputation.objects.select_for_update().get_or_create(
                user_id=user_id,
                defaults={
                    'total_submissions': total,
                    'approved_count': approved,
                    'rejected_count': rejected,
                    'disputed_count': disputed,
                    'success_rate': success_rate,
                    'trust_score': trust_score,
                    'level': level,
                }
            )
            if not created:
                UserReputation.objects.filter(pk=reputation.pk).update(
                    total_submissions=total,
                    approved_count=approved,
                    rejected_count=rejected,
                    disputed_count=disputed,
                    success_rate=success_rate,
                    trust_score=trust_score,
                    level=level,
                    last_updated=timezone.now(),
                )

        logger.info(
            f'Reputation updated for user #{user_id}: '
            f'score={trust_score}, success_rate={success_rate}%, level={level}'
        )
        return {'user_id': user_id, 'trust_score': trust_score, 'level': level}

    except Exception as exc:
        logger.exception(f'Error recalculating reputation for user #{user_id}: {exc}')
        raise self.retry(exc=exc)


# =============================================================================
# ── FRAUD DETECTION ───────────────────────────────────────────────────────────
# =============================================================================

@shared_task(
    name='promotions.tasks.detect_fraud_submission',
    bind=True,
    max_retries=2,
    queue='high_priority',
    soft_time_limit=30,
)
def detect_fraud_submission(self, submission_id: int):
    """AI-based fraud detection চালায়।"""
    from .models import TaskSubmission, FraudReport, DeviceFingerprint, Blacklist
    from .choices import FraudType, FraudAction

    try:
        submission = TaskSubmission.objects.select_related(
            'campaign', 'worker', 'device_fingerprint'
        ).get(pk=submission_id)

        fraud_signals = []
        confidence    = Decimal('0')

        # ── Check 1: Duplicate IP submission ─────────────────────────────
        duplicate_ip_count = TaskSubmission.objects.filter(
            campaign=submission.campaign,
            ip_address=submission.ip_address,
        ).exclude(pk=submission.pk).count()

        if duplicate_ip_count > 0:
            fraud_signals.append({'type': FraudType.DUPLICATE_SUBMIT, 'signal': 'duplicate_ip'})
            confidence += Decimal('40')

        # ── Check 2: Device fingerprint linked to multiple accounts ───────
        if submission.device_fingerprint:
            fp = submission.device_fingerprint
            if fp.linked_account_count > 1:
                fraud_signals.append({'type': FraudType.ACCOUNT_FARMING, 'signal': 'multi_account_device'})
                confidence += Decimal('50')
            if fp.is_flagged:
                fraud_signals.append({'type': FraudType.ACCOUNT_FARMING, 'signal': 'flagged_device'})
                confidence += Decimal('30')

        # ── Check 3: IP Blacklisted ───────────────────────────────────────
        if submission.ip_address and Blacklist.is_blacklisted('ip', submission.ip_address):
            fraud_signals.append({'type': FraudType.VPN_DETECTED, 'signal': 'blacklisted_ip'})
            confidence += Decimal('70')

        # ── Check 4: Submission speed (too fast = bot) ────────────────────
        recent_submissions = TaskSubmission.objects.filter(
            worker=submission.worker,
            submitted_at__gte=submission.submitted_at - timedelta(minutes=5),
        ).count()
        if recent_submissions > 10:
            fraud_signals.append({'type': FraudType.BOT_ACTIVITY, 'signal': 'high_velocity'})
            confidence += Decimal('60')

        # Cap at 100
        confidence = min(confidence, Decimal('100'))

        if fraud_signals:
            action = FraudAction.BANNED if confidence >= 90 else \
                     FraudAction.FLAGGED if confidence >= 50 else \
                     FraudAction.WARNED

            for signal in fraud_signals:
                FraudReport.objects.create(
                    user=submission.worker,
                    submission=submission,
                    fraud_type=signal['type'],
                    ai_model_version='internal_v1.0',
                    confidence_score=confidence,
                    evidence={'signals': fraud_signals, 'ip': submission.ip_address},
                    action_taken=action,
                )

            logger.warning(
                f'Fraud detected for submission #{submission_id}: '
                f'confidence={confidence}%, action={action}'
            )

            # High confidence → auto-reject submission
            if confidence >= Decimal('85') and action == FraudAction.BANNED:
                with transaction.atomic():
                    TaskSubmission.objects.filter(pk=submission_id).update(
                        status='rejected',
                        review_note=f'Auto-rejected: Fraud detected (confidence: {confidence}%)',
                        reviewed_at=timezone.now(),
                    )

        return {'submission_id': submission_id, 'confidence': float(confidence), 'signals': len(fraud_signals)}

    except TaskSubmission.DoesNotExist:
        logger.warning(f'Submission #{submission_id} not found for fraud detection.')
    except Exception as exc:
        logger.exception(f'Error in fraud detection for submission #{submission_id}: {exc}')
        raise self.retry(exc=exc)


# =============================================================================
# ── REFERRAL COMMISSION ───────────────────────────────────────────────────────
# =============================================================================

@shared_task(
    name='promotions.tasks.process_referral_payout',
    bind=True,
    max_retries=3,
    queue='default',
)
def process_referral_payout(self, submission_id: int):
    """Approved submission থেকে referral commission distribute করে।"""
    from .models import TaskSubmission, ReferralCommissionLog, PromotionTransaction
    from .choices import CommissionStatus, TransactionType

    REFERRAL_RATES = {
        1: Decimal('5.00'),   # Level 1: 5%
        2: Decimal('2.00'),   # Level 2: 2%
        3: Decimal('1.00'),   # Level 3: 1%
    }

    try:
        submission = TaskSubmission.objects.select_related('worker', 'campaign').get(pk=submission_id)
        if not submission.reward_usd:
            return {'skipped': 'no reward'}

        # User এর referral chain বের করো (আপনার User model অনুযায়ী implement করুন)
        referral_chain = _get_referral_chain(submission.worker_id, max_levels=3)

        created_commissions = []
        for level, referrer_id in enumerate(referral_chain, start=1):
            if level not in REFERRAL_RATES:
                break
            rate       = REFERRAL_RATES[level]
            commission = (submission.reward_usd * rate / 100).quantize(Decimal('0.000001'))
            if commission <= Decimal('0'):
                continue

            with transaction.atomic():
                ref_log, created = ReferralCommissionLog.objects.get_or_create(
                    referrer_id=referrer_id,
                    referred_id=submission.worker_id,
                    source_submission=submission,
                    level=level,
                    defaults={
                        'commission_usd': commission,
                        'commission_rate': rate,
                        'status': CommissionStatus.PAID,
                        'paid_at': timezone.now(),
                    }
                )
                if created:
                    created_commissions.append({'level': level, 'referrer_id': referrer_id, 'amount': str(commission)})

        logger.info(f'Referral commissions for submission #{submission_id}: {created_commissions}')
        return {'submission_id': submission_id, 'commissions': created_commissions}

    except TaskSubmission.DoesNotExist:
        logger.warning(f'Submission #{submission_id} not found for referral payout.')
    except Exception as exc:
        logger.exception(f'Error processing referral payout for submission #{submission_id}: {exc}')
        raise self.retry(exc=exc)


# =============================================================================
# ── ANALYTICS ─────────────────────────────────────────────────────────────────
# =============================================================================

@shared_task(
    name='promotions.tasks.generate_daily_analytics',
    bind=True,
    queue='low_priority',
)
def generate_daily_analytics(self, date_str: str = None):
    """প্রতিদিনের analytics summary generate করে। Cron: daily at 00:05 UTC।"""
    from .models import Campaign, TaskSubmission, CampaignAnalytics, AdminCommissionLog
    from .choices import CampaignStatus, SubmissionStatus
    from django.db.models import Count, Sum, Avg

    target_date = (
        timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        if date_str
        else timezone.now().date() - timedelta(days=1)  # Yesterday
    )

    active_campaigns = Campaign.objects.filter(
        status__in=[CampaignStatus.ACTIVE, CampaignStatus.COMPLETED, CampaignStatus.PAUSED]
    )

    updated = 0
    for campaign in active_campaigns:
        try:
            day_submissions = TaskSubmission.objects.filter(
                campaign=campaign,
                submitted_at__date=target_date,
            ).aggregate(
                total=Count('id'),
                approved=Count('id', filter=Q(status=SubmissionStatus.APPROVED)),
                rejected=Count('id', filter=Q(status=SubmissionStatus.REJECTED)),
                disputed=Count('id', filter=Q(status=SubmissionStatus.DISPUTED)),
                spent=Sum('reward_usd', filter=Q(status=SubmissionStatus.APPROVED)),
                avg_time=Avg('id'),  # placeholder — real impl এ completion time track করুন
            )

            day_commissions = AdminCommissionLog.objects.filter(
                campaign=campaign,
                created_at__date=target_date,
            ).aggregate(total_commission=Sum('commission_usd'))

            CampaignAnalytics.objects.update_or_create(
                campaign=campaign,
                date=target_date,
                defaults={
                    'total_submissions': day_submissions['total'] or 0,
                    'approved_count': day_submissions['approved'] or 0,
                    'rejected_count': day_submissions['rejected'] or 0,
                    'disputed_count': day_submissions['disputed'] or 0,
                    'total_spent_usd': day_submissions['spent'] or Decimal('0'),
                    'admin_commission_usd': day_commissions['total_commission'] or Decimal('0'),
                },
            )
            updated += 1
        except Exception as e:
            logger.exception(f'Error generating analytics for campaign #{campaign.pk}: {e}')

    logger.info(f'Daily analytics generated for {target_date}: {updated} campaigns')
    return {'date': str(target_date), 'campaigns_updated': updated}


@shared_task(
    name='promotions.tasks.cleanup_expired_blacklists',
    bind=True,
    queue='low_priority',
)
def cleanup_expired_blacklists(self):
    """Expire হয়ে যাওয়া temp_ban গুলো deactivate করে। Cron: every hour।"""
    from .models import Blacklist

    now     = timezone.now()
    updated = Blacklist.objects.filter(
        severity='temp_ban',
        expires_at__lte=now,
        is_active=True,
    ).update(is_active=False)

    logger.info(f'Expired blacklist entries deactivated: {updated}')
    return {'deactivated': updated}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_referral_chain(user_id: int, max_levels: int = 3) -> list:
    """User এর referral chain বের করে। আপনার referral model অনুযায়ী implement করুন।"""
    chain = []
    # Placeholder — আপনার User model/ReferralLink model অনুযায়ী পরিবর্তন করুন
    # Example:
    # from users.models import ReferralLink
    # current_user_id = user_id
    # for _ in range(max_levels):
    #     ref = ReferralLink.objects.filter(referred_id=current_user_id).select_related('referrer').first()
    #     if not ref:
    #         break
    #     chain.append(ref.referrer_id)
    #     current_user_id = ref.referrer_id
    return chain


@shared_task(bind=True, max_retries=3)
def process_daily_auto_payouts(self):
    """
    Process daily automatic payouts for eligible publishers.
    Runs at 6 AM UTC via Celery Beat.
    Pays publishers with 'daily' schedule who have $1+ balance.
    """
    from api.promotions.models import PublisherProfile, PromotionTransaction, PayoutBatch
    from django.db.models import Sum
    from decimal import Decimal

    DAILY_MIN_PAYOUT = Decimal('1.00')
    processed = 0
    errors = 0

    daily_publishers = PublisherProfile.objects.filter(
        tier='platinum',        # Platinum = daily pay
        approval_status='approved',
    ).select_related('user')

    for profile in daily_publishers:
        try:
            balance = PromotionTransaction.objects.filter(
                user=profile.user,
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            if balance < DAILY_MIN_PAYOUT:
                continue

            # Check if already paid today
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            already_paid = PayoutBatch.objects.filter(
                publisher=profile.user,
                status='completed',
                processed_at__gte=today_start,
            ).exists()

            if already_paid:
                continue

            # Get default payout method (from publisher's settings)
            default_method = 'paypal'  # In production: from PublisherProfile
            PayoutBatch.objects.create(
                publisher=profile.user,
                amount=balance,
                method=default_method,
                method_details={},
                status='pending',
                fee=Decimal('0'),
                net_amount=balance,
                notes='Auto daily payout',
            )
            # Lock balance
            PromotionTransaction.objects.create(
                user=profile.user,
                transaction_type='withdrawal',
                amount=-balance,
                status='pending',
                notes=f'Auto daily payout ${balance}',
            )
            processed += 1
        except Exception as e:
            errors += 1
            import logging
            logging.getLogger(__name__).error(f'Daily payout failed for {profile.user_id}: {e}')

    return {'processed': processed, 'errors': errors, 'date': timezone.now().date().isoformat()}
