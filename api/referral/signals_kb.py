# api/referral/signals_kb.py
# Knowledge base signals — signals that update internal knowledge/state
# Keeps derived data in sync without direct coupling
# "kb" = knowledge base / internal state sync
# ============================================================

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

logger = logging.getLogger(__name__)


# ── KB: ReferralTree sync when Referral changes ───────────────────────────────

@receiver(post_save, sender='referral.Referral')
def kb_sync_referral_tree(sender, instance, created, **kwargs):
    """
    When a Referral is created, update the referrer's ReferralTree stats.
    Keeps ReferralTree.level1_count in sync.
    """
    if not created:
        return

    def _update():
        try:
            from api.referral.repositories import ReferralTreeRepository
            from django.db.models import F
            from api.referral.models import ReferralTree

            tree, _ = ReferralTreeRepository.get_or_create_for_user(instance.referrer)
            ReferralTree.objects.filter(id=tree.id).update(
                level1_count=F('level1_count') + 1,
                total_members=F('total_members') + 1,
            )
        except Exception as e:
            logger.debug(f'[KBSignals] kb_sync_referral_tree failed: {e}')

    transaction.on_commit(_update)


# ── KB: User stats sync when CommissionLog changes ───────────────────────────

@receiver(post_save, sender='referral.CommissionLog')
def kb_sync_user_commission_stats(sender, instance, created, **kwargs):
    """
    Keep UserCommissionTier.total_commission_earned in sync.
    Also invalidate user stats cache.
    """
    if not created:
        return

    def _update():
        try:
            from api.referral.caching import ReferralUserStatsCache
            ReferralUserStatsCache.invalidate(instance.user_id)

            from api.referral.models import UserCommissionTier
            from django.db.models import F
            UserCommissionTier.objects.filter(user_id=instance.user_id).update(
                total_commission_earned=F('total_commission_earned') + instance.amount,
                total_active_referrals=F('total_active_referrals'),
            )
        except Exception as e:
            logger.debug(f'[KBSignals] kb_sync_user_commission_stats failed: {e}')

    transaction.on_commit(_update)


# ── KB: ReferralCode stats sync ───────────────────────────────────────────────

@receiver(post_save, sender='referral.Referral')
def kb_sync_code_conversion(sender, instance, created, **kwargs):
    """
    When referral created, update ReferralCode.revenue_generated.
    """
    if not created:
        return

    def _update():
        try:
            from api.referral.models import ReferralCode
            from django.db.models import F
            # Find the code that was used for this referral
            code = ReferralCode.objects.filter(
                user=instance.referrer, is_primary=True
            ).first()
            if code:
                ReferralCode.objects.filter(id=code.id).update(
                    conversions=F('conversions') + 1,
                )
        except Exception as e:
            logger.debug(f'[KBSignals] kb_sync_code_conversion failed: {e}')

    transaction.on_commit(_update)


# ── KB: Campaign spend sync ───────────────────────────────────────────────────

@receiver(post_save, sender='referral.CommissionLog')
def kb_sync_campaign_spend(sender, instance, created, **kwargs):
    """
    When commission log created, update campaign current_spend.
    """
    if not created or not instance.campaign_id:
        return

    def _update():
        try:
            from api.referral.models import ReferralCampaign
            from django.db.models import F
            ReferralCampaign.objects.filter(id=instance.campaign_id).update(
                current_spend=F('current_spend') + instance.amount,
            )
        except Exception as e:
            logger.debug(f'[KBSignals] kb_sync_campaign_spend failed: {e}')

    transaction.on_commit(_update)


# ── KB: ReferralInsight daily counter ────────────────────────────────────────

@receiver(post_save, sender='referral.Referral')
def kb_update_daily_insight(sender, instance, created, **kwargs):
    """
    Increment daily new_referrals counter in ReferralInsight.
    """
    if not created:
        return

    def _update():
        try:
            from api.referral.models import ReferralInsight
            from django.db.models import F
            from django.utils import timezone

            today = timezone.now().date()
            ReferralInsight.objects.update_or_create(
                date=today,
                tenant=instance.tenant,
                defaults={'new_referrals': 0},
            )
            ReferralInsight.objects.filter(
                date=today, tenant=instance.tenant
            ).update(new_referrals=F('new_referrals') + 1)
        except Exception as e:
            logger.debug(f'[KBSignals] kb_update_daily_insight failed: {e}')

    transaction.on_commit(_update)


# ── KB: Blacklist hit counter ─────────────────────────────────────────────────

@receiver(post_save, sender='referral.ReferralBlacklist')
def kb_log_blacklist_change(sender, instance, created, **kwargs):
    """
    Log blacklist additions to audit trail.
    """
    if not created:
        return

    try:
        from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger
        ReferralAuditLogger.log_blacklist_added(
            admin_user=instance.created_by,
            pattern_type=instance.pattern_type,
            pattern_value=instance.pattern_value,
        )
    except Exception as e:
        logger.debug(f'[KBSignals] kb_log_blacklist_change failed: {e}')


def connect_kb_signals():
    """
    Explicitly connect KB signals.
    Called from apps.py ready() to ensure signals are wired.
    """
    logger.info('[KBSignals] Knowledge base signals connected')
    # All signals are connected via @receiver decorators above
    # This function serves as an explicit confirmation point