# api/offer_inventory/signals.py
"""
Django Signals — All offer_inventory signals.
Auto-triggered side effects for model events.
"""
import logging
from decimal import Decimal
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# CONVERSION SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.Conversion')
def on_conversion_created(sender, instance, created, **kwargs):
    """
    New conversion created:
    1. Trigger async analytics update
    2. Update offer completion count
    3. Update daily stats
    """
    if not created:
        return

    logger.info(f'Conversion created: {instance.id} | offer={instance.offer_id}')

    try:
        from api.offer_inventory.tasks import update_daily_stats
        update_daily_stats.delay(str(instance.id))
    except Exception as e:
        logger.error(f'Conversion analytics signal error: {e}')


@receiver(post_save, sender='offer_inventory.Conversion')
def on_conversion_approved(sender, instance, created, **kwargs):
    """
    When conversion is approved:
    1. Trigger payout
    2. Update user loyalty
    3. Update AI interest map
    4. Fire conversion pixel
    """
    if created:
        return

    if not (instance.status and instance.status.name == 'approved' and instance.approved_at):
        return

    # Check if this approval just happened (within last 30 seconds)
    if instance.approved_at and (timezone.now() - instance.approved_at).seconds > 30:
        return

    logger.info(f'Conversion approved: {instance.id}')

    # 1. Trigger payout async
    try:
        from api.offer_inventory.tasks import process_approved_conversion_payout
        process_approved_conversion_payout.delay(str(instance.id))
    except Exception as e:
        logger.error(f'Payout signal error: {e}')

    # 2. Loyalty points
    try:
        from api.offer_inventory.marketing.loyalty_program import LoyaltyManager
        if instance.user:
            LoyaltyManager.award_conversion_points(instance.user, instance)
    except Exception as e:
        logger.error(f'Loyalty signal error: {e}')

    # 3. AI interest update
    try:
        from api.offer_inventory.ai_optimization.ai_recommender import AIRecommender
        if instance.user and instance.offer:
            AIRecommender.update_interests_from_conversion(instance.user, instance.offer)
    except Exception as e:
        logger.error(f'AI interest signal error: {e}')

    # 4. Pixel fire
    try:
        from api.offer_inventory.tasks import fire_conversion_pixel
        fire_conversion_pixel.delay(str(instance.id))
    except Exception as e:
        logger.error(f'Pixel signal error: {e}')

    # 5. Referral mark converted (first conversion)
    try:
        from api.offer_inventory.tasks import check_and_mark_referral_converted
        if instance.user:
            check_and_mark_referral_converted.delay(str(instance.user_id))
    except Exception as e:
        logger.error(f'Referral conversion signal error: {e}')


# ══════════════════════════════════════════════════════
# CLICK SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.Click')
def on_click_saved(sender, instance, created, **kwargs):
    """
    New click:
    1. Bot/fraud risk update
    2. Bot velocity tracking
    """
    if not created:
        return

    # Update risk score for high-fraud clicks
    if instance.is_fraud and instance.user_id:
        try:
            from .repository import FraudRepository
            FraudRepository.update_risk_score(
                instance.user_id, score_delta=5, flag=True
            )
        except Exception as e:
            logger.error(f'Click fraud risk signal error: {e}')

    # Track velocity for bot detection
    if instance.ip_address:
        try:
            from api.offer_inventory.security_fraud.bot_detection import BotDetector
            BotDetector.record_click(instance.ip_address)
        except Exception as e:
            logger.error(f'Click velocity signal error: {e}')


# ══════════════════════════════════════════════════════
# WITHDRAWAL SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.WithdrawalRequest')
def on_withdrawal_status_change(sender, instance, created, **kwargs):
    """
    Withdrawal status change:
    Notify user with appropriate message per status.
    """
    if created:
        return   # Creation notification handled in service layer

    from .repository import NotificationRepository

    messages = {
        'approved' : ('✅ উইথড্রয়াল অনুমোদিত!',
                      f'আপনার {instance.net_amount} টাকা প্রক্রিয়া করা হচ্ছে।'),
        'completed': ('💰 পেমেন্ট সম্পন্ন!',
                      f'আপনার {instance.net_amount} টাকা {instance.payment_method.provider if instance.payment_method else "আপনার অ্যাকাউন্টে"} পৌঁছেছে।'),
        'rejected' : ('❌ উইথড্রয়াল বাতিল',
                      f'কারণ: {instance.rejected_reason or "কারণ দেওয়া হয়নি"}। টাকা ওয়ালেটে ফেরত এসেছে।'),
    }

    if instance.status in messages:
        title, body = messages[instance.status]
        try:
            NotificationRepository.create(
                user_id   =instance.user_id,
                notif_type='payment',
                title     =title,
                body      =body,
            )
        except Exception as e:
            logger.error(f'Withdrawal notification signal error: {e}')


