# engagement/services/integration/notification_bridge.py
"""
NotificationBridge
==================
Engagement → api.notifications bridge.

All user-facing alerts (reward earned, level up, quest complete, etc.)
go through here. Never import notification models in engagement code.

Notification types sent by engagement:
    checkin_reward    — Daily check-in coin reward
    spin_reward       — Spin wheel result
    level_up          — XP level increase
    quest_complete    — Quest finished, claim available
    achievement       — Achievement unlocked
    leaderboard_rank  — Weekly leaderboard result
    referral_reward   — Referral commission earned
    shop_purchase     — Item purchased
    battle_pass_tier  — Battle Pass tier unlocked
    guild_event       — Guild activity
    chest_opened      — Loot box reward
    auction_outbid    — Outbid notification
    auction_won       — Auction won
"""

import logging
from typing import Optional

logger = logging.getLogger("engagement.integration.notification")

# ─── Notification type → icon + channel mapping ───────────────────────────────
NOTIF_CONFIG = {
    "checkin_reward":   {"icon": "🎁", "channels": ["in_app", "push"]},
    "spin_reward":      {"icon": "🎰", "channels": ["in_app"]},
    "level_up":         {"icon": "⬆️", "channels": ["in_app", "push"]},
    "quest_complete":   {"icon": "✅", "channels": ["in_app", "push"]},
    "achievement":      {"icon": "🏆", "channels": ["in_app", "push"]},
    "leaderboard_rank": {"icon": "🥇", "channels": ["in_app", "push"]},
    "referral_reward":  {"icon": "💰", "channels": ["in_app", "push"]},
    "shop_purchase":    {"icon": "🛍️", "channels": ["in_app"]},
    "battle_pass_tier": {"icon": "⚔️",  "channels": ["in_app", "push"]},
    "guild_event":      {"icon": "🛡️",  "channels": ["in_app"]},
    "chest_opened":     {"icon": "📦", "channels": ["in_app"]},
    "auction_outbid":   {"icon": "🔔", "channels": ["in_app", "push"]},
    "auction_won":      {"icon": "🎉", "channels": ["in_app", "push"]},
    "prestige":         {"icon": "⭐", "channels": ["in_app", "push"]},
    "scratch_reward":   {"icon": "🎫", "channels": ["in_app"]},
    "calendar_reward":  {"icon": "📅", "channels": ["in_app"]},
    "combo_bonus":      {"icon": "🔥", "channels": ["in_app"]},
    "anti_cheat_flag":  {"icon": "🚨", "channels": ["in_app"]},
}


