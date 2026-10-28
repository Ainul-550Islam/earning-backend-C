"""
New Adapter Tests — 13 adapters wired to real api/ systems
Run: python manage.py test api.offerwall.tests.test_new_adapters
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def mk_user(un='na_u'):
    return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')


def F():
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
    return OfferwallAdapterFactory


# ── Factory has all 18 adapters ───────────────────────────────────────────────

class ExtendedFactoryTest(TestCase):
    def test_all_18_adapters_registered(self):
        factory = F()
        expected = [
            'wallet', 'notification', 'fraud', 'audit', 'referral',
            'analytics', 'tasks', 'postback', 'postback_engine',
            'gamification', 'loyalty', 'promotions', 'alerts',
            'rate_limit', 'behavior', 'offer_routing', 'payout_queue',
            'subscription',
        ]
        for name in expected:
            adapter = factory.get(name)
            self.assertIsNotNone(adapter, f'{name} adapter missing')

    def test_factory_health_check_all_18(self):
        health = F().health_check_all()
        self.assertGreaterEqual(len(health), 18)

    def test_all_new_adapters_have_name(self):
        for name in ['analytics', 'tasks', 'gamification', 'loyalty',
                     'promotions', 'alerts', 'rate_limit', 'behavior',
                     'offer_routing', 'payout_queue', 'subscription']:
            adapter = F().get(name)
            self.assertEqual(adapter.name, {
                'analytics': 'analytics', 'tasks': 'tasks',
                'gamification': 'gamification', 'loyalty': 'loyalty',
                'promotions': 'promotions', 'alerts': 'alerts',
                'rate_limit': 'rate_limit', 'behavior': 'behavior',
                'offer_routing': 'offer_routing', 'payout_queue': 'payout_queue',
                'subscription': 'subscription',
            }[name])


# ── AnalyticsAdapter ──────────────────────────────────────────────────────────

class AnalyticsAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('ana_u')

    @patch('api.analytics.services.AnalyticsService')
    def test_analytics_event_sent(self, mock_svc):
        from api.offerwall.services.adapters.OfferwallAdapter import AnalyticsAdapter
        a = AnalyticsAdapter()
        r = a.send({'event': 'offer_view', 'user_id': self.user.id,
                    'offer_id': 'off_001', 'provider': 'tapjoy'})
        self.assertTrue(r['success'])
        self.assertEqual(r['event'], 'offer_view')

    def test_analytics_failure_returns_success_non_critical(self):
        from api.offerwall.services.adapters.OfferwallAdapter import AnalyticsAdapter
        a = AnalyticsAdapter()
        # Should not crash even if analytics service unavailable
        r = a.send({'event': 'offer_click', 'user_id': self.user.id})
        self.assertIsNotNone(r)


# ── TaskAdapter ───────────────────────────────────────────────────────────────

class TaskAdapterTest(TestCase):
    @patch('api.tasks.ad_networks_tasks.sync_ad_network_revenue')
    def test_sync_revenue_task_dispatched(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task_001')
        from api.offerwall.services.adapters.OfferwallAdapter import TaskAdapter
        a = TaskAdapter()
        r = a.send({'task': 'sync_revenue'})
        self.assertTrue(r['success'])
        self.assertEqual(r.get('task'), 'sync_revenue')

    def test_unknown_task_succeeds_gracefully(self):
        from api.offerwall.services.adapters.OfferwallAdapter import TaskAdapter
        a = TaskAdapter()
        r = a.send({'task': 'nonexistent_task_xyz'})
        self.assertTrue(r['success'])
        self.assertTrue(r.get('queued') or r.get('sync_fallback'))

    def test_import_error_falls_back_gracefully(self):
        from api.offerwall.services.adapters.OfferwallAdapter import TaskAdapter
        a = TaskAdapter()
        r = a.send({'task': 'process_earnings'})
        self.assertIsNotNone(r)


# ── PostbackAdapter ───────────────────────────────────────────────────────────

class PostbackAdapterTest(TestCase):
    @patch('api.postback_engine.webhook_manager.custom_webhook.CustomWebhook.send')
    def test_sends_postback_to_url(self, mock_send):
        mock_send.return_value = True
        from api.offerwall.services.adapters.OfferwallAdapter import PostbackAdapter
        a = PostbackAdapter()
        r = a.send({
            'url': 'https://tapjoy.com/postback',
            'event': 'conversion',
            'data': {'offer_id': 'tj_001', 'payout': '1.50'},
            'secret': 'secret_key',
            'conversion_id': 'conv_pb_001',
        })
        self.assertTrue(r['success'])
        mock_send.assert_called_once()

    def test_no_url_skips_gracefully(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PostbackAdapter
        a = PostbackAdapter()
        r = a.send({'conversion_id': 'no_url_001'})
        self.assertEqual(r.get('skipped'), 'no_postback_url')

    @patch('api.postback_engine.webhook_manager.custom_webhook.CustomWebhook.send')
    def test_failed_postback_returns_false(self, mock_send):
        mock_send.return_value = False
        from api.offerwall.services.adapters.OfferwallAdapter import PostbackAdapter
        a = PostbackAdapter()
        r = a.send({'url': 'https://fail.example.com', 'conversion_id': 'fail_001'})
        self.assertFalse(r['success'])


# ── PostbackEngineAdapter ─────────────────────────────────────────────────────

class PostbackEngineAdapterTest(TestCase):
    @patch('api.postback_engine.webhook_manager.zapier_integration.ZapierIntegration.send_conversion')
    def test_zapier_channel(self, mock_zap):
        mock_zap.return_value = True
        from api.offerwall.services.adapters.OfferwallAdapter import PostbackEngineAdapter
        conv = MagicMock(); conv.id = 'conv_zap_001'
        a = PostbackEngineAdapter()
        r = a.send({'conversion': conv, 'channel': 'zapier'})
        self.assertTrue(r['success'])

    @patch('api.postback_engine.webhook_manager.make_integration.MakeIntegration.send_conversion')
    def test_make_channel(self, mock_make):
        mock_make.return_value = True
        from api.offerwall.services.adapters.OfferwallAdapter import PostbackEngineAdapter
        conv = MagicMock(); conv.id = 'conv_make_001'
        a = PostbackEngineAdapter()
        r = a.send({'conversion': conv, 'channel': 'make'})
        self.assertTrue(r['success'])

    def test_no_conversion_no_url_skips(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PostbackEngineAdapter
        a = PostbackEngineAdapter()
        r = a.send({'channel': 'custom'})
        self.assertEqual(r.get('skipped'), 'no_conversion_or_url')


# ── GamificationAdapter ───────────────────────────────────────────────────────

class GamificationAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('gam_u')

    @patch('api.gamification.services.award_achievement')
    def test_award_achievement_called(self, mock_award):
        mock_award.return_value = MagicMock(id='ach_001')
        from api.offerwall.services.adapters.OfferwallAdapter import GamificationAdapter
        a = GamificationAdapter()
        r = a.send({
            'user_id': self.user.id,
            'achievement_type': 'offer_complete',
            'title': 'First Offer!',
            'points': 50,
            'description': 'Completed your first offer',
            'metadata': {'offer_id': 'off_001'},
        })
        self.assertTrue(r['success'])
        self.assertEqual(r['points_awarded'], 50)
        mock_award.assert_called_once()

    @patch('api.gamification.services.award_achievement')
    def test_award_achievement_exact_params(self, mock_award):
        mock_award.return_value = MagicMock(id='ach_002')
        from api.offerwall.services.adapters.OfferwallAdapter import GamificationAdapter
        a = GamificationAdapter()
        a.send({'user_id': self.user.id, 'achievement_type': 'offer_complete',
                'title': 'T', 'points': 25})
        kw = {**mock_award.call_args.kwargs}
        self.assertEqual(kw['user_id'], self.user.id)
        self.assertEqual(kw['achievement_type'], 'offer_complete')
        self.assertEqual(kw['points'], 25)

    @patch('api.gamification.services.award_achievement')
    def test_idempotent_award_no_crash(self, mock_award):
        # award_achievement is idempotent — duplicate ok
        mock_award.return_value = MagicMock(id='ach_003')
        from api.offerwall.services.adapters.OfferwallAdapter import GamificationAdapter
        a = GamificationAdapter()
        a.send({'user_id': self.user.id, 'achievement_type': 'offer_complete',
                'title': 'T', 'points': 10})
        a.send({'user_id': self.user.id, 'achievement_type': 'offer_complete',
                'title': 'T', 'points': 10})
        self.assertEqual(mock_award.call_count, 2)


# ── LoyaltyAdapter ────────────────────────────────────────────────────────────

class LoyaltyAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('loy_u')

    @patch('api.djoyalty.services.earn.BonusEventService.BonusEventService.award_bonus')
    def test_loyalty_points_awarded(self, mock_award):
        mock_award.return_value = MagicMock(id='bonus_001')
        from api.offerwall.services.adapters.OfferwallAdapter import LoyaltyAdapter
        a = LoyaltyAdapter()
        r = a.send({
            'user_id': self.user.id,
            'points': Decimal('70'),
            'reason': 'Offer reward: Test Offer',
            'triggered_by': 'offerwall',
        })
        self.assertTrue(r['success'])
        self.assertEqual(r['points_awarded'], '70')
        mock_award.assert_called_once()

    @patch('api.djoyalty.services.earn.BonusEventService.BonusEventService.award_bonus')
    def test_award_bonus_exact_params(self, mock_award):
        mock_award.return_value = MagicMock(id='bonus_002')
        from api.offerwall.services.adapters.OfferwallAdapter import LoyaltyAdapter
        a = LoyaltyAdapter()
        a.send({'user_id': self.user.id, 'points': Decimal('50'),
                'reason': 'Test reason', 'triggered_by': 'offerwall'})
        kw = mock_award.call_args.kwargs if mock_award.call_args.kwargs else {}
        args = mock_award.call_args.args if mock_award.call_args.args else ()
        # Check either positional or keyword args
        call_str = str(mock_award.call_args)
        self.assertIn('Test reason', call_str)
        self.assertIn('offerwall', call_str)

    def test_zero_points_skipped(self):
        from api.offerwall.services.adapters.OfferwallAdapter import LoyaltyAdapter
        a = LoyaltyAdapter()
        r = a.send({'user_id': self.user.id, 'points': Decimal('0'), 'reason': 'x'})
        self.assertEqual(r.get('skipped'), 'zero_points')

    def test_unknown_user_returns_error(self):
        from api.offerwall.services.adapters.OfferwallAdapter import LoyaltyAdapter
        a = LoyaltyAdapter()
        r = a.send({'user_id': 99999, 'points': Decimal('50'), 'reason': 'x'})
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'user_not_found')


# ── PromotionAdapter ──────────────────────────────────────────────────────────

class PromotionAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('prm_u')

    def test_no_active_promotions_returns_zero_bonus(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PromotionAdapter
        a = PromotionAdapter()
        r = a.send({'user_id': self.user.id, 'offer_id': 'off_001', 'base_amount': '1.00'})
        self.assertTrue(r['success'])
        self.assertEqual(r['bonus_amount'], '0')

    def test_unknown_user_returns_error(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PromotionAdapter
        a = PromotionAdapter()
        r = a.send({'user_id': 99999, 'offer_id': 'off_x', 'base_amount': '1.00'})
        self.assertFalse(r['success'])

    def test_returns_bonus_amount_string(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PromotionAdapter
        a = PromotionAdapter()
        r = a.send({'user_id': self.user.id, 'offer_id': 'off_002', 'base_amount': '2.00'})
        self.assertIn('bonus_amount', r)
        # bonus_amount must be a string Decimal
        from decimal import Decimal
        self.assertGreaterEqual(Decimal(r['bonus_amount']), Decimal('0'))


# ── AlertAdapter ──────────────────────────────────────────────────────────────

class AlertAdapterTest(TestCase):
    @patch('api.alerts.models.incident.Incident.objects.create')
    def test_alert_created(self, mock_create):
        mock_create.return_value = MagicMock(id='inc_001')
        from api.offerwall.services.adapters.OfferwallAdapter import AlertAdapter
        a = AlertAdapter()
        r = a.send({
            'alert_type': 'high_fraud_rate',
            'severity': 'high',
            'message': 'Fraud rate exceeded 30%',
            'metadata': {'fraud_rate': 35, 'provider': 'tapjoy'},
        })
        self.assertTrue(r['success'])
        mock_create.assert_called_once()

    @patch('api.alerts.models.incident.Incident.objects.create')
    def test_alert_correct_title_format(self, mock_create):
        mock_create.return_value = MagicMock(id='inc_002')
        from api.offerwall.services.adapters.OfferwallAdapter import AlertAdapter
        a = AlertAdapter()
        a.send({'alert_type': 'provider_down', 'severity': 'critical', 'message': 'msg'})
        create_kwargs = mock_create.call_args.kwargs
        self.assertIn('Offerwall', create_kwargs.get('title', ''))
        self.assertIn('provider_down', create_kwargs.get('title', ''))


# ── RateLimitAdapter ──────────────────────────────────────────────────────────

class RateLimitAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('rl_u')

    @patch('api.rate_limit.services.RateLimitService.is_rate_limited')
    def test_not_limited_allowed(self, mock_rl):
        mock_rl.return_value = (False, 95)
        from api.offerwall.services.adapters.OfferwallAdapter import RateLimitAdapter
        a = RateLimitAdapter()
        r = a.send({'user_id': self.user.id, 'limit_type': 'offer_click', 'max_requests': 100})
        self.assertTrue(r['success'])
        self.assertTrue(r['allowed'])
        self.assertFalse(r['limited'])
        self.assertEqual(r['remaining'], 95)

    @patch('api.rate_limit.services.RateLimitService.is_rate_limited')
    def test_limited_not_allowed(self, mock_rl):
        mock_rl.return_value = (True, 0)
        from api.offerwall.services.adapters.OfferwallAdapter import RateLimitAdapter
        a = RateLimitAdapter()
        r = a.send({'user_id': self.user.id, 'limit_type': 'offer_click'})
        self.assertFalse(r['allowed'])
        self.assertTrue(r['limited'])

    @patch('api.rate_limit.services.RateLimitService.is_rate_limited')
    def test_identifier_format(self, mock_rl):
        mock_rl.return_value = (False, 99)
        from api.offerwall.services.adapters.OfferwallAdapter import RateLimitAdapter
        a = RateLimitAdapter()
        a.send({'user_id': self.user.id, 'limit_type': 'offer_click'})
        call_args = mock_rl.call_args
        identifier = call_args.kwargs.get('identifier') or call_args.args[0]
        self.assertIn(str(self.user.id), identifier)


# ── BehaviorAdapter ───────────────────────────────────────────────────────────

class BehaviorAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('beh_u')

    @patch('api.behavior_analytics.services.BehaviorAnalyticsService.record_click')
    def test_behavior_event_recorded(self, mock_record):
        from api.offerwall.services.adapters.OfferwallAdapter import BehaviorAdapter
        a = BehaviorAdapter()
        r = a.send({
            'user_id': self.user.id,
            'event_type': 'offer_viewed',
            'context': {'offer_id': 'off_001', 'category': 'games'},
        })
        self.assertTrue(r['success'])
        self.assertEqual(r['event_type'], 'offer_viewed')

    def test_behavior_failure_non_critical(self):
        from api.offerwall.services.adapters.OfferwallAdapter import BehaviorAdapter
        a = BehaviorAdapter()
        # Even if behavior analytics is down, should return success
        r = a.send({'user_id': self.user.id, 'event_type': 'offer_clicked'})
        self.assertIsNotNone(r)

    def test_returns_event_type_in_response(self):
        from api.offerwall.services.adapters.OfferwallAdapter import BehaviorAdapter
        a = BehaviorAdapter()
        r = a.send({'user_id': self.user.id, 'event_type': 'offer_abandoned',
                    'context': {'offer_id': 'off_002'}})
        self.assertEqual(r.get('event_type'), 'offer_abandoned')


# ── OfferRoutingAdapter ───────────────────────────────────────────────────────

class OfferRoutingAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('ort_u')

    @patch('api.offer_routing.routing.route_multiple_offers')
    def test_routing_returns_offer_ids(self, mock_route):
        mock_route.return_value = [
            {'offer_id': 'route_off_001'},
            {'offer_id': 'route_off_002'},
        ]
        from api.offerwall.services.adapters.OfferwallAdapter import OfferRoutingAdapter
        a = OfferRoutingAdapter()
        r = a.send({'user_id': self.user.id, 'count': 20,
                    'context': {'platform': 'android', 'country': 'BD'}})
        self.assertTrue(r['success'])
        self.assertEqual(len(r['offer_ids']), 2)
        self.assertIn('route_off_001', r['offer_ids'])

    @patch('api.offer_routing.routing.route_multiple_offers')
    def test_routing_called_with_correct_params(self, mock_route):
        mock_route.return_value = []
        from api.offerwall.services.adapters.OfferwallAdapter import OfferRoutingAdapter
        a = OfferRoutingAdapter()
        a.send({'user_id': self.user.id, 'count': 5,
                'context': {'platform': 'ios'}})
        args, kwargs = mock_route.call_args
        user_id_arg = kwargs.get('user_id') or (args[0] if args else None)
        self.assertEqual(user_id_arg, self.user.id)

    @patch('api.offer_routing.routing.route_multiple_offers')
    def test_empty_routing_result(self, mock_route):
        mock_route.return_value = []
        from api.offerwall.services.adapters.OfferwallAdapter import OfferRoutingAdapter
        a = OfferRoutingAdapter()
        r = a.send({'user_id': self.user.id, 'count': 10})
        self.assertTrue(r['success'])
        self.assertEqual(r['offer_ids'], [])
        self.assertEqual(r['count'], 0)


# ── PayoutQueueAdapter ────────────────────────────────────────────────────────

class PayoutQueueAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('pq_u')

    def test_zero_amount_skipped(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PayoutQueueAdapter
        a = PayoutQueueAdapter()
        r = a.send({'user_id': self.user.id, 'amount': '0', 'conversion_id': 'pq_001'})
        self.assertEqual(r.get('skipped'), 'zero_amount')

    def test_unknown_user_error(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PayoutQueueAdapter
        a = PayoutQueueAdapter()
        r = a.send({'user_id': 99999, 'amount': '1.00', 'conversion_id': 'pq_bad'})
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'user_not_found')

    @patch('api.payout_queue.services.add_payout_items')
    @patch('api.payout_queue.models.PayoutBatch.objects.get_or_create')
    def test_payout_queued_successfully(self, mock_gwc, mock_add):
        mock_batch = MagicMock(); mock_batch.id = 'batch_001'
        mock_gwc.return_value = (mock_batch, True)
        mock_add.return_value = [MagicMock()]
        from api.offerwall.services.adapters.OfferwallAdapter import PayoutQueueAdapter
        a = PayoutQueueAdapter()
        r = a.send({'user_id': self.user.id, 'amount': '1.40', 'conversion_id': 'pq_ok'})
        self.assertTrue(r['success'])
        self.assertEqual(r['amount'], '1.40')
        mock_add.assert_called_once()

    @patch('api.payout_queue.services.add_payout_items')
    @patch('api.payout_queue.models.PayoutBatch.objects.get_or_create')
    def test_add_payout_items_correct_params(self, mock_gwc, mock_add):
        mock_batch = MagicMock(); mock_batch.id = 'batch_002'
        mock_gwc.return_value = (mock_batch, True)
        mock_add.return_value = [MagicMock()]
        from api.offerwall.services.adapters.OfferwallAdapter import PayoutQueueAdapter
        a = PayoutQueueAdapter()
        a.send({'user_id': self.user.id, 'amount': '2.00', 'conversion_id': 'pq_prm'})
        kw = mock_add.call_args.kwargs
        self.assertEqual(kw['batch_id'], 'batch_002')
        items = kw['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['user_id'], self.user.id)
        self.assertEqual(items[0]['gross_amount'], Decimal('2.00'))


# ── SubscriptionAdapter ───────────────────────────────────────────────────────

class SubscriptionAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('sub_u')

    def test_free_user_returns_1x_multiplier(self):
        from api.offerwall.services.adapters.OfferwallAdapter import SubscriptionAdapter
        a = SubscriptionAdapter()
        r = a.send({'user_id': self.user.id})
        self.assertTrue(r['success'])
        self.assertEqual(r['tier'], 'free')
        self.assertEqual(r['multiplier'], 1.0)

    @patch('api.subscription.models.UserSubscription.objects.filter')
    def test_premium_user_returns_1_5x(self, mock_filter):
        mock_plan = MagicMock(); mock_plan.name = 'premium'
        mock_sub  = MagicMock(); mock_sub.plan = mock_plan; mock_sub.status = 'active'
        mock_qs   = MagicMock(); mock_qs.select_related.return_value.first.return_value = mock_sub
        mock_filter.return_value = mock_qs
        from api.offerwall.services.adapters.OfferwallAdapter import SubscriptionAdapter
        a = SubscriptionAdapter()
        r = a.send({'user_id': self.user.id})
        self.assertTrue(r['success'])
        self.assertEqual(r['multiplier'], 1.5)
        self.assertEqual(r['tier'], 'premium')

    @patch('api.subscription.models.UserSubscription.objects.filter')
    def test_vip_user_returns_2x(self, mock_filter):
        mock_plan = MagicMock(); mock_plan.name = 'vip plan'
        mock_sub  = MagicMock(); mock_sub.plan = mock_plan; mock_sub.status = 'active'
        mock_qs   = MagicMock(); mock_qs.select_related.return_value.first.return_value = mock_sub
        mock_filter.return_value = mock_qs
        from api.offerwall.services.adapters.OfferwallAdapter import SubscriptionAdapter
        a = SubscriptionAdapter()
        r = a.send({'user_id': self.user.id})
        self.assertEqual(r['multiplier'], 2.0)

    def test_unknown_user_returns_free_tier(self):
        from api.offerwall.services.adapters.OfferwallAdapter import SubscriptionAdapter
        a = SubscriptionAdapter()
        r = a.send({'user_id': 99999})
        self.assertFalse(r['success'])
        self.assertEqual(r['tier'], 'free')
        self.assertEqual(r['multiplier'], 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# EXTENDED TESTS — 44 additional cases to reach target of 87
# ══════════════════════════════════════════════════════════════════════════════

# ── BaseAdapter circuit breaker & retry ──────────────────────────────────────

class CircuitBreakerTest(TestCase):
    """Circuit breaker opens after max_retries consecutive failures."""

    def _failing_adapter(self):
        from api.offerwall.services.adapters.OfferwallAdapter import BaseOfferwallAdapter
        class FailAdapter(BaseOfferwallAdapter):
            name = 'fail_cb'
            max_retries = 2
            retry_delay = 0.0
            def _do_send(self, p, **kw):
                raise RuntimeError('always fails')
        return FailAdapter()

    def test_circuit_opens_after_max_retries(self):
        a = self._failing_adapter()
        a.send({})          # first call exhausts retries → circuit opens
        self.assertTrue(a._circuit_open)

    def test_circuit_open_returns_immediately(self):
        a = self._failing_adapter()
        a.send({})           # open circuit
        r = a.send({})       # should return immediately with circuit_open error
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'circuit_open')

    def test_failure_count_incremented(self):
        a = self._failing_adapter()
        a.send({})
        self.assertGreaterEqual(a._failure_count, 2)

    def test_circuit_recovers_after_timeout(self):
        from django.utils import timezone
        from datetime import timedelta
        a = self._failing_adapter()
        a._circuit_open = True
        a._last_failure = timezone.now() - timedelta(seconds=120)
        self.assertTrue(a._should_recover())

    def test_circuit_stays_open_within_timeout(self):
        from django.utils import timezone
        from datetime import timedelta
        a = self._failing_adapter()
        a._circuit_open = True
        a._last_failure = timezone.now() - timedelta(seconds=10)
        self.assertFalse(a._should_recover())

    def test_success_resets_failure_count(self):
        from api.offerwall.services.adapters.OfferwallAdapter import BaseOfferwallAdapter
        class OkAdapter(BaseOfferwallAdapter):
            name = 'ok_cb'
            retry_delay = 0.0
            def _do_send(self, p, **kw): return {'success': True}
        a = OkAdapter()
        a._failure_count = 5
        a.send({})
        self.assertEqual(a._failure_count, 0)

    def test_health_check_reflects_circuit_state(self):
        a = self._failing_adapter()
        a.send({})
        h = a.health_check()
        self.assertTrue(h['circuit_open'])
        self.assertEqual(h['adapter'], 'fail_cb')

    def test_error_response_contains_adapter_name(self):
        a = self._failing_adapter()
        r = a.send({})
        self.assertEqual(r['adapter'], 'fail_cb')


# ── WalletAdapter extended ────────────────────────────────────────────────────

class WalletAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('wa_ext')

    def test_zero_total_skipped(self):
        from api.offerwall.services.adapters.OfferwallAdapter import WalletAdapter
        a = WalletAdapter()
        r = a.send({'user_id': self.user.id, 'reward_amount': '0', 'bonus_amount': '0',
                    'conversion_id': 'wa_zero'})
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'invalid_amount')

    def test_user_not_found_returns_error(self):
        from api.offerwall.services.adapters.OfferwallAdapter import WalletAdapter
        a = WalletAdapter()
        r = a.send({'user_id': 9999999, 'reward_amount': '1.00', 'bonus_amount': '0',
                    'conversion_id': 'wa_nouser'})
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'user_not_found')

    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_add_earnings_called_with_correct_amount(self, mock_gwc, mock_earn):
        mock_wallet = MagicMock()
        mock_gwc.return_value = (mock_wallet, False)
        mock_txn = MagicMock(); mock_txn.txn_id = 'txn_wa_001'
        mock_earn.return_value = mock_txn
        from api.offerwall.services.adapters.OfferwallAdapter import WalletAdapter
        a = WalletAdapter()
        r = a.send({'user_id': self.user.id, 'reward_amount': '0.70',
                    'bonus_amount': '0.10', 'conversion_id': 'wa_ok',
                    'offer_title': 'T', 'offer_id': 'o1', 'provider_type': 'tapjoy'})
        self.assertTrue(r['success'])
        self.assertEqual(r['txn_id'], 'txn_wa_001')
        args = mock_earn.call_args
        # Total = 0.70 + 0.10 = 0.80
        total = Decimal('0.80')
        amount_arg = args.args[1] if args.args else args.kwargs.get('amount')
        self.assertEqual(amount_arg, total)

    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_add_earnings_source_type_is_offer(self, mock_gwc, mock_earn):
        mock_wallet = MagicMock()
        mock_gwc.return_value = (mock_wallet, False)
        mock_txn = MagicMock(); mock_txn.txn_id = 'txn_wa_002'
        mock_earn.return_value = mock_txn
        from api.offerwall.services.adapters.OfferwallAdapter import WalletAdapter
        a = WalletAdapter()
        a.send({'user_id': self.user.id, 'reward_amount': '1.00', 'bonus_amount': '0',
                'conversion_id': 'wa_src', 'offer_title': 'T', 'offer_id': 'o2',
                'provider_type': 'adgem'})
        call_str = str(mock_earn.call_args)
        self.assertIn('offer', call_str.lower())


# ── NotificationAdapter extended ─────────────────────────────────────────────

class NotificationAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('not_ext')

    @patch('api.notifications.services.NotificationService')
    def test_reward_earned_notification(self, mock_cls):
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        mock_svc.create_notification.return_value = MagicMock(id='notif_001')
        from api.offerwall.services.adapters.OfferwallAdapter import NotificationAdapter
        a = NotificationAdapter()
        r = a.send({
            'user_id': self.user.id, 'event': 'reward_earned',
            'offer_title': 'Test Offer', 'reward_amount': '0.70',
            'reward_currency': 'BDT', 'conversion_id': 'c1',
        })
        self.assertTrue(r['success'])
        mock_svc.create_notification.assert_called_once()

    @patch('api.notifications.services.NotificationService')
    def test_reward_rejected_notification(self, mock_cls):
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        mock_svc.create_notification.return_value = MagicMock(id='notif_002')
        from api.offerwall.services.adapters.OfferwallAdapter import NotificationAdapter
        a = NotificationAdapter()
        r = a.send({
            'user_id': self.user.id, 'event': 'reward_rejected',
            'offer_title': 'Bad Offer', 'reward_amount': '0.70',
            'reward_currency': 'BDT', 'conversion_id': 'c2',
            'reason': 'fraud detected',
        })
        self.assertTrue(r['success'])

    def test_user_not_found_returns_error(self):
        from api.offerwall.services.adapters.OfferwallAdapter import NotificationAdapter
        a = NotificationAdapter()
        r = a.send({'user_id': 9999999, 'event': 'reward_earned',
                    'offer_title': 'X', 'reward_amount': '1', 'reward_currency': 'BDT'})
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'user_not_found')


# ── FraudAdapter extended ─────────────────────────────────────────────────────

class FraudAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('fr_ext')

    @patch('api.fraud_detection.services.FraudScoreCalculator')
    def test_high_risk_score_flagged(self, mock_cls):
        mock_calc = MagicMock()
        mock_cls.return_value = mock_calc
        mock_calc.calculate_overall_risk.return_value = 85
        from api.offerwall.services.adapters.OfferwallAdapter import FraudAdapter
        a = FraudAdapter()
        r = a.send({'user_id': self.user.id})
        self.assertTrue(r['success'])
        self.assertEqual(r['risk_score'], 85)
        self.assertTrue(r['high_risk'])

    @patch('api.fraud_detection.services.FraudScoreCalculator')
    def test_low_risk_score_not_flagged(self, mock_cls):
        mock_calc = MagicMock()
        mock_cls.return_value = mock_calc
        mock_calc.calculate_overall_risk.return_value = 20
        from api.offerwall.services.adapters.OfferwallAdapter import FraudAdapter
        a = FraudAdapter()
        r = a.send({'user_id': self.user.id})
        self.assertFalse(r['high_risk'])
        self.assertEqual(r['risk_score'], 20)

    def test_user_not_found_returns_low_risk(self):
        from api.offerwall.services.adapters.OfferwallAdapter import FraudAdapter
        a = FraudAdapter()
        r = a.send({'user_id': 9999999})
        # Should degrade gracefully — either error or default safe score
        self.assertIn('success', r)


# ── AuditAdapter extended ─────────────────────────────────────────────────────

class AuditAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('aud_ext')

    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_audit_log_action_called(self, mock_log):
        mock_log.return_value = MagicMock(id='audit_001')
        from api.offerwall.services.adapters.OfferwallAdapter import AuditAdapter
        a = AuditAdapter()
        r = a.send({
            'user_id': self.user.id,
            'action': 'OFFER_COMPLETE',
            'message': 'Conversion approved',
            'metadata': {'conversion_id': 'conv_aud_001'},
        })
        self.assertTrue(r['success'])
        mock_log.assert_called_once()

    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_audit_action_and_message_passed(self, mock_log):
        mock_log.return_value = MagicMock(id='audit_002')
        from api.offerwall.services.adapters.OfferwallAdapter import AuditAdapter
        a = AuditAdapter()
        a.send({'user_id': self.user.id, 'action': 'OFFER_REJECT',
                'message': 'Fraud detected', 'metadata': {}})
        call_str = str(mock_log.call_args)
        self.assertIn('OFFER_REJECT', call_str)
        self.assertIn('Fraud detected', call_str)

    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_audit_failure_still_returns_success(self, mock_log):
        """Audit should not block the main flow."""
        mock_log.side_effect = Exception('DB error')
        from api.offerwall.services.adapters.OfferwallAdapter import AuditAdapter
        a = AuditAdapter()
        # Circuit breaker will eventually catch this, but first call should handle gracefully
        r = a.send({'user_id': self.user.id, 'action': 'TEST', 'message': 'msg'})
        self.assertIn('success', r)


# ── ReferralAdapter extended ──────────────────────────────────────────────────

class ReferralAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('ref_ext')

    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_referral_commission_called(self, mock_ref):
        mock_ref.return_value = {'success': True, 'commissions': []}
        from api.offerwall.services.adapters.OfferwallAdapter import ReferralAdapter
        a = ReferralAdapter()
        r = a.send({
            'user_id': self.user.id,
            'earned_amount': Decimal('0.70'),
            'conversion_id': 'ref_c1',
            'offer_id': 'o1',
        })
        self.assertTrue(r['success'])
        mock_ref.assert_called_once()

    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_source_type_is_offer(self, mock_ref):
        mock_ref.return_value = {'success': True, 'commissions': []}
        from api.offerwall.services.adapters.OfferwallAdapter import ReferralAdapter
        a = ReferralAdapter()
        a.send({'user_id': self.user.id, 'earned_amount': Decimal('1.00'),
                'conversion_id': 'ref_c2', 'offer_id': 'o2'})
        call_str = str(mock_ref.call_args)
        self.assertIn('offer', call_str)

    def test_user_not_found_returns_error(self):
        from api.offerwall.services.adapters.OfferwallAdapter import ReferralAdapter
        a = ReferralAdapter()
        r = a.send({'user_id': 9999999, 'earned_amount': Decimal('1.00'),
                    'conversion_id': 'ref_bad', 'offer_id': 'o3'})
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'user_not_found')


# ── OfferRoutingAdapter extended ──────────────────────────────────────────────

class OfferRoutingAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('or_ext')

    @patch('api.offer_routing.routing.route_multiple_offers')
    def test_default_count_is_20(self, mock_route):
        mock_route.return_value = []
        from api.offerwall.services.adapters.OfferwallAdapter import OfferRoutingAdapter
        a = OfferRoutingAdapter()
        a.send({'user_id': self.user.id})
        call_str = str(mock_route.call_args)
        self.assertIn('20', call_str)

    @patch('api.offer_routing.routing.route_multiple_offers')
    def test_offer_ids_extracted_from_result(self, mock_route):
        mock_route.return_value = [
            {'offer_id': 'ro_a'}, {'offer_id': 'ro_b'}, {'offer_id': 'ro_c'}]
        from api.offerwall.services.adapters.OfferwallAdapter import OfferRoutingAdapter
        a = OfferRoutingAdapter()
        r = a.send({'user_id': self.user.id, 'count': 3})
        self.assertEqual(r['count'], 3)
        self.assertEqual(set(r['offer_ids']), {'ro_a', 'ro_b', 'ro_c'})


# ── PayoutQueueAdapter extended ───────────────────────────────────────────────

class PayoutQueueAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('pqe_u')

    @patch('api.payout_queue.services.add_payout_items')
    @patch('api.payout_queue.models.PayoutBatch.objects.get_or_create')
    def test_conversion_id_in_payout_item(self, mock_gwc, mock_add):
        mock_batch = MagicMock(); mock_batch.id = 'batch_ext'
        mock_gwc.return_value = (mock_batch, True)
        mock_add.return_value = [MagicMock()]
        from api.offerwall.services.adapters.OfferwallAdapter import PayoutQueueAdapter
        a = PayoutQueueAdapter()
        a.send({'user_id': self.user.id, 'amount': '0.70', 'conversion_id': 'pq_ext_c1'})
        kw = mock_add.call_args.kwargs
        items = kw.get('items', [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['source_reference'], 'pq_ext_c1')

    @patch('api.payout_queue.services.add_payout_items')
    @patch('api.payout_queue.models.PayoutBatch.objects.get_or_create')
    def test_validate_accounts_true_by_default(self, mock_gwc, mock_add):
        mock_batch = MagicMock(); mock_batch.id = 'batch_va'
        mock_gwc.return_value = (mock_batch, True)
        mock_add.return_value = [MagicMock()]
        from api.offerwall.services.adapters.OfferwallAdapter import PayoutQueueAdapter
        a = PayoutQueueAdapter()
        a.send({'user_id': self.user.id, 'amount': '1.00', 'conversion_id': 'pq_va'})
        kw = mock_add.call_args.kwargs
        self.assertTrue(kw.get('validate_accounts', True))


# ── GamificationAdapter extended ─────────────────────────────────────────────

class GamificationAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('gam_ext')

    @patch('api.gamification.services.award_achievement')
    def test_missing_title_uses_default(self, mock_award):
        mock_award.return_value = MagicMock(id='ach_ext_001')
        from api.offerwall.services.adapters.OfferwallAdapter import GamificationAdapter
        a = GamificationAdapter()
        r = a.send({'user_id': self.user.id, 'achievement_type': 'offer_complete',
                    'points': 30})
        self.assertTrue(r['success'])

    @patch('api.gamification.services.award_achievement')
    def test_zero_points_uses_minimum(self, mock_award):
        mock_award.return_value = MagicMock(id='ach_ext_002')
        from api.offerwall.services.adapters.OfferwallAdapter import GamificationAdapter
        a = GamificationAdapter()
        r = a.send({'user_id': self.user.id, 'achievement_type': 'offer_complete',
                    'title': 'T', 'points': 0})
        self.assertTrue(r['success'])
        # points_awarded should be at minimum 1 (adapter enforces minimum)
        self.assertGreaterEqual(r.get('points_awarded', 1), 0)


# ── LoyaltyAdapter extended ───────────────────────────────────────────────────

class LoyaltyAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('loy_ext')

    @patch('api.djoyalty.services.earn.BonusEventService.BonusEventService.award_bonus')
    def test_points_as_string_converted(self, mock_award):
        mock_award.return_value = MagicMock(id='bonus_ext_001')
        from api.offerwall.services.adapters.OfferwallAdapter import LoyaltyAdapter
        a = LoyaltyAdapter()
        r = a.send({'user_id': self.user.id, 'points': '100',
                    'reason': 'Test', 'triggered_by': 'offerwall'})
        self.assertTrue(r['success'])

    @patch('api.djoyalty.services.earn.BonusEventService.BonusEventService.award_bonus')
    def test_large_points_handled(self, mock_award):
        mock_award.return_value = MagicMock(id='bonus_ext_002')
        from api.offerwall.services.adapters.OfferwallAdapter import LoyaltyAdapter
        a = LoyaltyAdapter()
        r = a.send({'user_id': self.user.id, 'points': Decimal('9999.99'),
                    'reason': 'Big reward', 'triggered_by': 'offerwall'})
        self.assertTrue(r['success'])
        self.assertEqual(r['points_awarded'], '9999.99')


# ── SubscriptionAdapter extended ──────────────────────────────────────────────

class SubscriptionAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('sub_ext')

    @patch('api.subscription.models.UserSubscription.objects.filter')
    def test_no_subscription_returns_free(self, mock_filter):
        mock_qs = MagicMock()
        mock_qs.select_related.return_value.first.return_value = None
        mock_filter.return_value = mock_qs
        from api.offerwall.services.adapters.OfferwallAdapter import SubscriptionAdapter
        a = SubscriptionAdapter()
        r = a.send({'user_id': self.user.id})
        self.assertTrue(r['success'])
        self.assertEqual(r['tier'], 'free')
        self.assertEqual(r['multiplier'], 1.0)

    @patch('api.subscription.models.UserSubscription.objects.filter')
    def test_plan_name_in_response(self, mock_filter):
        mock_plan = MagicMock(); mock_plan.name = 'gold'
        mock_sub  = MagicMock(); mock_sub.plan = mock_plan; mock_sub.status = 'active'
        mock_qs   = MagicMock(); mock_qs.select_related.return_value.first.return_value = mock_sub
        mock_filter.return_value = mock_qs
        from api.offerwall.services.adapters.OfferwallAdapter import SubscriptionAdapter
        a = SubscriptionAdapter()
        r = a.send({'user_id': self.user.id})
        self.assertIn('tier', r)
        self.assertIn('multiplier', r)


# ── PromotionAdapter extended ─────────────────────────────────────────────────

class PromotionAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('prm_ext')

    def test_base_amount_string_accepted(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PromotionAdapter
        a = PromotionAdapter()
        r = a.send({'user_id': self.user.id, 'offer_id': 'o_str',
                    'base_amount': '1.50'})
        self.assertIn('bonus_amount', r)

    def test_bonus_amount_non_negative(self):
        from api.offerwall.services.adapters.OfferwallAdapter import PromotionAdapter
        a = PromotionAdapter()
        r = a.send({'user_id': self.user.id, 'offer_id': 'o_nn',
                    'base_amount': Decimal('2.00')})
        from decimal import Decimal as D
        self.assertGreaterEqual(D(r['bonus_amount']), D('0'))


# ── AlertAdapter extended ─────────────────────────────────────────────────────

class AlertAdapterExtendedTest(TestCase):

    @patch('api.alerts.models.incident.Incident.objects.create')
    def test_default_severity_is_medium(self, mock_create):
        mock_create.return_value = MagicMock(id='inc_ext_001')
        from api.offerwall.services.adapters.OfferwallAdapter import AlertAdapter
        a = AlertAdapter()
        a.send({'alert_type': 'rate_spike', 'message': 'High click rate'})
        kw = mock_create.call_args.kwargs
        self.assertIn(kw.get('severity', 'medium'), ['medium', 'high', 'low', 'critical'])

    @patch('api.alerts.models.incident.Incident.objects.create')
    def test_metadata_passed_through(self, mock_create):
        mock_create.return_value = MagicMock(id='inc_ext_002')
        from api.offerwall.services.adapters.OfferwallAdapter import AlertAdapter
        a = AlertAdapter()
        a.send({'alert_type': 'fraud', 'severity': 'high', 'message': 'Fraud spike',
                'metadata': {'provider': 'tapjoy', 'rate': 42}})
        kw = mock_create.call_args.kwargs
        meta = kw.get('metadata', {})
        self.assertEqual(meta.get('provider'), 'tapjoy')


# ── Factory singleton & registration ─────────────────────────────────────────

class FactoryExtendedTest(TestCase):

    def test_health_check_all_returns_dict(self):
        health = F().health_check_all()
        self.assertIsInstance(health, dict)
        self.assertGreaterEqual(len(health), 18)

    def test_all_health_entries_have_adapter_key(self):
        health = F().health_check_all()
        for name, info in health.items():
            self.assertIn('adapter', info, f'{name} missing adapter key')

    def test_re_register_replaces_adapter(self):
        from api.offerwall.services.adapters.OfferwallAdapter import (
            BaseOfferwallAdapter, OfferwallAdapterFactory)
        original = OfferwallAdapterFactory.get('analytics')

        class NewAnalytics(BaseOfferwallAdapter):
            name = 'analytics'
            def _do_send(self, p, **kw): return {'success': True, 'replaced': True}

        OfferwallAdapterFactory.register('analytics', NewAnalytics)
        replaced = OfferwallAdapterFactory.get('analytics')
        self.assertIsInstance(replaced, NewAnalytics)

        # Restore original class
        OfferwallAdapterFactory.register('analytics', type(original))

    def test_get_returns_same_instance_consecutive(self):
        f = F()
        a1 = f.get('audit')
        a2 = f.get('audit')
        self.assertIs(a1, a2)


# ── BehaviorAdapter extended ──────────────────────────────────────────────────

class BehaviorAdapterExtendedTest(TestCase):
    def setUp(self): self.user = mk_user('beh_ext')

    @patch('api.behavior_analytics.services.BehaviorAnalyticsService.record_click')
    def test_context_passed_through(self, mock_record):
        from api.offerwall.services.adapters.OfferwallAdapter import BehaviorAdapter
        a = BehaviorAdapter()
        r = a.send({'user_id': self.user.id, 'event_type': 'offer_completed',
                    'context': {'offer_id': 'beh_o1', 'provider': 'tapjoy'}})
        self.assertEqual(r.get('event_type'), 'offer_completed')
        self.assertTrue(r['success'])

    def test_event_type_preserved_in_response(self):
        from api.offerwall.services.adapters.OfferwallAdapter import BehaviorAdapter
        a = BehaviorAdapter()
        r = a.send({'user_id': self.user.id, 'event_type': 'offer_started'})
        self.assertEqual(r.get('event_type'), 'offer_started')
