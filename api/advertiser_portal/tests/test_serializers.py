"""
Test Serializers

Comprehensive tests for API serializers
including validation, serialization, and error handling.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import serializers
from unittest.mock import Mock, patch, MagicMock

from ..models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification
from ..models.campaign import AdCampaign, CampaignCreative, CampaignTargeting
from ..models.offer import AdvertiserOffer, OfferRequirement
from ..models.tracking import TrackingPixel, S2SPostback, Conversion
from ..models.billing import AdvertiserWallet, AdvertiserTransaction, AdvertiserInvoice
from ..serializers.advertiser import (
    AdvertiserSerializer, AdvertiserProfileSerializer, AdvertiserVerificationSerializer
)
from ..serializers.campaign import (
    AdCampaignSerializer, CampaignCreativeSerializer, CampaignTargetingSerializer
)
from ..serializers.offer import (
    AdvertiserOfferSerializer, OfferRequirementSerializer
)
from ..serializers.tracking import (
    TrackingPixelSerializer, S2SPostbackSerializer, ConversionSerializer
)
from ..serializers.billing import (
    AdvertiserWalletSerializer, AdvertiserTransactionSerializer, AdvertiserInvoiceSerializer
)

User = get_user_model()


class AdvertiserSerializerTestCase(APITestCase):
    """Test cases for AdvertiserSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.valid_data = {
            'company_name': 'Test Company',
            'contact_email': 'contact@testcompany.com',
            'contact_phone': '+1234567890',
            'website': 'https://testcompany.com',
            'industry': 'technology',
            'company_size': 'medium',
        }
    
    def test_create_advertiser_success(self):
        """Test successful advertiser creation."""
        serializer = AdvertiserSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        advertiser = serializer.save(user=self.user)
        
        self.assertIsInstance(advertiser, Advertiser)
        self.assertEqual(advertiser.user, self.user)
        self.assertEqual(advertiser.company_name, 'Test Company')
        self.assertEqual(advertiser.contact_email, 'contact@testcompany.com')
        self.assertEqual(advertiser.verification_status, 'pending')
    
    def test_create_advertiser_missing_required_fields(self):
        """Test advertiser creation with missing required fields."""
        invalid_data = self.valid_data.copy()
        del invalid_data['company_name']
        
        serializer = AdvertiserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('company_name', serializer.errors)
    
    def test_create_advertiser_invalid_email(self):
        """Test advertiser creation with invalid email."""
        invalid_data = self.valid_data.copy()
        invalid_data['contact_email'] = 'invalid-email'
        
        serializer = AdvertiserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('contact_email', serializer.errors)
    
    def test_create_advertiser_invalid_website(self):
        """Test advertiser creation with invalid website."""
        invalid_data = self.valid_data.copy()
        invalid_data['website'] = 'invalid-url'
        
        serializer = AdvertiserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('website', serializer.errors)
    
    def test_create_advertiser_invalid_phone(self):
        """Test advertiser creation with invalid phone."""
        invalid_data = self.valid_data.copy()
        invalid_data['contact_phone'] = 'invalid-phone'
        
        serializer = AdvertiserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('contact_phone', serializer.errors)
    
    def test_update_advertiser_success(self):
        """Test successful advertiser update."""
        advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Original Company',
            contact_email='original@testcompany.com',
            contact_phone='+1234567890',
            website='https://original.com',
            industry='technology',
            company_size='small'
        )
        
        update_data = {
            'company_name': 'Updated Company',
            'contact_email': 'updated@testcompany.com',
            'industry': 'finance'
        }
        
        serializer = AdvertiserSerializer(advertiser, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_advertiser = serializer.save()
        
        self.assertEqual(updated_advertiser.company_name, 'Updated Company')
        self.assertEqual(updated_advertiser.contact_email, 'updated@testcompany.com')
        self.assertEqual(updated_advertiser.industry, 'finance')
    
    def test_advertiser_serialization(self):
        """Test advertiser serialization."""
        advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        serializer = AdvertiserSerializer(advertiser)
        data = serializer.data
        
        self.assertEqual(data['company_name'], 'Test Company')
        self.assertEqual(data['contact_email'], 'contact@testcompany.com')
        self.assertEqual(data['verification_status'], 'pending')
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)


