# engagement/services/integration/event_bus.py
"""
EngagementEventBus
==================
Fire-and-forget event system for cross-app communication.

Pattern:
    engagement fires event → other apps subscribe via Django signals

Events fired:
    engagement.coins_earned         — user earned coins
    engagement.level_up             — user leveled up
    engagement.checkin_completed    — daily check-in done
    engagement.spin_completed       — spin wheel result
    engagement.quest_completed      — quest finished
    engagement.achievement_unlocked — achievement earned
    engagement.leaderboard_rewarded — weekly reward distributed
    engagement.referral_registered  — new referral link created
    engagement.shop_purchase        — item bought
    engagement.battle_pass_tier     — tier unlocked
    engagement.prestige             — user prestiged
    engagement.guild_joined         — user joined guild
    engagement.anti_cheat_flag      — suspicious activity detected

Other apps subscribe:
    from api.engagement.services.integration.event_bus import EngagementEventBus
    from django.dispatch import receiver

    @receiver(EngagementEventBus.COINS_EARNED)
    def on_coins_earned(sender, user, amount, source, **kwargs):
        # e.g. analytics, wallet sync, etc.
        pass
"""

import logging
from django.dispatch import Signal

logger = logging.getLogger("engagement.integration.event_bus")


class EngagementEventBus:
    """
    Django Signal-based event bus for engagement → other apps.

    All signals carry: sender=EngagementEventBus, user=User, **payload
    """

    # ── Signal definitions ────────────────────────────────────────────────────
    COINS_EARNED          = Signal()   # user, amount, source, wallet_txn_id
    COINS_DEDUCTED        = Signal()   # user, amount, source
    LEVEL_UP              = Signal()   # user, old_level, new_level, total_xp
    XP_GRANTED            = Signal()   # user, amount, source, new_total_xp
    CHECKIN_COMPLETED     = Signal()   # user, coins, streak, date
    SPIN_COMPLETED        = Signal()   # user, coins, outcome_idx, spins_remaining
    QUEST_COMPLETED       = Signal()   # user, quest_id, quest_title, coins, xp
    ACHIEVEMENT_UNLOCKED  = Signal()   # user, achievement_id, achievement_slug, coins, xp
    LEADERBOARD_REWARDED  = Signal()   # user, rank, coins, season
    REFERRAL_REGISTERED   = Signal()   # referrer, referee, code
    SHOP_PURCHASE         = Signal()   # user, item_slug, coins_spent, quantity
    BATTLE_PASS_TIER      = Signal()   # user, tier, is_premium, coins, xp
    PRESTIGE              = Signal()   # user, prestige_level, bonus_coins
    GUILD_JOINED          = Signal()   # user, guild_id, guild_name
    GUILD_LEFT            = Signal()   # user, guild_id
    CHALLENGE_JOINED      = Signal()   # user, challenge_id
    CHALLENGE_COMPLETED   = Signal()   # user, challenge_id, coins, xp
    CHEST_OPENED          = Signal()   # user, chest_slug, reward_type, coins
    AUCTION_BID           = Signal()   # user, auction_id, bid_amount
    AUCTION_WON           = Signal()   # user, auction_id, winning_bid
    SCRATCH_COMPLETED     = Signal()   # user, template_slug, coins
    CALENDAR_DAY_CLAIMED  = Signal()   # user, day_number, coins
    ANTI_CHEAT_FLAG       = Signal()   # user, rule_slug, severity, details

    # ── Fire helpers ──────────────────────────────────────────────────────────

    @classmethod
    def fire(cls, signal: Signal, **kwargs) -> None:
        """
        Fire a signal safely — never raises, logs errors.
        Catches exceptions from individual handlers via send_robust().
        """
        try:
            results = signal.send_robust(sender=cls, **kwargs)
            for receiver_fn, result in results:
                if isinstance(result, Exception):
                    logger.error(
                        f"EngagementEventBus.fire handler {receiver_fn.__name__} "
                        f"raised {type(result).__name__}: {result}"
                    )
        except Exception as e:
            logger.error(f"EngagementEventBus.fire FAILED signal={signal}: {e}")

    # ── Convenience fire methods ──────────────────────────────────────────────

    @classmethod
    def emit_coins_earned(cls, user, amount, source: str, wallet_txn_id: str = None):
        cls.fire(cls.COINS_EARNED,
                 user=user, amount=amount, source=source,
                 wallet_txn_id=wallet_txn_id)

    @classmethod
    def emit_coins_deducted(cls, user, amount, source: str):
        cls.fire(cls.COINS_DEDUCTED, user=user, amount=amount, source=source)

    @classmethod
    def emit_level_up(cls, user, old_level: int, new_level: int, total_xp: int):
        cls.fire(cls.LEVEL_UP,
                 user=user, old_level=old_level,
                 new_level=new_level, total_xp=total_xp)

    @classmethod
    def emit_xp_granted(cls, user, amount: int, source: str, new_total_xp: int):
        cls.fire(cls.XP_GRANTED,
                 user=user, amount=amount, source=source,
                 new_total_xp=new_total_xp)

    @classmethod
    def emit_checkin(cls, user, coins: float, streak: int, date=None):
        from datetime import date as _date
        cls.fire(cls.CHECKIN_COMPLETED,
                 user=user, coins=coins, streak=streak,
                 date=date or _date.today())

    @classmethod
    def emit_spin(cls, user, coins: float, outcome_idx: int, spins_remaining: int):
        cls.fire(cls.SPIN_COMPLETED,
                 user=user, coins=coins,
                 outcome_idx=outcome_idx, spins_remaining=spins_remaining)

    @classmethod
    def emit_quest_completed(cls, user, quest_id: int, quest_title: str,
                              coins: float, xp: int):
        cls.fire(cls.QUEST_COMPLETED,
                 user=user, quest_id=quest_id, quest_title=quest_title,
                 coins=coins, xp=xp)

    @classmethod
    def emit_achievement(cls, user, achievement_id: int, achievement_slug: str,
                          coins: float, xp: int):
        cls.fire(cls.ACHIEVEMENT_UNLOCKED,
                 user=user, achievement_id=achievement_id,
                 achievement_slug=achievement_slug, coins=coins, xp=xp)

    @classmethod
    def emit_leaderboard_rewarded(cls, user, rank: int, coins: float, season: str):
        cls.fire(cls.LEADERBOARD_REWARDED,
                 user=user, rank=rank, coins=coins, season=season)

    @classmethod
    def emit_referral_registered(cls, referrer, referee, code: str):
        cls.fire(cls.REFERRAL_REGISTERED,
                 referrer=referrer, referee=referee, code=code)

    @classmethod
    def emit_shop_purchase(cls, user, item_slug: str, coins_spent: float, quantity: int = 1):
        cls.fire(cls.SHOP_PURCHASE,
                 user=user, item_slug=item_slug,
                 coins_spent=coins_spent, quantity=quantity)

    @classmethod
    def emit_battle_pass_tier(cls, user, tier: int, is_premium: bool,
                               coins: float, xp: int):
        cls.fire(cls.BATTLE_PASS_TIER,
                 user=user, tier=tier, is_premium=is_premium,
                 coins=coins, xp=xp)

    @classmethod
    def emit_prestige(cls, user, prestige_level: int, bonus_coins: float):
        cls.fire(cls.PRESTIGE,
                 user=user, prestige_level=prestige_level,
                 bonus_coins=bonus_coins)

    @classmethod
    def emit_anti_cheat_flag(cls, user, rule_slug: str, severity: int, details: dict):
        cls.fire(cls.ANTI_CHEAT_FLAG,
                 user=user, rule_slug=rule_slug,
                 severity=severity, details=details)
