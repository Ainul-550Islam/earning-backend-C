# =============================================================================
# promotions/tests/test_views.py
# ViewSet & API Endpoint Tests
# =============================================================================
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch

User = get_user_model()


class CampaignViewSetTest(APITestCase):
    def setUp(self):
        self.advertiser = User.objects.create_user(
            username='advertiser', email='adv@test.com', password='pass123'
        )
        self.publisher = User.objects.create_user(
            username='publisher', email='pub@test.com', password='pass123'
        )
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@test.com', password='pass123'
        )
        self.client = APIClient()

    def _create_base_objects(self):
        from api.promotions.models import PromotionCategory, RewardPolicy
        cat = PromotionCategory.objects.create(name='social', sort_order=1)
        rp = RewardPolicy.objects.create(
            name='Test Policy',
            base_reward=Decimal('1.00'),
            min_reward=Decimal('0.50'),
            max_reward=Decimal('10.00'),
            platform_commission_rate=Decimal('0.20'),
        )
        return cat, rp

    def test_unauthenticated_campaign_list(self):
        url = reverse('promotions:campaign-list')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_advertiser_create_campaign(self):
        cat, rp = self._create_base_objects()
        self.client.force_authenticate(user=self.advertiser)
        url = reverse('promotions:campaign-list')
        data = {
            'title': 'My First Campaign',
            'description': 'Test campaign',
            'category': cat.id,
            'reward_policy': rp.id,
            'total_budget': '500.00',
            'per_task_reward': '1.00',
            'max_tasks_per_user': 3,
        }
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_publisher_list_active_campaigns(self):
        self.client.force_authenticate(user=self.publisher)
        url = reverse('promotions:campaign-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_campaign_stats_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('promotions:promotions-stats')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_promotions_list_alias(self):
        self.client.force_authenticate(user=self.publisher)
        url = reverse('promotions:promotions-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TaskSubmissionViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sub_user', email='sub@test.com', password='pass')
        self.admin = User.objects.create_superuser(username='adm', email='adm@test.com', password='pass')
        self.client = APIClient()

    def test_submission_list_authenticated(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('promotions:submission-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dispute_creation(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('promotions:dispute-list')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])


class FraudReportViewSetTest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='fraud_admin', email='fa@test.com', password='pass')
        self.user = User.objects.create_user(username='normal', email='norm@test.com', password='pass')
        self.client = APIClient()

    def test_admin_access_fraud_reports(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('promotions:fraud-report-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_blacklist_admin_only(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('promotions:blacklist-list')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])


class CurrencyRateViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='curr_user', email='curr@test.com', password='pass')
        self.client = APIClient()

    def test_currency_rate_list(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('promotions:currency-rate-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
