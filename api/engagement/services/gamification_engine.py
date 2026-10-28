# engagement/services/gamification_engine.py
"""
Central Gamification Orchestration Engine — World #1 Complete 100%
Every user action routes through here so ALL 35 systems stay in sync.
"""
import logging
from datetime import date
from django.db import models
from .achievement_service import AchievementService
from .quest_service import QuestService
from .notification_service import NotificationService
from .analytics_service import AnalyticsService
from .webhook_service import WebhookService

logger = logging.getLogger(__name__)


class GamificationEngine:

    @classmethod
    def on_checkin(cls, user, checkin, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        streak = checkin.consecutive_days
        QuestService.record_action(user, "checkin", increment=1, tenant=t)
        from ..models.checkin import DailyCheckIn
        total_ci = DailyCheckIn.objects.filter(user=user).count()
        unlocked  = AchievementService.check_and_unlock(user, "streak", streak, t)
        unlocked += AchievementService.check_and_unlock(user, "coins", total_ci, t)
        cls._grant_battle_pass_xp(user, "checkin", t)
        cls._guild_contribute(user, xp_amount=10, metric="total_checkins", t=t)
        cls._seasonal_action(user, "checkin", t)
        cls._register_combo(user, "checkin")
        cls._check_milestones(user, t)
        if streak in (3, 7, 14, 30, 50, 100, 365):
            cls._post_feed(user, "streak_milestone", f"{streak}-Day Streak!", f"Reached a {streak}-day streak!", t)
        if streak in (3, 7, 14, 30, 100):
            NotificationService.send(user, "checkin_reminder",
                title=f"🔥 {streak}-Day Streak!", body=f"You're on a {streak}-day streak!",
                data={"streak": streak}, tenant=t)
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        AnalyticsService.record(user, "checkin", coins_delta=float(checkin.coins_earned),
                                xp_delta=checkin.xp_earned, tenant=t)
        WebhookService.dispatch("checkin", {"user_id": user.pk, "streak": streak,
            "coins_earned": float(checkin.coins_earned), "date": str(date.today())}, tenant=t)

    @classmethod
    def on_spin(cls, user, spin, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        QuestService.record_action(user, "spin", increment=1, tenant=t)
        from ..models.spinwheel import SpinWheel
        total_spins = SpinWheel.objects.filter(user=user).count()
        unlocked = AchievementService.check_and_unlock(user, "spins", total_spins, t)
        cls._grant_battle_pass_xp(user, "spin", t)
        cls._seasonal_action(user, "spin", t)
        cls._register_combo(user, "spin")
        cls._check_milestones(user, t)
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        AnalyticsService.record(user, "spin", coins_delta=float(spin.coins_won), xp_delta=spin.xp_earned, tenant=t)
        WebhookService.dispatch("spin", {"user_id": user.pk, "coins_won": float(spin.coins_won), "is_boosted": spin.is_boosted}, tenant=t)

    @classmethod
    def on_level_up(cls, user, old_level: int, new_level: int, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        unlocked = AchievementService.check_and_unlock(user, "level", new_level, t)
        cls._check_milestones(user, t)
        cls._post_feed(user, "level_up", f"Level {new_level}!", f"Reached Level {new_level}!", t)
        NotificationService.send(user, "level_up", title=f"⬆️ Level {new_level}!",
            body=f"You reached Level {new_level}. Keep going!",
            data={"old_level": old_level, "new_level": new_level}, tenant=t)
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        AnalyticsService.record(user, "level_up", properties={"old_level": old_level, "new_level": new_level}, tenant=t)
        WebhookService.dispatch("level_up", {"user_id": user.pk, "old_level": old_level, "new_level": new_level}, tenant=t)

    @classmethod
    def on_purchase(cls, user, purchase, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        QuestService.record_action(user, "buy_item", increment=1, tenant=t)
        from ..models.shop import ShopPurchase
        total = ShopPurchase.objects.filter(user=user).count()
        unlocked = AchievementService.check_and_unlock(user, "purchase", total, t)
        cls._grant_battle_pass_xp(user, "shop_purchase", t)
        cls._seasonal_action(user, "shop_purchase", t)
        cls._check_milestones(user, t)
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        AnalyticsService.record(user, "shop_purchased", coins_delta=-float(purchase.coins_spent), tenant=t)
        WebhookService.dispatch("shop_purchase", {"user_id": user.pk, "item_slug": purchase.item.slug, "coins_spent": float(purchase.coins_spent)}, tenant=t)

    @classmethod
    def on_referral(cls, user, referral, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        from ..models.referral import Referral
        total = Referral.objects.filter(referrer=user, status__in=["confirmed", "rewarded"]).count()
        unlocked = AchievementService.check_and_unlock(user, "referral", total, t)
        cls._grant_battle_pass_xp(user, "referral", t)
        cls._check_milestones(user, t)
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        AnalyticsService.record(user, "referral", properties={"referral_id": referral.pk}, tenant=t)
        WebhookService.dispatch("referral", {"user_id": user.pk, "referral_id": referral.pk}, tenant=t)

    @classmethod
    def on_quest_complete(cls, user, user_quest, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        from ..models.quest import UserQuest
        total_quests = UserQuest.objects.filter(user=user, status="completed").count()
        unlocked = AchievementService.check_and_unlock(user, "quest", total_quests, t)
        cls._grant_battle_pass_xp(user, "quest_complete", t)
        cls._guild_contribute(user, xp_amount=50, metric="total_quests", t=t)
        cls._check_milestones(user, t)
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        AnalyticsService.record(user, "quest_completed", xp_delta=user_quest.quest.xp_reward,
                                coins_delta=float(user_quest.quest.coin_reward), tenant=t)
        WebhookService.dispatch("quest_complete", {"user_id": user.pk, "quest_slug": user_quest.quest.slug}, tenant=t)

    @classmethod
    def on_achievement_unlock(cls, user, achievement, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        cls._grant_battle_pass_xp(user, "achievement", t)
        cls._post_feed(user, "achievement", f"Unlocked: {achievement.name}!", achievement.description, t)
        cls._check_milestones(user, t)
        AnalyticsService.record(user, "achievement_unlocked", xp_delta=achievement.xp_reward,
                                properties={"slug": achievement.slug}, tenant=t)
        WebhookService.dispatch("achievement", {"user_id": user.pk,
            "achievement_slug": achievement.slug, "achievement_name": achievement.name}, tenant=t)

    @classmethod
    def on_chest_open(cls, user, opening, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        AnalyticsService.record(user, "chest_opened", coins_delta=float(opening.coins_won),
                                xp_delta=opening.xp_won, tenant=t)

    @classmethod
    def on_prestige(cls, user, prestige_level: int, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        unlocked = AchievementService.check_and_unlock(user, "prestige", prestige_level, t)
        cls._post_feed(user, "prestige", f"Prestige {prestige_level}!", "Reset and reached a new prestige level!", t)
        cls._check_milestones(user, t)
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        AnalyticsService.record(user, "session_end", properties={"prestige_level": prestige_level}, tenant=t)
        WebhookService.dispatch("prestige", {"user_id": user.pk, "prestige_level": prestige_level}, tenant=t)

    @classmethod
    def on_guild_join(cls, user, guild, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        cls._post_feed(user, "guild_join", f"Joined {guild.name}!", f"Now a member of {guild.name}.", t)
        AnalyticsService.record(user, "guild_joined", properties={"guild_id": guild.pk, "guild_name": guild.name}, tenant=t)
        WebhookService.dispatch("guild_event", {"user_id": user.pk, "guild_id": guild.pk, "event": "joined"}, tenant=t)

    @classmethod
    def on_leaderboard_reward(cls, user, rank: int, coins: float, tenant=None):
        t = tenant or getattr(user, "tenant", None)
        if rank <= 3:
            cls._post_feed(user, "leaderboard_top", f"Leaderboard #{rank}!",
                           f"Finished #{rank} on today's leaderboard!", t)
        AnalyticsService.record(user, "campaign_received", coins_delta=coins,
                                properties={"rank": rank, "type": "leaderboard_reward"}, tenant=t)
        WebhookService.dispatch("leaderboard", {"user_id": user.pk, "rank": rank, "coins": coins}, tenant=t)

    @classmethod
    def on_earning_complete(cls, user, earning_data, tenant=None):
        """Handle earning task/CPAlead completion."""
        t = tenant or getattr(user, "tenant", None)
        
        # Track total earnings for achievements
        total_earnings = cls._get_total_earnings(user, t)
        unlocked = AchievementService.check_and_unlock(user, "earnings", total_earnings, t)
        
        # Grant battle pass XP for earning completions
        cls._grant_battle_pass_xp(user, "earning_task", t)
        
        # Check milestones
        cls._check_milestones(user, t)
        
        # Register combo for earning streaks
        cls._register_combo(user, "earning")
        
        # Handle seasonal events
        cls._seasonal_action(user, "earning_task", t)
        
        # Notify achievements
        for a in unlocked:
            cls._notify_achievement(user, a, t)
        
        # Record analytics
        AnalyticsService.record(
            user, 
            "earning_completed", 
            coins_delta=earning_data.get('coins_granted', 0),
            xp_delta=earning_data.get('xp_granted', 0),
            value=earning_data.get('amount', 0),
            properties={
                'task_id': earning_data.get('task_id'),
                'offer_id': earning_data.get('offer_id'),
                'conversion_type': earning_data.get('conversion_type', 'unknown')
            },
            tenant=t
        )
        
        # Dispatch webhook
        WebhookService.dispatch("earning_completed", {
            "user_id": user.pk,
            "earning_data": earning_data
        }, tenant=t)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _notify_achievement(user, achievement, tenant):
        NotificationService.send(user, "achievement",
            title=f"🏆 {achievement.name} Unlocked!", body=achievement.description,
            icon=achievement.icon, data={"achievement_slug": achievement.slug}, tenant=tenant)

    @staticmethod
    def _grant_battle_pass_xp(user, action: str, tenant):
        try:
            from .battle_pass_service import BattlePassService
            result = BattlePassService.grant_xp(user, action, tenant)
            if result.get("tier_ups"):
                NotificationService.send(user, "reward",
                    title=f"Battle Pass Tier {result['new_tier']}!",
                    body=f"You reached Battle Pass Tier {result['new_tier']}!",
                    data={"new_tier": result["new_tier"]}, tenant=tenant)
        except Exception as exc:
            logger.debug("_grant_battle_pass_xp: %s", exc)

    @staticmethod
    def _guild_contribute(user, xp_amount: int, metric: str, t):
        try:
            from ..models.guild import GuildMember
            from .guild_service import GuildService
            member = GuildMember.objects.filter(user=user, status="active").select_related("guild").first()
            if member:
                GuildService.contribute_xp(user, member.guild, xp_amount)
                GuildService.advance_challenge(member.guild, metric, increment=1)
        except Exception as exc:
            logger.debug("_guild_contribute: %s", exc)

    @staticmethod
    def _seasonal_action(user, action: str, tenant):
        try:
            from .seasonal_event_service import SeasonalEventService
            SeasonalEventService.record_action(user, action, increment=1, tenant=tenant)
        except Exception as exc:
            logger.debug("_seasonal_action: %s", exc)

    @staticmethod
    def _register_combo(user, action: str):
        try:
            from .combo_service import ComboService
            ComboService.register_action(user, action)
        except Exception as exc:
            logger.debug("_register_combo: %s", exc)

    @staticmethod
    def _check_milestones(user, tenant):
        try:
            from .prestige_service import MilestoneService
            newly_unlocked = MilestoneService.check_all(user, tenant)
            for milestone in newly_unlocked:
                NotificationService.send(user, "achievement",
                    title=f"🎯 Milestone: {milestone.name}",
                    body="You reached a major milestone!",
                    data={"milestone_slug": milestone.slug}, tenant=tenant)
        except Exception as exc:
            logger.debug("_check_milestones: %s", exc)

    @staticmethod
    def _post_feed(user, feed_type: str, title: str, body: str, tenant):
        try:
            from .social_service import SocialService
            SocialService.post_feed_item(user, feed_type, title, body, tenant=tenant)
        except Exception as exc:
            logger.debug("_post_feed: %s", exc)

    @staticmethod
    def _get_total_earnings(user, tenant):
        """Calculate total earnings for a user from various sources."""
        try:
            # Try to get from EarningTask first (if available)
            try:
                from api.models import EarningTask
                qs = EarningTask.objects.filter(user=user, completed_at__isnull=False)
                if tenant:
                    qs = qs.filter(tenant=tenant)
                total = qs.aggregate(total=models.Sum('amount'))['total'] or 0
                return float(total)
            except ImportError:
                pass
            
            # Fallback to engagement analytics
            from ..models.analytics import EngagementEvent
            qs = EngagementEvent.objects.filter(
                user=user, 
                event_type__in=["earning_task_completed", "cpa_lead_conversion"]
            )
            if tenant:
                qs = qs.filter(tenant=tenant)
            total = qs.aggregate(total=models.Sum('value'))['total'] or 0
            return float(total)
            
        except Exception as exc:
            logger.debug("_get_total_earnings: %s", exc)
            return 0.0
