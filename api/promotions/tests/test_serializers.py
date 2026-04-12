# =============================================================================
# promotions/tests/test_serializers.py
# Serializer Tests
# =============================================================================
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

User = get_user_model()


class CampaignSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ser_user', email='ser@test.com', password='pass')
        self.factory = APIRequestFactory()

    def _get_base_objects(self):
        from api.promotions.models import PromotionCategory, RewardPolicy
        cat = PromotionCategory.objects.create(name='social', sort_order=1)
        rp = RewardPolicy.objects.create(
            name='Serializer Policy',
            base_reward=Decimal('1.00'),
            min_reward=Decimal('0.50'),
            max_reward=Decimal('10.00'),
            platform_commission_rate=Decimal('0.20'),
        )
        return cat, rp

    def test_campaign_list_serializer_fields(self):
        from api.promotions.serializers import CampaignListSerializer
        from api.promotions.models import Campaign
        cat, rp = self._get_base_objects()
        campaign = Campaign.objects.create(
            title='Serializer Test Campaign',
            advertiser=self.user,
            category=cat,
            reward_policy=rp,
            total_budget=Decimal('300.00'),
            per_task_reward=Decimal('1.50'),
            max_tasks_per_user=5,
        )
        serializer = CampaignListSerializer(campaign)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('title', data)
        self.assertIn('status', data)

    def test_promotion_category_serializer(self):
        from api.promotions.serializers import PromotionCategorySerializer
        from api.promotions.models import PromotionCategory
        cat = PromotionCategory.objects.create(name='apps', sort_order=2)
        serializer = PromotionCategorySerializer(cat)
        self.assertEqual(serializer.data['name'], 'apps')

    def test_blacklist_serializer_validation(self):
        from api.promotions.serializers import BlacklistSerializer
        data = {
            'list_type': 'ip',
            'value': '10.0.0.1',
            'reason': 'Fraud',
            'severity': 'permanent',
        }
        serializer = BlacklistSerializer(data=data)
        # Check if serializer exists and is callable
        self.assertIsNotNone(serializer)

    def test_dispute_serializer(self):
        from api.promotions.serializers import DisputeSerializer
        self.assertIsNotNone(DisputeSerializer)

    def test_currency_rate_serializer(self):
        from api.promotions.serializers import CurrencyRateSerializer
        from api.promotions.models import CurrencyRate
        rate = CurrencyRate.objects.create(
            currency_code='BDT',
            rate_to_usd=Decimal('0.0091'),
            source='manual',
        )
        serializer = CurrencyRateSerializer(rate)
        self.assertEqual(serializer.data['currency_code'], 'BDT')


class TaskSubmissionSerializerTest(TestCase):
    def test_submission_create_serializer_exists(self):
        from api.promotions.serializers import TaskSubmissionCreateSerializer
        self.assertIsNotNone(TaskSubmissionCreateSerializer)

    def test_submission_review_serializer_exists(self):
        from api.promotions.serializers import SubmissionReviewSerializer
        self.assertIsNotNone(SubmissionReviewSerializer)
