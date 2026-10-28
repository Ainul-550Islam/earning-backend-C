# engagement/services/adapters/behavior_analytics_adapter.py
"""
BehaviorAnalyticsAdapter
========================
Wraps api.behavior_analytics for engagement.

Engagement records user behavior so that:
    - Recommendation engine knows what rewards users prefer
    - Anti-fraud system has behavioral baseline
    - Personalization engine can adjust offer order
    - Analytics team can study engagement funnels

Events tracked:
    engagement_action   — checkin, spin, quest, etc.
    reward_received     — amount + source
    shop_view           — item browsed
    shop_purchase       — item bought
    leaderboard_view    — user checked rankings
    achievement_view    — user viewed achievements
    battle_pass_view    — user opened battle pass
    guild_action        — joined/left/posted
    social_action       — liked/followed/friended
"""

import logging
from typing import Optional

logger = logging.getLogger("engagement.adapters.behavior_analytics")


class BehaviorAnalyticsAdapter:
    """
    Engagement → api.behavior_analytics adapter.
    All methods are async-safe and never block the request.
    """

    @staticmethod
    def _track(user, event_type: str, path: str, metadata: dict = None,
                ip: str = None) -> bool:
        """Core track method."""
        try:
            from api.behavior_analytics.services import UserPathService
            UserPathService().record(
                user=user,
                path=path,
                event_type=event_type,
                metadata=metadata or {},
                ip_address=ip or "",
            )
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"BehaviorAnalyticsAdapter._track {event_type}: {e}")
        return False

    @staticmethod
    def _record_click(user, element: str, page: str,
                       metadata: dict = None) -> bool:
        try:
            from api.behavior_analytics.services import ClickMetricService
            ClickMetricService().record_click(
                user=user,
                element=element,
                page=page,
                metadata=metadata or {},
            )
            return True
        except Exception:
            return False

    # ── Engagement-specific tracking ──────────────────────────────────────────

    @staticmethod
    def track_checkin(user, streak: int, coins: float, ip: str = None):
        BehaviorAnalyticsAdapter._track(
            user, "checkin", "/engagement/daily-checkin/",
            {"streak": streak, "coins": coins}, ip
        )

    @staticmethod
    def track_spin(user, outcome_idx: int, coins: float, ip: str = None):
        BehaviorAnalyticsAdapter._track(
            user, "spin", "/engagement/spin-wheel/",
            {"outcome_idx": outcome_idx, "coins": coins}, ip
        )

    @staticmethod
    def track_quest_complete(user, quest_id: int, quest_type: str, coins: float):
        BehaviorAnalyticsAdapter._track(
            user, "quest_complete", "/engagement/quests/",
            {"quest_id": quest_id, "quest_type": quest_type, "coins": coins}
        )

    @staticmethod
    def track_achievement(user, achievement_slug: str, coins: float, xp: int):
        BehaviorAnalyticsAdapter._track(
            user, "achievement_unlock", "/engagement/achievements/",
            {"slug": achievement_slug, "coins": coins, "xp": xp}
        )

    @staticmethod
    def track_shop_purchase(user, item_slug: str, item_type: str,
                             price: float, ip: str = None):
        BehaviorAnalyticsAdapter._track(
            user, "shop_purchase", "/engagement/shop/purchase/",
            {"item": item_slug, "type": item_type, "price": price}, ip
        )
        BehaviorAnalyticsAdapter._record_click(
            user, f"buy_{item_slug}", "/engagement/shop/"
        )

    @staticmethod
    def track_leaderboard_view(user, rank: Optional[int] = None):
        BehaviorAnalyticsAdapter._track(
            user, "page_view", "/engagement/leaderboard/",
            {"user_rank": rank}
        )

    @staticmethod
    def track_battle_pass_view(user, tier: int, is_premium: bool):
        BehaviorAnalyticsAdapter._track(
            user, "page_view", "/engagement/battle-pass/",
            {"tier": tier, "is_premium": is_premium}
        )

    @staticmethod
    def track_social_action(user, action: str, target_id: int = None):
        BehaviorAnalyticsAdapter._track(
            user, f"social_{action}", f"/engagement/social/{action}/",
            {"target_id": target_id}
        )

    @staticmethod
    def track_guild_action(user, action: str, guild_id: int = None):
        BehaviorAnalyticsAdapter._track(
            user, f"guild_{action}", f"/engagement/guilds/{action}/",
            {"guild_id": guild_id}
        )

    @staticmethod
    def track_reward_received(user, amount: float, source: str,
                               new_balance: float):
        BehaviorAnalyticsAdapter._track(
            user, "reward_received", f"/engagement/reward/{source}/",
            {"amount": amount, "source": source, "new_balance": new_balance}
        )

    @staticmethod
    def get_engagement_score(user) -> dict:
        """
        Get behavior-based engagement score for a user.
        Used for personalization and anti-fraud.
        """
        try:
            from api.behavior_analytics.services import EngagementScoreService
            # Note: the service uses calculate_for_user based on our grep
            score_data = EngagementScoreService().calculate_for_user(user)
            return {
                "score":  score_data.get("score", 0),
                "level":  score_data.get("level", "new"),
                "source": "behavior_analytics_app",
            }
        except Exception:
            # Fallback: compute from engagement models
            try:
                from api.engagement.models.checkin import DailyCheckIn
                from api.engagement.models.spinwheel import SpinWheel
                from api.engagement.models.xp import UserXP
                from datetime import timedelta
                from django.utils import timezone

                week_ago = timezone.now() - timedelta(days=7)
                checkins = DailyCheckIn.objects.filter(
                    user=user, created_at__gte=week_ago
                ).count()
                spins = SpinWheel.objects.filter(
                    user=user, spun_at__gte=week_ago
                ).count()
                xp_obj = UserXP.objects.filter(user=user).first()
                level = getattr(xp_obj, "level", 1)
                # Simple heuristic
                score = min(100, (checkins * 10) + (spins * 3) + (level * 5))
                return {"score": score, "level": "active" if score > 50 else "casual",
                        "source": "engagement_fallback"}
            except Exception:
                return {"score": 0, "level": "new", "source": "unavailable"}
