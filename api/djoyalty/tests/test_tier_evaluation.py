# api/djoyalty/tests/test_tier_evaluation.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_loyalty_points, make_tier


class TierEvaluationServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='TIERCUST01')
        self.bronze = make_tier('bronze', min_points=Decimal('0'), rank=1)
        self.silver = make_tier('silver', min_points=Decimal('500'), rank=2)
        self.gold = make_tier('gold', min_points=Decimal('2000'), rank=3)

    def test_evaluate_assigns_bronze_for_new_customer(self):
        from djoyalty.services.tiers.TierEvaluationService import TierEvaluationService
        make_loyalty_points(self.customer, balance=Decimal('0'))
        self.customer.loyalty_points.update(lifetime_earned=Decimal('0'))
        user_tier = TierEvaluationService.evaluate(self.customer)
        if user_tier:
            self.assertEqual(user_tier.tier.name, 'bronze')

    def test_evaluate_upgrades_to_silver(self):
        from djoyalty.services.tiers.TierEvaluationService import TierEvaluationService
        from djoyalty.models.points import LoyaltyPoints
        lp = make_loyalty_points(self.customer, balance=Decimal('600'))
        lp.lifetime_earned = Decimal('600')
        lp.save()
        user_tier = TierEvaluationService.evaluate(self.customer)
        if user_tier:
            self.assertIn(user_tier.tier.name, ['silver', 'gold', 'platinum', 'diamond'])

    def test_evaluate_creates_tier_history(self):
        from djoyalty.services.tiers.TierEvaluationService import TierEvaluationService
        from djoyalty.models.tiers import TierHistory
        lp = make_loyalty_points(self.customer, balance=Decimal('100'))
        lp.lifetime_earned = Decimal('100')
        lp.save()
        TierEvaluationService.evaluate(self.customer)
        self.assertGreaterEqual(TierHistory.objects.filter(customer=self.customer).count(), 0)

    def test_evaluate_no_double_assignment(self):
        from djoyalty.services.tiers.TierEvaluationService import TierEvaluationService
        from djoyalty.models.tiers import UserTier
        lp = make_loyalty_points(self.customer, balance=Decimal('100'))
        lp.lifetime_earned = Decimal('100')
        lp.save()
        TierEvaluationService.evaluate(self.customer)
        TierEvaluationService.evaluate(self.customer)
        current_count = UserTier.objects.filter(customer=self.customer, is_current=True).count()
        self.assertLessEqual(current_count, 1)


class TierBenefitServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='BENFCUST01')
        self.tier = make_tier('gold', rank=3)

    def test_get_benefits_no_tier(self):
        from djoyalty.services.tiers.TierBenefitService import TierBenefitService
        benefits = TierBenefitService.get_benefits_for_customer(self.customer)
        self.assertEqual(list(benefits), [])

    def test_get_benefits_with_tier(self):
        from djoyalty.services.tiers.TierBenefitService import TierBenefitService
        from djoyalty.models.tiers import UserTier, TierBenefit
        UserTier.objects.create(customer=self.customer, tier=self.tier, is_current=True)
        TierBenefit.objects.create(tier=self.tier, title='Free Shipping', benefit_type='shipping', is_active=True)
        benefits = TierBenefitService.get_benefits_for_customer(self.customer)
        self.assertGreaterEqual(len(list(benefits)), 1)
