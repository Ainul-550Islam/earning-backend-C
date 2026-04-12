# =============================================================================
# promotions/tests/test_models.py
# Model Unit Tests — Full Coverage
# =============================================================================
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock

User = get_user_model()


class PromotionCategoryModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='pass123'
        )

    def test_category_creation(self):
        from api.promotions.models import PromotionCategory
        cat = PromotionCategory.objects.create(name='social', sort_order=1)
        self.assertEqual(str(cat.name), 'social')
        self.assertTrue(cat.is_active)
        self.assertFalse(cat.is_deleted)

    def test_category_soft_delete(self):
        from api.promotions.models import PromotionCategory
        cat = PromotionCategory.objects.create(name='apps', sort_order=2)
        cat.delete(deleted_by=self.user)
        self.assertTrue(cat.is_deleted)
        self.assertIsNotNone(cat.deleted_at)
        # Soft deleted should not appear in default manager
        self.assertEqual(PromotionCategory.objects.filter(name='apps').count(), 0)
        self.assertEqual(PromotionCategory.all_objects.filter(name='apps').count(), 1)

    def test_platform_creation(self):
        from api.promotions.models import Platform
        p = Platform.objects.create(name='youtube', display_name='YouTube')
        self.assertEqual(p.name, 'youtube')
        self.assertTrue(p.is_active)

    def test_reward_policy_validation(self):
        from api.promotions.models import RewardPolicy
        rp = RewardPolicy(
            name='Basic Policy',
            base_reward=Decimal('0.50'),
            min_reward=Decimal('0.10'),
            max_reward=Decimal('10.00'),
            platform_commission_rate=Decimal('0.20'),
        )
        rp.full_clean()  # Should not raise

    def test_campaign_budget_constraint(self):
        from api.promotions.models import Campaign, PromotionCategory, RewardPolicy
        cat = PromotionCategory.objects.create(name='web', sort_order=3)
        rp = RewardPolicy.objects.create(
            name='Test Policy',
            base_reward=Decimal('1.00'),
            min_reward=Decimal('0.50'),
            max_reward=Decimal('5.00'),
            platform_commission_rate=Decimal('0.15'),
        )
        campaign = Campaign(
            title='Test Campaign',
            advertiser=self.user,
            category=cat,
            reward_policy=rp,
            total_budget=Decimal('100.00'),
            per_task_reward=Decimal('1.00'),
            max_tasks_per_user=5,
        )
        campaign.full_clean()
        campaign.save()
        self.assertEqual(campaign.status, 'draft')

    def test_submission_status_transitions(self):
        from api.promotions.models import Campaign, TaskSubmission, PromotionCategory, RewardPolicy
        cat = PromotionCategory.objects.create(name='surveys', sort_order=4)
        rp = RewardPolicy.objects.create(
            name='Survey Policy',
            base_reward=Decimal('0.75'),
            min_reward=Decimal('0.25'),
            max_reward=Decimal('3.00'),
            platform_commission_rate=Decimal('0.20'),
        )
        campaign = Campaign.objects.create(
            title='Survey Campaign',
            advertiser=self.user,
            category=cat,
            reward_policy=rp,
            total_budget=Decimal('500.00'),
            per_task_reward=Decimal('0.75'),
            max_tasks_per_user=1,
        )
        sub = TaskSubmission.objects.create(
            campaign=campaign,
            user=self.user,
            proof_type='screenshot',
        )
        self.assertEqual(sub.status, 'pending')

    def test_escrow_wallet_creation(self):
        from api.promotions.models import EscrowWallet, Campaign, PromotionCategory, RewardPolicy
        cat = PromotionCategory.objects.create(name='social')
        rp = RewardPolicy.objects.create(
            name='Escrow Policy',
            base_reward=Decimal('1.00'),
            min_reward=Decimal('0.50'),
            max_reward=Decimal('10.00'),
            platform_commission_rate=Decimal('0.20'),
        )
        campaign = Campaign.objects.create(
            title='Escrow Test',
            advertiser=self.user,
            category=cat,
            reward_policy=rp,
            total_budget=Decimal('200.00'),
            per_task_reward=Decimal('1.00'),
            max_tasks_per_user=10,
        )
        escrow = EscrowWallet.objects.create(
            campaign=campaign,
            locked_amount=Decimal('200.00'),
            released_amount=Decimal('0.00'),
        )
        self.assertEqual(escrow.status, 'locked')
        self.assertEqual(escrow.available_amount, Decimal('200.00'))

    def test_blacklist_creation(self):
        from api.promotions.models import Blacklist
        bl = Blacklist.objects.create(
            list_type='ip',
            value='192.168.1.100',
            reason='Fraud detected',
            severity='permanent',
            created_by=self.user,
        )
        self.assertEqual(bl.list_type, 'ip')
        self.assertEqual(bl.severity, 'permanent')

    def test_user_reputation_defaults(self):
        from api.promotions.models import UserReputation
        rep = UserReputation.objects.create(user=self.user)
        self.assertEqual(rep.trust_score, Decimal('100.00'))
        self.assertEqual(rep.total_submissions, 0)
        self.assertEqual(rep.approved_count, 0)


class CampaignAnalyticsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='adv', email='adv@x.com', password='p')

    def test_analytics_aggregation(self):
        from api.promotions.models import CampaignAnalytics, Campaign, PromotionCategory, RewardPolicy
        cat = PromotionCategory.objects.create(name='apps')
        rp = RewardPolicy.objects.create(
            name='App Policy',
            base_reward=Decimal('2.00'),
            min_reward=Decimal('1.00'),
            max_reward=Decimal('20.00'),
            platform_commission_rate=Decimal('0.25'),
        )
        campaign = Campaign.objects.create(
            title='App Campaign',
            advertiser=self.user,
            category=cat,
            reward_policy=rp,
            total_budget=Decimal('1000.00'),
            per_task_reward=Decimal('2.00'),
            max_tasks_per_user=3,
        )
        analytics = CampaignAnalytics.objects.create(
            campaign=campaign,
            date=timezone.now().date(),
            impressions=1000,
            clicks=150,
            conversions=25,
            revenue=Decimal('50.00'),
            spend=Decimal('37.50'),
        )
        self.assertEqual(analytics.ctr, Decimal('15.00'))
        self.assertEqual(analytics.cvr, Decimal('16.67'))
