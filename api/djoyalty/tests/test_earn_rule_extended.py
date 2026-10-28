# api/djoyalty/tests/test_earn_rule_extended.py
"""
Extended EarnRuleViewSet tests -- conditions, tier_multipliers,
earn_transactions, rule_log。 All 4 actions: previously 0 tested。
"""
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _setup():
    from djoyalty.models.core import Tenant
    from djoyalty.models.earn_rules import EarnRule
    from djoyalty.models.tiers import LoyaltyTier
    t    = Tenant.objects.create(name=f'ERCo-{Tenant.objects.count()}',
                                  slug=f'er-{Tenant.objects.count()}', is_active=True)
    rule = EarnRule.objects.create(
        tenant=t, name='Purchase Rule', trigger='purchase',
        earn_type='points_per_currency', earn_value=Decimal('1.0'),
        is_active=True,
    )
    tier = LoyaltyTier.objects.create(tenant=t, name='Gold', rank=3,
                                       min_points=1000, is_active=True)
    return t, rule, tier

def _admin():
    u = User.objects.create_user(username=f'era_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c


class EarnRuleConditionTest(TestCase):
    def setUp(self):
        self.tenant, self.rule, self.tier = _setup()
        self.admin = _admin()

    def test_list_conditions_empty(self):
        resp = self.admin.get(f'/api/loyalty/earn-rules/{self.rule.pk}/conditions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    def test_create_condition(self):
        resp = self.admin.post(f'/api/loyalty/earn-rules/{self.rule.pk}/conditions/', {
            'condition_type': 'min_cart_value',
            'operator':       'gte',
            'value':          '500',
            'is_active':      True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['condition_type'], 'min_cart_value')
        self.assertEqual(resp.data['operator'], 'gte')

    def test_conditions_requires_admin(self):
        u   = User.objects.create_user(username=f'erp_{User.objects.count()}', password='pw')
        cli = APIClient(); cli.force_authenticate(user=u)
        resp = cli.get(f'/api/loyalty/earn-rules/{self.rule.pk}/conditions/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class EarnRuleTierMultiplierTest(TestCase):
    def setUp(self):
        self.tenant, self.rule, self.tier = _setup()
        self.admin = _admin()

    def test_list_tier_multipliers_empty(self):
        resp = self.admin.get(f'/api/loyalty/earn-rules/{self.rule.pk}/tier-multipliers/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    def test_create_tier_multiplier(self):
        resp = self.admin.post(f'/api/loyalty/earn-rules/{self.rule.pk}/tier-multipliers/', {
            'tier_id':    self.tier.pk,
            'multiplier': '2.5',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['tier_id'], self.tier.pk)
        self.assertEqual(resp.data['multiplier'], '2.5')

    def test_update_existing_multiplier(self):
        """Creating same tier_id again should update, not duplicate."""
        self.admin.post(f'/api/loyalty/earn-rules/{self.rule.pk}/tier-multipliers/',
                        {'tier_id': self.tier.pk, 'multiplier': '2.0'})
        resp = self.admin.post(f'/api/loyalty/earn-rules/{self.rule.pk}/tier-multipliers/',
                               {'tier_id': self.tier.pk, 'multiplier': '3.0'})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        from djoyalty.models.earn_rules import EarnRuleTierMultiplier
        self.assertEqual(
            EarnRuleTierMultiplier.objects.filter(earn_rule=self.rule, tier=self.tier).count(), 1
        )


class EarnTransactionLogTest(TestCase):
    def setUp(self):
        self.tenant, self.rule, self.tier = _setup()
        self.admin = _admin()

    def test_earn_transactions_returns_list(self):
        resp = self.admin.get('/api/loyalty/earn-rules/earn-transactions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_earn_transactions_filter_by_customer(self):
        resp = self.admin.get('/api/loyalty/earn-rules/earn-transactions/?customer_id=1')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_earn_transactions_filter_by_rule(self):
        resp = self.admin.get(f'/api/loyalty/earn-rules/earn-transactions/?rule_id={self.rule.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_rule_log_returns_list(self):
        resp = self.admin.get('/api/loyalty/earn-rules/rule-log/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_earn_transactions_requires_admin(self):
        u   = User.objects.create_user(username=f'ernp_{User.objects.count()}', password='pw')
        cli = APIClient(); cli.force_authenticate(user=u)
        resp = cli.get('/api/loyalty/earn-rules/earn-transactions/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
