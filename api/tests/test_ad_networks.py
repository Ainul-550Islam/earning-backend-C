# api/tests/test_ad_networks.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class AdNetworkTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def _make_network(self):
        from api.ad_networks.models import AdNetwork
        return AdNetwork.objects.create(
            name=f'Network_{uid()}',
            category='offerwall',   # ✅ required, has choices
            is_active=True,
        )

    def _make_offer(self, network):
        from api.ad_networks.models import Offer
        return Offer.objects.create(
            ad_network=network,
            external_id=f'EXT_{uid()}',     # ✅ unique required
            title=f'Offer_{uid()}',
            description='Test offer',
            reward_amount=10.00,
            click_url='https://example.com/click',
            status='active',
        )

    def test_ad_network_creation(self):
        network = self._make_network()
        self.assertTrue(network.is_active)

    def test_offer_category_creation(self):
        from api.ad_networks.models import OfferCategory
        cat = OfferCategory.objects.create(
            name=f'Cat_{uid()}',
            slug=f'cat-{uid()}',        # ✅ slug unique required
            category_type='offer',
        )
        network = self._make_network()
        self.assertIsNotNone(network)
        network = self._make_network()
        network = self._make_network()
        self.assertTrue(network.is_active)
        network = self._make_network()
        self.assertEqual(network.category, 'offerwall')

    def test_offer_creation(self):
        network = self._make_network()
        offer = self._make_offer(network)
        self.assertEqual(offer.status, 'active')

    def test_offerwall_creation(self):
        from api.ad_networks.models import OfferWall
        wall = OfferWall.objects.create(
            name=f'Wall_{uid()}',
            slug=f'wall-{uid()}',       # ✅ slug unique required
            wall_type='main',
            is_active=True,
        )
        self.assertTrue(wall.is_active)

    def test_webhook_log_creation(self):
        from api.ad_networks.models import AdNetworkWebhookLog
        # ad_network is now nullable in updated model
        log = AdNetworkWebhookLog.objects.create(
            payload={'test': 'data'},
            is_processed=False,
        )
        self.assertFalse(log.is_processed)

    def test_user_offer_limit(self):
        from api.ad_networks.models import UserOfferLimit
        # offer is now nullable in updated model
        limit = UserOfferLimit.objects.create(
            user=self.user,
            offer=None,
        )
        self.assertIsNotNone(limit)

    def test_blacklisted_ip(self):
        from api.ad_networks.models import BlacklistedIP
        ip = BlacklistedIP.objects.create(
            ip_address='10.0.0.1',
            reason='bot',
            is_active=True,
        )
        self.assertTrue(ip.is_active)

    def test_network_statistic(self):
        from api.ad_networks.models import NetworkStatistic
        from datetime import date
        network = self._make_network()
        stat = NetworkStatistic.objects.create(
            ad_network=network,
            date=date.today(),
            clicks=10,
            conversions=2,
        )
        self.assertEqual(stat.clicks, 10)

    def test_fraud_detection_rule(self):
        from api.ad_networks.models import FraudDetectionRule
        rule = FraudDetectionRule.objects.create(
            name=f'Rule_{uid()}',
            rule_type='ip',
            action='block',
            severity='high',
            condition={'threshold': 10},
            is_active=True,
        )
        self.assertTrue(rule.is_active)