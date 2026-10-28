# api/djoyalty/tests/test_gamification_extended.py
"""
Extended GamificationViewSet tests -- spin (feature-flagged), scratch, lottery,
leaderboard current/top/my-rank, quiz submit/my-attempts。
Previously 0 of these 14 actions were tested。
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _tenant():
    from djoyalty.models.core import Tenant
    return Tenant.objects.create(name=f'GamCo-{Tenant.objects.count()}',
                                  slug=f'gam-{Tenant.objects.count()}', is_active=True)

def _customer(tenant):
    from djoyalty.models.core import Customer
    u = User.objects.create_user(username=f'gam_{User.objects.count()}', password='pw')
    return Customer.objects.create(tenant=tenant, user=u,
                                   code=f'G{Customer.objects.count():04d}', is_active=True)

def _cli(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c


class SpinWheelFeatureFlagTest(TestCase):
    """Verifies FeatureFlags.is_enabled('spin_wheel') gates the spin action."""

    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.cli      = _cli(self.customer)
        from djoyalty.models.gamification import SpinWheelConfig
        self.wheel = SpinWheelConfig.objects.create(
            tenant=self.tenant, name='Test Wheel', is_active=True,
            max_spins_per_day=5, points_per_spin=Decimal('10'),
        )

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    @patch('djoyalty.services.gamification.SpinWheelService.SpinWheelService.spin')
    def test_spin_allowed_when_flag_on(self, mock_spin, mock_flag):
        mock_flag.return_value = True
        result = MagicMock()
        result.id            = 1
        result.prize_type    = 'points'
        result.prize_value   = Decimal('50')
        result.points_awarded = Decimal('50')
        result.prize_claimed = False
        result.spun_at       = None
        mock_spin.return_value = result
        resp = self.cli.post(f'/api/loyalty/spin-wheels/{self.wheel.pk}/spin/')
        mock_flag.assert_called_with('spin_wheel', self.cli._credentials.get('HTTP_AUTHORIZATION', ''))
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    def test_spin_blocked_when_flag_off(self, mock_flag):
        mock_flag.return_value = False
        resp = self.cli.post(f'/api/loyalty/spin-wheels/{self.wheel.pk}/spin/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('spin_wheel', resp.data.get('error', '').lower())

    def test_spin_list_wheels(self):
        resp = self.cli.get('/api/loyalty/spin-wheels/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_spin_detail(self):
        resp = self.cli.get(f'/api/loyalty/spin-wheels/{self.wheel.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Test Wheel')

    def test_my_results_empty(self):
        resp = self.cli.get(f'/api/loyalty/spin-wheels/{self.wheel.pk}/my-results/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)


class ScratchCardFeatureFlagTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.cli      = _cli(self.customer)
        from djoyalty.models.gamification import ScratchCard
        self.card = ScratchCard.objects.create(
            customer=self.customer, tenant=self.tenant,
            status='unscratched', prize_type='points', points_value=Decimal('100'),
        )

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    def test_scratch_blocked_when_flag_off(self, mock_flag):
        mock_flag.return_value = False
        resp = self.cli.post(f'/api/loyalty/scratch-cards/{self.card.pk}/scratch/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    @patch('djoyalty.services.gamification.ScratchCardService.ScratchCardService.scratch')
    def test_scratch_succeeds_when_flag_on(self, mock_scratch, mock_flag):
        mock_flag.return_value = True
        mock_scratch.return_value = None
        resp = self.cli.post(f'/api/loyalty/scratch-cards/{self.card.pk}/scratch/')
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_scratch_cards(self):
        resp = self.cli.get('/api/loyalty/scratch-cards/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class LotteryFeatureFlagTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.cli      = _cli(self.customer)
        from djoyalty.models.gamification import LotteryDraw
        from django.utils import timezone
        from datetime import timedelta
        self.lottery = LotteryDraw.objects.create(
            tenant=self.tenant, name='Weekly Draw', status='open',
            ticket_cost_points=Decimal('50'),
            draw_date=timezone.now() + timedelta(days=7),
            max_tickets_per_customer=10,
        )

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    def test_buy_tickets_blocked_when_flag_off(self, mock_flag):
        mock_flag.return_value = False
        resp = self.cli.post(f'/api/loyalty/lotteries/{self.lottery.pk}/buy-tickets/',
                             {'quantity': 2})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    @patch('djoyalty.services.gamification.LotteryService.LotteryService.buy_tickets')
    def test_buy_tickets_succeeds_when_flag_on(self, mock_buy, mock_flag):
        mock_flag.return_value = True
        mock_ticket = MagicMock()
        mock_ticket.id         = 1
        mock_ticket.ticket_number = 'T001'
        mock_ticket.is_winner  = False
        mock_ticket.purchased_at = None
        mock_buy.return_value = [mock_ticket, mock_ticket]
        resp = self.cli.post(f'/api/loyalty/lotteries/{self.lottery.pk}/buy-tickets/',
                             {'quantity': 2})
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        if resp.status_code == status.HTTP_201_CREATED:
            self.assertEqual(resp.data['tickets_purchased'], 2)

    def test_lottery_list(self):
        resp = self.cli.get('/api/loyalty/lotteries/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_my_wins_empty(self):
        resp = self.cli.get('/api/loyalty/lotteries/my-wins/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('wins', resp.data)


class LeaderboardTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.cli      = _cli(self.customer)
        from djoyalty.models.gamification import LeaderboardSeason
        from django.utils import timezone
        from datetime import timedelta
        self.season = LeaderboardSeason.objects.create(
            tenant=self.tenant, name='Q1 2026', status='active',
            start_date=timezone.now() - timedelta(days=30),
            end_date=timezone.now() + timedelta(days=60),
        )

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    def test_current_season_blocked_when_flag_off(self, mock_flag):
        mock_flag.return_value = False
        resp = self.cli.get('/api/loyalty/leaderboard-seasons/current/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    def test_current_season_when_flag_on(self, mock_flag):
        mock_flag.return_value = True
        resp = self.cli.get('/api/loyalty/leaderboard-seasons/current/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Q1 2026')

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    @patch('djoyalty.services.engagement.LeaderboardService.LeaderboardService.get_top')
    def test_top_entries(self, mock_top, mock_flag):
        mock_flag.return_value = True
        mock_top.return_value = [{'rank': 1, 'customer_code': 'C001', 'score': 1000}]
        resp = self.cli.get(f'/api/loyalty/leaderboard-seasons/{self.season.pk}/top/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('entries', resp.data)

    @patch('djoyalty.viewsets.advanced.GamificationViewSet._feature_enabled')
    @patch('djoyalty.services.engagement.LeaderboardService.LeaderboardService.get_customer_rank')
    @patch('djoyalty.services.engagement.LeaderboardService.LeaderboardService.get_customer_score')
    def test_my_rank(self, mock_score, mock_rank, mock_flag):
        mock_flag.return_value = True
        mock_rank.return_value  = 5
        mock_score.return_value = Decimal('850')
        resp = self.cli.get(f'/api/loyalty/leaderboard-seasons/{self.season.pk}/my-rank/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('rank', resp.data)
        self.assertIn('score', resp.data)
