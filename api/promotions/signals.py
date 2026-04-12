# =============================================================================
# api/promotions/signals.py
# Django Signals — Model events এ automatic actions
# =============================================================================

import logging
from django.conf import settings
from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    TaskSubmission, Dispute, Campaign, EscrowWallet,
    AdminCommissionLog, UserReputation, CampaignAnalytics,
    ReferralCommissionLog, FraudReport, Blacklist,
)
from .choices import (
    SubmissionStatus, DisputeStatus, CampaignStatus,
    EscrowStatus, CommissionStatus, FraudAction,
)
from .constants import (
    NOTIFY_SUBMISSION_APPROVED, NOTIFY_SUBMISSION_REJECTED,
    NOTIFY_DISPUTE_RESOLVED, NOTIFY_CAMPAIGN_ENDED,
    BUDGET_LOW_THRESHOLD_PERCENT, NOTIFY_BUDGET_LOW,
    TASK_RECALCULATE_REPUTATION, TASK_DETECT_FRAUD,
    TASK_PROCESS_REFERRAL_PAYOUT,
)

logger = logging.getLogger('promotions.signals')


# =============================================================================
# ── TASK SUBMISSION SIGNALS ───────────────────────────────────────────────────
# =============================================================================

@receiver(pre_save, sender=TaskSubmission)
def track_submission_status_change(sender, instance, **kwargs):
    """Status change হলে previous status track করে।"""
    if instance.pk:
        try:
            old = TaskSubmission.objects.get(pk=instance.pk)
            instance._previous_status = old.status
        except TaskSubmission.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=TaskSubmission)
def on_submission_saved(sender, instance: TaskSubmission, created: bool, **kwargs):
    """Submission save হলে বিভিন্ন action নেয়।"""
    previous = getattr(instance, '_previous_status', None)
    current  = instance.status

    # ── নতুন submission তৈরি হলে ──────────────────────────────────────────
    if created:
        _update_analytics_on_submission(instance, 'new')
        # Async fraud detection
        transaction.on_commit(lambda: _trigger_fraud_detection(instance.pk))
        logger.info(f'New submission #{instance.pk} created for campaign #{instance.campaign_id}')
        return

    # ── Status পরিবর্তন হলে ───────────────────────────────────────────────
    if previous and previous != current:
        logger.info(f'Submission #{instance.pk} status: {previous} → {current}')

        if current == SubmissionStatus.APPROVED:
            _handle_submission_approved(instance)

        elif current == SubmissionStatus.REJECTED:
            _handle_submission_rejected(instance)


def _handle_submission_approved(submission: TaskSubmission):
    """Submission approve হলে reward, commission, analytics সব update করে।"""
    try:
        with transaction.atomic():
            # ১. Reward calculate করে assign করো
            reward = _calculate_reward(submission)
            if reward and not submission.reward_usd:
                TaskSubmission.objects.filter(pk=submission.pk).update(reward_usd=reward)
                submission.reward_usd = reward

            # ২. Admin commission log তৈরি করো
            _create_admin_commission_log(submission)

            # ৩. Escrow থেকে reward amount release করো
            _release_escrow_for_submission(submission)

            # ৪. User reputation update করো (async)
            transaction.on_commit(lambda: _schedule_reputation_update(submission.worker_id))

            # ৫. Referral commission process করো (async)
            transaction.on_commit(lambda: _trigger_referral_commission(submission.pk))

            # ৬. Analytics update করো
            _update_analytics_on_submission(submission, 'approved')

            # ৭. Notification পাঠাও (async)
            transaction.on_commit(lambda: _send_notification(
                user_id=submission.worker_id,
                notification_type=NOTIFY_SUBMISSION_APPROVED,
                context={'submission_id': submission.pk, 'reward_usd': str(submission.reward_usd or 0)},
            ))
    except Exception as e:
        logger.exception(f'Error handling approved submission #{submission.pk}: {e}')