# ══════════════════════════════════════════════════════
# FRAUD SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.FraudAttempt')
def on_fraud_attempt_created(sender, instance, created, **kwargs):
    """
    Fraud attempt logged:
    1. Check if user should be auto-suspended
    2. Alert admin if critical
    """
    if not created:
        return

    if not instance.user_id:
        return

    try:
        from .repository import FraudRepository
        profile = FraudRepository.get_user_risk_profile(instance.user_id)
        if profile and profile.risk_score >= 90 and not profile.is_suspended:
            profile.is_suspended      = True
            profile.suspension_reason = f'Auto-suspended: critical risk score {profile.risk_score:.1f}'
            profile.save(update_fields=['is_suspended', 'suspension_reason'])
            logger.warning(f'User auto-suspended: {instance.user_id} (score={profile.risk_score})')

            # Notify admin
            from .repository import NotificationRepository
            NotificationRepository.create(
                user_id   =None,
                notif_type='system',
                title     ='⚠️ User Auto-Suspended',
                body      =f'User ID {instance.user_id} suspended. Risk score: {profile.risk_score:.1f}',
            )
    except Exception as e:
        logger.error(f'Fraud attempt auto-suspend signal error: {e}')


# ══════════════════════════════════════════════════════
# OFFER SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.Offer')
def on_offer_status_change(sender, instance, created, **kwargs):
    """
    Offer status changed:
    1. Invalidate caches
    2. Notify if offer expired/paused
    """
    # Invalidate SmartLink and offer caches
    cache.delete(f'offer_avail:{instance.id}')
    cache.delete(f'offer_epc:{instance.id}')
    cache.delete(f'offers:detail:{instance.id}')

    if not created and instance.status in ('paused', 'expired'):
        logger.info(f'Offer {instance.id} → {instance.status}')


@receiver(post_save, sender='offer_inventory.OfferCap')
def on_offer_cap_updated(sender, instance, created, **kwargs):
    """Cap updated — invalidate availability cache."""
    cache.delete(f'offer_avail:{instance.offer_id}')


# ══════════════════════════════════════════════════════
# USER PROFILE SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.UserProfile')
def on_profile_updated(sender, instance, created, **kwargs):
    """Profile updated — invalidate user cache."""
    cache.delete(f'user_profile:{instance.user_id}')
    cache.delete_pattern(f'ai_rec:{instance.user_id}:*') if hasattr(cache, 'delete_pattern') else None


@receiver(post_save, sender='offer_inventory.UserKYC')
def on_kyc_status_change(sender, instance, created, **kwargs):
    """KYC approved/rejected — notify user."""
    if created:
        return

    from .repository import NotificationRepository

    messages = {
        'approved': ('✅ KYC যাচাই সম্পন্ন!',
                     'আপনার পরিচয় যাচাই সফল হয়েছে। এখন উইথড্রয়াল করতে পারবেন।'),
        'rejected': ('❌ KYC যাচাই ব্যর্থ',
                     f'কারণ: {instance.reject_reason or "ডকুমেন্ট পুনরায় জমা দিন"}।'),
        'resubmit': ('📋 KYC পুনরায় জমা দিন',
                     'আপনার KYC ডকুমেন্টে সমস্যা আছে। পুনরায় সঠিক ডকুমেন্ট জমা দিন।'),
    }

    if instance.status in messages:
        title, body = messages[instance.status]
        try:
            NotificationRepository.create(
                user_id   =instance.user_id,
                notif_type='info',
                title     =title,
                body      =body,
            )
        except Exception as e:
            logger.error(f'KYC notification signal error: {e}')


# ══════════════════════════════════════════════════════
# MASTER SWITCH SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.MasterSwitch')
def on_master_switch_toggled(sender, instance, created, **kwargs):
    """Feature flag changed — invalidate feature cache."""
    cache.delete(f'feature:{instance.tenant_id}:{instance.feature}')
    logger.info(
        f'Feature {"enabled" if instance.is_enabled else "disabled"}: '
        f'{instance.feature} | tenant={instance.tenant_id}'
    )


# ══════════════════════════════════════════════════════
# NETWORK SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.OfferNetwork')
def on_network_status_change(sender, instance, created, **kwargs):
    """Network status changed — invalidate circuit breaker."""
    if not created and instance.status != 'active':
        # Reset circuit breaker cache for this network
        cache.delete(f'cb_state:offerwall:{instance.slug}')
        cache.delete(f'cb_failures:offerwall:{instance.slug}')
        logger.info(f'Network {instance.slug} → {instance.status} | circuit reset')


# ══════════════════════════════════════════════════════
# WALLET SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.WalletTransaction')
def on_wallet_transaction(sender, instance, created, **kwargs):
    """Wallet transaction created — invalidate balance cache."""
    if created:
        cache.delete(f'wallet_balance:{instance.user_id}')
        # Invalidate notification unread count
        cache.delete(f'notif_unread:{instance.user_id}')


