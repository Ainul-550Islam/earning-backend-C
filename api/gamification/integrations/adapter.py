"""
api/gamification/integrations/adapter.py

Gamification ↔ সব module-এর central integration hub।

এই adapter-টা gamification-এর বাইরের module থেকে event receive করে
এবং gamification-এর service layer-এ delegate করে।

Connected modules:
  ┌─────────────────────────────────────────────────────────────┐
  │  notifications  ← achievement awarded, leaderboard finalized │
  │  wallet         → deposit/withdrawal → achievement check     │
  │  users          → login/KYC/profile  → milestone check       │
  │  referral       → referral contest   → ContestCycle sync     │
  │  support        → ticket resolved    → points award          │
  │  payment_gw     → conversion done    → achievement check     │
  │  engagement     → check-in/spin      → streak achievement    │
  │  analytics      ← all gamification events                    │
  └─────────────────────────────────────────────────────────────┘

Usage (in any external module):
    from api.gamification.integrations.adapter import gamification_adapter

    # wallet credit হলে:
    gamification_adapter.on_wallet_credited(user=user, amount=amount, source="deposit")

    # user login হলে:
    gamification_adapter.on_user_event(user=user, event="first_login")
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# INTEGRATION_SYSTEM: CircuitBreaker protecting outbound notification/analytics calls
try:
    from api.gamification.INTEGRATION_SYSTEM.wiring import call_with_circuit_breaker
    _HAS_CIRCUIT_BREAKER = True
except Exception:
    _HAS_CIRCUIT_BREAKER = False
    def call_with_circuit_breaker(fn, *args, fallback=None, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return fallback

_GUARD = "api.gamification.integrations.adapter"  # prevent double-import


class GamificationAdapter:
    """
    Gamification-এর সাথে সব module-এর integration point।

    প্রতিটি public method একটি external event represent করে।
    সব method defensive — কোনো exception কখনো caller-এ bubble up করবে না।
    """

    # ─── Wallet Integration ────────────────────────────────────────────────────

    def on_wallet_credited(
        self,
        user: Any,
        amount: float,
        source: str = "deposit",
        **kwargs,
    ) -> None:
        """
        Wallet credit হলে — deposit milestone চেক করো।

        Called from: api.wallet (after credit operation)
        Triggers:    MILESTONE achievement (earned_10, earned_100, earned_1000)

        Usage:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.on_wallet_credited(user=user, amount=500.0, source="deposit")
        """
        try:
            from .wallet_adapter import WalletGamificationAdapter
            WalletGamificationAdapter().on_credited(user=user, amount=amount, source=source)
        except Exception as exc:
            logger.error("[gamification_adapter] on_wallet_credited failed: %s", exc)

    def on_wallet_withdrawal(
        self,
        user: Any,
        amount: float,
        status: str,
        **kwargs,
    ) -> None:
        """
        Withdrawal approved/processed হলে।

        Called from: api.wallet (after withdrawal)
        Triggers:    MILESTONE achievement (first_withdrawal)
        """
        try:
            from .wallet_adapter import WalletGamificationAdapter
            WalletGamificationAdapter().on_withdrawal(user=user, amount=amount, status=status)
        except Exception as exc:
            logger.error("[gamification_adapter] on_wallet_withdrawal failed: %s", exc)

    # ─── Users Integration ─────────────────────────────────────────────────────

    def on_user_event(
        self,
        user: Any,
        event: str,
        context: Optional[dict] = None,
        **kwargs,
    ) -> None:
        """
        User lifecycle event হলে।

        Called from: api.users (signals/post_save)
        Events:      first_login, profile_complete, kyc_verified,
                     first_withdrawal, referral_first
        Triggers:    MILESTONE achievement

        Usage:
            gamification_adapter.on_user_event(user=user, event="first_login")
            gamification_adapter.on_user_event(user=user, event="kyc_verified")
        """
        try:
            from .users_adapter import UsersGamificationAdapter
            UsersGamificationAdapter().on_event(user=user, event=event, context=context or {})
        except Exception as exc:
            logger.error("[gamification_adapter] on_user_event(%s) failed: %s", event, exc)

    def on_user_tier_changed(
        self,
        user: Any,
        old_tier: str,
        new_tier: str,
        **kwargs,
    ) -> None:
        """
        User tier upgrade হলে (BRONZE → SILVER → GOLD → PLATINUM → DIAMOND)।

        Called from: api.users.profile (tier logic)
        Triggers:    MILESTONE achievement (tier_gold, tier_platinum, etc.)
        """
        try:
            from .users_adapter import UsersGamificationAdapter
            UsersGamificationAdapter().on_tier_changed(
                user=user, old_tier=old_tier, new_tier=new_tier
            )
        except Exception as exc:
            logger.error("[gamification_adapter] on_user_tier_changed failed: %s", exc)

    # ─── Notifications Integration ─────────────────────────────────────────────

    def notify_achievement_awarded(
        self,
        achievement: Any,
        **kwargs,
    ) -> None:
        """
        Achievement award হলে notification পাঠাও।

        Called from: gamification receivers.on_achievement_awarded
        Sends:       push + in_app notification via api.notifications
        """
        try:
            from .notifications_adapter import NotificationsGamificationAdapter
            def _send():
                NotificationsGamificationAdapter().send_achievement_notification(achievement)
            call_with_circuit_breaker(_send, fallback=None)
        except Exception as exc:
            logger.error("[gamification_adapter] notify_achievement_awarded failed: %s", exc)

    def notify_leaderboard_finalized(
        self,
        snapshot: Any,
        top_n: int = 10,
        **kwargs,
    ) -> None:
        """
        Leaderboard finalize হলে top users-দের notify করো।

        Called from: gamification receivers.on_leaderboard_snapshot_finalized
        Sends:       in_app notification to top N users
        """
        try:
            from .notifications_adapter import NotificationsGamificationAdapter
            NotificationsGamificationAdapter().send_leaderboard_notification(
                snapshot=snapshot, top_n=top_n
            )
        except Exception as exc:
            logger.error("[gamification_adapter] notify_leaderboard_finalized failed: %s", exc)

    def notify_contest_reward(
        self,
        user: Any,
        reward: Any,
        rank: int,
        **kwargs,
    ) -> None:
        """
        Contest reward distribute হলে winner-কে notify করো।

        Called from: gamification.services.distribute_cycle_rewards
        Sends:       push + in_app notification
        """
        try:
            from .notifications_adapter import NotificationsGamificationAdapter
            NotificationsGamificationAdapter().send_contest_reward_notification(
                user=user, reward=reward, rank=rank
            )
        except Exception as exc:
            logger.error("[gamification_adapter] notify_contest_reward failed: %s", exc)

    # ─── Referral Integration ──────────────────────────────────────────────────

    def on_referral_contest_started(
        self,
        referral_contest: Any,
        **kwargs,
    ) -> None:
        """
        Referral contest start হলে gamification-এ ContestCycle তৈরি করো।

        Called from: api.referral (contest creation signal)
        Creates:     ContestCycle (DRAFT) in gamification
        """
        try:
            from .referral_adapter import ReferralGamificationAdapter
            ReferralGamificationAdapter().on_contest_started(referral_contest)
        except Exception as exc:
            logger.error("[gamification_adapter] on_referral_contest_started failed: %s", exc)

    def on_referral_commission_earned(
        self,
        user: Any,
        amount: float,
        referral_count: int,
        **kwargs,
    ) -> None:
        """
        Referral commission earn হলে achievement চেক করো।

        Called from: api.referral (commission credited)
        Triggers:    MILESTONE achievement
        """
        try:
            from .referral_adapter import ReferralGamificationAdapter
            ReferralGamificationAdapter().on_commission_earned(
                user=user, amount=amount, referral_count=referral_count
            )
        except Exception as exc:
            logger.error("[gamification_adapter] on_referral_commission_earned failed: %s", exc)

    # ─── Support Integration ───────────────────────────────────────────────────

    def on_support_ticket_resolved(
        self,
        ticket: Any,
        **kwargs,
    ) -> None:
        """
        Support ticket resolve হলে user-কে loyalty points দাও।

        Called from: api.support (ticket status change)
        Triggers:    BONUS achievement + points
        """
        try:
            from .support_adapter import SupportGamificationAdapter
            SupportGamificationAdapter().on_ticket_resolved(ticket)
        except Exception as exc:
            logger.error("[gamification_adapter] on_support_ticket_resolved failed: %s", exc)

    def on_support_csat_submitted(
        self,
        ticket: Any,
        score: int,
        **kwargs,
    ) -> None:
        """
        CSAT rating submit হলে।

        Called from: api.support (rating submitted)
        Triggers:    BONUS points for good ratings (score >= 4)
        """
        try:
            from .support_adapter import SupportGamificationAdapter
            SupportGamificationAdapter().on_csat_submitted(ticket=ticket, score=score)
        except Exception as exc:
            logger.error("[gamification_adapter] on_support_csat_submitted failed: %s", exc)

    def get_user_gamification_context(
        self,
        user: Any,
    ) -> dict:
        """
        Support priority নির্ধারণের জন্য user-এর gamification status।

        Called from: api.support (SLA/priority calculation)
        Returns:     {is_vip, total_achievements, priority: "high"|"medium"|"low"}
        """
        try:
            from .support_adapter import SupportGamificationAdapter
            return SupportGamificationAdapter().get_user_context(user)
        except Exception as exc:
            logger.error("[gamification_adapter] get_user_gamification_context failed: %s", exc)
            return {"is_vip": False, "total_achievements": 0, "priority": "low"}

    # ─── Payment Gateway Integration ───────────────────────────────────────────

    def on_payment_deposit_completed(
        self,
        user: Any,
        amount: float,
        deposit: Any = None,
        **kwargs,
    ) -> None:
        """
        Deposit complete হলে achievement milestone চেক করো।

        Called from: api.payment_gateways IntegrationAdapter
        Triggers:    MILESTONE achievement (earned_10, earned_100, etc.)
        """
        try:
            from .payment_adapter import PaymentGamificationAdapter
            PaymentGamificationAdapter().on_deposit_completed(
                user=user, amount=amount, deposit=deposit
            )
        except Exception as exc:
            logger.error("[gamification_adapter] on_payment_deposit_completed failed: %s", exc)

    def on_conversion_approved(
        self,
        user: Any,
        payout: float,
        conversion: Any = None,
        **kwargs,
    ) -> None:
        """
        Offerwall/postback conversion approve হলে।

        Called from: api.payment_gateways IntegrationAdapter
        Triggers:    MILESTONE achievement
        """
        try:
            from .payment_adapter import PaymentGamificationAdapter
            PaymentGamificationAdapter().on_conversion_approved(
                user=user, payout=payout, conversion=conversion
            )
        except Exception as exc:
            logger.error("[gamification_adapter] on_conversion_approved failed: %s", exc)

    # ─── Engagement Integration ────────────────────────────────────────────────

    def on_daily_checkin(
        self,
        user: Any,
        consecutive_days: int,
        **kwargs,
    ) -> None:
        """
        Daily check-in হলে streak achievement চেক করো।

        Called from: api.engagement (DailyCheckIn created)
        Triggers:    STREAK achievement (3-day, 7-day, 30-day streaks)
        """
        try:
            from .engagement_adapter import EngagementGamificationAdapter
            EngagementGamificationAdapter().on_checkin(
                user=user, consecutive_days=consecutive_days
            )
        except Exception as exc:
            logger.error("[gamification_adapter] on_daily_checkin failed: %s", exc)

    def on_spin_wheel(
        self,
        user: Any,
        coins_won: int,
        **kwargs,
    ) -> None:
        """
        Spin wheel use করলে।

        Called from: api.engagement (SpinWheel created)
        Triggers:    BONUS achievement (big win)
        """
        try:
            from .engagement_adapter import EngagementGamificationAdapter
            EngagementGamificationAdapter().on_spin(user=user, coins_won=coins_won)
        except Exception as exc:
            logger.error("[gamification_adapter] on_spin_wheel failed: %s", exc)

    # ─── Analytics Integration ─────────────────────────────────────────────────

    def track_event(
        self,
        event_name: str,
        user: Any = None,
        properties: Optional[dict] = None,
        **kwargs,
    ) -> None:
        """
        Gamification event-কে analytics-এ track করো।

        Called internally by other adapter methods.
        Sends to: api.analytics

        Usage:
            gamification_adapter.track_event(
                "achievement_awarded",
                user=user,
                properties={"type": "BADGE", "points": 100}
            )
        """
        try:
            from .analytics_adapter import AnalyticsGamificationAdapter
            AnalyticsGamificationAdapter().track(
                event_name=event_name, user=user, properties=properties or {}
            )
        except Exception as exc:
            logger.debug("[gamification_adapter] track_event(%s) failed: %s", event_name, exc)



    # ─── KYC Integration ───────────────────────────────────────────────────────

    def on_kyc_verified(self, user: Any, kyc: Any = None, **kwargs) -> None:
        """KYC verified → badge + 75 points। api.kyc থেকে call করো।"""
        try:
            from .kyc_adapter import KYCGamificationAdapter
            KYCGamificationAdapter().on_kyc_verified(user=user, kyc=kyc)
        except Exception as exc:
            logger.error("[gamification_adapter] on_kyc_verified failed: %s", exc)

    def on_kyc_rejected(self, user: Any, kyc: Any = None, reason: str = "", **kwargs) -> None:
        """KYC rejected → শুধু analytics track করো।"""
        try:
            from .kyc_adapter import KYCGamificationAdapter
            KYCGamificationAdapter().on_kyc_rejected(user=user, kyc=kyc, reason=reason)
        except Exception as exc:
            logger.error("[gamification_adapter] on_kyc_rejected failed: %s", exc)

    # ─── Subscription Integration ──────────────────────────────────────────────

    def on_subscription_activated(self, sender, instance, **kwargs) -> None:
        """Subscription active → Subscriber badge। api.subscription signal থেকে।"""
        try:
            from .subscription_adapter import SubscriptionGamificationAdapter
            SubscriptionGamificationAdapter().on_activated(sender=sender, instance=instance)
        except Exception as exc:
            logger.error("[gamification_adapter] on_subscription_activated failed: %s", exc)

    def on_subscription_plan_changed(self, sender, instance,
                                     old_plan=None, new_plan=None, **kwargs) -> None:
        """Plan upgrade → tier bonus। api.subscription plan_changed signal থেকে।"""
        try:
            from .subscription_adapter import SubscriptionGamificationAdapter
            SubscriptionGamificationAdapter().on_plan_changed(
                sender=sender, instance=instance, old_plan=old_plan, new_plan=new_plan)
        except Exception as exc:
            logger.error("[gamification_adapter] on_subscription_plan_changed failed: %s", exc)

    # ─── PayoutQueue Integration ───────────────────────────────────────────────

    def on_payout_succeeded(self, item: Any, **kwargs) -> None:
        """Payout success → count milestone। api.payout_queue signal থেকে।"""
        try:
            from .payout_queue_adapter import PayoutQueueGamificationAdapter
            PayoutQueueGamificationAdapter().on_payout_succeeded(item=item)
        except Exception as exc:
            logger.error("[gamification_adapter] on_payout_succeeded failed: %s", exc)

    # ─── Offerwall Integration ─────────────────────────────────────────────────

    def on_offer_completed(self, user: Any, payout: float = 0,
                           network: str = "", offer_id: str = "", **kwargs) -> None:
        """Offer complete → count + payout milestone। api.offerwall থেকে।"""
        try:
            from .offerwall_adapter import OfferwallGamificationAdapter
            OfferwallGamificationAdapter().on_offer_completed(
                user=user, payout=payout, network=network, offer_id=offer_id)
        except Exception as exc:
            logger.error("[gamification_adapter] on_offer_completed failed: %s", exc)

    # ─── PostbackEngine Integration ────────────────────────────────────────────

    def on_postback_rewarded(self, raw_log: Any = None,
                             conversion: Any = None, **kwargs) -> None:
        """Postback rewarded → points/USD milestone। api.postback_engine signal থেকে।"""
        try:
            from .postback_engine_adapter import PostbackEngineGamificationAdapter
            PostbackEngineGamificationAdapter().on_postback_rewarded(
                raw_log=raw_log, conversion=conversion)
        except Exception as exc:
            logger.error("[gamification_adapter] on_postback_rewarded failed: %s", exc)

    # ─── DJoyalty Integration ──────────────────────────────────────────────────

    def on_djoyalty_tier_upgraded(self, event: Any, **kwargs) -> None:
        """DJoyalty tier up → gamification tier badge। djoyalty EventRegistry থেকে।"""
        try:
            from .djoyalty_adapter import DJoyaltyGamificationAdapter
            DJoyaltyGamificationAdapter().on_tier_upgraded(event)
        except Exception as exc:
            logger.error("[gamification_adapter] on_djoyalty_tier_upgraded failed: %s", exc)

    def on_djoyalty_badge_unlocked(self, event: Any, **kwargs) -> None:
        """DJoyalty badge → gamification badge sync।"""
        try:
            from .djoyalty_adapter import DJoyaltyGamificationAdapter
            DJoyaltyGamificationAdapter().on_badge_unlocked(event)
        except Exception as exc:
            logger.error("[gamification_adapter] on_djoyalty_badge_unlocked failed: %s", exc)

    # ─── Monetization Integration ──────────────────────────────────────────────

    def on_monetization_level_up(self, user_level: Any, **kwargs) -> None:
        """UserLevel up → level achievement। monetization_tools signal থেকে।"""
        try:
            from .monetization_adapter import MonetizationGamificationAdapter
            MonetizationGamificationAdapter().on_level_up(user_level)
        except Exception as exc:
            logger.error("[gamification_adapter] on_monetization_level_up failed: %s", exc)

    # ─── Security Integration ──────────────────────────────────────────────────

    def on_user_banned(self, sender=None, instance=None,
                       created: bool = False, **kwargs) -> None:
        """UserBan → achievements freeze। api.security post_save থেকে।"""
        try:
            from .security_adapter import SecurityGamificationAdapter
            SecurityGamificationAdapter().on_user_ban_save(
                sender=sender, instance=instance, created=created)
        except Exception as exc:
            logger.error("[gamification_adapter] on_user_banned failed: %s", exc)

    def is_user_allowed_achievement(self, user: Any) -> bool:
        """
        award_achievement এর আগে call করো।
        Returns False if user is banned, fraud-flagged, or rate-limited।
        """
        try:
            from .security_adapter import SecurityGamificationAdapter
            from .fraud_detection_adapter import FraudDetectionGamificationAdapter
            from .rate_limit_adapter import RateLimitGamificationAdapter
            if SecurityGamificationAdapter().check_user_is_banned(user):
                return False
            if FraudDetectionGamificationAdapter().is_user_fraud_flagged(user):
                return False
            if RateLimitGamificationAdapter().is_achievement_blocked(user):
                return False
            return True
        except Exception:
            return True  # fail open — never block on error

    # ─── FraudDetection Integration ────────────────────────────────────────────

    def on_fraud_score_high(self, user: Any, score: float,
                            signals: list = None, **kwargs) -> None:
        """High fraud score → achievements pause। api.fraud_detection থেকে।"""
        try:
            from .fraud_detection_adapter import FraudDetectionGamificationAdapter
            FraudDetectionGamificationAdapter().on_high_fraud_score(
                user=user, score=score, signals=signals)
        except Exception as exc:
            logger.error("[gamification_adapter] on_fraud_score_high failed: %s", exc)

    def on_user_auto_banned(self, user: Any, ban_type: str = "auto_ban",
                            score: float = 0, **kwargs) -> None:
        """AutoBan → recent suspicious awards revoke। api.fraud_detection থেকে।"""
        try:
            from .fraud_detection_adapter import FraudDetectionGamificationAdapter
            FraudDetectionGamificationAdapter().on_user_auto_banned(
                user=user, ban_type=ban_type, score=score)
        except Exception as exc:
            logger.error("[gamification_adapter] on_user_auto_banned failed: %s", exc)

    # ─── RateLimit Integration ─────────────────────────────────────────────────

    def on_rate_limit_violation(self, request: Any = None, endpoint: str = "",
                                user: Any = None, **kwargs) -> None:
        """Rate limit hit → violation count। api.rate_limit middleware থেকে।"""
        try:
            from .rate_limit_adapter import RateLimitGamificationAdapter
            RateLimitGamificationAdapter().on_rate_limit_hit(
                request=request, endpoint=endpoint, user=user)
        except Exception as exc:
            logger.error("[gamification_adapter] on_rate_limit_violation failed: %s", exc)

# ── Singleton ──────────────────────────────────────────────────────────────────
gamification_adapter = GamificationAdapter()