def _handle_submission_rejected(submission: TaskSubmission):
    """Submission reject হলে analytics update ও notification পাঠায়।"""
    try:
        _update_analytics_on_submission(submission, 'rejected')
        transaction.on_commit(lambda: _schedule_reputation_update(submission.worker_id))
        transaction.on_commit(lambda: _send_notification(
            user_id=submission.worker_id,
            notification_type=NOTIFY_SUBMISSION_REJECTED,
            context={
                'submission_id': submission.pk,
                'reason': submission.review_note,
            },
        ))
    except Exception as e:
        logger.exception(f'Error handling rejected submission #{submission.pk}: {e}')


# =============================================================================
# ── DISPUTE SIGNALS ───────────────────────────────────────────────────────────
# =============================================================================

@receiver(pre_save, sender=Dispute)
def track_dispute_status_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Dispute.objects.get(pk=instance.pk)
            instance._previous_status = old.status
        except Dispute.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Dispute)
def on_dispute_saved(sender, instance: Dispute, created: bool, **kwargs):
    previous = getattr(instance, '_previous_status', None)
    current  = instance.status

    if created:
        # Submission status → disputed তে update করো
        TaskSubmission.objects.filter(pk=instance.submission_id).update(
            status=SubmissionStatus.DISPUTED
        )
        logger.info(f'Dispute #{instance.pk} created for submission #{instance.submission_id}')
        return

    if previous and previous != current:
        if current in (DisputeStatus.RESOLVED_APPROVED, DisputeStatus.RESOLVED_REJECTED):
            _handle_dispute_resolved(instance, current)


def _handle_dispute_resolved(dispute: Dispute, outcome: str):
    """Dispute resolve হলে submission final status update করে।"""
    try:
        with transaction.atomic():
            if outcome == DisputeStatus.RESOLVED_APPROVED:
                submission = dispute.submission
                submission.approve(reviewer=dispute.resolved_by, note='Dispute resolved in favor of worker.')
            else:
                submission = dispute.submission
                submission.reject(
                    reviewer=dispute.resolved_by,
                    note=dispute.admin_note or 'Dispute resolved against worker.',
                )

            transaction.on_commit(lambda: _send_notification(
                user_id=dispute.worker_id,
                notification_type=NOTIFY_DISPUTE_RESOLVED,
                context={
                    'dispute_id': dispute.pk,
                    'outcome': outcome,
                    'admin_note': dispute.admin_note,
                },
            ))
    except Exception as e:
        logger.exception(f'Error resolving dispute #{dispute.pk}: {e}')


# =============================================================================
# ── CAMPAIGN SIGNALS ──────────────────────────────────────────────────────────
# =============================================================================

@receiver(pre_save, sender=Campaign)
def track_campaign_status_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Campaign.all_objects.get(pk=instance.pk)
            instance._previous_status = old.status
            instance._previous_spent  = old.spent_usd
        except Campaign.DoesNotExist:
            instance._previous_status = None
            instance._previous_spent  = Decimal('0')
    else:
        instance._previous_status = None
        instance._previous_spent  = Decimal('0')