class NotificationBridge:
    """
    Engagement → Notifications bridge.
    Gracefully no-ops if api.notifications is unavailable.
    """

    @staticmethod
    def _send(user, notif_type: str, title: str, body: str, data: dict = None) -> bool:
        """Core send method — tries api.notifications, falls back to in-app model."""
        cfg = NOTIF_CONFIG.get(notif_type, {"icon": "🔔", "channels": ["in_app"]})
        icon = cfg["icon"]
        full_title = f"{icon} {title}"

        # ── Try api.notifications (full system) ───────────────────────────────
        try:
            from api.notifications.models import Notification as SysNotification
            SysNotification.objects.create(
                user=user,
                notification_type=notif_type,
                title=full_title,
                message=body,
                data=data or {},
                is_read=False,
            )
            logger.debug(
                f"NotificationBridge: sent {notif_type} to user={user.pk}"
            )
            return True
        except Exception:
            pass

        # ── Fallback: engagement in-app notification model ────────────────────
        try:
            from api.engagement.models.notification import Notification as EngNotif
            EngNotif.objects.create(
                user=user,
                type=notif_type,
                title=full_title,
                body=body,
                data=data or {},
            )
            return True
        except Exception as e:
            logger.error(
                f"NotificationBridge: all channels failed user={user.pk} "
                f"type={notif_type}: {e}"
            )
            return False

    # ── Specific notification methods ─────────────────────────────────────────

    @staticmethod
    def checkin_reward(user, coins: float, streak: int):
        return NotificationBridge._send(
            user, "checkin_reward",
            title="Daily Check-In Reward!",
            body=f"You earned {coins:.0f} coins! 🎁 Day {streak} streak!",
            data={"coins": coins, "streak": streak},
        )

    @staticmethod
    def spin_reward(user, coins: float, spins_remaining: int):
        return NotificationBridge._send(
            user, "spin_reward",
            title="Spin Wheel Result",
            body=f"You won {coins:.0f} coins! {spins_remaining} spins remaining today.",
            data={"coins": coins, "spins_remaining": spins_remaining},
        )

    @staticmethod
    def level_up(user, old_level: int, new_level: int, coins_bonus: float = 0):
        return NotificationBridge._send(
            user, "level_up",
            title=f"Level Up! You're now Level {new_level}!",
            body=(
                f"Congratulations! You leveled up from {old_level} → {new_level}."
                + (f" Bonus: {coins_bonus:.0f} coins!" if coins_bonus else "")
            ),
            data={"old_level": old_level, "new_level": new_level, "coins_bonus": coins_bonus},
        )

    @staticmethod
    def quest_complete(user, quest_title: str, coin_reward: float, xp_reward: int):
        return NotificationBridge._send(
            user, "quest_complete",
            title="Quest Complete!",
            body=f"'{quest_title}' done! Claim {coin_reward:.0f} coins + {xp_reward} XP.",
            data={"quest": quest_title, "coins": coin_reward, "xp": xp_reward},
        )

    @staticmethod
    def achievement_unlocked(user, achievement_name: str, coin_reward: float, xp_reward: int):
        return NotificationBridge._send(
            user, "achievement",
            title="Achievement Unlocked!",
            body=f"🏆 {achievement_name} — {coin_reward:.0f} coins + {xp_reward} XP",
            data={"achievement": achievement_name, "coins": coin_reward, "xp": xp_reward},
        )

    @staticmethod
    def leaderboard_reward(user, rank: int, coins: float, season: str = ""):
        ordinal = {1: "1st 🥇", 2: "2nd 🥈", 3: "3rd 🥉"}.get(rank, f"#{rank}")
        return NotificationBridge._send(
            user, "leaderboard_rank",
            title="Leaderboard Reward!",
            body=f"You finished {ordinal} this week! Prize: {coins:.0f} coins.",
            data={"rank": rank, "coins": coins, "season": season},
        )

    @staticmethod
    def referral_commission(user, referee_username: str, coins: float, level: int = 1):
        return NotificationBridge._send(
            user, "referral_reward",
            title="Referral Commission Earned!",
            body=f"{referee_username} completed a task — you earned {coins:.2f} coins (L{level}).",
            data={"referee": referee_username, "coins": coins, "level": level},
        )

    @staticmethod
    def shop_purchase_success(user, item_name: str, coins_spent: float):
        return NotificationBridge._send(
            user, "shop_purchase",
            title="Purchase Successful!",
            body=f"'{item_name}' added to your inventory. -{coins_spent:.0f} coins.",
            data={"item": item_name, "coins_spent": coins_spent},
        )

    @staticmethod
    def battle_pass_tier(user, tier: int, is_premium: bool, coins: float, xp: int):
        tier_type = "Premium" if is_premium else "Free"
        return NotificationBridge._send(
            user, "battle_pass_tier",
            title=f"Battle Pass Tier {tier} Unlocked!",
            body=f"{tier_type} reward: {coins:.0f} coins + {xp} XP",
            data={"tier": tier, "is_premium": is_premium, "coins": coins, "xp": xp},
        )

    @staticmethod
    def chest_opened(user, chest_name: str, reward_type: str, coins: float = 0):
        reward_str = f"{coins:.0f} coins" if reward_type == "coins" else reward_type
        return NotificationBridge._send(
            user, "chest_opened",
            title=f"You opened a {chest_name}!",
            body=f"Reward: {reward_str}",
            data={"chest": chest_name, "reward_type": reward_type, "coins": coins},
        )

    @staticmethod
    def auction_outbid(user, auction_title: str, refund_coins: float, new_bid: float):
        return NotificationBridge._send(
            user, "auction_outbid",
            title="You've Been Outbid!",
            body=(
                f"Someone outbid you on '{auction_title}'. "
                f"{refund_coins:.0f} coins refunded. Current bid: {new_bid:.0f}."
            ),
            data={"auction": auction_title, "refund": refund_coins, "new_bid": new_bid},
        )

    @staticmethod
    def auction_won(user, auction_title: str, winning_bid: float):
        return NotificationBridge._send(
            user, "auction_won",
            title="You Won the Auction! 🎉",
            body=f"Congratulations! You won '{auction_title}' for {winning_bid:.0f} coins.",
            data={"auction": auction_title, "winning_bid": winning_bid},
        )

    @staticmethod
    def prestige_complete(user, prestige_level: int, bonus_coins: float):
        return NotificationBridge._send(
            user, "prestige",
            title=f"Prestige Level {prestige_level} Achieved! ⭐",
            body=f"You reset and gained Prestige {prestige_level}! Bonus: {bonus_coins:.0f} coins.",
            data={"prestige_level": prestige_level, "bonus_coins": bonus_coins},
        )

    @staticmethod
    def scratch_reward(user, coins: float):
        return NotificationBridge._send(
            user, "scratch_reward",
            title="Scratch Card Reward!",
            body=f"You scratched {coins:.0f} coins! 🎫",
            data={"coins": coins},
        )

    @staticmethod
    def combo_bonus(user, multiplier: float, coins: float):
        return NotificationBridge._send(
            user, "combo_bonus",
            title=f"Combo Bonus x{multiplier:.1f}! 🔥",
            body=f"Your combo multiplier earned you {coins:.0f} extra coins!",
            data={"multiplier": multiplier, "coins": coins},
        )

    @staticmethod
    def send_custom(user, notif_type: str, title: str, body: str, data: dict = None) -> bool:
        """Generic send for any engagement event not listed above."""
        return NotificationBridge._send(user, notif_type, title, body, data)
