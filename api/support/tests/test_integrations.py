# api/support/tests/test_integrations.py
"""Tests for integration adapters."""
from django.test import TestCase
from unittest.mock import patch, MagicMock


def make_user(username='integ_u'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username=username, email=f'{username}@t.com', password='p')


class WalletAdapterTest(TestCase):
    def test_get_balance_returns_dict(self):
        from api.support.integrations.integ_adapter import WalletAdapter
        adapter = WalletAdapter()
        user    = make_user('wallet_a')
        result  = adapter.get_balance(user)
        self.assertIsInstance(result, dict)
        self.assertIn('available', result)

    def test_get_balance_handles_missing_wallet(self):
        from api.support.integrations.integ_adapter import WalletAdapter
        adapter = WalletAdapter()
        user    = make_user('no_wallet')
        result  = adapter.get_balance(user)
        # Should not crash — returns empty dict
        self.assertEqual(result.get('available', 0), 0)


class FraudAdapterTest(TestCase):
    def test_get_risk_score_returns_dict(self):
        from api.support.integrations.integ_adapter import FraudAdapter
        adapter = FraudAdapter()
        user    = make_user('fraud_a')
        result  = adapter.get_risk_score(user)
        self.assertIsInstance(result, dict)
        self.assertIn('score', result)
        self.assertIn('is_flagged', result)

    def test_is_safe_to_auto_approve_low_risk(self):
        from api.support.integrations.integ_adapter import FraudAdapter
        from decimal import Decimal
        adapter = FraudAdapter()
        user    = make_user('safe_u')
        # No fraud profile — defaults to safe
        safe, reason = adapter.is_safe_to_auto_approve(user, Decimal('50'))
        self.assertTrue(safe)


class PostbackAdapterTest(TestCase):
    def test_verify_missing_postback(self):
        from api.support.integrations.integ_adapter import PostbackAdapter
        adapter = PostbackAdapter()
        user    = make_user('pb_u')
        result  = adapter.verify_offer_completion(user, 'OFF_NONE', '')
        self.assertFalse(result['found'])
        self.assertIsInstance(result['confidence'], float)


class EventBusTest(TestCase):
    def test_subscribe_and_publish(self):
        from api.support.integrations.event_bus import SupportEventBus
        bus     = SupportEventBus()
        results = []

        @bus.on('test.event')
        def handler(event_type, **data):
            results.append(data.get('value'))

        bus.publish('test.event', value='hello')
        self.assertIn('hello', results)

    def test_multiple_handlers(self):
        from api.support.integrations.event_bus import SupportEventBus
        bus   = SupportEventBus()
        calls = []
        bus.subscribe('multi.test', lambda **kw: calls.append(1))
        bus.subscribe('multi.test', lambda **kw: calls.append(2))
        bus.publish('multi.test')
        self.assertEqual(len(calls), 2)


class HealthCheckerTest(TestCase):
    def test_check_database(self):
        from api.support.integrations.health_check import health_checker
        ok, msg = health_checker.check_database()
        self.assertTrue(ok)

    def test_health_summary_structure(self):
        from api.support.integrations.health_check import health_checker
        summary = health_checker.get_health_summary()
        self.assertIn('status', summary)
        self.assertIn('healthy', summary)
        self.assertIn('unhealthy', summary)