@receiver(post_save, sender=Campaign)
def on_campaign_saved(sender, instance: Campaign, created: bool, **kwargs):
    previous_status = getattr(instance, '_previous_status', None)
    previous_spent  = getattr(instance, '_previous_spent', Decimal('0'))

    if created:
        # Escrow wallet তৈরি করো
        EscrowWallet.objects.get_or_create(
            campaign=instance,
            defaults={
                'advertiser': instance.advertiser,
                'locked_amount_usd': instance.total_budget_usd,
            },
        )
        logger.info(f'Campaign #{instance.pk} created, escrow locked: ${instance.total_budget_usd}')
        return

    # Status পরিবর্তন হলে
    if previous_status and previous_status != instance.status:
        logger.info(f'Campaign #{instance.pk} status: {previous_status} → {instance.status}')

        if instance.status == CampaignStatus.COMPLETED:
            _handle_campaign_completed(instance)

        elif instance.status == CampaignStatus.CANCELLED:
            _handle_campaign_cancelled(instance)

    # Budget low warning
    if instance.total_budget_usd > 0:
        remaining_pct = (instance.spent_usd / instance.total_budget_usd) * 100
        if remaining_pct >= (100 - BUDGET_LOW_THRESHOLD_PERCENT):
            if previous_spent < instance.spent_usd:  # নতুন খরচ হয়েছে
                transaction.on_commit(lambda: _send_notification(
                    user_id=instance.advertiser_id,
                    notification_type=NOTIFY_BUDGET_LOW,
                    context={'campaign_id': instance.pk, 'remaining_pct': float(100 - remaining_pct)},
                ))


def _handle_campaign_completed(campaign: Campaign):
    """Campaign complete হলে remaining escrow refund করে।"""
    try:
        with transaction.atomic():
            escrow = EscrowWallet.objects.select_for_update().get(campaign=campaign)
            if escrow.remaining_amount_usd > 0:
                escrow.status = EscrowStatus.REFUNDED
                escrow.released_at = timezone.now()
                escrow.save(update_fields=['status', 'released_at'])
                logger.info(
                    f'Campaign #{campaign.pk} completed. '
                    f'Escrow refunded: ${escrow.remaining_amount_usd}'
                )
    except EscrowWallet.DoesNotExist:
        logger.warning(f'No escrow found for completed campaign #{campaign.pk}')
    except Exception as e:
        logger.exception(f'Error completing campaign #{campaign.pk}: {e}')


def _handle_campaign_cancelled(campaign: Campaign):
    """Campaign cancel হলে সব escrow refund করে।"""
    _handle_campaign_completed(campaign)  # Same logic


# =============================================================================
# ── FRAUD REPORT SIGNALS ──────────────────────────────────────────────────────
# =============================================================================

@receiver(post_save, sender=FraudReport)
def on_fraud_report_saved(sender, instance: FraudReport, created: bool, **kwargs):
    if not created:
        return
    # High confidence fraud → auto-flag device
    if (
        instance.confidence_score and
        instance.confidence_score >= Decimal('90') and
        instance.action_taken == FraudAction.FLAGGED
    ):
        if instance.submission and instance.submission.device_fingerprint_id:
            from .models import DeviceFingerprint
            DeviceFingerprint.objects.filter(
                pk=instance.submission.device_fingerprint_id
            ).update(is_flagged=True, flag_reason=f'Auto-flagged: FraudReport #{instance.pk}')
            logger.warning(
                f'Device #{instance.submission.device_fingerprint_id} '
                f'auto-flagged due to high-confidence fraud report #{instance.pk}'
            )


# =============================================================================
# ── BLACKLIST SIGNALS ─────────────────────────────────────────────────────────
# =============================================================================

@receiver(post_save, sender=Blacklist)
def on_blacklist_saved(sender, instance: Blacklist, created: bool, **kwargs):
    if not created:
        return
    # User blacklisted হলে active sessions invalidate করো
    if instance.type == 'user' and instance.severity in ('temp_ban', 'permanent'):
        transaction.on_commit(lambda: _invalidate_user_sessions(instance.value))
        logger.warning(f'User {instance.value} blacklisted: {instance.severity}')


# =============================================================================
# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────
# =============================================================================

def _calculate_reward(submission: TaskSubmission) -> Decimal | None:
    """Submission এর জন্য reward calculate করে।"""
    try:
        from .models import RewardPolicy
        worker_country = _get_user_country(submission.worker_id)
        policy = RewardPolicy.objects.filter(
            country_code=worker_country,
            category=submission.campaign.category,
            is_active=True,
        ).first()
        if policy:
            return policy.rate_usd
        # Fallback to default policy
        fallback = RewardPolicy.objects.filter(
            country_code='US',
            category=submission.campaign.category,
            is_active=True,
        ).first()
        return fallback.rate_usd if fallback else None
    except Exception as e:
        logger.exception(f'Error calculating reward for submission #{submission.pk}: {e}')
        return None


