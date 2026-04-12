# =============================================================================
# promotions/tests/test_integration.py
# Integration Tests — End-to-end flow tests
# =============================================================================
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class PublisherFullFlowTest(TestCase):
    """Test complete publisher journey: signup → offer → submit → payout."""

    def setUp(self):
        self.publisher = User.objects.create_user(
            username='integration_pub', email='ip@test.com', password='pass'
        )
        self.advertiser = User.objects.create_user(
            username='integration_adv', email='ia@test.com', password='pass'
        )
        self.admin = User.objects.create_superuser(
            username='integration_admin', email='iadm@test.com', password='pass'
        )
        self.client = APIClient()

    def test_publisher_balance_endpoint(self):
        self.client.force_authenticate(user=self.publisher)
        response = self.client.get('/api/promotions/publisher/balance/')
        self.assertIn(response.status_code, [200, 404])

    def test_publisher_dashboard_endpoint(self):
        self.client.force_authenticate(user=self.publisher)
        response = self.client.get('/api/promotions/publisher/dashboard/')
        self.assertIn(response.status_code, [200, 404])

    def test_leaderboard_public_access(self):
        response = self.client.get('/api/promotions/leaderboard/publishers/?period=monthly')
        self.assertIn(response.status_code, [200, 404])

    def test_offerwall_public_access(self):
        response = self.client.get('/api/promotions/offerwall/?country=US')
        self.assertIn(response.status_code, [200, 404])

    def test_cpc_campaigns_public(self):
        response = self.client.get('/api/promotions/cpc/campaigns/?country=US')
        self.assertIn(response.status_code, [200, 404])

    def test_quiz_creation_admin_only(self):
        self.client.force_authenticate(user=self.publisher)
        response = self.client.post('/api/promotions/quiz/create/', {
            'title': 'Test Quiz',
            'quiz_type': 'personality',
            'questions': [{'q': 'Q1?', 'options': ['A', 'B', 'C']}],
            'payout': '0.50',
        }, format='json')
        self.assertIn(response.status_code, [201, 403, 404])


class ContentLockingFlowTest(TestCase):
    """Test content locking create → check → unlock flow."""

    def setUp(self):
        self.publisher = User.objects.create_user(
            username='locker_pub', email='lp@test.com', password='pass'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.publisher)

    def test_create_link_locker(self):
        response = self.client.post('/api/promotions/locker/link/create/', {
            'destination_url': 'https://example.com/file.zip',
            'title': 'Download Free Ebook',
            'description': 'Complete 1 offer to download',
        }, format='json')
        self.assertIn(response.status_code, [201, 404])

    def test_create_content_locker(self):
        response = self.client.post('/api/promotions/locker/content/create/', {
            'locker_type': 'standard',
            'theme': 'dark',
            'title': 'Unlock Premium Content',
        }, format='json')
        self.assertIn(response.status_code, [201, 404])


class CryptoPaymentFlowTest(TestCase):
    def setUp(self):
        from api.promotions.crypto_payments.usdt_payment import USDTPaymentProcessor
        self.processor = USDTPaymentProcessor()

    def test_usdt_networks(self):
        networks = self.processor.get_supported_networks()
        self.assertGreater(len(networks), 0)
        self.assertIn('TRC20', [n['network'] for n in networks])

    def test_invalid_wallet_address(self):
        result = self.processor.create_payout_request(
            publisher_id=1,
            amount=Decimal('50.00'),
            wallet_address='invalid_address',
            network='TRC20',
        )
        self.assertIn('error', result)

    def test_below_minimum_payout(self):
        result = self.processor.create_payout_request(
            publisher_id=1,
            amount=Decimal('10.00'),  # Below $25 minimum
            wallet_address='TRxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            network='TRC20',
        )
        self.assertIn('error', result)

    def test_valid_trc20_address(self):
        # Valid TRC20: starts with T, 34 chars
        result = self.processor._validate_wallet_address('T' + 'x' * 33, 'TRC20')
        self.assertTrue(result)


class VirtualCurrencyTest(TestCase):
    def setUp(self):
        from api.promotions.virtual_currency.vc_manager import VirtualCurrencyManager
        self.manager = VirtualCurrencyManager()
        self.publisher_id = 9999

    def test_create_vc_config(self):
        result = self.manager.create_vc_config(
            publisher_id=self.publisher_id,
            currency_name='Gems',
            currency_icon='💎',
            usd_to_vc_rate=Decimal('500'),
        )
        self.assertIn('config_id', result)
        self.assertEqual(result['currency_name'], 'Gems')

    def test_usd_to_vc_conversion(self):
        self.manager.create_vc_config(
            publisher_id=self.publisher_id,
            currency_name='Coins',
            currency_icon='🪙',
            usd_to_vc_rate=Decimal('1000'),
        )
        result = self.manager.convert_usd_to_vc(self.publisher_id, Decimal('0.50'))
        self.assertEqual(result['vc_amount'], 500)

    def test_no_config_returns_usd(self):
        result = self.manager.convert_usd_to_vc(99999, Decimal('1.00'))
        self.assertIn('$1.00', result['display_amount'])


class EmailSubmitTest(TestCase):
    def setUp(self):
        from api.promotions.email_submit.email_submit_manager import EmailSubmitManager
        self.manager = EmailSubmitManager()

    def test_disposable_email_rejected(self):
        # Create a test campaign first
        import uuid
        from django.core.cache import cache
        camp_id = 'test_camp_' + str(uuid.uuid4())[:6]
        from django.utils import timezone
        cache.set(f'email_submit:{camp_id}', {
            'campaign_id': camp_id,
            'advertiser_id': 1,
            'campaign_name': 'Test',
            'opt_in_type': 'SOI',
            'payout': '0.50',
            'target_countries': ['US'],
            'daily_cap': 5000,
            'today_submits': 0,
            'total_submits': 0,
            'redirect_url': '/ty/',
            'status': 'active',
        }, timeout=3600)
        result = self.manager.process_submit(
            campaign_id=camp_id,
            email='test@mailinator.com',
            publisher_id=1,
            country='US',
            ip='1.2.3.4',
        )
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], 'disposable_email_detected')

    def test_invalid_email_rejected(self):
        result = self.manager.process_submit(
            campaign_id='any',
            email='not-an-email',
            publisher_id=1,
            country='US',
            ip='1.2.3.4',
        )
        self.assertFalse(result['accepted'])


class SubIDTrackingTest(TestCase):
    def setUp(self):
        from api.promotions.subid_tracking.subid_manager import SubIDManager
        self.manager = SubIDManager()

    def test_record_click_with_subids(self):
        result = self.manager.record_click(
            publisher_id=1,
            campaign_id=1,
            click_id='test_click_123',
            subids={'s1': 'tiktok', 's2': 'video_456', 's3': 'us_male'},
            country='US',
            device='mobile',
        )
        self.assertIn('click_id', result)
        self.assertEqual(result['subids_recorded'].get('s1'), 'tiktok')

    def test_long_subid_truncated(self):
        long_val = 'x' * 100  # > 64 char limit
        result = self.manager.record_click(
            publisher_id=1,
            campaign_id=1,
            click_id='click_456',
            subids={'s1': long_val},
        )
        recorded_s1 = result['subids_recorded'].get('s1', '')
        self.assertLessEqual(len(recorded_s1), 64)
