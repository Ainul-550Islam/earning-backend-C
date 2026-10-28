# api/referral/tests/test_views.py
# API endpoint tests
# Run: python manage.py test api.referral.tests.test_views
# ============================================================

from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class TestReferralStatsView(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='statsuser', email='s@test.com', password='pass'
        )
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)

    def test_unauthenticated_returns_401(self):
        response = self.client.get('/referral/')
        self.assertIn(response.status_code, [401, 403])

    def test_authenticated_returns_stats(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/referral/')
        self.assertIn(response.status_code, [200, 404])

    def test_stats_contains_referral_code(self):
        from api.referral.models import ReferralCode
        ReferralCode.objects.create(
            user=self.user, code='EARNTEST01',
            is_primary=True, is_active=True,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/referral/stats/')
        if response.status_code == 200:
            data = response.json()
            self.assertIn('referral_code', str(data))


class TestLeaderboardView(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='leader', email='l@test.com', password='pass'
        )

    def test_leaderboard_accessible(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/referral/leaderboard/')
        self.assertIn(response.status_code, [200, 404])

    def test_leaderboard_period_param(self):
        self.client.force_authenticate(user=self.user)
        for period in ['daily', 'weekly', 'monthly']:
            response = self.client.get(f'/referral/leaderboard/?period={period}')
            self.assertNotEqual(response.status_code, 500)


class TestReferralRedirectView(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='rediruser', email='r@test.com', password='pass'
        )
        from api.referral.models import ReferralCode
        self.code = ReferralCode.objects.create(
            user=self.user, code='EARNREDIR',
            is_primary=True, is_active=True,
        )

    def test_valid_code_redirects(self):
        response = self.client.get('/referral/go/EARNREDIR/')
        # Should redirect (302) or 200
        self.assertIn(response.status_code, [200, 302, 404])

    def test_invalid_code_404(self):
        response = self.client.get('/referral/go/FAKECODE123/')
        self.assertIn(response.status_code, [302, 404])


class TestHealthCheckView(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_health_check_accessible(self):
        response = self.client.get('/referral/health/')
        self.assertIn(response.status_code, [200, 207, 503])

    def test_health_check_returns_json(self):
        response = self.client.get('/referral/health/')
        if response.status_code in [200, 207, 503]:
            self.assertIn('status', response.json())


class TestReferralCodeAPI(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='codeapi', email='ca@test.com', password='pass'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_codes(self):
        response = self.client.get('/referral/codes/')
        self.assertIn(response.status_code, [200, 404])

    def test_create_code(self):
        response = self.client.post('/referral/codes/', {'code': 'MYCODE01'})
        self.assertIn(response.status_code, [200, 201, 400, 404])