class AdvertiserProfileSerializerTestCase(APITestCase):
    """Test cases for AdvertiserProfileSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.valid_data = {
            'company_description': 'A great technology company',
            'logo_url': 'https://example.com/logo.png',
            'address': '123 Main St, City, State',
            'city': 'Test City',
            'country': 'US',
            'postal_code': '12345',
        }
    
    def test_create_profile_success(self):
        """Test successful profile creation."""
        serializer = AdvertiserProfileSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        profile = serializer.save(advertiser=self.advertiser)
        
        self.assertIsInstance(profile, AdvertiserProfile)
        self.assertEqual(profile.advertiser, self.advertiser)
        self.assertEqual(profile.company_description, 'A great technology company')
        self.assertEqual(profile.city, 'Test City')
    
    def test_update_profile_success(self):
        """Test successful profile update."""
        profile = AdvertiserProfile.objects.create(
            advertiser=self.advertiser,
            company_description='Original description',
            city='Original City'
        )
        
        update_data = {
            'company_description': 'Updated description',
            'city': 'Updated City'
        }
        
        serializer = AdvertiserProfileSerializer(profile, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_profile = serializer.save()
        
        self.assertEqual(updated_profile.company_description, 'Updated description')
        self.assertEqual(updated_profile.city, 'Updated City')
    
    def test_profile_serialization(self):
        """Test profile serialization."""
        profile = AdvertiserProfile.objects.create(
            advertiser=self.advertiser,
            company_description='Test description',
            city='Test City',
            country='US'
        )
        
        serializer = AdvertiserProfileSerializer(profile)
        data = serializer.data
        
        self.assertEqual(data['company_description'], 'Test description')
        self.assertEqual(data['city'], 'Test City')
        self.assertEqual(data['country'], 'US')


class AdvertiserVerificationSerializerTestCase(APITestCase):
    """Test cases for AdvertiserVerificationSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.valid_data = {
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'status': 'pending',
        }
    
    def test_create_verification_success(self):
        """Test successful verification creation."""
        serializer = AdvertiserVerificationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        verification = serializer.save(advertiser=self.advertiser)
        
        self.assertIsInstance(verification, AdvertiserVerification)
        self.assertEqual(verification.advertiser, self.advertiser)
        self.assertEqual(verification.document_type, 'business_license')
        self.assertEqual(verification.status, 'pending')
    
    def test_create_verification_invalid_document_type(self):
        """Test verification creation with invalid document type."""
        invalid_data = self.valid_data.copy()
        invalid_data['document_type'] = 'invalid_type'
        
        serializer = AdvertiserVerificationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('document_type', serializer.errors)
    
    def test_create_verification_invalid_expiry_date(self):
        """Test verification creation with invalid expiry date."""
        invalid_data = self.valid_data.copy()
        invalid_data['expiry_date'] = 'invalid-date'
        
        serializer = AdvertiserVerificationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('expiry_date', serializer.errors)
    
    def test_verification_serialization(self):
        """Test verification serialization."""
        verification = AdvertiserVerification.objects.create(
            advertiser=self.advertiser,
            document_type='business_license',
            document_number='BL123456',
            expiry_date='2025-12-31',
            status='pending'
        )
        
        serializer = AdvertiserVerificationSerializer(verification)
        data = serializer.data
        
        self.assertEqual(data['document_type'], 'business_license')
        self.assertEqual(data['document_number'], 'BL123456')
        self.assertEqual(data['status'], 'pending')


