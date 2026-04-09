# api/djoyalty/tests/test_earn_rules.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_earn_rule, make_tier


class EarnRuleEngineTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='EARNCUST01')
        self.rule = make_earn_rule(
            name='Purchase Rule',
            rule_type='percentage',
            trigger='purchase',
            points_value=Decimal('1'),
            multiplier=Decimal('1'),
            min_spend=Decimal('0'),
            is_active=True,
            priority=10,
        )

    def test_get_applicable_rules_returns_active_rules(self):
        from djoyalty.services.earn.EarnRuleEngine import EarnRuleEngine
        rules = EarnRuleEngine.get_applicable_rules(self.customer, 'purchase')
        self.assertGreaterEqual(len(rules), 1)

    def test_get_applicable_rules_inactive_excluded(self):
        from djoyalty.services.earn.EarnRuleEngine import EarnRuleEngine
        self.rule.is_active = False
        self.rule.save()
        rules = EarnRuleEngine.get_applicable_rules(self.customer, 'purchase')
        rule_ids = [r.id for r in rules]
        self.assertNotIn(self.rule.id, rule_ids)

    def test_calculate_points_percentage_rule(self):
        from djoyalty.services.earn.EarnRuleEngine import EarnRuleEngine
        points = EarnRuleEngine.calculate_points(self.customer, Decimal('100'), 'purchase')
        self.assertGreaterEqual(points, Decimal('0'))

    def test_calculate_points_min_spend_not_met(self):
        from djoyalty.services.earn.EarnRuleEngine import EarnRuleEngine
        self.rule.min_spend = Decimal('500')
        self.rule.save()
        points = EarnRuleEngine.calculate_points(self.customer, Decimal('10'), 'purchase')
        self.assertEqual(points, Decimal('0'))

    def test_calculate_points_wrong_trigger(self):
        from djoyalty.services.earn.EarnRuleEngine import EarnRuleEngine
        points = EarnRuleEngine.calculate_points(self.customer, Decimal('100'), 'birthday')
        self.assertEqual(points, Decimal('0'))


class BonusEventServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='BONCUST01')

    def test_award_bonus_creates_record(self):
        from djoyalty.services.earn.BonusEventService import BonusEventService
        from djoyalty.models.earn_rules import BonusEvent
        BonusEventService.award_bonus(self.customer, Decimal('100'), 'Test bonus')
        self.assertTrue(BonusEvent.objects.filter(customer=self.customer, reason='Test bonus').exists())

    def test_award_bonus_updates_balance(self):
        from djoyalty.services.earn.BonusEventService import BonusEventService
        from djoyalty.models.points import LoyaltyPoints
        BonusEventService.award_bonus(self.customer, Decimal('150'), 'Welcome')
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertEqual(lp.balance, Decimal('150'))

    def test_award_bonus_creates_ledger(self):
        from djoyalty.services.earn.BonusEventService import BonusEventService
        from djoyalty.models.points import PointsLedger
        BonusEventService.award_bonus(self.customer, Decimal('50'), 'Bonus test')
        self.assertTrue(PointsLedger.objects.filter(customer=self.customer, source='bonus').exists())