def _create_admin_commission_log(submission: TaskSubmission):
    """Admin commission log তৈরি করে।"""
    if not submission.reward_usd:
        return
    try:
        profit_margin     = submission.campaign.profit_margin or Decimal('30')
        commission_rate   = profit_margin / 100
        gross             = submission.reward_usd / (1 - commission_rate)
        commission        = gross - submission.reward_usd

        AdminCommissionLog.objects.get_or_create(
            submission=submission,
            defaults={
                'campaign':           submission.campaign,
                'gross_amount_usd':   gross,
                'worker_reward_usd':  submission.reward_usd,
                'commission_usd':     commission,
                'commission_rate':    profit_margin,
            },
        )
    except Exception as e:
        logger.exception(f'Error creating commission log for submission #{submission.pk}: {e}')


def _release_escrow_for_submission(submission: TaskSubmission):
    """Approved submission এর reward amount escrow থেকে release করে।"""
    if not submission.reward_usd:
        return
    try:
        escrow = EscrowWallet.objects.select_for_update().get(
            campaign=submission.campaign,
            status__in=[EscrowStatus.LOCKED, EscrowStatus.PARTIALLY_RELEASED],
        )
        escrow.release(submission.reward_usd + (submission.bonus_usd or Decimal('0')))
    except EscrowWallet.DoesNotExist:
        logger.warning(f'No active escrow for campaign #{submission.campaign_id}')
    except Exception as e:
        logger.exception(f'Error releasing escrow for submission #{submission.pk}: {e}')


def _update_analytics_on_submission(submission: TaskSubmission, event_type: str):
    """CampaignAnalytics দৈনিক record update করে।"""
    try:
        today = timezone.now().date()
        analytics, _ = CampaignAnalytics.objects.get_or_create(
            campaign=submission.campaign,
            date=today,
        )
        from django.db.models import F
        if event_type == 'new':
            CampaignAnalytics.objects.filter(pk=analytics.pk).update(
                total_submissions=F('total_submissions') + 1
            )
        elif event_type == 'approved':
            CampaignAnalytics.objects.filter(pk=analytics.pk).update(
                approved_count=F('approved_count') + 1,
                total_spent_usd=F('total_spent_usd') + (submission.reward_usd or 0),
            )
        elif event_type == 'rejected':
            CampaignAnalytics.objects.filter(pk=analytics.pk).update(
                rejected_count=F('rejected_count') + 1
            )
    except Exception as e:
        logger.exception(f'Error updating analytics for submission #{submission.pk}: {e}')


def _schedule_reputation_update(user_id: int):
    """User reputation async update করে (Celery task)।"""
    try:
        from .tasks import recalculate_user_reputation
        recalculate_user_reputation.delay(user_id)
    except Exception as e:
        logger.exception(f'Error scheduling reputation update for user #{user_id}: {e}')


def _trigger_fraud_detection(submission_id: int):
    """Fraud detection Celery task trigger করে।"""
    try:
        from .tasks import detect_fraud_submission
        detect_fraud_submission.delay(submission_id)
    except Exception as e:
        logger.exception(f'Error triggering fraud detection for submission #{submission_id}: {e}')


def _trigger_referral_commission(submission_id: int):
    """Referral commission Celery task trigger করে।"""
    try:
        from .tasks import process_referral_payout
        process_referral_payout.delay(submission_id)
    except Exception as e:
        logger.exception(f'Error triggering referral commission for submission #{submission_id}: {e}')