class AdCampaignSerializerTestCase(APITestCase):
    """Test cases for AdCampaignSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        # Fund wallet
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('1000.00')
        wallet.save()
        
        self.valid_data = {
            'name': 'Test Campaign',
            'description': 'Test campaign description',
            'campaign_type': 'display',
            'budget_limit': '1000.00',
            'daily_budget': '100.00',
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
            'target_ctr': '2.0',
            'target_cpa': '5.0',
            'target_conversion_rate': '1.0',
        }
    
    def test_create_campaign_success(self):
        """Test successful campaign creation."""
        serializer = AdCampaignSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        campaign = serializer.save(advertiser=self.advertiser)
        
        self.assertIsInstance(campaign, AdCampaign)
        self.assertEqual(campaign.advertiser, self.advertiser)
        self.assertEqual(campaign.name, 'Test Campaign')
        self.assertEqual(campaign.budget_limit, Decimal('1000.00'))
        self.assertEqual(campaign.status, 'draft')
    
    def test_create_campaign_insufficient_balance(self):
        """Test campaign creation with insufficient balance."""
        # Set wallet balance to 0
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('0.00')
        wallet.save()
        
        serializer = AdCampaignSerializer(data=self.valid_data)
        # Should still be valid, but save will fail
        self.assertTrue(serializer.is_valid())
        
        with self.assertRaises(serializers.ValidationError):
            serializer.save(advertiser=self.advertiser)
    
    def test_create_campaign_invalid_dates(self):
        """Test campaign creation with invalid dates."""
        invalid_data = self.valid_data.copy()
        invalid_data['start_date'] = timezone.now().date()
        invalid_data['end_date'] = (timezone.now() - timezone.timedelta(days=1)).date()
        
        serializer = AdCampaignSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('end_date', serializer.errors)
    
    def test_create_campaign_invalid_budgets(self):
        """Test campaign creation with invalid budgets."""
        invalid_data = self.valid_data.copy()
        invalid_data['daily_budget'] = '2000.00'  # Higher than budget limit
        invalid_data['budget_limit'] = '1000.00'
        
        serializer = AdCampaignSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('daily_budget', serializer.errors)
    
    def test_campaign_serialization(self):
        """Test campaign serialization."""
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            description='Test description',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='draft'
        )
        
        serializer = AdCampaignSerializer(campaign)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Campaign')
        self.assertEqual(data['campaign_type'], 'display')
        self.assertEqual(data['budget_limit'], '1000.00')
        self.assertEqual(data['status'], 'draft')


class CampaignCreativeSerializerTestCase(APITestCase):
    """Test cases for CampaignCreativeSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        self.valid_data = {
            'name': 'Test Creative',
            'creative_type': 'image',
            'file_path': '/path/to/image.jpg',
            'file_size': 1024,
            'file_mime_type': 'image/jpeg',
            'status': 'active',
        }
    
    def test_create_creative_success(self):
        """Test successful creative creation."""
        serializer = CampaignCreativeSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        creative = serializer.save(campaign=self.campaign)
        
        self.assertIsInstance(creative, CampaignCreative)
        self.assertEqual(creative.campaign, self.campaign)
        self.assertEqual(creative.name, 'Test Creative')
        self.assertEqual(creative.creative_type, 'image')
        self.assertEqual(creative.status, 'active')
    
    def test_create_creative_invalid_type(self):
        """Test creative creation with invalid type."""
        invalid_data = self.valid_data.copy()
        invalid_data['creative_type'] = 'invalid_type'
        
        serializer = CampaignCreativeSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('creative_type', serializer.errors)
    
    def test_creative_serialization(self):
        """Test creative serialization."""
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            name='Test Creative',
            creative_type='image',
            file_path='/path/to/image.jpg',
            file_size=1024,
            file_mime_type='image/jpeg',
            status='active'
        )
        
        serializer = CampaignCreativeSerializer(creative)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Creative')
        self.assertEqual(data['creative_type'], 'image')
        self.assertEqual(data['status'], 'active')


