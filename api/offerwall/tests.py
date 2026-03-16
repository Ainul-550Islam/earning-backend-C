"""
Offerwall tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import *
from .utils.RewardCalculator import RewardCalculator
from .utils.OfferValidator import OfferValidator

User = get_user_model()


class OfferProviderTestCase(TestCase):
    """Test OfferProvider model"""
    
    def setUp(self):
        self.provider = OfferProvider.objects.create(
            name='Test Provider',
            provider_type='tapjoy',
            api_key='test_key',
            app_id='test_app',
            revenue_share=Decimal('70.00'),
            status='active'
        )
    
    def test_provider_creation(self):
        """Test provider is created correctly"""
        self.assertEqual(self.provider.name, 'Test Provider')
        self.assertEqual(self.provider.provider_type, 'tapjoy')
        self.assertTrue(self.provider.is_active())
    
    def test_provider_status(self):
        """Test provider status"""
        self.provider.status = 'inactive'
        self.provider.save()
        self.assertFalse(self.provider.is_active())


class OfferTestCase(TestCase):
    """Test Offer model"""
    
    def setUp(self):
        self.provider = OfferProvider.objects.create(
            name='Test Provider',
            provider_type='tapjoy',
            revenue_share=Decimal('70.00')
        )
        
        self.category = OfferCategory.objects.create(
            name='Games',
            slug='games'
        )
        
        self.offer = Offer.objects.create(
            provider=self.provider,
            external_offer_id='test_123',
            title='Test Offer',
            description='Test description',
            payout=Decimal('1.00'),
            reward_amount=Decimal('0.70'),
            category=self.category,
            offer_type='app_install',
            platform='android',
            click_url='https://example.com/click',
            status='active'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_offer_creation(self):
        """Test offer is created correctly"""
        self.assertEqual(self.offer.title, 'Test Offer')
        self.assertEqual(self.offer.payout, Decimal('1.00'))
        self.assertEqual(self.offer.reward_amount, Decimal('0.70'))
    
    def test_offer_is_active(self):
        """Test offer active status"""
        self.assertTrue(self.offer.is_active())
        
        self.offer.status = 'paused'
        self.offer.save()
        self.assertFalse(self.offer.is_active())
    
    def test_offer_availability_for_user(self):
        """Test offer availability for specific user"""
        self.assertTrue(self.offer.is_available_for_user(self.user))
    
    def test_offer_increment_counts(self):
        """Test incrementing offer counters"""
        initial_views = self.offer.view_count
        self.offer.increment_view()
        self.assertEqual(self.offer.view_count, initial_views + 1)
        
        initial_clicks = self.offer.click_count
        self.offer.increment_click()
        self.assertEqual(self.offer.click_count, initial_clicks + 1)


class RewardCalculatorTestCase(TestCase):
    """Test RewardCalculator"""
    
    def setUp(self):
        self.provider = OfferProvider.objects.create(
            name='Test Provider',
            provider_type='tapjoy',
            revenue_share=Decimal('70.00')
        )
        
        self.offer = Offer.objects.create(
            provider=self.provider,
            external_offer_id='test_123',
            title='Test Offer',
            description='Test',
            payout=Decimal('1.00'),
            reward_amount=Decimal('0.70'),
            click_url='https://example.com'
        )
        
        self.calculator = RewardCalculator(self.offer, self.provider)
    
    def test_calculate_user_reward(self):
        """Test user reward calculation"""
        payout = Decimal('1.00')
        reward = self.calculator.calculate_user_reward(payout)
        
        expected = Decimal('0.70')  # 70% of 1.00
        self.assertEqual(reward, expected)
    
    def test_calculate_platform_fee(self):
        """Test platform fee calculation"""
        payout = Decimal('1.00')
        fee = self.calculator.calculate_platform_fee(payout)
        
        expected = Decimal('0.30')  # 30% of 1.00
        self.assertEqual(fee, expected)
    
    def test_calculate_total_reward(self):
        """Test total reward calculation"""
        payout = Decimal('1.00')
        result = self.calculator.calculate_total_reward(payout)
        
        self.assertEqual(result['base_reward'], Decimal('0.70'))
        self.assertIn('total_reward', result)
        self.assertIn('currency', result)


class OfferValidatorTestCase(TestCase):
    """Test OfferValidator"""
    
    def setUp(self):
        self.provider = OfferProvider.objects.create(
            name='Test Provider',
            provider_type='tapjoy',
            status='active'
        )
        
        self.offer = Offer.objects.create(
            provider=self.provider,
            external_offer_id='test_123',
            title='Test Offer',
            description='Test',
            payout=Decimal('1.00'),
            reward_amount=Decimal('0.70'),
            status='active',
            click_url='https://example.com'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.validator = OfferValidator(self.offer)
    
    def test_validate_active_offer(self):
        """Test validating active offer"""
        self.assertTrue(self.validator.validate_offer_availability(self.user))
    
    def test_validate_inactive_offer(self):
        """Test validating inactive offer"""
        self.offer.status = 'paused'
        self.offer.save()
        
        from .exceptions import OfferInactiveException
        with self.assertRaises(OfferInactiveException):
            self.validator.validate_offer_availability(self.user)
    
    def test_validate_payout_amount(self):
        """Test payout validation"""
        self.assertTrue(self.validator.validate_payout_amount(Decimal('1.00')))
        
        from .exceptions import InvalidRewardException
        with self.assertRaises(InvalidRewardException):
            self.validator.validate_payout_amount(Decimal('-1.00'))


class OfferConversionTestCase(TestCase):
    """Test OfferConversion"""
    
    def setUp(self):
        self.provider = OfferProvider.objects.create(
            name='Test Provider',
            provider_type='tapjoy'
        )
        
        self.offer = Offer.objects.create(
            provider=self.provider,
            external_offer_id='test_123',
            title='Test Offer',
            description='Test',
            payout=Decimal('1.00'),
            reward_amount=Decimal('0.70'),
            click_url='https://example.com'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.conversion = OfferConversion.objects.create(
            offer=self.offer,
            user=self.user,
            conversion_id='test_conv_123',
            payout_amount=Decimal('1.00'),
            reward_amount=Decimal('0.70'),
            status='pending'
        )
    
    def test_conversion_creation(self):
        """Test conversion is created"""
        self.assertEqual(self.conversion.status, 'pending')
        self.assertEqual(self.conversion.reward_amount, Decimal('0.70'))
    
    def test_conversion_approve(self):
        """Test conversion approval"""
        result = self.conversion.approve()
        self.assertTrue(result)
        self.assertEqual(self.conversion.status, 'approved')
        self.assertIsNotNone(self.conversion.approved_at)
    
    def test_conversion_reject(self):
        """Test conversion rejection"""
        self.conversion.reject(reason='Test rejection')
        self.assertEqual(self.conversion.status, 'rejected')
        self.assertEqual(self.conversion.rejection_reason, 'Test rejection')