def _send_notification(user_id: int, notification_type: str, context: dict):
    """Notification পাঠানোর placeholder — আপনার notification system অনুযায়ী implement করুন।"""
    try:
        # Example: from notifications.tasks import send_user_notification
        # send_user_notification.delay(user_id, notification_type, context)
        logger.info(f'Notification [{notification_type}] → User #{user_id} | context: {context}')
    except Exception as e:
        logger.exception(f'Error sending notification to user #{user_id}: {e}')


def _get_user_country(user_id: int) -> str:
    """User এর দেশ বের করে — আপনার User Profile model অনুযায়ী implement করুন।"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.select_related('profile').get(pk=user_id)
        return getattr(getattr(user, 'profile', None), 'country_code', 'US') or 'US'
    except Exception:
        return 'US'


def _invalidate_user_sessions(user_id_str: str):
    """Blacklisted user এর সব session invalidate করে।"""
    try:
        from django.contrib.sessions.models import Session
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(pk=int(user_id_str))
        # সব active session মুছে ফেলো
        Session.objects.filter(
            session_key__in=[
                s.session_key for s in Session.objects.all()
                if s.get_decoded().get('_auth_user_id') == str(user.pk)
            ]
        ).delete()
        logger.info(f'Sessions invalidated for blacklisted user #{user_id_str}')
    except Exception as e:
        logger.exception(f'Error invalidating sessions for user #{user_id_str}: {e}')


# =============================================================================
# NEW MODEL SIGNALS
# =============================================================================
from django.db.models.signals import post_save
from api.promotions.models import (
    PublisherProfile, EmailSubmitConversion, PayoutBatch,
    CPIAppCampaign, QuizCampaign,
)


@receiver(post_save, sender=settings.AUTH_USER_MODEL if hasattr(settings, 'AUTH_USER_MODEL') else 'auth.User')
def create_user_profiles(sender, instance, created, **kwargs):
    """Auto-create Publisher + Advertiser profiles on user registration."""
    if created:
        try:
            PublisherProfile.objects.get_or_create(user=instance)
        except Exception:
            pass


@receiver(post_save, sender=EmailSubmitConversion)
def on_email_submit_conversion(sender, instance, created, **kwargs):
    """When DOI email is confirmed — trigger payout."""
    if not created and instance.is_confirmed and instance.is_paid is False:
        try:
            from api.promotions.models import PromotionTransaction
            PromotionTransaction.objects.create(
                user=instance.publisher,
                transaction_type='reward',
                amount=instance.payout_amount,
                status='completed',
                notes=f'Email Submit DOI — Campaign #{instance.campaign_id}',
                metadata={'campaign_id': instance.campaign_id, 'type': 'email_submit_doi'},
            )
            instance.is_paid = True
            instance.paid_at = __import__('django.utils.timezone', fromlist=['now']).now()
            EmailSubmitConversion.objects.filter(pk=instance.pk).update(
                is_paid=True, paid_at=instance.paid_at
            )
        except Exception as e:
            logging.getLogger(__name__).error(f'Email submit payout signal failed: {e}')


@receiver(post_save, sender=PayoutBatch)
def on_payout_batch_status_change(sender, instance, created, **kwargs):
    """Send notification when payout status changes."""
    if not created:
        if instance.status == 'completed':
            try:
                profile = PublisherProfile.objects.filter(user=instance.publisher).first()
                if profile and profile.device_token_fcm:
                    from api.promotions.notifications.fcm_push import FCMPushNotification
                    FCMPushNotification().notify_payout_processed(
                        device_token=profile.device_token_fcm,
                        amount=str(instance.net_amount),
                        method=instance.method,
                    )
                if profile and profile.phone_number:
                    from api.promotions.notifications.sms_sender import SMSSender
                    SMSSender().send_payout_confirmation(
                        phone=profile.phone_number,
                        amount=str(instance.net_amount),
                        method=instance.method,
                    )
            except Exception:
                pass
