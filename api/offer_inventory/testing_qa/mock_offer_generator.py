# api/offer_inventory/testing_qa/mock_offer_generator.py
"""
Mock Offer Generator — Create realistic test data for development and QA.
Generates offers, clicks, conversions, users with valid relationships.
"""
import random
import uuid
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

OFFER_TITLES = [
    'Install & Play Puzzle Game', 'Complete Survey — Earn Cash',
    'Sign Up & Get Bonus', 'Watch Video Ad', 'Download Free App',
    'Complete Profile Setup', 'Refer a Friend Bonus', 'Daily Check-in Reward',
    'Shop & Earn Cashback', 'Play & Win — Casino App',
    'Register on Shopping Site', 'Take Personality Quiz',
    'Subscribe to Newsletter', 'Test New App — Beta',
    'Complete Financial Survey', 'Install VPN App',
]
CATEGORIES   = ['Games', 'Surveys', 'Shopping', 'Finance', 'Apps', 'Videos']
COUNTRIES    = ['BD', 'IN', 'US', 'GB', 'CA', 'AU', 'SG', 'MY']
DEVICES      = ['mobile', 'desktop', 'tablet']
NETWORKS     = ['tapjoy', 'fyber', 'adgem', 'offertoro', 'cpalead']


class MockOfferGenerator:
    """Generate realistic test data for offer inventory."""

    @staticmethod
    def create_network(slug: str = None) -> object:
        """Create a test affiliate network."""
        from api.offer_inventory.models import OfferNetwork
        slug = slug or f'test-network-{uuid.uuid4().hex[:6]}'
        return OfferNetwork.objects.create(
            name             =f'Test Network {slug}',
            slug             =slug,
            status           ='active',
            revenue_share_pct=Decimal(str(random.choice([60, 65, 70, 75]))),
            is_s2s_enabled   =True,
        )

    @staticmethod
    def create_offer(network=None, tenant=None, payout: Decimal = None) -> object:
        """Create a single realistic test offer."""
        from api.offer_inventory.models import Offer, OfferNetwork, OfferCategory

        if not network:
            network = OfferNetwork.objects.filter(status='active').first()
            if not network:
                network = MockOfferGenerator.create_network()

        category, _ = OfferCategory.objects.get_or_create(
            name=random.choice(CATEGORIES),
            defaults={'slug': random.choice(CATEGORIES).lower(), 'is_active': True}
        )

        payout_amount  = payout or Decimal(str(round(random.uniform(0.1, 2.0), 4)))
        reward_amount  = (payout_amount * Decimal('0.70')).quantize(Decimal('0.0001'))
        cvr            = round(random.uniform(0.5, 8.0), 2)

        return Offer.objects.create(
            title           =random.choice(OFFER_TITLES),
            description     =f'Complete this offer to earn {reward_amount} BDT.',
            offer_url       =f'https://test-offer-{uuid.uuid4().hex[:8]}.example.com',
            network         =network,
            category        =category,
            tenant          =tenant,
            status          ='active',
            payout_amount   =payout_amount,
            reward_amount   =reward_amount,
            reward_type     ='cash',
            conversion_rate =cvr,
            is_featured     =random.random() < 0.2,
            estimated_time  =random.choice(['2 min', '5 min', '10 min', '15 min']),
            difficulty      =random.choice(['easy', 'medium', 'hard']),
        )

    @staticmethod
    def create_batch_offers(count: int = 10, network=None,
                             tenant=None) -> list:
        """Create multiple test offers."""
        return [
            MockOfferGenerator.create_offer(network, tenant)
            for _ in range(count)
        ]

    @staticmethod
    def create_test_user(username: str = None, tenant=None) -> object:
        """Create a test user with profile and wallet."""
        User = get_user_model()
        username = username or f'testuser_{uuid.uuid4().hex[:8]}'
        user     = User.objects.create_user(
            username=username,
            email   =f'{username}@test.example.com',
            password='testpass123',
        )
        # Ensure wallet exists
        try:
            from api.offer_inventory.finance_payment.wallet_integration import WalletIntegration
            WalletIntegration.ensure_wallet(user)
        except Exception:
            pass
        return user

    @staticmethod
    def create_click(offer, user, ip: str = None,
                      country: str = None) -> object:
        """Create a realistic test click."""
        from api.offer_inventory.models import Click
        import secrets
        return Click.objects.create(
            offer       =offer,
            user        =user,
            ip_address  =ip or f'{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}',
            user_agent  ='Mozilla/5.0 (Linux; Android 11; Test) Chrome/90.0.4430.91',
            country_code=country or random.choice(COUNTRIES),
            device_type =random.choice(DEVICES),
            click_token =secrets.token_hex(32),
            is_unique   =True,
            is_fraud    =False,
        )

    @staticmethod
    def create_conversion(click, status_name: str = 'approved') -> object:
        """Create a test conversion with proper status."""
        from api.offer_inventory.models import Conversion, ConversionStatus
        status, _ = ConversionStatus.objects.get_or_create(
            name=status_name,
            defaults={'description': status_name.capitalize(), 'is_terminal': status_name != 'pending'}
        )
        return Conversion.objects.create(
            click          =click,
            offer          =click.offer,
            user           =click.user,
            status         =status,
            payout_amount  =click.offer.payout_amount,
            reward_amount  =click.offer.reward_amount,
            transaction_id =f'TEST_TX_{uuid.uuid4().hex[:12].upper()}',
            ip_address     =click.ip_address,
            country_code   =click.country_code,
        )

    @staticmethod
    def seed_full_scenario(offers: int = 5, users: int = 3,
                            clicks_per_user: int = 5,
                            tenant=None) -> dict:
        """
        Create a complete test scenario:
        network → offers → users → clicks → conversions.
        """
        network      = MockOfferGenerator.create_network()
        test_offers  = MockOfferGenerator.create_batch_offers(offers, network, tenant)
        test_users   = [MockOfferGenerator.create_test_user() for _ in range(users)]
        test_clicks  = []
        test_convs   = []

        for user in test_users:
            for _ in range(clicks_per_user):
                offer = random.choice(test_offers)
                click = MockOfferGenerator.create_click(offer, user)
                test_clicks.append(click)
                # ~50% conversion rate in test
                if random.random() < 0.5:
                    conv = MockOfferGenerator.create_conversion(click, 'approved')
                    test_convs.append(conv)
                    Click.objects.filter(id=click.id).update(converted=True)

        from api.offer_inventory.models import Click
        logger.info(
            f'Test scenario seeded: {offers} offers, {users} users, '
            f'{len(test_clicks)} clicks, {len(test_convs)} conversions'
        )
        return {
            'network'    : network,
            'offers'     : test_offers,
            'users'      : test_users,
            'clicks'     : test_clicks,
            'conversions': test_convs,
        }

    @staticmethod
    def cleanup_test_data(prefix: str = 'testuser_'):
        """Remove all test data created by mock generator."""
        User = get_user_model()
        deleted = User.objects.filter(username__startswith=prefix).delete()
        logger.info(f'Test data cleaned: {deleted}')
        return deleted