class AdvertiserOfferSerializerTestCase(APITestCase):
    """Test cases for AdvertiserOfferSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.valid_data = {
            'name': 'Test Offer',
            'description': 'Test offer description',
            'offer_type': 'cpa',
            'payout_amount': '10.00',
            'currency': 'USD',
            'landing_page': 'https://example.com/offer',
            'target_countries': ['US', 'CA', 'UK'],
            'allowed_devices': ['desktop', 'mobile'],
            'tracking_method': 'postback',
            'cookie_duration': 30,
            'status': 'draft',
        }
    
    def test_create_offer_success(self):
        """Test successful offer creation."""
        serializer = AdvertiserOfferSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        offer = serializer.save(advertiser=self.advertiser)
        
        self.assertIsInstance(offer, AdvertiserOffer)
        self.assertEqual(offer.advertiser, self.advertiser)
        self.assertEqual(offer.name, 'Test Offer')
        self.assertEqual(offer.offer_type, 'cpa')
        self.assertEqual(offer.payout_amount, Decimal('10.00'))
        self.assertEqual(offer.status, 'draft')
    
    def test_create_offer_invalid_payout(self):
        """Test offer creation with invalid payout."""
        invalid_data = self.valid_data.copy()
        invalid_data['payout_amount'] = '-10.00'
        
        serializer = AdvertiserOfferSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('payout_amount', serializer.errors)
    
    def test_create_offer_invalid_url(self):
        """Test offer creation with invalid URL."""
        invalid_data = self.valid_data.copy()
        invalid_data['landing_page'] = 'invalid-url'
        
        serializer = AdvertiserOfferSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('landing_page', serializer.errors)
    
    def test_offer_serialization(self):
        """Test offer serialization."""
        offer = AdvertiserOffer.objects.create(
            advertiser=self.advertiser,
            name='Test Offer',
            description='Test offer description',
            offer_type='cpa',
            payout_amount=Decimal('10.00'),
            currency='USD',
            landing_page='https://example.com/offer',
            target_countries=['US', 'CA', 'UK'],
            status='draft'
        )
        
        serializer = AdvertiserOfferSerializer(offer)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Offer')
        self.assertEqual(data['offer_type'], 'cpa')
        self.assertEqual(data['payout_amount'], '10.00')
        self.assertEqual(data['status'], 'draft')


class TrackingPixelSerializerTestCase(APITestCase):
    """Test cases for TrackingPixelSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.valid_data = {
            'name': 'Test Pixel',
            'pixel_type': 'conversion',
            'description': 'Test conversion pixel',
            'target_url': 'https://example.com/thank-you',
            'status': 'active',
        }
    
    def test_create_pixel_success(self):
        """Test successful pixel creation."""
        serializer = TrackingPixelSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        pixel = serializer.save(advertiser=self.advertiser)
        
        self.assertIsInstance(pixel, TrackingPixel)
        self.assertEqual(pixel.advertiser, self.advertiser)
        self.assertEqual(pixel.name, 'Test Pixel')
        self.assertEqual(pixel.pixel_type, 'conversion')
        self.assertEqual(pixel.status, 'active')
        self.assertIsNotNone(pixel.pixel_code)
    
    def test_create_pixel_invalid_type(self):
        """Test pixel creation with invalid type."""
        invalid_data = self.valid_data.copy()
        invalid_data['pixel_type'] = 'invalid_type'
        
        serializer = TrackingPixelSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('pixel_type', serializer.errors)
    
    def test_create_pixel_invalid_url(self):
        """Test pixel creation with invalid URL."""
        invalid_data = self.valid_data.copy()
        invalid_data['target_url'] = 'invalid-url'
        
        serializer = TrackingPixelSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('target_url', serializer.errors)
    
    def test_pixel_serialization(self):
        """Test pixel serialization."""
        pixel = TrackingPixel.objects.create(
            advertiser=self.advertiser,
            name='Test Pixel',
            pixel_type='conversion',
            description='Test conversion pixel',
            target_url='https://example.com/thank-you',
            pixel_code='pixel_12345',
            status='active'
        )
        
        serializer = TrackingPixelSerializer(pixel)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Pixel')
        self.assertEqual(data['pixel_type'], 'conversion')
        self.assertEqual(data['status'], 'active')
        self.assertIn('pixel_code', data)


