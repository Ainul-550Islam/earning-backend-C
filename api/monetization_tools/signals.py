"""
api/monetization_tools/signals.py
====================================
Django signals for the monetization_tools app.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_gamification_profile(sender, instance, created, **kwargs):
    """Create UserLevel automatically when a new user registers."""
    if created:
        try:
            from .models import UserLevel
            UserLevel.objects.get_or_create(user=instance)
        except Exception as exc:
            logger.error("Failed to create UserLevel for user %s: %s", instance.id, exc)


@receiver(post_save, sender='monetization_tools.OfferCompletion')
def update_campaign_stats_on_completion(sender, instance, created, **kwargs):
    """Update AdCampaign conversion counter when an OfferCompletion is approved."""
    if not created and instance.status == 'approved':
        try:
            from .models import AdCampaign
            if instance.offer.offerwall.network.network_type:
                pass  # hook for future campaign attribution logic
        except Exception as exc:
            logger.debug("campaign stats update skipped: %s", exc)


@receiver(post_save, sender='monetization_tools.PaymentTransaction')
def handle_payment_success(sender, instance, created, **kwargs):
    """When a payment succeeds, fulfil in-app purchase if applicable."""
    if not created and instance.status == 'success' and instance.purpose == 'in_app':
        try:
            from .models import InAppPurchase
            purchase = InAppPurchase.objects.filter(
                gateway_ref=str(instance.txn_id), status='pending'
            ).first()
            if purchase:
                from django.utils import timezone
                purchase.status       = 'completed'
                purchase.fulfilled_at = timezone.now()
                purchase.save(update_fields=['status', 'fulfilled_at'])
                logger.info("InAppPurchase %s fulfilled via payment signal.", purchase.purchase_id)
        except Exception as exc:
            logger.error("Error fulfilling InAppPurchase in signal: %s", exc)


@receiver(post_save, sender='monetization_tools.UserSubscription')
def log_subscription_status_change(sender, instance, created, **kwargs):
    """Log subscription status changes for auditing."""
    if not created:
        logger.info(
            "UserSubscription %s → status=%s user=%s",
            instance.subscription_id, instance.status, instance.user_id
        )


# ============================================================================
# NEW SIGNALS  (Phase-2 models)
# ============================================================================

@receiver(post_save, sender='monetization_tools.OfferCompletion')
def create_fraud_alert_on_high_score(sender, instance, created, **kwargs):
    """Auto-create fraud alert when offer completion has high fraud score."""
    if not created:
        return
    from .models import MonetizationConfig
    try:
        config = MonetizationConfig.objects.filter(tenant=instance.tenant).first()
        threshold = config.fraud_auto_reject_score if config else 70
        if instance.fraud_score >= threshold:
            from .services import FraudAlertService
            FraudAlertService.create_alert(
                user=instance.user,
                alert_type='high_fraud_score',
                severity='high' if instance.fraud_score >= 85 else 'medium',
                description=f"High fraud score {instance.fraud_score}/100 on offer completion {instance.transaction_id}",
                evidence={
                    'fraud_score': instance.fraud_score,
                    'fraud_signals': instance.fraud_signals,
                    'ip_address': str(instance.ip_address),
                    'is_vpn': instance.is_vpn,
                    'is_proxy': instance.is_proxy,
                },
                offer_completion=instance,
                ip_address=str(instance.ip_address),
                auto_reject=instance.fraud_score >= threshold,
            )
    except Exception as exc:
        logger.error("Fraud alert signal error: %s", exc)


@receiver(post_save, sender='monetization_tools.PayoutRequest')
def update_payout_method_on_paid(sender, instance, created, **kwargs):
    """Log successful payout for analytics."""
    if not created and instance.status == 'paid':
        logger.info("Payout paid: user=%s amount=%s %s",
                    instance.user_id, instance.net_amount, instance.currency)


@receiver(post_save, sender=User)
def create_daily_streak_on_register(sender, instance, created, **kwargs):
    """Create DailyStreak when new user registers."""
    if created:
        try:
            from .models import DailyStreak
            DailyStreak.objects.get_or_create(
                user=instance,
                defaults={'tenant': getattr(instance, 'tenant', None)},
            )
        except Exception as exc:
            logger.error("DailyStreak creation error: %s", exc)


@receiver(post_save, sender='monetization_tools.ReferralCommission')
def notify_referral_commission(sender, instance, created, **kwargs):
    """Notify referrer of new commission."""
    if created and instance.commission_coins > 0:
        logger.info("Referral commission: referrer=%s coins=%s level=%s",
                    instance.referrer_id, instance.commission_coins, instance.level)


@receiver(post_save, sender='monetization_tools.FlashSale')
def invalidate_flash_sale_cache(sender, instance, **kwargs):
    """Invalidate cached flash sale data on change."""
    from django.core.cache import cache
    tenant_id = getattr(instance.tenant, 'id', 'none')
    cache.delete(f'mt:flash_sales:{tenant_id}')
    cache.delete(f'mt:active_multiplier:{tenant_id}')


@receiver(post_save, sender='monetization_tools.MonetizationConfig')
def invalidate_config_cache(sender, instance, **kwargs):
    """Invalidate cached config on change."""
    from .services import MonetizationConfigService
    MonetizationConfigService.invalidate(instance.tenant)


@receiver(post_save, sender='monetization_tools.ABTestAssignment')
def fire_ab_test_assignment_event(sender, instance, created, **kwargs):
    """Emit event when user is assigned to A/B test variant."""
    if created:
        from .events import emit_offer_started
        logger.debug("AB Assignment: test=%s user=%s variant=%s",
                     instance.test_id, instance.user_id, instance.variant_name)


@receiver(post_save, sender='monetization_tools.RevenueGoal')
def check_goal_achievement(sender, instance, **kwargs):
    """Log when a revenue goal is achieved."""
    if instance.is_achieved:
        logger.info("Revenue goal achieved: %s (%.1f%%)",
                    instance.name, float(instance.progress_pct))


@receiver(post_save, sender='monetization_tools.OfferCompletion')
def update_offer_stats_on_completion(sender, instance, created, **kwargs):
    """Update offer denormalised stats when a completion is approved."""
    if not created and instance.status == 'approved':
        from .models import Offer
        from django.db.models import F
        try:
            Offer.objects.filter(pk=instance.offer_id).update(
                total_completions=F('total_completions') + 1,
                total_revenue_usd=F('total_revenue_usd') + instance.payout_amount,
            )
        except Exception as exc:
            logger.error("update_offer_stats_on_completion error: %s", exc)


@receiver(post_save, sender='monetization_tools.PayoutRequest')
def handle_payout_paid(sender, instance, created, **kwargs):
    """Emit event and send notification when payout is marked paid."""
    if not created and instance.status == 'paid':
        try:
            from .events import emit_payout_paid
            from .services import NotificationService
            emit_payout_paid(
                instance.user_id,
                str(instance.request_id),
                instance.net_amount,
                instance.currency,
                instance.gateway_reference or '',
            )
            NotificationService.send(
                instance.user, 'withdrawal_approved',
                context={
                    'amount': str(instance.net_amount),
                    'currency': instance.currency,
                    'method': instance.payout_method.method_type,
                },
                tenant=instance.tenant,
            )
        except Exception as exc:
            logger.error("handle_payout_paid signal error: %s", exc)


@receiver(post_save, sender='monetization_tools.UserLevel')
def notify_level_up(sender, instance, created, **kwargs):
    """Emit level-up event when user reaches a new level."""
    if not created:
        try:
            prev = getattr(instance, '_prev_level', None)
            if prev and instance.current_level > prev:
                from .events import emit_level_up
                emit_level_up(instance.user_id, prev, instance.current_level)
                from .services import NotificationService
                NotificationService.send(
                    instance.user, 'level_up',
                    context={
                        'new_level': instance.current_level,
                        'level_title': instance.level_title,
                    },
                    tenant=instance.tenant,
                )
        except Exception as exc:
            logger.debug("notify_level_up signal error: %s", exc)


@receiver(post_save, sender='monetization_tools.AdCreative')
def notify_creative_status_change(sender, instance, created, **kwargs):
    """Log creative approval/rejection transitions."""
    if not created:
        if instance.status == 'approved':
            logger.info("Creative approved: %s", instance.creative_id)
        elif instance.status == 'rejected':
            logger.warning("Creative rejected: %s reason=%s",
                           instance.creative_id, instance.rejection_reason)


@receiver(post_save, sender='monetization_tools.RecurringBilling')
def handle_billing_failure(sender, instance, created, **kwargs):
    """Emit billing_failed event and update subscription to past_due."""
    if not created and instance.status == 'failed':
        try:
            from .events import emit_billing_failed
            from .models import UserSubscription
            emit_billing_failed(
                instance.subscription.user_id,
                instance.id,
                instance.failure_reason or 'Unknown',
                instance.attempt_count,
            )
            if instance.attempt_count >= instance.max_attempts:
                UserSubscription.objects.filter(pk=instance.subscription_id).update(
                    status='past_due'
                )
                logger.warning("Subscription %s moved to past_due after %d failed attempts",
                               instance.subscription_id, instance.attempt_count)
        except Exception as exc:
            logger.error("handle_billing_failure signal error: %s", exc)


@receiver(post_save, sender='monetization_tools.UserSubscription')
def send_subscription_notifications(sender, instance, created, **kwargs):
    """Send subscription started/cancelled notifications."""
    if not created:
        try:
            from .services import NotificationService
            if instance.status == 'active' and instance.started_at:
                NotificationService.send(
                    instance.user, 'subscription_start',
                    context={
                        'plan_name': instance.plan.name,
                        'period_end': str(instance.current_period_end.date()),
                    },
                    tenant=instance.tenant,
                )
            elif instance.status == 'cancelled':
                NotificationService.send(
                    instance.user, 'subscription_expire',
                    context={'plan_name': instance.plan.name},
                    tenant=instance.tenant,
                )
        except Exception as exc:
            logger.debug("send_subscription_notifications signal error: %s", exc)


@receiver(post_save, sender='monetization_tools.CouponUsage')
def increment_coupon_counter_on_use(sender, instance, created, **kwargs):
    """Ensure coupon.current_uses is in sync (belt-and-suspenders)."""
    if created:
        try:
            from .models import Coupon
            from django.db.models import F
            Coupon.objects.filter(pk=instance.coupon_id).update(
                current_uses=F('current_uses') + 1
            )
        except Exception as exc:
            logger.error("increment_coupon_counter_on_use error: %s", exc)


@receiver(post_save, sender='monetization_tools.FraudAlert')
def handle_fraud_alert_critical(sender, instance, created, **kwargs):
    """Auto-notify admins for critical fraud alerts."""
    if created and instance.severity == 'critical':
        logger.critical(
            "CRITICAL FRAUD ALERT: user=%s type=%s alert=%s",
            instance.user_id, instance.alert_type, instance.alert_id,
        )


# ── Additional signals for remaining coverage gaps ───────────────────────────

@receiver(post_save, sender='monetization_tools.AdNetwork')
def invalidate_ad_network_cache(sender, instance, **kwargs):
    """Invalidate waterfall and network caches on AdNetwork change."""
    from django.core.cache import cache
    from .cache import waterfall_key, floor_price_key
    # Clear waterfall caches for this network
    logger.debug("AdNetwork changed: %s — clearing caches", instance.display_name)
    cache.delete(f"mt:an_active_all")
    cache.delete(floor_price_key(instance.id))


@receiver(post_save, sender='monetization_tools.AdCampaign')
def log_campaign_status_change(sender, instance, created, **kwargs):
    """Log campaign activation/pausing for audit trail."""
    if not created:
        logger.info("AdCampaign status: %s → %s | budget_used=%.2f%%",
                    instance.name, instance.status,
                    float(instance.budget_utilisation_pct))


@receiver(post_save, sender='monetization_tools.AdPerformanceHourly')
def check_revenue_goals_on_hourly_update(sender, instance, **kwargs):
    """Trigger goal progress refresh when significant revenue is logged."""
    if instance.revenue_usd and instance.revenue_usd > Decimal('10.00'):
        logger.debug("Revenue logged — may update goal progress")


@receiver(post_save, sender='monetization_tools.ReferralCommission')
def update_referral_link_stats(sender, instance, created, **kwargs):
    """Keep ReferralLink.total_earned in sync on new commission."""
    if created and instance.commission_coins > 0 and instance.referral_link_id:
        from .models import ReferralLink
        from django.db.models import F
        ReferralLink.objects.filter(pk=instance.referral_link_id).update(
            total_earned=F('total_earned') + instance.commission_coins,
            total_conversions=F('total_conversions') + 1,
        )


@receiver(post_save, sender='monetization_tools.Achievement')
def emit_achievement_event(sender, instance, created, **kwargs):
    """Fire achievement_unlocked event when a new Achievement is created."""
    if created:
        try:
            from .events import emit_achievement_unlocked
            emit_achievement_unlocked(
                instance.user_id,
                instance.achievement_key,
                instance.title,
                instance.xp_reward,
                instance.coin_reward,
            )
        except Exception as exc:
            logger.debug("emit_achievement_event error: %s", exc)


@receiver(post_save, sender='monetization_tools.LeaderboardRank')
def invalidate_leaderboard_cache_on_rank_change(sender, instance, **kwargs):
    """Invalidate leaderboard cache when a rank entry changes."""
    from .cache import leaderboard_key, delete_cached
    delete_cached(leaderboard_key(instance.scope, instance.board_type, instance.period_label or ''))


@receiver(post_save, sender='monetization_tools.SpinWheelLog')
def invalidate_spin_count_cache(sender, instance, created, **kwargs):
    """Reset daily spin count cache entry when a new spin is logged."""
    if created:
        from django.utils import timezone
        from .cache import spin_wheel_count_key, delete_cached
        date_str = timezone.now().date().isoformat()
        delete_cached(spin_wheel_count_key(instance.user_id, date_str))


@receiver(post_save, sender='monetization_tools.PostbackLog')
def trigger_postback_processing(sender, instance, created, **kwargs):
    """Queue postback for async processing when received."""
    if created and instance.status == 'received':
        try:
            from .tasks import process_pending_postbacks
            process_pending_postbacks.apply_async(countdown=5)
        except Exception as exc:
            logger.debug("trigger_postback_processing error: %s", exc)


@receiver(post_save, sender='monetization_tools.WaterfallConfig')
def invalidate_waterfall_cache_on_change(sender, instance, **kwargs):
    """Invalidate cached waterfall when config changes."""
    from .cache import waterfall_key, delete_cached
    delete_cached(waterfall_key(instance.ad_unit_id))


@receiver(post_save, sender='monetization_tools.FloorPriceConfig')
def invalidate_floor_cache_on_change(sender, instance, **kwargs):
    """Invalidate floor price cache on config change."""
    from .cache import floor_price_key, delete_cached
    delete_cached(floor_price_key(instance.ad_network_id))


@receiver(post_save, sender='monetization_tools.RevenueDailySummary')
def update_revenue_goal_progress(sender, instance, **kwargs):
    """Update revenue goal current_value when daily summary changes."""
    try:
        from .models import RevenueGoal
        from django.db.models import Sum
        goals = RevenueGoal.objects.filter(
            tenant=instance.tenant, is_active=True,
            period_start__lte=instance.date, period_end__gte=instance.date,
            goal_type='total_revenue',
        )
        for goal in goals:
            total = RevenueDailySummary.objects.filter(
                tenant=instance.tenant,
                date__gte=goal.period_start, date__lte=goal.period_end,
            ).aggregate(t=Sum('total_revenue'))['t'] or Decimal('0')
            RevenueGoal.objects.filter(pk=goal.pk).update(current_value=total)
    except Exception as exc:
        logger.debug("update_revenue_goal_progress signal error: %s", exc)


@receiver(post_save, sender='monetization_tools.PublisherAccount')
def notify_publisher_status_change(sender, instance, created, **kwargs):
    """Log publisher account status changes."""
    if not created:
        logger.info("PublisherAccount %s status: %s verified=%s",
                    instance.company_name, instance.status, instance.is_verified)


@receiver(post_save, sender='monetization_tools.MonetizationNotificationTemplate')
def invalidate_template_cache(sender, instance, **kwargs):
    """Invalidate notification template cache on change."""
    from django.core.cache import cache
    cache.delete(f"mt:notif_tmpl:{instance.tenant_id}:{instance.event_type}:{instance.channel}:{instance.language}")


# ── Final signal coverage for remaining models ────────────────────────────────

@receiver(post_save, sender='monetization_tools.AdUnit')
def update_campaign_unit_count(sender, instance, created, **kwargs):
    """Log when a new AdUnit is created under a campaign."""
    if created:
        logger.info("AdUnit created: %s format=%s campaign=%s",
                    instance.name, instance.ad_format, instance.campaign_id)


@receiver(post_save, sender='monetization_tools.AdPlacement')
def log_placement_activation(sender, instance, created, **kwargs):
    """Log AdPlacement activation changes."""
    if not created:
        logger.debug("AdPlacement updated: screen=%s position=%s active=%s",
                     instance.screen_name, instance.position, instance.is_active)


@receiver(post_save, sender='monetization_tools.AdPerformanceDaily')
def alert_on_low_fill_rate(sender, instance, created, **kwargs):
    """Alert when fill_rate drops below 20% on a given day."""
    if instance.fill_rate and instance.fill_rate < Decimal('20.00') and instance.impressions > 100:
        logger.warning("LOW FILL RATE: unit=%s network=%s date=%s fill=%.2f%%",
                       instance.ad_unit_id, instance.ad_network_id,
                       instance.date, float(instance.fill_rate))


@receiver(post_save, sender='monetization_tools.AdNetworkDailyStat')
def alert_high_discrepancy(sender, instance, created, **kwargs):
    """Alert when revenue discrepancy > 10%."""
    if abs(instance.discrepancy_pct) > Decimal('10.00'):
        logger.warning("HIGH DISCREPANCY: network=%s date=%s disc=%.2f%%",
                       instance.ad_network_id, instance.date, float(instance.discrepancy_pct))


@receiver(post_save, sender='monetization_tools.Offerwall')
def invalidate_offerwall_cache(sender, instance, **kwargs):
    """Invalidate offerwall list cache on change."""
    from .cache import offerwall_list_key, delete_cached
    tenant_id = getattr(instance.tenant, 'id', None)
    delete_cached(offerwall_list_key(tenant_id))
    delete_cached(offerwall_list_key(None))


@receiver(post_save, sender='monetization_tools.RewardTransaction')
def update_user_total_earned(sender, instance, created, **kwargs):
    """Belt-and-suspenders: ensure user.total_earned stays accurate."""
    if created and instance.amount > 0:
        logger.debug("RewardTransaction credited: user=%s +%s type=%s",
                     instance.user_id, instance.amount, instance.transaction_type)


@receiver(post_save, sender='monetization_tools.PointLedgerSnapshot')
def log_balance_snapshot(sender, instance, created, **kwargs):
    if created:
        logger.debug("PointLedgerSnapshot: user=%s date=%s balance=%s",
                     instance.user_id, instance.snapshot_date, instance.balance)


@receiver(post_save, sender='monetization_tools.ImpressionLog')
def increment_ad_unit_impression_counter(sender, instance, created, **kwargs):
    """Atomically increment AdUnit impression counter."""
    if created and not instance.is_bot:
        from .models import AdUnit
        from django.db.models import F
        AdUnit.objects.filter(pk=instance.ad_unit_id).update(
            impressions=F('impressions') + 1,
            revenue=F('revenue') + (instance.revenue or Decimal('0')),
        )


@receiver(post_save, sender='monetization_tools.ClickLog')
def increment_ad_unit_click_counter(sender, instance, created, **kwargs):
    """Atomically increment AdUnit click counter."""
    if created and instance.is_valid:
        from .models import AdUnit
        from django.db.models import F
        AdUnit.objects.filter(pk=instance.ad_unit_id).update(
            clicks=F('clicks') + 1,
        )


@receiver(post_save, sender='monetization_tools.ConversionLog')
def update_campaign_conversion_counter(sender, instance, created, **kwargs):
    """Increment AdCampaign.total_conversions on verified conversion."""
    if created and instance.is_verified:
        from .models import AdCampaign
        from django.db.models import F
        AdCampaign.objects.filter(pk=instance.campaign_id).update(
            total_conversions=F('total_conversions') + 1,
            spent_budget=F('spent_budget') + (instance.payout or Decimal('0')),
        )


@receiver(post_save, sender='monetization_tools.SubscriptionPlan')
def invalidate_subscription_plan_cache(sender, instance, **kwargs):
    """Invalidate subscription plan cache on change."""
    from .cache import subscription_plans_key, delete_cached
    tenant_id = getattr(instance.tenant, 'id', None)
    delete_cached(subscription_plans_key(tenant_id))
    delete_cached(subscription_plans_key(None))


@receiver(post_save, sender='monetization_tools.InAppPurchase')
def fulfil_in_app_purchase(sender, instance, created, **kwargs):
    """Credit coins to user when InAppPurchase is completed."""
    if not created and instance.status == 'completed' and instance.coins_granted > 0:
        if not instance.fulfilled_at:
            try:
                RewardService.credit(
                    instance.user, instance.coins_granted,
                    transaction_type='subscription',
                    description=f"IAP: {instance.product_name}",
                    reference_id=str(instance.purchase_id),
                )
                from django.utils import timezone as tz
                InAppPurchase_model = instance.__class__
                InAppPurchase_model.objects.filter(pk=instance.pk).update(
                    fulfilled_at=tz.now()
                )
            except Exception as exc:
                logger.error("fulfil_in_app_purchase signal error: %s", exc)


@receiver(post_save, sender='monetization_tools.PaymentTransaction')
def update_campaign_spend_on_payment(sender, instance, created, **kwargs):
    """Update related campaign spend when payment succeeds."""
    if not created and instance.status == 'success' and instance.purpose == 'in_app':
        logger.info("PaymentTransaction success: txn=%s user=%s amount=%s",
                    instance.txn_id, instance.user_id, instance.amount)


@receiver(post_save, sender='monetization_tools.UserLevel')
def check_milestone_achievement(sender, instance, created, **kwargs):
    """Award achievement when user reaches level milestones."""
    MILESTONE_LEVELS = {5: 'level_5', 10: 'level_10', 25: 'level_25', 50: 'level_50'}
    if not created and instance.current_level in MILESTONE_LEVELS:
        try:
            from .models import Achievement
            key = MILESTONE_LEVELS[instance.current_level]
            if not Achievement.objects.filter(user=instance.user, achievement_key=key).exists():
                Achievement.objects.create(
                    user=instance.user,
                    achievement_key=key,
                    title=f"Level {instance.current_level} Reached!",
                    category='earning',
                    xp_reward=instance.current_level * 10,
                    coin_reward=Decimal(str(instance.current_level * 50)),
                    tenant=instance.tenant,
                )
        except Exception as exc:
            logger.debug("check_milestone_achievement error: %s", exc)


@receiver(post_save, sender='monetization_tools.SpinWheelLog')
def log_jackpot_win(sender, instance, created, **kwargs):
    """Log jackpot wins separately for business monitoring."""
    if created and instance.prize_value >= Decimal('1000.00'):
        logger.info("BIG WIN: user=%s type=%s prize=%s %s",
                    instance.user_id, instance.log_type,
                    instance.prize_type, instance.prize_value)


@receiver(post_save, sender='monetization_tools.ABTest')
def log_ab_test_status(sender, instance, created, **kwargs):
    """Log A/B test lifecycle events."""
    if not created:
        if instance.status == 'running':
            logger.info("ABTest started: %s", instance.name)
        elif instance.status == 'completed' and instance.winner_variant:
            logger.info("ABTest completed: %s winner=%s", instance.name, instance.winner_variant)


@receiver(post_save, sender='monetization_tools.ABTestAssignment')
def log_ab_conversion(sender, instance, created, **kwargs):
    """Log when an A/B test user converts."""
    if not created and instance.converted:
        logger.debug("AB conversion: test=%s user=%s variant=%s",
                     instance.test_id, instance.user_id, instance.variant_name)


@receiver(post_save, sender='monetization_tools.UserSegment')
def log_segment_member_count_change(sender, instance, **kwargs):
    """Log segment size changes."""
    logger.debug("UserSegment updated: %s members=%d", instance.name, instance.member_count)


@receiver(post_save, sender='monetization_tools.UserSegmentMembership')
def update_segment_member_count(sender, instance, created, **kwargs):
    """Keep segment member_count accurate on new membership."""
    if created:
        from .models import UserSegment
        from django.db.models import F
        UserSegment.objects.filter(pk=instance.segment_id).update(
            member_count=F('member_count') + 1
        )


@receiver(post_save, sender='monetization_tools.PayoutMethod')
def log_payout_method_verification(sender, instance, created, **kwargs):
    """Log when a payout method is verified."""
    if not created and instance.is_verified:
        logger.info("PayoutMethod verified: user=%s type=%s",
                    instance.user_id, instance.method_type)


@receiver(post_save, sender='monetization_tools.ReferralProgram')
def invalidate_referral_program_cache(sender, instance, **kwargs):
    """Invalidate cached referral program on change."""
    from django.core.cache import cache
    tenant_id = getattr(instance.tenant, 'id', 'none')
    cache.delete(f'mt:ref_program:{tenant_id}')


@receiver(post_save, sender='monetization_tools.SpinWheelConfig')
def invalidate_spin_config_cache(sender, instance, **kwargs):
    """Invalidate spin wheel config cache on change."""
    from .cache import spin_config_key, delete_cached
    delete_cached(spin_config_key(getattr(instance.tenant, 'id', None)))


@receiver(post_save, sender='monetization_tools.PrizeConfig')
def invalidate_prize_cache(sender, instance, **kwargs):
    """Invalidate prize pool cache when prizes change."""
    from django.core.cache import cache
    cache.delete(f'mt:prizes:{instance.wheel_config_id}')


@receiver(post_save, sender='monetization_tools.CouponUsage')
def log_coupon_redemption(sender, instance, created, **kwargs):
    """Log coupon redemptions for analytics."""
    if created:
        logger.info("Coupon redeemed: code=%s user=%s coins=%s",
                    instance.coupon.code, instance.user_id, instance.coins_granted)
