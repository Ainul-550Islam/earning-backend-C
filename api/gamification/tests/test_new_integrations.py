"""
api/gamification/tests/test_new_integrations.py

New Integration Adapter Tests:
  KYC, Subscription, PayoutQueue, Offerwall, PostbackEngine,
  DJoyalty, Monetization, Security, FraudDetection, RateLimit
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch, call
from django.test import TestCase
from django.utils import timezone

from ..integrations.kyc_adapter import KYCGamificationAdapter
from ..integrations.subscription_adapter import SubscriptionGamificationAdapter, PLAN_ACHIEVEMENTS
from ..integrations.payout_queue_adapter import PayoutQueueGamificationAdapter, PAYOUT_COUNT_MILESTONES
from ..integrations.offerwall_adapter import OfferwallGamificationAdapter, OFFER_COUNT_MILESTONES
from ..integrations.postback_engine_adapter import PostbackEngineGamificationAdapter
from ..integrations.djoyalty_adapter import DJoyaltyGamificationAdapter, TIER_MAP
from ..integrations.monetization_adapter import MonetizationGamificationAdapter, LEVEL_ACHIEVEMENTS
from ..integrations.security_adapter import SecurityGamificationAdapter
from ..integrations.fraud_detection_adapter import FraudDetectionGamificationAdapter
from ..integrations.rate_limit_adapter import RateLimitGamificationAdapter, BLOCK_THRESHOLD
from ..integrations.adapter import gamification_adapter, GamificationAdapter

from .factories import UserFactory, UserAchievementFactory


def _user(**kwargs):
    return UserFactory(**kwargs)


def _ach(user=None, **kwargs):
    return UserAchievementFactory(
        user=user or _user(),
        is_awarded=True,
        awarded_at=timezone.now(),
        **kwargs,
    )


# ===========================================================================
# KYCGamificationAdapter
# ===========================================================================

class KYCAdapterTest(TestCase):

    def setUp(self):
        self.adapter = KYCGamificationAdapter()
        self.user = _user()

    @patch.object(KYCGamificationAdapter, "_award")
    def test_on_kyc_verified_awards_badge(self, mock_award):
        kyc = MagicMock()
        kyc.id = "kyc-1"
        self.adapter.on_kyc_verified(user=self.user, kyc=kyc)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertEqual(kwargs[1], "Identity Verified")
        self.assertEqual(kwargs[3], 75)

    @patch.object(KYCGamificationAdapter, "_award")
    def test_on_kyc_rejected_no_award(self, mock_award):
        self.adapter.on_kyc_rejected(user=self.user, reason="duplicate")
        mock_award.assert_not_called()

    @patch.object(KYCGamificationAdapter, "_award")
    def test_on_kyc_expired_no_award(self, mock_award):
        self.adapter.on_kyc_expired(user=self.user)
        mock_award.assert_not_called()

    def test_on_kyc_verified_never_raises(self):
        with patch.object(KYCGamificationAdapter, "_award", side_effect=Exception("db")):
            self.adapter.on_kyc_verified(user=self.user)

    def test_connect_signals_never_raises(self):
        self.adapter.connect_signals()  # must not raise


# ===========================================================================
# SubscriptionGamificationAdapter
# ===========================================================================

class SubscriptionAdapterTest(TestCase):

    def setUp(self):
        self.adapter = SubscriptionGamificationAdapter()
        self.user = _user()

    def _make_sub(self, plan_name="premium"):
        plan = MagicMock()
        plan.name = plan_name
        sub = MagicMock()
        sub.user = self.user
        sub.plan = plan
        sub.id = "sub-1"
        return sub

    @patch.object(SubscriptionGamificationAdapter, "_award")
    def test_on_activated_premium(self, mock_award):
        sub = self._make_sub("premium")
        self.adapter.on_activated(sender=None, instance=sub)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertEqual(kwargs[1], PLAN_ACHIEVEMENTS["premium"]["title"])
        self.assertEqual(kwargs[3], PLAN_ACHIEVEMENTS["premium"]["points"])

    @patch.object(SubscriptionGamificationAdapter, "_award")
    def test_on_activated_no_user_skips(self, mock_award):
        sub = MagicMock()
        sub.user = None
        self.adapter.on_activated(sender=None, instance=sub)
        mock_award.assert_not_called()

    @patch.object(SubscriptionGamificationAdapter, "_award")
    def test_on_renewed_awards_loyalty(self, mock_award):
        sub = self._make_sub()
        self.adapter.on_renewed(sender=None, instance=sub)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertEqual(kwargs[1], "Loyal Subscriber")

    @patch.object(SubscriptionGamificationAdapter, "_award")
    def test_on_plan_changed_upgrade_awards_diff(self, mock_award):
        old_plan = MagicMock(); old_plan.name = "basic"
        new_plan = MagicMock(); new_plan.name = "premium"
        sub = self._make_sub()
        self.adapter.on_plan_changed(sender=None, instance=sub,
                                     old_plan=old_plan, new_plan=new_plan)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        expected_pts = PLAN_ACHIEVEMENTS["premium"]["points"] - PLAN_ACHIEVEMENTS["basic"]["points"]
        self.assertEqual(kwargs[3], expected_pts)

    @patch.object(SubscriptionGamificationAdapter, "_award")
    def test_on_plan_changed_downgrade_no_award(self, mock_award):
        old_plan = MagicMock(); old_plan.name = "premium"
        new_plan = MagicMock(); new_plan.name = "basic"
        sub = self._make_sub()
        self.adapter.on_plan_changed(sender=None, instance=sub,
                                     old_plan=old_plan, new_plan=new_plan)
        mock_award.assert_not_called()

    def test_never_raises(self):
        with patch.object(SubscriptionGamificationAdapter, "_award", side_effect=Exception("x")):
            self.adapter.on_activated(sender=None, instance=self._make_sub())


# ===========================================================================
# PayoutQueueGamificationAdapter
# ===========================================================================

class PayoutQueueAdapterTest(TestCase):

    def setUp(self):
        self.adapter = PayoutQueueGamificationAdapter()
        self.user = _user()

    def _make_item(self, user=None, amount=100.0):
        item = MagicMock()
        item.user = user or self.user
        item.net_amount = amount
        item.id = "item-1"
        item.status = "succeeded"
        item.error_code = ""
        return item

    @patch.object(PayoutQueueGamificationAdapter, "_award")
    @patch.object(PayoutQueueGamificationAdapter, "_get_payout_count", return_value=1)
    def test_on_payout_succeeded_first(self, mock_count, mock_award):
        item = self._make_item()
        self.adapter.on_payout_succeeded(item)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertEqual(kwargs[1], PAYOUT_COUNT_MILESTONES[1]["title"])

    @patch.object(PayoutQueueGamificationAdapter, "_award")
    @patch.object(PayoutQueueGamificationAdapter, "_get_payout_count", return_value=3)
    def test_on_payout_succeeded_non_milestone_no_award(self, mock_count, mock_award):
        item = self._make_item()
        self.adapter.on_payout_succeeded(item)
        mock_award.assert_not_called()

    @patch.object(PayoutQueueGamificationAdapter, "_award")
    def test_on_payout_failed_no_award(self, mock_award):
        item = self._make_item()
        item.error_code = "INSUFFICIENT_FUNDS"
        self.adapter.on_payout_failed(item)
        mock_award.assert_not_called()

    def test_never_raises(self):
        with patch.object(PayoutQueueGamificationAdapter, "_get_payout_count",
                          side_effect=Exception("db")):
            self.adapter.on_payout_succeeded(self._make_item())


# ===========================================================================
# OfferwallGamificationAdapter
# ===========================================================================

class OfferwallAdapterTest(TestCase):

    def setUp(self):
        self.adapter = OfferwallGamificationAdapter()
        self.user = _user()

    @patch.object(OfferwallGamificationAdapter, "_award")
    @patch.object(OfferwallGamificationAdapter, "_get_offer_count", return_value=1)
    @patch.object(OfferwallGamificationAdapter, "_get_total_payout", return_value=Decimal("0"))
    def test_on_offer_completed_first(self, mock_total, mock_count, mock_award):
        self.adapter.on_offer_completed(user=self.user, payout=10.0, network="adgate")
        awards = [c[0][1] for c in mock_award.call_args_list]
        self.assertIn(OFFER_COUNT_MILESTONES[1]["title"], awards)

    @patch.object(OfferwallGamificationAdapter, "_award")
    @patch.object(OfferwallGamificationAdapter, "_get_offer_count", return_value=3)
    @patch.object(OfferwallGamificationAdapter, "_get_total_payout", return_value=Decimal("90"))
    def test_on_offer_completed_crosses_payout_threshold(self, mock_total, mock_count, mock_award):
        # total was 90, adding 20 → crosses 100
        self.adapter.on_offer_completed(user=self.user, payout=20.0)
        award_titles = [c[0][1] for c in mock_award.call_args_list]
        self.assertIn("Solid Earner", award_titles)

    @patch.object(OfferwallGamificationAdapter, "_award")
    def test_on_offer_completed_no_user(self, mock_award):
        self.adapter.on_offer_completed(user=None, payout=50.0)
        mock_award.assert_not_called()

    def test_never_raises(self):
        with patch.object(OfferwallGamificationAdapter, "_get_offer_count",
                          side_effect=Exception("db")):
            self.adapter.on_offer_completed(user=self.user, payout=10.0)


# ===========================================================================
# PostbackEngineGamificationAdapter
# ===========================================================================

class PostbackEngineAdapterTest(TestCase):

    def setUp(self):
        self.adapter = PostbackEngineGamificationAdapter()
        self.user = _user()

    def _make_conversion(self, points=500, usd=5.0):
        c = MagicMock()
        c.user = self.user
        c.points_awarded = points
        c.usd_awarded = usd
        c.id = "conv-1"
        return c

    @patch.object(PostbackEngineGamificationAdapter, "_check_points_total")
    @patch.object(PostbackEngineGamificationAdapter, "_check_usd_total")
    def test_on_postback_rewarded_calls_both_checks(self, mock_usd, mock_pts):
        conv = self._make_conversion()
        self.adapter.on_postback_rewarded(conversion=conv)
        mock_pts.assert_called_once_with(self.user, 500)
        mock_usd.assert_called_once_with(self.user, 5.0)

    @patch.object(PostbackEngineGamificationAdapter, "_award")
    @patch.object(PostbackEngineGamificationAdapter, "_get_total_points_awarded", return_value=900)
    def test_check_points_total_crosses_threshold(self, mock_total, mock_award):
        self.adapter._check_points_total(self.user, 200)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertEqual(kwargs[1], "Points Collector")

    @patch.object(PostbackEngineGamificationAdapter, "_award")
    @patch.object(PostbackEngineGamificationAdapter, "_get_total_usd_awarded",
                  return_value=Decimal("45"))
    def test_check_usd_total_crosses_threshold(self, mock_total, mock_award):
        self.adapter._check_usd_total(self.user, 10.0)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertIn("$50", kwargs[2])

    def test_no_user_skips(self):
        raw = MagicMock(); raw.user = None; raw.user_id = None
        conv = MagicMock(); conv.user = None; conv.user_id = None
        with patch.object(PostbackEngineGamificationAdapter, "_check_points_total") as m:
            self.adapter.on_postback_rewarded(raw_log=raw, conversion=conv)
            m.assert_not_called()


# ===========================================================================
# DJoyaltyGamificationAdapter
# ===========================================================================

class DJoyaltyAdapterTest(TestCase):

    def setUp(self):
        self.adapter = DJoyaltyGamificationAdapter()
        self.user = _user()

    def _make_event(self, tier="gold", badge="", days=0, points=0):
        e = MagicMock()
        e.customer = self.user
        e.new_tier = tier
        e.badge_name = badge
        e.streak_days = days
        e.points = points
        return e

    @patch.object(DJoyaltyGamificationAdapter, "_award")
    def test_on_tier_upgraded_gold(self, mock_award):
        event = self._make_event(tier="gold")
        self.adapter.on_tier_upgraded(event)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertEqual(kwargs[1], TIER_MAP["gold"]["title"])
        self.assertEqual(kwargs[3], TIER_MAP["gold"]["points"])

    @patch.object(DJoyaltyGamificationAdapter, "_award")
    def test_on_tier_upgraded_unknown_tier(self, mock_award):
        event = self._make_event(tier="obsidian")
        self.adapter.on_tier_upgraded(event)
        mock_award.assert_not_called()

    @patch.object(DJoyaltyGamificationAdapter, "_award")
    def test_on_badge_unlocked(self, mock_award):
        event = self._make_event(badge="Super Referrer")
        self.adapter.on_badge_unlocked(event)
        mock_award.assert_called_once()
        kwargs = mock_award.call_args[0]
        self.assertIn("Super Referrer", kwargs[1])

    @patch.object(DJoyaltyGamificationAdapter, "_award")
    def test_on_badge_unlocked_empty_name_skips(self, mock_award):
        event = self._make_event(badge="")
        self.adapter.on_badge_unlocked(event)
        mock_award.assert_not_called()

    @patch("api.gamification.integrations.adapter.gamification_adapter")
    def test_on_streak_milestone_delegates(self, mock_adapter):
        event = self._make_event(days=7)
        self.adapter.on_streak_milestone(event)
        mock_adapter.on_daily_checkin.assert_called_once_with(
            user=self.user, consecutive_days=7
        )

    def test_all_tier_map_entries_valid(self):
        for tier, cfg in TIER_MAP.items():
            self.assertIn("title", cfg)
            self.assertIn("points", cfg)
            self.assertGreater(cfg["points"], 0)


# ===========================================================================
# MonetizationGamificationAdapter
# ===========================================================================

class MonetizationAdapterTest(TestCase):

    def setUp(self):
        self.adapter = MonetizationGamificationAdapter()
        self.user = _user()

    def _make_user_level(self, level=5, xp=500, current_xp=100):
        ul = MagicMock()
        ul.user = self.user
        ul.current_level = level
        ul.total_xp_earned = xp
        ul.current_xp = current_xp
        return ul

    @patch.object(MonetizationGamificationAdapter, "_award")
    def test_on_level_up_milestone(self, mock_award):
        ul = self._make_user_level(level=5, xp=500, current_xp=50)
        self.adapter.on_level_up(ul)
        titles = [c[0][1] for c in mock_award.call_args_list]
        self.assertIn(LEVEL_ACHIEVEMENTS[5]["title"], titles)

    @patch.object(MonetizationGamificationAdapter, "_award")
    def test_on_level_up_non_milestone_no_level_award(self, mock_award):
        ul = self._make_user_level(level=3, xp=200, current_xp=50)
        self.adapter.on_level_up(ul)
        titles = [c[0][1] for c in mock_award.call_args_list]
        self.assertNotIn("Level 3 Achiever", titles)

    @patch.object(MonetizationGamificationAdapter, "_award")
    def test_on_level_up_no_user(self, mock_award):
        ul = MagicMock(); ul.user = None
        self.adapter.on_level_up(ul)
        mock_award.assert_not_called()

    @patch("api.gamification.integrations.offerwall_adapter.OfferwallGamificationAdapter.on_offer_completed")
    def test_on_offer_completed_delegates_to_offerwall(self, mock_ow):
        comp = MagicMock()
        comp.status = "approved"
        comp.user = self.user
        comp.payout_amount = 50.0
        comp.id = "c1"
        offer = MagicMock(); offer.network = "tapjoy"
        comp.offer = offer
        self.adapter.on_offer_completed(comp)
        mock_ow.assert_called_once()

    @patch("api.gamification.integrations.offerwall_adapter.OfferwallGamificationAdapter.on_offer_completed")
    def test_on_offer_completed_pending_skips(self, mock_ow):
        comp = MagicMock(); comp.status = "pending"
        self.adapter.on_offer_completed(comp)
        mock_ow.assert_not_called()


# ===========================================================================
# SecurityGamificationAdapter
# ===========================================================================

class SecurityAdapterTest(TestCase):

    def setUp(self):
        self.adapter = SecurityGamificationAdapter()
        self.user = _user()

    def test_on_user_ban_save_active_freezes(self):
        ban = MagicMock(); ban.user = self.user
        ban.status = "active"; ban.reason = "fraud"; ban.id = "ban-1"
        with patch.object(SecurityGamificationAdapter, "_freeze_achievements") as mock_freeze:
            self.adapter.on_user_ban_save(sender=None, instance=ban, created=True)
            mock_freeze.assert_called_once()

    def test_on_user_ban_save_expired_unfreezes(self):
        ban = MagicMock(); ban.user = self.user
        ban.status = "expired"; ban.id = "ban-1"
        with patch.object(SecurityGamificationAdapter, "_unfreeze_achievements") as mock_unfreeze:
            self.adapter.on_user_ban_save(sender=None, instance=ban, created=False)
            mock_unfreeze.assert_called_once_with(self.user)

    def test_on_user_ban_save_no_user_skips(self):
        ban = MagicMock(); ban.user = None; ban.status = "active"
        with patch.object(SecurityGamificationAdapter, "_freeze_achievements") as mock_freeze:
            self.adapter.on_user_ban_save(sender=None, instance=ban, created=True)
            mock_freeze.assert_not_called()

    def test_check_user_is_banned_returns_false_on_import_error(self):
        result = self.adapter.check_user_is_banned(self.user)
        self.assertFalse(result)  # security app not installed in test env

    def test_on_security_incident_low_severity_skips(self):
        incident = MagicMock(); incident.user = self.user; incident.severity = "low"
        with patch.object(SecurityGamificationAdapter, "_freeze_achievements") as mock_freeze:
            self.adapter.on_security_incident(incident)
            mock_freeze.assert_not_called()

    def test_on_security_incident_high_severity_freezes(self):
        incident = MagicMock()
        incident.user = self.user; incident.severity = "high"; incident.id = "inc-1"
        with patch.object(SecurityGamificationAdapter, "_freeze_achievements") as mock_freeze:
            self.adapter.on_security_incident(incident)
            mock_freeze.assert_called_once()

    def test_never_raises(self):
        ban = MagicMock(); ban.user = self.user; ban.status = "active"; ban.reason = "x"; ban.id = 1
        with patch.object(SecurityGamificationAdapter, "_freeze_achievements",
                          side_effect=Exception("db")):
            self.adapter.on_user_ban_save(sender=None, instance=ban, created=True)


# ===========================================================================
# FraudDetectionGamificationAdapter
# ===========================================================================

class FraudDetectionAdapterTest(TestCase):

    def setUp(self):
        self.adapter = FraudDetectionGamificationAdapter()
        self.user = _user()

    @patch.object(FraudDetectionGamificationAdapter, "_pause_user_achievements")
    def test_on_high_fraud_score_above_threshold(self, mock_pause):
        self.adapter.on_high_fraud_score(user=self.user, score=85.0)
        mock_pause.assert_called_once()

    @patch.object(FraudDetectionGamificationAdapter, "_pause_user_achievements")
    def test_on_high_fraud_score_below_threshold(self, mock_pause):
        self.adapter.on_high_fraud_score(user=self.user, score=50.0)
        mock_pause.assert_not_called()

    @patch.object(FraudDetectionGamificationAdapter, "_pause_user_achievements")
    @patch.object(FraudDetectionGamificationAdapter, "_revoke_recent_suspicious_awards")
    def test_on_user_auto_banned_pauses_and_revokes(self, mock_revoke, mock_pause):
        self.adapter.on_user_auto_banned(user=self.user, ban_type="auto_ban", score=92.0)
        mock_pause.assert_called_once()
        mock_revoke.assert_called_once_with(self.user)

    @patch.object(FraudDetectionGamificationAdapter, "_pause_user_achievements")
    def test_on_high_fraud_score_no_user(self, mock_pause):
        self.adapter.on_high_fraud_score(user=None, score=95.0)
        mock_pause.assert_not_called()

    def test_is_user_fraud_flagged_returns_false_on_import_error(self):
        result = self.adapter.is_user_fraud_flagged(self.user)
        self.assertFalse(result)

    def test_on_fraud_cleared_never_raises(self):
        self.adapter.on_fraud_cleared(user=self.user)  # no FraudFlag in test env

    def test_never_raises(self):
        with patch.object(FraudDetectionGamificationAdapter, "_pause_user_achievements",
                          side_effect=Exception("err")):
            self.adapter.on_high_fraud_score(user=self.user, score=90.0)


# ===========================================================================
# RateLimitGamificationAdapter
# ===========================================================================

class RateLimitAdapterTest(TestCase):

    def setUp(self):
        self.adapter = RateLimitGamificationAdapter()
        self.user = _user()

    def _make_request(self, path="/api/tasks/complete/"):
        req = MagicMock()
        req.user = self.user   # real Django user — is_authenticated is a property
        req.path = path
        return req

    @patch("django.core.cache.cache.set")
    @patch("django.core.cache.cache.get", return_value=0)
    def test_on_rate_limit_hit_increments(self, mock_get, mock_set):
        req = self._make_request()
        self.adapter.on_rate_limit_hit(request=req, endpoint="/api/tasks/complete/")
        mock_set.assert_called()

    @patch.object(RateLimitGamificationAdapter, "_temp_block_achievements")
    @patch.object(RateLimitGamificationAdapter, "_increment_violation_count",
                  return_value=BLOCK_THRESHOLD)
    def test_on_rate_limit_hit_blocks_at_threshold(self, mock_inc, mock_block):
        req = self._make_request()
        self.adapter.on_rate_limit_hit(request=req, endpoint="/api/tasks/complete/")
        mock_block.assert_called_once()

    @patch.object(RateLimitGamificationAdapter, "_temp_block_achievements")
    @patch.object(RateLimitGamificationAdapter, "_increment_violation_count", return_value=2)
    def test_on_rate_limit_hit_no_block_below_threshold(self, mock_inc, mock_block):
        req = self._make_request()
        self.adapter.on_rate_limit_hit(request=req, endpoint="/api/tasks/complete/")
        mock_block.assert_not_called()

    @patch("django.core.cache.cache.get", return_value={"endpoint": "/api/tasks/complete/"})
    def test_is_achievement_blocked_true(self, mock_get):
        result = self.adapter.is_achievement_blocked(self.user)
        self.assertTrue(result)

    @patch("django.core.cache.cache.get", return_value=None)
    def test_is_achievement_blocked_false(self, mock_get):
        result = self.adapter.is_achievement_blocked(self.user)
        self.assertFalse(result)

    @patch("django.core.cache.cache.delete")
    def test_on_rate_limit_cleared_deletes_keys(self, mock_delete):
        self.adapter.on_rate_limit_cleared(self.user)
        self.assertEqual(mock_delete.call_count, 2)

    def test_unauthenticated_user_skips(self):
        from django.contrib.auth.models import AnonymousUser
        req = MagicMock()
        req.user = AnonymousUser()
        with patch.object(RateLimitGamificationAdapter, "_increment_violation_count") as mock_inc:
            self.adapter.on_rate_limit_hit(request=req)
            mock_inc.assert_not_called()

    def test_never_raises(self):
        with patch.object(RateLimitGamificationAdapter, "_increment_violation_count",
                          side_effect=Exception("cache down")):
            req = self._make_request()
            self.adapter.on_rate_limit_hit(request=req)


# ===========================================================================
# GamificationAdapter hub — new methods
# ===========================================================================

class GamificationAdapterNewMethodsTest(TestCase):

    def setUp(self):
        self.adapter = GamificationAdapter()
        self.user = _user()

    @patch("api.gamification.integrations.kyc_adapter.KYCGamificationAdapter.on_kyc_verified")
    def test_on_kyc_verified_delegates(self, mock_kyc):
        self.adapter.on_kyc_verified(user=self.user)
        mock_kyc.assert_called_once_with(user=self.user, kyc=None)

    @patch("api.gamification.integrations.subscription_adapter.SubscriptionGamificationAdapter.on_activated")
    def test_on_subscription_activated_delegates(self, mock_sub):
        instance = MagicMock()
        self.adapter.on_subscription_activated(sender=None, instance=instance)
        mock_sub.assert_called_once()

    @patch("api.gamification.integrations.payout_queue_adapter.PayoutQueueGamificationAdapter.on_payout_succeeded")
    def test_on_payout_succeeded_delegates(self, mock_pq):
        item = MagicMock()
        self.adapter.on_payout_succeeded(item=item)
        mock_pq.assert_called_once_with(item=item)

    @patch("api.gamification.integrations.offerwall_adapter.OfferwallGamificationAdapter.on_offer_completed")
    def test_on_offer_completed_delegates(self, mock_ow):
        self.adapter.on_offer_completed(user=self.user, payout=50.0, network="adgate")
        mock_ow.assert_called_once()

    @patch("api.gamification.integrations.postback_engine_adapter.PostbackEngineGamificationAdapter.on_postback_rewarded")
    def test_on_postback_rewarded_delegates(self, mock_pb):
        conv = MagicMock()
        self.adapter.on_postback_rewarded(conversion=conv)
        mock_pb.assert_called_once()

    @patch("api.gamification.integrations.djoyalty_adapter.DJoyaltyGamificationAdapter.on_tier_upgraded")
    def test_on_djoyalty_tier_upgraded_delegates(self, mock_dj):
        event = MagicMock()
        self.adapter.on_djoyalty_tier_upgraded(event=event)
        mock_dj.assert_called_once_with(event)

    @patch("api.gamification.integrations.monetization_adapter.MonetizationGamificationAdapter.on_level_up")
    def test_on_monetization_level_up_delegates(self, mock_mt):
        ul = MagicMock()
        self.adapter.on_monetization_level_up(user_level=ul)
        mock_mt.assert_called_once_with(ul)

    @patch("api.gamification.integrations.security_adapter.SecurityGamificationAdapter.on_user_ban_save")
    def test_on_user_banned_delegates(self, mock_sec):
        ban = MagicMock()
        self.adapter.on_user_banned(sender=None, instance=ban, created=True)
        mock_sec.assert_called_once()

    @patch("api.gamification.integrations.fraud_detection_adapter.FraudDetectionGamificationAdapter.on_high_fraud_score")
    def test_on_fraud_score_high_delegates(self, mock_fraud):
        self.adapter.on_fraud_score_high(user=self.user, score=88.0)
        mock_fraud.assert_called_once_with(user=self.user, score=88.0, signals=None)

    @patch("api.gamification.integrations.rate_limit_adapter.RateLimitGamificationAdapter.on_rate_limit_hit")
    def test_on_rate_limit_violation_delegates(self, mock_rl):
        self.adapter.on_rate_limit_violation(endpoint="/api/tasks/complete/", user=self.user)
        mock_rl.assert_called_once()

    @patch("api.gamification.integrations.security_adapter.SecurityGamificationAdapter.check_user_is_banned",
           return_value=False)
    @patch("api.gamification.integrations.fraud_detection_adapter.FraudDetectionGamificationAdapter.is_user_fraud_flagged",
           return_value=False)
    @patch("api.gamification.integrations.rate_limit_adapter.RateLimitGamificationAdapter.is_achievement_blocked",
           return_value=False)
    def test_is_user_allowed_achievement_true(self, mock_rl, mock_fraud, mock_sec):
        result = self.adapter.is_user_allowed_achievement(self.user)
        self.assertTrue(result)

    @patch("api.gamification.integrations.security_adapter.SecurityGamificationAdapter.check_user_is_banned",
           return_value=True)
    def test_is_user_allowed_achievement_false_when_banned(self, mock_ban):
        result = self.adapter.is_user_allowed_achievement(self.user)
        self.assertFalse(result)

    def test_is_user_allowed_achievement_fails_open(self):
        with patch("api.gamification.integrations.security_adapter.SecurityGamificationAdapter.check_user_is_banned",
                   side_effect=Exception("db error")):
            result = self.adapter.is_user_allowed_achievement(self.user)
            self.assertTrue(result)  # fail open — never block on error

    def test_all_new_methods_never_raise(self):
        for method, kwargs in [
            ("on_kyc_verified",            {"user": self.user}),
            ("on_kyc_rejected",            {"user": self.user}),
            ("on_subscription_activated",  {"sender": None, "instance": MagicMock()}),
            ("on_payout_succeeded",        {"item": MagicMock()}),
            ("on_offer_completed",         {"user": self.user, "payout": 10.0}),
            ("on_postback_rewarded",       {"conversion": MagicMock()}),
            ("on_djoyalty_tier_upgraded",  {"event": MagicMock()}),
            ("on_monetization_level_up",   {"user_level": MagicMock()}),
            ("on_user_banned",             {"sender": None, "instance": MagicMock(), "created": True}),
            ("on_fraud_score_high",        {"user": self.user, "score": 90.0}),
            ("on_user_auto_banned",        {"user": self.user, "ban_type": "auto_ban"}),
            ("on_rate_limit_violation",    {"user": self.user, "endpoint": "/x/"}),
        ]:
            with self.subTest(method=method):
                with patch(f"api.gamification.integrations.kyc_adapter.KYCGamificationAdapter.on_kyc_verified",
                           side_effect=Exception("boom")):
                    getattr(self.adapter, method)(**kwargs)  # must not raise
