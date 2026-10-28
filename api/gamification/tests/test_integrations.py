"""
api/gamification/tests/test_integrations.py

Integration Adapter Test Suite — সব adapter-এর unit tests।
External modules mock করা হয়েছে — শুধু adapter logic test হচ্ছে।
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch, call, ANY

from django.test import TestCase
from django.utils import timezone

from ..integrations.adapter import GamificationAdapter, gamification_adapter
from ..integrations.wallet_adapter import WalletGamificationAdapter, EARNING_MILESTONES
from ..integrations.users_adapter import (
    UsersGamificationAdapter, FIRST_LOGIN, KYC_APPROVED, PROFILE_UPDATED,
    REFERRAL_JOINED, WITHDRAWAL_REQ, EVENT_ACHIEVEMENT_MAP,
)
from ..integrations.notifications_adapter import NotificationsGamificationAdapter
from ..integrations.referral_adapter import ReferralGamificationAdapter
from ..integrations.support_adapter import SupportGamificationAdapter, CATEGORY_POINTS
from ..integrations.payment_adapter import PaymentGamificationAdapter
from ..integrations.engagement_adapter import EngagementGamificationAdapter, STREAK_MILESTONES
from ..integrations.analytics_adapter import AnalyticsGamificationAdapter

from .factories import UserFactory, ContestCycleFactory, UserAchievementFactory


def _make_user(**kwargs):
    return UserFactory(**kwargs)


def _make_achievement(user=None, **kwargs):
    u = user or _make_user()
    return UserAchievementFactory(
        user=u,
        is_awarded=True,
        awarded_at=timezone.now(),
        **kwargs,
    )


# ===========================================================================
# GamificationAdapter (central hub)
# ===========================================================================

class GamificationAdapterTest(TestCase):

    def setUp(self):
        self.adapter = GamificationAdapter()
        self.user = _make_user()

    # ── Wallet ────────────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.wallet_adapter.WalletGamificationAdapter")
    def test_on_wallet_credited_delegates(self, MockWallet):
        mock_instance = MockWallet.return_value
        self.adapter.on_wallet_credited(user=self.user, amount=500.0, source="deposit")
        mock_instance.on_credited.assert_called_once_with(
            user=self.user, amount=500.0, source="deposit"
        )

    @patch("api.gamification.integrations.wallet_adapter.WalletGamificationAdapter")
    def test_on_wallet_credited_never_raises(self, MockWallet):
        MockWallet.return_value.on_credited.side_effect = RuntimeError("boom")
        # Must not raise
        self.adapter.on_wallet_credited(user=self.user, amount=100.0)

    @patch("api.gamification.integrations.wallet_adapter.WalletGamificationAdapter")
    def test_on_wallet_withdrawal_delegates(self, MockWallet):
        mock_instance = MockWallet.return_value
        self.adapter.on_wallet_withdrawal(user=self.user, amount=200.0, status="processed")
        mock_instance.on_withdrawal.assert_called_once_with(
            user=self.user, amount=200.0, status="processed"
        )

    # ── Users ─────────────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.users_adapter.UsersGamificationAdapter")
    def test_on_user_event_delegates(self, MockUsers):
        mock_instance = MockUsers.return_value
        self.adapter.on_user_event(user=self.user, event=FIRST_LOGIN)
        mock_instance.on_event.assert_called_once_with(
            user=self.user, event=FIRST_LOGIN, context={}
        )

    @patch("api.gamification.integrations.users_adapter.UsersGamificationAdapter")
    def test_on_user_event_never_raises(self, MockUsers):
        MockUsers.return_value.on_event.side_effect = Exception("fail")
        self.adapter.on_user_event(user=self.user, event="anything")

    @patch("api.gamification.integrations.users_adapter.UsersGamificationAdapter")
    def test_on_user_tier_changed_delegates(self, MockUsers):
        mock_instance = MockUsers.return_value
        self.adapter.on_user_tier_changed(
            user=self.user, old_tier="BRONZE", new_tier="GOLD"
        )
        mock_instance.on_tier_changed.assert_called_once_with(
            user=self.user, old_tier="BRONZE", new_tier="GOLD"
        )

    # ── Notifications ─────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.notifications_adapter.NotificationsGamificationAdapter")
    def test_notify_achievement_awarded_delegates(self, MockNotif):
        mock_instance = MockNotif.return_value
        ach = _make_achievement(user=self.user)
        self.adapter.notify_achievement_awarded(ach)
        mock_instance.send_achievement_notification.assert_called_once_with(ach)

    @patch("api.gamification.integrations.notifications_adapter.NotificationsGamificationAdapter")
    def test_notify_achievement_never_raises(self, MockNotif):
        MockNotif.return_value.send_achievement_notification.side_effect = Exception("boom")
        ach = _make_achievement(user=self.user)
        self.adapter.notify_achievement_awarded(ach)  # must not raise

    @patch("api.gamification.integrations.notifications_adapter.NotificationsGamificationAdapter")
    def test_notify_leaderboard_finalized_delegates(self, MockNotif):
        mock_instance = MockNotif.return_value
        snap = MagicMock()
        self.adapter.notify_leaderboard_finalized(snap, top_n=5)
        mock_instance.send_leaderboard_notification.assert_called_once_with(
            snapshot=snap, top_n=5
        )

    @patch("api.gamification.integrations.notifications_adapter.NotificationsGamificationAdapter")
    def test_notify_contest_reward_delegates(self, MockNotif):
        mock_instance = MockNotif.return_value
        reward = MagicMock()
        self.adapter.notify_contest_reward(user=self.user, reward=reward, rank=1)
        mock_instance.send_contest_reward_notification.assert_called_once_with(
            user=self.user, reward=reward, rank=1
        )

    # ── Referral ──────────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.referral_adapter.ReferralGamificationAdapter")
    def test_on_referral_contest_started_delegates(self, MockRef):
        mock_instance = MockRef.return_value
        contest = MagicMock()
        self.adapter.on_referral_contest_started(referral_contest=contest)
        mock_instance.on_contest_started.assert_called_once_with(contest)

    @patch("api.gamification.integrations.referral_adapter.ReferralGamificationAdapter")
    def test_on_referral_commission_delegates(self, MockRef):
        mock_instance = MockRef.return_value
        self.adapter.on_referral_commission_earned(
            user=self.user, amount=100.0, referral_count=5
        )
        mock_instance.on_commission_earned.assert_called_once_with(
            user=self.user, amount=100.0, referral_count=5
        )

    # ── Support ───────────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.support_adapter.SupportGamificationAdapter")
    def test_on_support_ticket_resolved_delegates(self, MockSupport):
        mock_instance = MockSupport.return_value
        ticket = MagicMock()
        self.adapter.on_support_ticket_resolved(ticket=ticket)
        mock_instance.on_ticket_resolved.assert_called_once_with(ticket)

    @patch("api.gamification.integrations.support_adapter.SupportGamificationAdapter")
    def test_on_support_csat_delegates(self, MockSupport):
        mock_instance = MockSupport.return_value
        ticket = MagicMock()
        self.adapter.on_support_csat_submitted(ticket=ticket, score=5)
        mock_instance.on_csat_submitted.assert_called_once_with(ticket=ticket, score=5)

    @patch("api.gamification.integrations.support_adapter.SupportGamificationAdapter")
    def test_get_user_gamification_context_delegates(self, MockSupport):
        mock_instance = MockSupport.return_value
        mock_instance.get_user_context.return_value = {"is_vip": True, "priority": "high"}
        result = self.adapter.get_user_gamification_context(self.user)
        self.assertEqual(result["is_vip"], True)

    @patch("api.gamification.integrations.support_adapter.SupportGamificationAdapter")
    def test_get_user_gamification_context_fallback_on_error(self, MockSupport):
        MockSupport.return_value.get_user_context.side_effect = Exception("err")
        result = self.adapter.get_user_gamification_context(self.user)
        self.assertEqual(result["priority"], "low")
        self.assertFalse(result["is_vip"])

    # ── Payment ───────────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.payment_adapter.PaymentGamificationAdapter")
    def test_on_payment_deposit_completed_delegates(self, MockPay):
        mock_instance = MockPay.return_value
        self.adapter.on_payment_deposit_completed(
            user=self.user, amount=1000.0, deposit=MagicMock()
        )
        mock_instance.on_deposit_completed.assert_called_once()

    @patch("api.gamification.integrations.payment_adapter.PaymentGamificationAdapter")
    def test_on_conversion_approved_delegates(self, MockPay):
        mock_instance = MockPay.return_value
        self.adapter.on_conversion_approved(user=self.user, payout=50.0)
        mock_instance.on_conversion_approved.assert_called_once()

    # ── Engagement ────────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.engagement_adapter.EngagementGamificationAdapter")
    def test_on_daily_checkin_delegates(self, MockEng):
        mock_instance = MockEng.return_value
        self.adapter.on_daily_checkin(user=self.user, consecutive_days=7)
        mock_instance.on_checkin.assert_called_once_with(
            user=self.user, consecutive_days=7
        )

    @patch("api.gamification.integrations.engagement_adapter.EngagementGamificationAdapter")
    def test_on_spin_wheel_delegates(self, MockEng):
        mock_instance = MockEng.return_value
        self.adapter.on_spin_wheel(user=self.user, coins_won=50)
        mock_instance.on_spin.assert_called_once_with(user=self.user, coins_won=50)

    # ── Analytics ─────────────────────────────────────────────────────────────

    @patch("api.gamification.integrations.analytics_adapter.AnalyticsGamificationAdapter")
    def test_track_event_delegates(self, MockAnalytics):
        mock_instance = MockAnalytics.return_value
        self.adapter.track_event("test_event", user=self.user, properties={"x": 1})
        mock_instance.track.assert_called_once_with(
            event_name="test_event", user=self.user, properties={"x": 1}
        )

    @patch("api.gamification.integrations.analytics_adapter.AnalyticsGamificationAdapter")
    def test_track_event_never_raises(self, MockAnalytics):
        MockAnalytics.return_value.track.side_effect = Exception("boom")
        self.adapter.track_event("event")  # must not raise

    # ── Singleton ─────────────────────────────────────────────────────────────

    def test_singleton_exists(self):
        self.assertIsInstance(gamification_adapter, GamificationAdapter)


# ===========================================================================
# WalletGamificationAdapter
# ===========================================================================

class WalletAdapterTest(TestCase):

    def setUp(self):
        self.adapter = WalletGamificationAdapter()
        self.user = _make_user()

    @patch.object(WalletGamificationAdapter, "_get_total_earned", return_value=Decimal("0"))
    @patch.object(WalletGamificationAdapter, "_award_earning_milestone")
    @patch.object(WalletGamificationAdapter, "_check_first_deposit")
    def test_on_credited_checks_first_deposit(self, mock_first, mock_milestone, mock_total):
        self.adapter.on_credited(user=self.user, amount=50.0, source="deposit")
        mock_first.assert_called_once_with(self.user)

    @patch.object(WalletGamificationAdapter, "_get_total_earned", return_value=Decimal("0"))
    @patch.object(WalletGamificationAdapter, "_award_earning_milestone")
    def test_on_credited_triggers_milestone_when_crossed(self, mock_milestone, mock_total):
        # total was 0, new amount=100 → crosses milestone 10 and 100
        self.adapter.on_credited(user=self.user, amount=150.0, source="deposit")
        # Should award for every milestone crossed
        called_milestones = [c.args[1] for c in mock_milestone.call_args_list]
        self.assertIn(10, called_milestones)
        self.assertIn(100, called_milestones)

    @patch.object(WalletGamificationAdapter, "_get_total_earned", return_value=Decimal("99"))
    @patch.object(WalletGamificationAdapter, "_award_earning_milestone")
    def test_on_credited_no_milestone_when_already_above(self, mock_milestone, mock_total):
        # Already at 99, adding 0.5 — no milestone crossed
        self.adapter.on_credited(user=self.user, amount=0.5, source="deposit")
        mock_milestone.assert_not_called()

    @patch.object(WalletGamificationAdapter, "_check_first_withdrawal")
    def test_on_withdrawal_approved_checks_first(self, mock_first):
        self.adapter.on_withdrawal(user=self.user, amount=100.0, status="approved")
        mock_first.assert_called_once_with(self.user)

    @patch.object(WalletGamificationAdapter, "_check_first_withdrawal")
    def test_on_withdrawal_pending_skipped(self, mock_first):
        self.adapter.on_withdrawal(user=self.user, amount=100.0, status="pending")
        mock_first.assert_not_called()

    def test_on_credited_never_raises(self):
        with patch.object(
            WalletGamificationAdapter, "_get_total_earned", side_effect=Exception("db error")
        ):
            # Must not raise
            self.adapter.on_credited(user=self.user, amount=100.0)

    def test_all_milestones_have_achievement_titles(self):
        from ..integrations.wallet_adapter import DEPOSIT_ACHIEVEMENT_TITLES
        for m in EARNING_MILESTONES:
            self.assertIn(m, DEPOSIT_ACHIEVEMENT_TITLES)


# ===========================================================================
# UsersGamificationAdapter
# ===========================================================================

class UsersAdapterTest(TestCase):

    def setUp(self):
        self.adapter = UsersGamificationAdapter()
        self.user = _make_user()

    @patch.object(UsersGamificationAdapter, "_award")
    def test_on_event_first_login(self, mock_award):
        self.adapter.on_event(user=self.user, event=FIRST_LOGIN)
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        self.assertEqual(call_kwargs["title"], EVENT_ACHIEVEMENT_MAP[FIRST_LOGIN]["title"])
        self.assertEqual(call_kwargs["points"], EVENT_ACHIEVEMENT_MAP[FIRST_LOGIN]["points"])

    @patch.object(UsersGamificationAdapter, "_award")
    def test_on_event_kyc_approved(self, mock_award):
        self.adapter.on_event(user=self.user, event=KYC_APPROVED)
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        self.assertEqual(call_kwargs["points"], EVENT_ACHIEVEMENT_MAP[KYC_APPROVED]["points"])

    @patch.object(UsersGamificationAdapter, "_award")
    def test_on_event_unknown_skips(self, mock_award):
        self.adapter.on_event(user=self.user, event="UNKNOWN_EVENT_XYZ")
        mock_award.assert_not_called()

    @patch.object(UsersGamificationAdapter, "_award")
    def test_on_tier_changed_gold(self, mock_award):
        self.adapter.on_tier_changed(user=self.user, old_tier="SILVER", new_tier="GOLD")
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        self.assertIn("GOLD", call_kwargs["description"])

    @patch.object(UsersGamificationAdapter, "_award")
    def test_on_tier_changed_unknown_tier_skips(self, mock_award):
        self.adapter.on_tier_changed(user=self.user, old_tier="X", new_tier="UNKNOWN")
        mock_award.assert_not_called()

    def test_on_event_never_raises(self):
        with patch.object(UsersGamificationAdapter, "_award", side_effect=Exception("err")):
            self.adapter.on_event(user=self.user, event=FIRST_LOGIN)

    def test_all_events_have_required_keys(self):
        required = {"title", "description", "points", "badge", "once"}
        for event, config in EVENT_ACHIEVEMENT_MAP.items():
            missing = required - set(config.keys())
            self.assertEqual(missing, set(), f"Event '{event}' missing keys: {missing}")


# ===========================================================================
# NotificationsGamificationAdapter
# ===========================================================================

class NotificationsAdapterTest(TestCase):

    def setUp(self):
        self.adapter = NotificationsGamificationAdapter()
        self.user = _make_user()

    @patch.object(NotificationsGamificationAdapter, "_send")
    def test_send_achievement_notification(self, mock_send):
        ach = _make_achievement(user=self.user, title="Test Badge", points_awarded=100)
        self.adapter.send_achievement_notification(ach)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        self.assertEqual(call_kwargs["user"], self.user)
        self.assertIn("push", call_kwargs["channels"])
        self.assertIn("in_app", call_kwargs["channels"])

    @patch.object(NotificationsGamificationAdapter, "_send")
    def test_send_achievement_no_user_skips(self, mock_send):
        ach = MagicMock()
        ach.user = None
        self.adapter.send_achievement_notification(ach)
        mock_send.assert_not_called()

    @patch("django.contrib.auth.get_user_model")
    @patch.object(NotificationsGamificationAdapter, "_send")
    def test_send_leaderboard_notification_empty_data(self, mock_send, mock_get_model):
        snap = MagicMock()
        snap.snapshot_data = []
        self.adapter.send_leaderboard_notification(snap, top_n=10)
        mock_send.assert_not_called()

    @patch.object(NotificationsGamificationAdapter, "_send")
    def test_send_contest_reward_notification(self, mock_send):
        reward = MagicMock()
        reward.title = "Grand Prize"
        reward.reward_value = 500
        reward.reward_type = "POINTS"
        reward.contest_cycle.name = "Summer Contest"
        self.adapter.send_contest_reward_notification(
            user=self.user, reward=reward, rank=1
        )
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        self.assertIn("1", call_kwargs["title"])
        self.assertEqual(call_kwargs["priority"], "high")

    def test_send_falls_back_to_async_when_no_service(self):
        with patch(
            "api.gamification.integrations.notifications_adapter.NotificationsGamificationAdapter._send_async"
        ) as mock_async:
            # Simulate ImportError for NotificationService
            with patch.dict("sys.modules", {"api.notifications.services": None}):
                self.adapter._send(
                    user=self.user,
                    notification_type="test",
                    title="T",
                    message="M",
                    data={},
                    channels=["in_app"],
                )

    def test_never_raises_on_full_flow(self):
        ach = _make_achievement(user=self.user)
        with patch.object(
            NotificationsGamificationAdapter, "_send", side_effect=Exception("net error")
        ):
            self.adapter.send_achievement_notification(ach)  # must not raise


# ===========================================================================
# ReferralGamificationAdapter
# ===========================================================================

class ReferralAdapterTest(TestCase):

    def setUp(self):
        self.adapter = ReferralGamificationAdapter()
        self.user = _make_user()

    @patch("api.gamification.services.create_contest_cycle")
    def test_on_contest_started_creates_cycle(self, mock_create):
        from datetime import timedelta
        now = timezone.now()
        mock_create.return_value = MagicMock(id="cycle-123")

        contest = MagicMock()
        contest.id = 42
        contest.title = "Top Referrer"
        contest.start_date = now
        contest.end_date = now + timedelta(days=30)
        contest.prize_pool = 5000
        contest.contest_type = "referral_count"

        self.adapter.on_contest_started(contest)

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertIn("referral", call_kwargs["name"].lower())
        self.assertIn("42", call_kwargs["slug"])

    @patch("api.gamification.services.create_contest_cycle")
    def test_on_contest_started_missing_dates_skips(self, mock_create):
        contest = MagicMock()
        contest.start_date = None
        contest.end_date = None
        self.adapter.on_contest_started(contest)
        mock_create.assert_not_called()

    @patch.object(ReferralGamificationAdapter, "_award")
    @patch.object(ReferralGamificationAdapter, "_get_total_commission", return_value=Decimal("0"))
    def test_on_commission_earned_referral_milestone(self, mock_total, mock_award):
        self.adapter.on_commission_earned(
            user=self.user, amount=10.0, referral_count=5
        )
        # Should award for referral_count=5 milestone
        awarded_titles = [c[1]["title"] for c in mock_award.call_args_list]
        self.assertIn("Referral Pro", awarded_titles)

    @patch.object(ReferralGamificationAdapter, "_award")
    @patch.object(
        ReferralGamificationAdapter, "_get_total_commission", return_value=Decimal("90")
    )
    def test_on_commission_earned_commission_milestone_crossed(self, mock_total, mock_award):
        # total was 90, new amount=20 → crosses 100 threshold
        self.adapter.on_commission_earned(
            user=self.user, amount=20.0, referral_count=0
        )
        awarded_titles = [c[1]["title"] for c in mock_award.call_args_list]
        self.assertIn("Commission Starter", awarded_titles)

    def test_on_commission_earned_never_raises(self):
        with patch.object(
            ReferralGamificationAdapter, "_get_total_commission",
            side_effect=Exception("db error")
        ):
            self.adapter.on_commission_earned(
                user=self.user, amount=100.0, referral_count=1
            )

    def test_on_contest_started_never_raises(self):
        with patch(
            "api.gamification.services.create_contest_cycle",
            side_effect=Exception("service error")
        ):
            contest = MagicMock()
            contest.start_date = timezone.now()
            contest.end_date = timezone.now()
            self.adapter.on_contest_started(contest)


# ===========================================================================
# SupportGamificationAdapter
# ===========================================================================

class SupportAdapterTest(TestCase):

    def setUp(self):
        self.adapter = SupportGamificationAdapter()
        self.user = _make_user()

    def _make_ticket(self, category="payment", status="resolved", user=None):
        ticket = MagicMock()
        ticket.user = user or self.user
        ticket.category = category
        ticket.status = status
        ticket.ticket_id = "TKT-001"
        ticket.assigned_agent = None
        return ticket

    @patch.object(SupportGamificationAdapter, "_award")
    def test_on_ticket_resolved_payment(self, mock_award):
        ticket = self._make_ticket(category="payment")
        self.adapter.on_ticket_resolved(ticket)
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        self.assertEqual(call_kwargs["points"], CATEGORY_POINTS["payment"])

    @patch.object(SupportGamificationAdapter, "_award")
    def test_on_ticket_resolved_fraud_gets_more_points(self, mock_award):
        ticket = self._make_ticket(category="fraud")
        self.adapter.on_ticket_resolved(ticket)
        call_kwargs = mock_award.call_args[1]
        self.assertEqual(call_kwargs["points"], CATEGORY_POINTS["fraud"])
        self.assertGreater(CATEGORY_POINTS["fraud"], CATEGORY_POINTS["payment"])

    @patch.object(SupportGamificationAdapter, "_award")
    def test_on_ticket_resolved_no_user_skips(self, mock_award):
        ticket = self._make_ticket()
        ticket.user = None
        self.adapter.on_ticket_resolved(ticket)
        mock_award.assert_not_called()

    @patch.object(SupportGamificationAdapter, "_award")
    def test_on_csat_submitted_score_5_awards_user(self, mock_award):
        ticket = self._make_ticket()
        self.adapter.on_csat_submitted(ticket=ticket, score=5)
        # Should award user (15 pts)
        calls = mock_award.call_args_list
        user_call = next((c for c in calls if c[1]["user"] == self.user), None)
        self.assertIsNotNone(user_call)
        self.assertEqual(user_call[1]["points"], 15)

    @patch.object(SupportGamificationAdapter, "_award")
    def test_on_csat_submitted_score_5_awards_agent(self, mock_award):
        agent = _make_user()
        ticket = self._make_ticket()
        ticket.assigned_agent = agent
        self.adapter.on_csat_submitted(ticket=ticket, score=5)
        calls = mock_award.call_args_list
        agent_call = next((c for c in calls if c[1]["user"] == agent), None)
        self.assertIsNotNone(agent_call)
        self.assertEqual(agent_call[1]["points"], 20)

    @patch.object(SupportGamificationAdapter, "_award")
    def test_on_csat_submitted_score_3_no_award(self, mock_award):
        ticket = self._make_ticket()
        self.adapter.on_csat_submitted(ticket=ticket, score=3)
        mock_award.assert_not_called()

    def test_get_user_context_vip_detection(self):
        from ..choices import AchievementType
        _make_achievement(
            user=self.user,
            achievement_type=AchievementType.BADGE,
            title="VIP Gold Member",
        )
        result = self.adapter.get_user_context(self.user)
        self.assertTrue(result["is_vip"])
        self.assertEqual(result["priority"], "high")

    def test_get_user_context_low_priority_no_achievements(self):
        user = _make_user()
        result = self.adapter.get_user_context(user)
        self.assertFalse(result["is_vip"])
        self.assertEqual(result["priority"], "low")

    def test_get_user_context_never_raises(self):
        with patch(
            "api.gamification.models.UserAchievement.objects",
            side_effect=Exception("db error")
        ):
            result = self.adapter.get_user_context(self.user)
            self.assertEqual(result["priority"], "low")

    def test_on_ticket_resolved_never_raises(self):
        with patch.object(
            SupportGamificationAdapter, "_award", side_effect=Exception("err")
        ):
            ticket = self._make_ticket()
            self.adapter.on_ticket_resolved(ticket)


# ===========================================================================
# PaymentGamificationAdapter
# ===========================================================================

class PaymentAdapterTest(TestCase):

    def setUp(self):
        self.adapter = PaymentGamificationAdapter()
        self.user = _make_user()

    @patch.object(PaymentGamificationAdapter, "_award")
    def test_on_deposit_completed_threshold_100(self, mock_award):
        self.adapter.on_deposit_completed(user=self.user, amount=100.0)
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        self.assertEqual(call_kwargs["title"], "Depositor I")

    @patch.object(PaymentGamificationAdapter, "_award")
    def test_on_deposit_completed_highest_threshold_wins(self, mock_award):
        # 5000 amount → should award highest applicable threshold
        self.adapter.on_deposit_completed(user=self.user, amount=5000.0)
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        self.assertEqual(call_kwargs["title"], "Depositor IV")

    @patch.object(PaymentGamificationAdapter, "_award")
    def test_on_deposit_completed_below_threshold_no_award(self, mock_award):
        self.adapter.on_deposit_completed(user=self.user, amount=50.0)
        mock_award.assert_not_called()

    @patch.object(PaymentGamificationAdapter, "_award")
    def test_on_deposit_no_user_skips(self, mock_award):
        self.adapter.on_deposit_completed(user=None, amount=500.0)
        mock_award.assert_not_called()

    @patch.object(PaymentGamificationAdapter, "_award")
    def test_on_conversion_approved(self, mock_award):
        self.adapter.on_conversion_approved(user=self.user, payout=50.0)
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        self.assertEqual(call_kwargs["title"], "Consistent Earner")

    @patch.object(PaymentGamificationAdapter, "_award")
    def test_on_conversion_no_user_skips(self, mock_award):
        self.adapter.on_conversion_approved(user=None, payout=100.0)
        mock_award.assert_not_called()

    def test_on_deposit_never_raises(self):
        with patch.object(
            PaymentGamificationAdapter, "_award", side_effect=Exception("err")
        ):
            self.adapter.on_deposit_completed(user=self.user, amount=200.0)


# ===========================================================================
# EngagementGamificationAdapter
# ===========================================================================

class EngagementAdapterTest(TestCase):

    def setUp(self):
        self.adapter = EngagementGamificationAdapter()
        self.user = _make_user()

    @patch.object(EngagementGamificationAdapter, "_award_streak")
    def test_on_checkin_3_day_streak(self, mock_streak):
        self.adapter.on_checkin(user=self.user, consecutive_days=3)
        mock_streak.assert_called_once()
        call_kwargs = mock_streak.call_args[1]
        self.assertEqual(call_kwargs["title"], "3-Day Streak")
        self.assertEqual(call_kwargs["consecutive_days"], 3)

    @patch.object(EngagementGamificationAdapter, "_award_streak")
    def test_on_checkin_7_day_streak(self, mock_streak):
        self.adapter.on_checkin(user=self.user, consecutive_days=7)
        call_kwargs = mock_streak.call_args[1]
        self.assertEqual(call_kwargs["title"], "7-Day Streak")

    @patch.object(EngagementGamificationAdapter, "_award_streak")
    def test_on_checkin_non_milestone_no_streak(self, mock_streak):
        self.adapter.on_checkin(user=self.user, consecutive_days=4)
        mock_streak.assert_not_called()

    @patch.object(EngagementGamificationAdapter, "_award_bonus")
    def test_on_checkin_first_day_awards_bonus(self, mock_bonus):
        self.adapter.on_checkin(user=self.user, consecutive_days=1)
        mock_bonus.assert_called_once()

    @patch.object(EngagementGamificationAdapter, "_award_bonus")
    def test_on_spin_big_win_awards_bonus(self, mock_bonus):
        self.adapter.on_spin(user=self.user, coins_won=50)
        mock_bonus.assert_called_once()
        call_kwargs = mock_bonus.call_args[1]
        self.assertEqual(call_kwargs["title"], "Big Spinner!")

    @patch.object(EngagementGamificationAdapter, "_award_bonus")
    def test_on_spin_small_win_no_award(self, mock_bonus):
        self.adapter.on_spin(user=self.user, coins_won=10)
        mock_bonus.assert_not_called()

    @patch.object(EngagementGamificationAdapter, "_award_bonus")
    def test_on_spin_points_proportional(self, mock_bonus):
        self.adapter.on_spin(user=self.user, coins_won=50)
        call_kwargs = mock_bonus.call_args[1]
        self.assertEqual(call_kwargs["points"], 50 // 5)

    def test_on_checkin_never_raises(self):
        with patch.object(
            EngagementGamificationAdapter, "_award_streak", side_effect=Exception("err")
        ):
            self.adapter.on_checkin(user=self.user, consecutive_days=7)

    def test_on_spin_never_raises(self):
        with patch.object(
            EngagementGamificationAdapter, "_award_bonus", side_effect=Exception("err")
        ):
            self.adapter.on_spin(user=self.user, coins_won=100)

    def test_no_user_skips_checkin(self):
        with patch.object(EngagementGamificationAdapter, "_award_streak") as mock_s:
            self.adapter.on_checkin(user=None, consecutive_days=7)
            mock_s.assert_not_called()

    def test_all_streak_milestones_have_required_fields(self):
        for days, config in STREAK_MILESTONES.items():
            self.assertIn("title", config, f"Streak {days}d missing title")
            self.assertIn("points", config, f"Streak {days}d missing points")
            self.assertIn("badge", config, f"Streak {days}d missing badge")
            self.assertGreater(config["points"], 0, f"Streak {days}d points must be > 0")


# ===========================================================================
# AnalyticsGamificationAdapter
# ===========================================================================

class AnalyticsAdapterTest(TestCase):

    def setUp(self):
        self.adapter = AnalyticsGamificationAdapter()
        self.user = _make_user()

    @patch("api.gamification.integrations.analytics_adapter.AnalyticsGamificationAdapter._track_via_service")
    def test_track_uses_service_first(self, mock_service):
        mock_service.return_value = True
        self.adapter.track("test_event", user=self.user)
        mock_service.assert_called_once()

    @patch("api.gamification.integrations.analytics_adapter.AnalyticsGamificationAdapter._track_via_service")
    @patch("api.gamification.integrations.analytics_adapter.AnalyticsGamificationAdapter._track_via_task")
    def test_track_falls_back_to_task(self, mock_task, mock_service):
        mock_service.return_value = False
        mock_task.return_value = True
        self.adapter.track("test_event", user=self.user)
        mock_task.assert_called_once()

    @patch("api.gamification.integrations.analytics_adapter.AnalyticsGamificationAdapter._track_via_service")
    @patch("api.gamification.integrations.analytics_adapter.AnalyticsGamificationAdapter._track_via_task")
    def test_track_falls_back_to_log(self, mock_task, mock_service):
        mock_service.return_value = False
        mock_task.return_value = False
        # No exception — just logs
        self.adapter.track("test_event", user=self.user)

    def test_track_prefixes_event_name(self):
        with patch.object(
            AnalyticsGamificationAdapter, "_track_via_service"
        ) as mock_svc:
            mock_svc.return_value = True
            self.adapter.track("wallet_credited", user=self.user)
            event_arg = mock_svc.call_args[0][0]
            self.assertTrue(event_arg.startswith("gamification."))

    def test_track_no_double_prefix(self):
        with patch.object(
            AnalyticsGamificationAdapter, "_track_via_service"
        ) as mock_svc:
            mock_svc.return_value = True
            self.adapter.track("gamification.wallet_credited", user=self.user)
            event_arg = mock_svc.call_args[0][0]
            self.assertFalse(
                event_arg.startswith("gamification.gamification."),
                "Event name should not be double-prefixed"
            )

    def test_track_includes_user_id_in_props(self):
        with patch.object(
            AnalyticsGamificationAdapter, "_track_via_service"
        ) as mock_svc:
            mock_svc.return_value = True
            self.adapter.track("event", user=self.user, properties={"x": 1})
            props = mock_svc.call_args[0][1]
            self.assertIn("user_id", props)
            self.assertEqual(props["user_id"], str(self.user.pk))

    def test_track_anonymous_user(self):
        with patch.object(
            AnalyticsGamificationAdapter, "_track_via_service"
        ) as mock_svc:
            mock_svc.return_value = True
            self.adapter.track("event", user=None)
            props = mock_svc.call_args[0][1]
            self.assertEqual(props["user_id"], "anonymous")

    def test_track_via_service_import_error(self):
        result = self.adapter._track_via_service("event", {})
        # api.analytics may not be installed → returns False
        self.assertFalse(result)

    def test_track_via_task_import_error(self):
        result = self.adapter._track_via_task("event", "u1", {})
        self.assertFalse(result)

    def test_never_raises_even_if_all_fail(self):
        # Both helpers fail → falls back to structured log — must not raise
        with patch.object(
            AnalyticsGamificationAdapter, "_track_via_service", return_value=False
        ), patch.object(
            AnalyticsGamificationAdapter, "_track_via_task", return_value=False
        ):
            self.adapter.track("event", user=self.user)  # must not raise


# ===========================================================================
# Receivers integration (with real signals)
# ===========================================================================

class ReceiversIntegrationTest(TestCase):

    def setUp(self):
        self.user = _make_user()

    @patch("api.gamification.integrations.adapter.gamification_adapter")
    def test_on_achievement_awarded_calls_notify(self, mock_adapter):
        from ..signals import achievement_awarded
        from ..choices import AchievementType
        ach = _make_achievement(user=self.user, achievement_type=AchievementType.BADGE)
        achievement_awarded.send(sender=None, achievement=ach)
        mock_adapter.notify_achievement_awarded.assert_called_once_with(ach)

    @patch("api.gamification.integrations.adapter.gamification_adapter")
    def test_on_achievement_awarded_calls_analytics(self, mock_adapter):
        from ..signals import achievement_awarded
        from ..choices import AchievementType
        ach = _make_achievement(user=self.user, achievement_type=AchievementType.BADGE)
        achievement_awarded.send(sender=None, achievement=ach)
        mock_adapter.track_event.assert_called()

    @patch("api.gamification.integrations.adapter.gamification_adapter")
    def test_on_achievement_awarded_missing_achievement(self, mock_adapter):
        from ..signals import achievement_awarded
        # Missing 'achievement' kwarg — should not raise
        achievement_awarded.send(sender=None)
        mock_adapter.notify_achievement_awarded.assert_not_called()

    @patch("django.core.cache.cache.delete")
    @patch("api.gamification.integrations.adapter.gamification_adapter")
    def test_on_leaderboard_finalized_invalidates_cache(self, mock_adapter, mock_delete):
        from ..signals import leaderboard_snapshot_finalized
        snap = MagicMock()
        snap.id = "snap-1"
        snap.contest_cycle_id = "cycle-1"
        snap.scope = "GLOBAL"
        snap.entry_count = 5
        leaderboard_snapshot_finalized.send(sender=None, snapshot=snap)
        mock_delete.assert_called_with("leaderboard:cycle-1:GLOBAL")

    @patch("api.gamification.integrations.adapter.gamification_adapter")
    def test_on_leaderboard_finalized_calls_notify(self, mock_adapter):
        from ..signals import leaderboard_snapshot_finalized
        snap = MagicMock()
        snap.entry_count = 5
        leaderboard_snapshot_finalized.send(sender=None, snapshot=snap)
        mock_adapter.notify_leaderboard_finalized.assert_called_once()
