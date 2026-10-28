# engagement/services/adapters/audit_log_adapter.py
"""
AuditLogAdapter
===============
Wraps api.audit_logs for engagement.

Every significant engagement event is audit-logged:
    - Coin credit/debit
    - Level up
    - Achievement unlock
    - Shop purchase
    - Referral registration
    - Anti-cheat flag
    - Admin actions (admin_grant_xp, etc.)

Log schema:
    action:      snake_case action name
    actor:       user who did it
    target:      user/object affected (if different from actor)
    app:         "engagement"
    level:       "info" | "warning" | "critical"
    data:        {coins, xp, source, ip, ...}
"""

import logging
from typing import Optional

logger = logging.getLogger("engagement.adapters.audit_log")


class AuditLogAdapter:
    """
    Engagement → api.audit_logs adapter.
    All methods are fire-and-forget — never block engagement flow.
    """

    # ── Internal sender ───────────────────────────────────────────────────────

    @staticmethod
    def _log(action: str, actor, target=None, level: str = "info",
             data: dict = None, ip: str = None) -> bool:
        """Core log method — tries api.audit_logs, falls back to Django logging."""
        payload = {
            "action":     action,
            "app":        "engagement",
            "level":      level,
            "ip_address": ip or "",
            "data":       data or {},
        }
        if actor:
            payload["user"] = actor
            payload["user_id"] = getattr(actor, "pk", None)
        if target and target != actor:
            payload["target_id"] = getattr(target, "pk", None)
            payload["target_type"] = type(target).__name__

        # ── Try api.audit_logs ────────────────────────────────────────────────
        try:
            from api.audit_logs.services.LogService import LogService
            LogService().create_log(**payload)
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"AuditLogAdapter api.audit_logs failed: {e}")

        # ── Fallback: structured Django log ───────────────────────────────────
        log_fn = getattr(logger, level if level in ("info", "warning", "error") else "info")
        log_fn(
            f"[AUDIT] action={action} user={getattr(actor, 'pk', '?')} "
            f"app=engagement data={data}"
        )
        return False

    # ── Convenience methods ───────────────────────────────────────────────────

    @staticmethod
    def log_coins_earned(user, amount: float, source: str, new_balance: float,
                          ip: str = None, wallet_txn_id: str = None):
        AuditLogAdapter._log(
            action="engagement.coins_earned",
            actor=user,
            level="info",
            data={
                "amount": amount,
                "source": source,
                "new_balance": new_balance,
                "wallet_txn_id": wallet_txn_id,
            },
            ip=ip,
        )

    @staticmethod
    def log_coins_deducted(user, amount: float, source: str, new_balance: float,
                            ip: str = None):
        AuditLogAdapter._log(
            action="engagement.coins_deducted",
            actor=user,
            level="info",
            data={"amount": amount, "source": source, "new_balance": new_balance},
            ip=ip,
        )

    @staticmethod
    def log_level_up(user, old_level: int, new_level: int, total_xp: int):
        AuditLogAdapter._log(
            action="engagement.level_up",
            actor=user,
            level="info",
            data={"old_level": old_level, "new_level": new_level, "total_xp": total_xp},
        )

    @staticmethod
    def log_achievement_unlocked(user, achievement_slug: str, coins: float, xp: int):
        AuditLogAdapter._log(
            action="engagement.achievement_unlocked",
            actor=user,
            level="info",
            data={"achievement": achievement_slug, "coins": coins, "xp": xp},
        )

    @staticmethod
    def log_checkin(user, streak: int, coins: float, ip: str = None):
        AuditLogAdapter._log(
            action="engagement.daily_checkin",
            actor=user,
            level="info",
            data={"streak": streak, "coins": coins},
            ip=ip,
        )

    @staticmethod
    def log_spin(user, coins: float, outcome_idx: int, ip: str = None):
        AuditLogAdapter._log(
            action="engagement.spin_wheel",
            actor=user,
            level="info",
            data={"coins": coins, "outcome_idx": outcome_idx},
            ip=ip,
        )

    @staticmethod
    def log_shop_purchase(user, item_slug: str, coins: float, quantity: int = 1):
        AuditLogAdapter._log(
            action="engagement.shop_purchase",
            actor=user,
            level="info",
            data={"item": item_slug, "coins": coins, "quantity": quantity},
        )

    @staticmethod
    def log_referral(referrer, referee, code: str):
        AuditLogAdapter._log(
            action="engagement.referral_registered",
            actor=referrer,
            target=referee,
            level="info",
            data={"code": code, "referee_id": getattr(referee, "pk", None)},
        )

    @staticmethod
    def log_anti_cheat_flag(user, rule_slug: str, severity: int,
                             details: dict, ip: str = None):
        AuditLogAdapter._log(
            action="engagement.anti_cheat_flag",
            actor=user,
            level="warning",
            data={"rule": rule_slug, "severity": severity, "details": details},
            ip=ip,
        )

    @staticmethod
    def log_admin_action(admin_user, target_user, action: str,
                          details: dict = None):
        AuditLogAdapter._log(
            action=f"engagement.admin.{action}",
            actor=admin_user,
            target=target_user,
            level="info",
            data=details or {},
        )

    @staticmethod
    def log_fraud_block(user, action: str, score: int, reason: str,
                         ip: str = None):
        AuditLogAdapter._log(
            action="engagement.fraud_blocked",
            actor=user,
            level="warning",
            data={"action": action, "score": score, "reason": reason},
            ip=ip,
        )

    @staticmethod
    def log_battle_pass_tier(user, tier: int, is_premium: bool,
                              coins: float, xp: int):
        AuditLogAdapter._log(
            action="engagement.battle_pass_tier",
            actor=user,
            level="info",
            data={"tier": tier, "is_premium": is_premium,
                  "coins": coins, "xp": xp},
        )

    @staticmethod
    def log_auction(user, auction_id: int, action: str,
                     bid_amount: float = 0, ip: str = None):
        AuditLogAdapter._log(
            action=f"engagement.auction_{action}",
            actor=user,
            level="info",
            data={"auction_id": auction_id, "bid": bid_amount},
            ip=ip,
        )

    @staticmethod
    def log_prestige(user, prestige_level: int, bonus_coins: float):
        AuditLogAdapter._log(
            action="engagement.prestige",
            actor=user,
            level="info",
            data={"prestige_level": prestige_level, "bonus_coins": bonus_coins},
        )

    @staticmethod
    def log_generic(user, action: str, data: dict = None,
                     level: str = "info", ip: str = None):
        """Generic log for any engagement action not covered above."""
        AuditLogAdapter._log(
            action=f"engagement.{action}",
            actor=user,
            level=level,
            data=data or {},
            ip=ip,
        )
