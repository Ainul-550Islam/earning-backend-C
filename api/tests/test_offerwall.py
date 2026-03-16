# api/tests/test_offerwall.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]

class SafeOfferwallTest(TestCase):
    """Offerwall Test with Defensive Coding - No more surprises!"""

    def setUp(self):
        """Test setup with defensive user creation"""
        try:
            self.user = User.objects.create_user(
                username=f'u_{uid()}',
                email=f'{uid()}@test.com',
                password='x'
            )
            self.assertTrue(self.user.pk, "User creation failed")
        except Exception as e:
            self.fail(f"❌ Setup failed: {e}")

    def _make_provider(self):
        """Create provider with fallback defaults"""
        from api.offerwall.models import OfferProvider
        try:
            return OfferProvider.objects.create(
                name=f'Provider_{uid()}',
                provider_type='custom',          # valid choice
                status='active',                   # default active
            )
        except IntegrityError as e:
            logger.error(f"Provider creation failed: {e}")
            with transaction.atomic():
                # Try with minimal fields
                return OfferProvider.objects.create(
                    name=f'Provider_{uid()}',
                    provider_type='custom',
                )
        except Exception as e:
            self.fail(f"❌ Unexpected error creating provider: {e}")

    def _make_offer(self, provider):
        """Create offer with all required fields"""
        from api.offerwall.models import Offer
        return Offer.objects.create(
            provider=provider,
            external_offer_id=f'EXT_{uid()}',
            title=f'Offer_{uid()}',
            description='Test offer description',
            offer_type='app_install',          # valid choice
            status='active',
            payout=Decimal('1.00'),                        # ✅ required NOT NULL field
            click_url='https://example.com/click',
        )

    def _make_click(self, offer):
        """Create click with all required fields"""
        from api.offerwall.models import OfferClick
        return OfferClick.objects.create(
            offer=offer,
            user=self.user,
            click_id=f'CLK_{uid()}',
            ip_address='127.0.0.1',
            user_agent='TestAgent/1.0',
        )

    def _make_conversion(self, offer):
        """Create conversion with all required fields"""
        from api.offerwall.models import OfferConversion
        return OfferConversion.objects.create(
            offer=offer,
            user=self.user,
            conversion_id=f'CONV_{uid()}',
            payout_amount=Decimal('1.00'),
            payout_currency='USD',
            reward_amount=Decimal('50.00'),
            reward_currency='Points',
            status='pending',
        )

    # ========== ACTUAL TESTS ==========

    def test_offer_creation(self):
        """Test offer creation – bulletproof"""
        provider = self._make_provider()
        offer = self._make_offer(provider)
        self.assertEqual(offer.status, 'active')

    def test_offer_click_tracking(self):
        """Test offer click tracking – bulletproof"""
        provider = self._make_provider()
        offer = self._make_offer(provider)
        click = self._make_click(offer)
        self.assertEqual(click.user, self.user)

    def test_offer_conversion(self):
        """Test offer conversion – bulletproof"""
        provider = self._make_provider()
        offer = self._make_offer(provider)
        conversion = self._make_conversion(offer)
        self.assertEqual(conversion.status, 'pending')



class OfferwallTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def _make_provider(self):
        from api.offerwall.models import OfferProvider
        return OfferProvider.objects.create(
            name=f'Provider_{uid()}',
            provider_type='custom',
            status='active',
        )

    def _make_offer(self, provider):
        from api.offerwall.models import Offer
        return Offer.objects.create(
            provider=provider,
            external_offer_id=f'EXT_{uid()}',
            title=f'Offer_{uid()}',
            description='Test offer description',
            offer_type='app_install',
            status='active',
            payout=Decimal('1.00'),
            click_url='https://example.com/click',
        )

    def test_offer_creation(self):
        from api.offerwall.models import Offer
        provider = self._make_provider()
        offer = self._make_offer(provider)
        self.assertEqual(offer.status, 'active')

    def test_offer_click_tracking(self):
        from api.offerwall.models import OfferClick
        provider = self._make_provider()
        offer = self._make_offer(provider)
        click = OfferClick.objects.create(
            offer=offer,
            user=self.user,
            click_id=f'CLK_{uid()}',
            ip_address='127.0.0.1',
            user_agent='TestAgent/1.0',
        )
        self.assertEqual(click.user, self.user)

    def test_offer_conversion(self):
        from api.offerwall.models import OfferConversion
        from decimal import Decimal
        provider = self._make_provider()
        offer = self._make_offer(provider)
        conversion = OfferConversion.objects.create(
            offer=offer,
            user=self.user,
            conversion_id=f'CONV_{uid()}',
            payout_amount=Decimal('1.00'),
            payout_currency='USD',
            reward_amount=Decimal('50.00'),
            reward_currency='Points',
            status='pending',
        )
        self.assertEqual(conversion.status, 'pending')