# ══════════════════════════════════════════════════════
# REFERRAL SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.UserReferral')
def on_referral_converted(sender, instance, created, **kwargs):
    """Referral marked as converted — award referrer bonus."""
    if created or not instance.is_converted:
        return

    try:
        from .repository import NotificationRepository
        NotificationRepository.create(
            user_id   =instance.referrer_id,
            notif_type='success',
            title     ='🎉 রেফারেল সফল!',
            body      =f'{instance.referred.username} আপনার রেফারেল লিংক থেকে যোগ দিয়েছে।',
        )
    except Exception as e:
        logger.error(f'Referral signal error: {e}')


# ══════════════════════════════════════════════════════
# NEW MODULE SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.Conversion')
def on_conversion_heatmap_update(sender, instance, created, **kwargs):
    """Update user activity heatmap on each conversion."""
    if not created or not instance.user:
        return
    try:
        from api.offer_inventory.user_behavior_analysis import ActivityHeatmapService
        ActivityHeatmapService.update_heatmap(instance.user, instance.created_at)
    except Exception as e:
        logger.debug(f'Heatmap update signal error: {e}')


@receiver(post_save, sender='offer_inventory.Conversion')
def on_conversion_webhook_fire(sender, instance, created, **kwargs):
    """Fire webhooks when a conversion is approved."""
    if created:
        return
    if instance.status and instance.status.name == 'approved' and instance.approved_at:
        try:
            from api.offer_inventory.webhooks import WebhookDispatcher
            WebhookDispatcher.fire_conversion_approved(
                instance, tenant=getattr(instance, 'tenant', None)
            )
        except Exception as e:
            logger.debug(f'Webhook signal error: {e}')


@receiver(post_save, sender='offer_inventory.WithdrawalRequest')
def on_withdrawal_completed_webhook(sender, instance, created, **kwargs):
    """Fire webhook when withdrawal is completed."""
    if created or instance.status != 'completed':
        return
    try:
        from api.offer_inventory.webhooks import WebhookDispatcher
        WebhookDispatcher.fire_withdrawal_completed(instance)
    except Exception as e:
        logger.debug(f'Withdrawal webhook signal error: {e}')


@receiver(post_save, sender='offer_inventory.Offer')
def on_offer_scheduled_activation(sender, instance, created, **kwargs):
    """When offer is created with future start, auto-schedule activation."""
    if not created:
        return
    if instance.starts_at and instance.starts_at > timezone.now() and instance.status == 'draft':
        try:
            from api.offer_inventory.affiliate_advanced import OfferSchedulerEngine
            OfferSchedulerEngine.schedule_activation(
                str(instance.id),
                instance.starts_at,
                instance.expires_at,
            )
        except Exception as e:
            logger.debug(f'Offer schedule signal error: {e}')


@receiver(post_save, sender='offer_inventory.FraudAttempt')
def on_fraud_webhook_fire(sender, instance, created, **kwargs):
    """Fire webhook on fraud detection."""
    if not created:
        return
    try:
        from api.offer_inventory.webhooks import WebhookDispatcher
        WebhookDispatcher.fire_fraud_detected(
            instance.user_id,
            instance.fraud_type if hasattr(instance, 'fraud_type') else 'unknown',
        )
    except Exception as e:
        logger.debug(f'Fraud webhook signal error: {e}')


# ══════════════════════════════════════════════════════
# RTB + PUBLISHER SIGNALS
# ══════════════════════════════════════════════════════

@receiver(post_save, sender='offer_inventory.Publisher')
def on_publisher_approved(sender, instance, created, **kwargs):
    """Welcome email when publisher is approved."""
    if not created and instance.status == 'active':
        try:
            from api.offer_inventory.notifications.email_alert_system import EmailAlertSystem
            EmailAlertSystem._send(
                [instance.contact_email],
                '✅ Publisher Account Approved',
                f'Dear {instance.company_name},\n\nYour publisher account has been approved.\n'
                f'API Key: {instance.api_key}\n\nStart integrating our SDK today!'
            )
            logger.info(f'Publisher approval email sent: {instance.contact_email}')
        except Exception as e:
            logger.debug(f'Publisher approval email error: {e}')


@receiver(post_save, sender='offer_inventory.BidLog')
def on_bid_win(sender, instance, created, **kwargs):
    """Update publisher revenue on bid win."""
    if created and instance.is_won and instance.clearing_price:
        try:
            from api.offer_inventory.models import Publisher
            from django.db.models import F
            Publisher.objects.filter(
                id=instance.publisher_id
            ).update(total_earned=F('total_earned') + (instance.clearing_price * Decimal('0.30')))
        except Exception as e:
            logger.debug(f'Publisher revenue update error: {e}')
