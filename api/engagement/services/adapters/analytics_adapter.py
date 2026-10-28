"""
AnalyticsAdapter
================
Wraps api.analytics for engagement metrics reporting.

Engagement sends events to the analytics pipeline for:
    - Revenue attribution (which engagement feature drives retention)
    - Cohort analysis (Day-1/7/30 retention after feature use)
    - Funnel analysis (spin → quest → shop purchase path)
    - A/B test tracking (feature flag experiment results)
    - Real-time dashboard metrics (active users, coins issued, etc.)

Events sent:
    engagement_session_start
    engagement_action           — any action with value
    engagement_conversion       — shop purchase / battle pass unlock
    engagement_churn_risk       — user has low engagement score
    engagement_viral            — referral chain growing
"""

import logging
logger = logging.getLogger("engagement.adapters.analytics")


class AnalyticsAdapter:

    @staticmethod
    def _send(event: str, user=None, properties: dict = None,
               revenue: float = None) -> bool:
        """Core analytics event sender."""
        payload = {
            "event":      f"engagement.{event}",
            "app":        "engagement",
            "properties": properties or {},
        }
        if user:
            payload["user_id"] = getattr(user, "pk", None)
        if revenue is not None:
            payload["revenue"] = revenue

        try:
            from api.analytics.services import AnalyticsService
            AnalyticsService().track(**payload)
            return True
        except Exception:
            pass

        # Fallback: structured log (picked up by log aggregator)
        logger.info(
            f"[ANALYTICS] event={payload['event']} "
            f"user={payload.get('user_id')} "
            f"props={properties}"
        )
        return False

    # ── Specific analytics events ─────────────────────────────────────────────

    @staticmethod
    def track_checkin(user, streak: int, coins: float):
        AnalyticsAdapter._send("checkin", user,
                                {"streak": streak, "coins": coins})

    @staticmethod
    def track_spin(user, coins: float):
        AnalyticsAdapter._send("spin", user, {"coins": coins})

    @staticmethod
    def track_level_up(user, old_level: int, new_level: int):
        AnalyticsAdapter._send("level_up", user,
                                {"from": old_level, "to": new_level})

    @staticmethod
    def track_quest_complete(user, quest_id: int, quest_type: str, coins: float):
        AnalyticsAdapter._send("quest_complete", user,
                                {"id": quest_id, "type": quest_type, "coins": coins})

    @staticmethod
    def track_achievement(user, slug: str, coins: float):
        AnalyticsAdapter._send("achievement", user,
                                {"slug": slug, "coins": coins})

    @staticmethod
    def track_shop_purchase(user, item_slug: str, item_type: str,
                             price_coins: float):
        AnalyticsAdapter._send("shop_purchase", user,
                                {"item": item_slug, "type": item_type,
                                 "price_coins": price_coins},
                                revenue=price_coins * 0.001)  # 0.1% rev attribution

    @staticmethod
    def track_battle_pass_unlock(user, tier: int, is_premium: bool):
        AnalyticsAdapter._send("battle_pass_tier", user,
                                {"tier": tier, "premium": is_premium})

    @staticmethod
    def track_referral(referrer, referee):
        AnalyticsAdapter._send("referral", referrer,
                                {"referee_id": getattr(referee, "pk", None)})

    @staticmethod
    def track_prestige(user, level: int):
        AnalyticsAdapter._send("prestige", user, {"level": level})

    @staticmethod
    def track_feature_flag(user, flag_slug: str, enabled: bool):
        AnalyticsAdapter._send("feature_flag_evaluated", user,
                                {"flag": flag_slug, "enabled": enabled})

    @staticmethod
    def track_ab_variant(user, test_slug: str, variant_slug: str):
        AnalyticsAdapter._send("ab_variant_assigned", user,
                                {"test": test_slug, "variant": variant_slug})

    @staticmethod
    def track_ab_conversion(user, test_slug: str, variant_slug: str):
        AnalyticsAdapter._send("ab_conversion", user,
                                {"test": test_slug, "variant": variant_slug})

    @staticmethod
    def track_guild_join(user, guild_id: int):
        AnalyticsAdapter._send("guild_join", user, {"guild_id": guild_id})

    @staticmethod
    def track_churn_risk(user, engagement_score: int, last_active_days: int):
        AnalyticsAdapter._send("churn_risk", user,
                                {"score": engagement_score,
                                 "days_inactive": last_active_days})

    @staticmethod
    def flush():
        """Flush any buffered analytics events (called at request end)."""
        try:
            from api.analytics.services import AnalyticsService
            AnalyticsService().flush()
        except Exception:
            pass
