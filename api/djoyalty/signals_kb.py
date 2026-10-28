# api/djoyalty/signals_kb.py
"""
Djoyalty Signals KB -- Knowledge-base signal handlers।
Connects loyalty events to knowledge-base and audit tracking।
Tracks: what events happened, why, with full context for support।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from django.dispatch import receiver
from .signals import points_earned, points_redeemed, tier_changed, badge_unlocked

logger = logging.getLogger(__name__)


@receiver(points_earned)
def kb_on_points_earned(sender, customer, points, source, balance, **kwargs):
    """Log points earned to knowledge base / audit trail।"""
    try:
        from .models.audit import AdminAuditLog
        AdminAuditLog.log(
            action='points_earned',
            category='points',
            customer=customer,
            performed_by='system',
            new_value={
                'points_earned': str(points),
                'new_balance': str(balance),
                'source': source,
            },
            description=f'+{points} pts via {source}. Balance: {balance}',
            severity='info',
        )
    except Exception as e:
        logger.debug('kb_on_points_earned error: %s', e)


@receiver(points_redeemed)
def kb_on_points_redeemed(sender, customer, points, reward_type, **kwargs):
    """Log redemption to audit trail।"""
    try:
        from .models.audit import AdminAuditLog
        AdminAuditLog.log(
            action='points_redeemed',
            category='redemption',
            customer=customer,
            new_value={
                'points_redeemed': str(points),
                'reward_type': reward_type,
            },
            description=f'-{points} pts for {reward_type}',
            severity='info',
        )
    except Exception as e:
        logger.debug('kb_on_points_redeemed error: %s', e)


@receiver(tier_changed)
def kb_on_tier_changed(sender, customer, new_tier, **kwargs):
    """Log tier change to audit trail।"""
    try:
        from .models.audit import AdminAuditLog
        AdminAuditLog.log(
            action='tier_changed',
            category='tier',
            customer=customer,
            new_value={'new_tier': new_tier},
            description=f'Tier changed to {new_tier}',
            severity='info',
        )
        # Also update AI profile
        from .services.AIPersonalizationService import AIPersonalizationService
        AIPersonalizationService.update_ai_profile(customer)
    except Exception as e:
        logger.debug('kb_on_tier_changed error: %s', e)


@receiver(badge_unlocked)
def kb_on_badge_unlocked(sender, customer, badge, **kwargs):
    """Log badge unlock to audit trail।"""
    try:
        from .models.audit import AdminAuditLog
        AdminAuditLog.log(
            action='badge_unlocked',
            category='other',
            customer=customer,
            new_value={'badge_name': badge.name, 'badge_id': badge.id},
            description=f'Badge unlocked: {badge.name}',
            severity='info',
        )
    except Exception as e:
        logger.debug('kb_on_badge_unlocked error: %s', e)


def connect_kb_signals():
    """Ensure all KB signal handlers are connected (called from apps.py)।"""
    # Signals auto-connect via @receiver decorators above
    # This function exists for explicit connection if needed
    logger.debug('signals_kb: knowledge-base signal handlers connected')