class ConversionSerializerTestCase(APITestCase):
    """Test cases for ConversionSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.pixel = TrackingPixel.objects.create(
            advertiser=self.advertiser,
            name='Test Pixel',
            pixel_type='conversion',
            description='Test conversion pixel',
            target_url='https://example.com/thank-you',
            status='active'
        )
        
        self.valid_data = {
            'conversion_id': 'conv_12345',
            'revenue': '25.00',
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'status': 'pending',
        }
    
    def test_create_conversion_success(self):
        """Test successful conversion creation."""
        serializer = ConversionSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        conversion = serializer.save(
            advertiser=self.advertiser,
            pixel=self.pixel
        )
        
        self.assertIsInstance(conversion, Conversion)
        self.assertEqual(conversion.advertiser, self.advertiser)
        self.assertEqual(conversion.pixel, self.pixel)
        self.assertEqual(conversion.conversion_id, 'conv_12345')
        self.assertEqual(conversion.revenue, Decimal('25.00'))
        self.assertEqual(conversion.status, 'pending')
    
    def test_create_conversion_invalid_revenue(self):
        """Test conversion creation with invalid revenue."""
        invalid_data = self.valid_data.copy()
        invalid_data['revenue'] = '-25.00'
        
        serializer = ConversionSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('revenue', serializer.errors)
    
    def test_create_conversion_invalid_ip(self):
        """Test conversion creation with invalid IP."""
        invalid_data = self.valid_data.copy()
        invalid_data['ip_address'] = 'invalid-ip'
        
        serializer = ConversionSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('ip_address', serializer.errors)
    
    def test_conversion_serialization(self):
        """Test conversion serialization."""
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            pixel=self.pixel,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            status='pending'
        )
        
        serializer = ConversionSerializer(conversion)
        data = serializer.data
        
        self.assertEqual(data['conversion_id'], 'conv_12345')
        self.assertEqual(data['revenue'], '25.00')
        self.assertEqual(data['status'], 'pending')


class AdvertiserWalletSerializerTestCase(APITestCase):
    """Test cases for AdvertiserWalletSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.wallet = AdvertiserWallet.objects.create(
            advertiser=self.advertiser,
            balance=Decimal('1000.00'),
            credit_limit=Decimal('2000.00'),
            status='active'
        )
    
    def test_wallet_serialization(self):
        """Test wallet serialization."""
        serializer = AdvertiserWalletSerializer(self.wallet)
        data = serializer.data
        
        self.assertEqual(data['balance'], '1000.00')
        self.assertEqual(data['credit_limit'], '2000.00')
        self.assertEqual(data['status'], 'active')
        self.assertIn('available_balance', data)
        self.assertIn('available_credit', data)
    
    def test_wallet_update_balance(self):
        """Test wallet balance update."""
        update_data = {
            'balance': '1500.00'
        }
        
        serializer = AdvertiserWalletSerializer(
            self.wallet,
            data=update_data,
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        
        updated_wallet = serializer.save()
        self.assertEqual(updated_wallet.balance, Decimal('1500.00'))
    
    def test_wallet_update_credit_limit(self):
        """Test wallet credit limit update."""
        update_data = {
            'credit_limit': '3000.00'
        }
        
        serializer = AdvertiserWalletSerializer(
            self.wallet,
            data=update_data,
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        
        updated_wallet = serializer.save()
        self.assertEqual(updated_wallet.credit_limit, Decimal('3000.00'))


class AdvertiserTransactionSerializerTestCase(APITestCase):
    """Test cases for AdvertiserTransactionSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.valid_data = {
            'transaction_type': 'deposit',
            'amount': '500.00',
            'payment_method': 'credit_card',
            'payment_reference': 'payment_12345',
            'status': 'completed',
        }
    
    def test_create_transaction_success(self):
        """Test successful transaction creation."""
        serializer = AdvertiserTransactionSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        transaction = serializer.save(advertiser=self.advertiser)
        
        self.assertIsInstance(transaction, AdvertiserTransaction)
        self.assertEqual(transaction.advertiser, self.advertiser)
        self.assertEqual(transaction.transaction_type, 'deposit')
        self.assertEqual(transaction.amount, Decimal('500.00'))
        self.assertEqual(transaction.status, 'completed')
    
    def test_create_transaction_invalid_amount(self):
        """Test transaction creation with invalid amount."""
        invalid_data = self.valid_data.copy()
        invalid_data['amount'] = '-500.00'
        
        serializer = AdvertiserTransactionSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('amount', serializer.errors)
    
    def test_create_transaction_invalid_type(self):
        """Test transaction creation with invalid type."""
        invalid_data = self.valid_data.copy()
        invalid_data['transaction_type'] = 'invalid_type'
        
        serializer = AdvertiserTransactionSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('transaction_type', serializer.errors)
    
    def test_transaction_serialization(self):
        """Test transaction serialization."""
        transaction = AdvertiserTransaction.objects.create(
            advertiser=self.advertiser,
            transaction_type='deposit',
            amount=Decimal('500.00'),
            payment_method='credit_card',
            payment_reference='payment_12345',
            status='completed'
        )
        
        serializer = AdvertiserTransactionSerializer(transaction)
        data = serializer.data
        
        self.assertEqual(data['transaction_type'], 'deposit')
        self.assertEqual(data['amount'], '500.00')
        self.assertEqual(data['status'], 'completed')


class SerializerValidationTestCase(APITestCase):
    """Test cases for serializer validation."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
    
    def test_nested_serialization(self):
        """Test nested serialization with related objects."""
        # Create profile
        profile = AdvertiserProfile.objects.create(
            advertiser=self.advertiser,
            company_description='Test description',
            city='Test City',
            country='US'
        )
        
        # Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        # Test advertiser serialization with nested data
        serializer = AdvertiserSerializer(self.advertiser)
        data = serializer.data
        
        self.assertIn('profile', data)
        self.assertIn('campaigns', data)
        
        # Check nested data
        profile_data = data['profile']
        self.assertEqual(profile_data['city'], 'Test City')
        
        campaigns_data = data['campaigns']
        self.assertEqual(len(campaigns_data), 1)
        self.assertEqual(campaigns_data[0]['name'], 'Test Campaign')
    
    def test_bulk_create_validation(self):
        """Test bulk create validation."""
        campaign_data = {
            'name': 'Bulk Campaign',
            'campaign_type': 'display',
            'budget_limit': '1000.00',
            'daily_budget': '100.00',
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
        }
        
        serializer = AdCampaignSerializer(data=campaign_data)
        self.assertTrue(serializer.is_valid())
        
        # Create multiple campaigns
        campaigns = []
        for i in range(3):
            data = campaign_data.copy()
            data['name'] = f'Campaign {i}'
            
            serializer = AdCampaignSerializer(data=data)
            self.assertTrue(serializer.is_valid())
            
            campaign = serializer.save(advertiser=self.advertiser)
            campaigns.append(campaign)
        
        self.assertEqual(len(campaigns), 3)
        
        for i, campaign in enumerate(campaigns):
            self.assertEqual(campaign.name, f'Campaign {i}')
            self.assertEqual(campaign.advertiser, self.advertiser)
    
    def test_custom_validation_methods(self):
        """Test custom validation methods."""
        # Test campaign budget validation
        invalid_campaign_data = {
            'name': 'Invalid Campaign',
            'campaign_type': 'display',
            'budget_limit': '1000.00',
            'daily_budget': '2000.00',  # Higher than budget limit
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
        }
        
        serializer = AdCampaignSerializer(data=invalid_campaign_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('daily_budget', serializer.errors)
        self.assertIn('cannot exceed budget limit', str(serializer.errors['daily_budget']))
    
    def test_serializer_field_level_validation(self):
        """Test field-level validation."""
        # Test email validation
        invalid_advertiser_data = {
            'company_name': 'Test Company',
            'contact_email': 'invalid-email',  # Invalid email
            'contact_phone': '+1234567890',
            'website': 'https://testcompany.com',
            'industry': 'technology',
            'company_size': 'medium',
        }
        
        serializer = AdvertiserSerializer(data=invalid_advertiser_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('contact_email', serializer.errors)
    
    def test_serializer_conditional_validation(self):
        """Test conditional validation."""
        # Test offer validation based on type
        offer_data = {
            'name': 'Test Offer',
            'description': 'Test offer description',
            'offer_type': 'cpa',
            'payout_amount': '10.00',
            'currency': 'USD',
            'landing_page': 'https://example.com/offer',
            'target_countries': ['US', 'CA', 'UK'],
            'tracking_method': 'postback',
            'cookie_duration': 30,
        }
        
        serializer = AdvertiserOfferSerializer(data=offer_data)
        self.assertTrue(serializer.is_valid())
        
        # Test missing required fields for CPA
        invalid_offer_data = offer_data.copy()
        del invalid_offer_data['payout_amount']
        
        serializer = AdvertiserOfferSerializer(data=invalid_offer_data)
        self.assertFalse(serializer.is_valid())
        
        self.assertIn('payout_amount', serializer.errors)
    
    def test_serializer_error_messages(self):
        """Test serializer error messages."""
        invalid_data = {
            'company_name': '',  # Empty name
            'contact_email': 'invalid-email',
            'contact_phone': 'invalid-phone',
            'website': 'invalid-url',
            'industry': 'invalid_industry',
            'company_size': 'invalid_size',
        }
        
        serializer = AdvertiserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        
        errors = serializer.errors
        
        # Check that all required fields have errors
        self.assertIn('company_name', errors)
        self.assertIn('contact_email', errors)
        self.assertIn('contact_phone', errors)
        self.assertIn('website', errors)
        self.assertIn('industry', errors)
        self.assertIn('company_size', errors)
        
        # Check error messages are meaningful
        self.assertIn('required', str(errors['company_name']))
        self.assertIn('valid', str(errors['contact_email']))
    
    def test_serializer_data_transformation(self):
        """Test serializer data transformation."""
        # Test decimal field transformation
        campaign_data = {
            'name': 'Test Campaign',
            'campaign_type': 'display',
            'budget_limit': '1000.00',
            'daily_budget': '100.00',
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
        }
        
        serializer = AdCampaignSerializer(data=campaign_data)
        self.assertTrue(serializer.is_valid())
        
        # Check that string values are properly transformed
        validated_data = serializer.validated_data
        self.assertIsInstance(validated_data['budget_limit'], Decimal)
        self.assertIsInstance(validated_data['daily_budget'], Decimal)
        self.assertEqual(validated_data['budget_limit'], Decimal('1000.00'))
        self.assertEqual(validated_data['daily_budget'], Decimal('100.00'))
    
    def test_serializer_read_only_fields(self):
        """Test serializer read-only fields."""
        # Create a conversion
        pixel = TrackingPixel.objects.create(
            advertiser=self.advertiser,
            name='Test Pixel',
            pixel_type='conversion',
            description='Test conversion pixel',
            target_url='https://example.com/thank-you',
            status='active'
        )
        
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            pixel=pixel,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            status='pending'
        )
        
        serializer = ConversionSerializer(conversion)
        data = serializer.data
        
        # Check that read-only fields are included in output
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)
        self.assertIn('fraud_score', data)
        
        # Try to update read-only field
        update_data = {
            'conversion_id': 'new_conv_12345',
            'created_at': '2023-01-01T00:00:00Z'  # Should be ignored
        }
        
        serializer = ConversionSerializer(conversion, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_conversion = serializer.save()
        # conversion_id should be updated, but created_at should remain unchanged
        self.assertEqual(updated_conversion.conversion_id, 'new_conv_12345')
        self.assertNotEqual(updated_conversion.created_at, '2023-01-01T00:00:00Z')
