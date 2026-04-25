"""
Test Integration

Comprehensive integration tests for the Advertiser Portal API
testing end-to-end workflows and system interactions.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.reverse import reverse
from unittest.mock import Mock, patch, MagicMock

from ..models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification
from ..models.campaign import AdCampaign, CampaignCreative, CampaignTargeting
from ..models.offer import AdvertiserOffer, OfferRequirement
from ..models.tracking import TrackingPixel, S2SPostback, Conversion
from ..models.billing import AdvertiserWallet, AdvertiserTransaction, AdvertiserInvoice
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None
try:
    from ..services import CampaignService
except ImportError:
    CampaignService = None
try:
    from ..services import OfferService
except ImportError:
    OfferService = None
try:
    from ..services import TrackingPixelService
except ImportError:
    TrackingPixelService = None
try:
    from ..services import ConversionTrackingService
except ImportError:
    ConversionTrackingService = None
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None

User = get_user_model()


class AdvertiserIntegrationTestCase(APITestCase):
    """Integration tests for advertiser workflows."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )
        
        self.advertiser_service = AdvertiserService()
    
    def test_complete_advertiser_onboarding_workflow(self):
        """Test complete advertiser onboarding workflow."""
        # 1. Register advertiser
        advertiser_data = {
            'company_name': 'New Company',
            'contact_email': 'contact@newcompany.com',
            'contact_phone': '+1234567890',
            'website': 'https://newcompany.com',
            'industry': 'technology',
            'company_size': 'medium',
        }
        
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-list')
        response = self.client.post(url, advertiser_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        advertiser = Advertiser.objects.get(pk=response.data['id'])
        
        # 2. Create profile
        profile_data = {
            'company_description': 'A great technology company',
            'address': '123 Main St, City, State',
            'city': 'Test City',
            'country': 'US',
            'postal_code': '12345',
        }
        
        url = reverse('advertiserprofile-list')
        response = self.client.post(url, profile_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = AdvertiserProfile.objects.get(advertiser=advertiser)
        
        # 3. Upload verification documents
        verification_data = {
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'status': 'pending',
        }
        
        url = reverse('advertiserverification-list')
        response = self.client.post(url, verification_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        verification = AdvertiserVerification.objects.get(advertiser=advertiser)
        
        # 4. Approve verification (staff action)
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('advertiserverification-approve', kwargs={'pk': verification.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Check advertiser status
        advertiser.refresh_from_db()
        self.assertEqual(advertiser.verification_status, 'verified')
        
        # 6. Fund wallet
        wallet_data = {
            'amount': '1000.00',
            'payment_method': 'credit_card',
            'payment_reference': 'payment_12345'
        }
        
        url = reverse('wallet-deposit', kwargs={'pk': advertiser.wallet.pk})
        response = self.client.post(url, wallet_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify complete workflow
        advertiser.refresh_from_db()
        self.assertEqual(advertiser.verification_status, 'verified')
        self.assertEqual(advertiser.wallet.balance, Decimal('1000.00'))
        self.assertIsNotNone(advertiser.profile)
        self.assertEqual(AdvertiserVerification.objects.filter(advertiser=advertiser).count(), 1)
    
    def test_advertiser_suspension_workflow(self):
        """Test advertiser suspension workflow."""
        # Create and verify advertiser
        advertiser = self.advertiser_service.create_advertiser(
            self.user,
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
        
        # Verify advertiser
        advertiser.verification_status = 'verified'
        advertiser.save()
        
        # Create active campaign
        campaign = AdCampaign.objects.create(
            advertiser=advertiser,
            name='Active Campaign',
            campaign_type='display',
            budget_limit=Decimal('500.00'),
            daily_budget=Decimal('50.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        # Suspend advertiser (staff action)
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('advertiser-suspend', kwargs={'pk': advertiser.pk})
        
        suspend_data = {
            'reason': 'Policy violation'
        }
        
        response = self.client.post(url, suspend_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify suspension effects
        advertiser.refresh_from_db()
        self.assertEqual(advertiser.status, 'suspended')
        
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'paused')
        
        wallet = advertiser.wallet
        wallet.refresh_from_db()
        self.assertEqual(wallet.status, 'suspended')


class CampaignIntegrationTestCase(APITestCase):
    """Integration tests for campaign workflows."""
    
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
            company_size='medium',
            verification_status='verified'
        )
        
        # Fund wallet
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('2000.00')
        wallet.save()
        
        self.campaign_service = CampaignService()
    
    def test_complete_campaign_lifecycle(self):
        """Test complete campaign lifecycle."""
        # 1. Create campaign
        campaign_data = {
            'name': 'Test Campaign',
            'description': 'Test campaign description',
            'campaign_type': 'display',
            'budget_limit': '1000.00',
            'daily_budget': '100.00',
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
            'target_ctr': '2.0',
            'target_cpa': '5.0',
        }
        
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.post(url, campaign_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        campaign = AdCampaign.objects.get(pk=response.data['id'])
        self.assertEqual(campaign.status, 'draft')
        
        # 2. Add targeting
        targeting_data = {
            'campaign': campaign.pk,
            'target_type': 'geo',
            'target_value': 'US,CA,UK',
            'is_active': True,
        }
        
        url = reverse('campaigntargeting-list')
        response = self.client.post(url, targeting_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 3. Add creative
        creative_data = {
            'campaign': campaign.pk,
            'name': 'Test Creative',
            'creative_type': 'image',
            'file_path': '/path/to/image.jpg',
            'file_size': 1024,
            'file_mime_type': 'image/jpeg',
            'status': 'active',
        }
        
        url = reverse('campaigncreative-list')
        response = self.client.post(url, creative_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 4. Start campaign
        url = reverse('campaign-start', kwargs={'pk': campaign.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'active')
        
        # 5. Simulate campaign spend
        for i in range(10):
            AdvertiserTransaction.objects.create(
                advertiser=self.advertiser,
                transaction_type='charge',
                amount=Decimal('10.00'),
                description=f'Campaign spend {i+1}',
                status='completed'
            )
            
            campaign.spend_amount += Decimal('10.00')
            campaign.save()
        
        # 6. Check campaign statistics
        url = reverse('campaign-statistics', kwargs={'pk': campaign.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
        
        # 7. Pause campaign
        url = reverse('campaign-pause', kwargs={'pk': campaign.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'paused')
        
        # 8. End campaign
        url = reverse('campaign-end', kwargs={'pk': campaign.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'ended')
    
    def test_campaign_budget_enforcement(self):
        """Test campaign budget enforcement."""
        # Create campaign with small budget
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Budget Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('100.00'),
            daily_budget=Decimal('50.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        # Simulate spend that exceeds budget
        campaign.spend_amount = Decimal('110.00')  # Exceeds budget
        campaign.save()
        
        # Run budget enforcement task
        from ..tasks.budget_check_tasks import auto_pause_over_budget_campaigns
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = auto_pause_over_budget_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertGreater(len(result['paused_campaigns']), 0)
            
            # Check that campaign was paused
            campaign.refresh_from_db()
            self.assertEqual(campaign.status, 'paused')
    
    def test_campaign_optimization_workflow(self):
        """Test campaign optimization workflow."""
        # Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Optimization Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        # Add performance data
        campaign.impressions = 10000
        campaign.clicks = 100
        campaign.conversions = 5
        campaign.ctr = 1.0
        campaign.cpc = 0.50
        campaign.cpa = 20.00
        campaign.save()
        
        # Run optimization
        try:
            from ..services import CampaignOptimizer
        except ImportError:
            CampaignOptimizer = None
        optimizer = CampaignOptimizer()
        
        optimization_result = optimizer.optimize_campaign(campaign)
        
        self.assertIn('optimization_applied', optimization_result)
        self.assertIn('bid_adjustments', optimization_result)
        self.assertIn('targeting_adjustments', optimization_result)


class OfferIntegrationTestCase(APITestCase):
    """Integration tests for offer workflows."""
    
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
            company_size='medium',
            verification_status='verified'
        )
        
        self.offer_service = OfferService()
    
    def test_complete_offer_lifecycle(self):
        """Test complete offer lifecycle."""
        # 1. Create offer
        offer_data = {
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
        }
        
        self.client.force_authenticate(user=self.user)
        url = reverse('offer-list')
        response = self.client.post(url, offer_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        offer = AdvertiserOffer.objects.get(pk=response.data['id'])
        self.assertEqual(offer.status, 'draft')
        
        # 2. Add requirements
        requirement_data = {
            'offer': offer.pk,
            'requirement_type': 'minimum_age',
            'value': '18',
            'description': 'Users must be 18 or older',
            'is_required': True,
        }
        
        url = reverse('offerrequirement-list')
        response = self.client.post(url, requirement_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 3. Submit for review
        url = reverse('offer-submit-for-review', kwargs={'pk': offer.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'pending_review')
        
        # 4. Approve offer (staff action)
        staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )
        
        self.client.force_authenticate(user=staff_user)
        url = reverse('offer-approve', kwargs={'pk': offer.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'approved')
        
        # 5. Publish offer
        self.client.force_authenticate(user=self.user)
        url = reverse('offer-publish', kwargs={'pk': offer.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'active')
        self.assertTrue(offer.is_published)
        
        # 6. Generate tracking
        tracking_service = TrackingPixelService()
        pixel = tracking_service.create_tracking_pixel(
            self.advertiser,
            {
                'name': f'{offer.name} Pixel',
                'pixel_type': 'conversion',
                'description': f'Conversion pixel for {offer.name}',
                'target_url': offer.landing_page,
                'status': 'active',
            }
        )
        
        # 7. Create conversions
        conversion_service = ConversionTrackingService()
        for i in range(5):
            conversion = conversion_service.record_conversion({
                'conversion_id': f'conv_{i}',
                'revenue': Decimal('15.00'),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'pixel': pixel,
                'offer': offer,
            })
            
            conversion_service.approve_conversion(conversion)
        
        # 8. Check offer statistics
        url = reverse('offer-statistics', kwargs={'pk': offer.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
        
        stats = response.data['statistics']
        self.assertEqual(stats['total_conversions'], 5)
        self.assertEqual(stats['total_payout'], Decimal('50.00'))
    
    def test_offer_quality_scoring(self):
        """Test offer quality scoring."""
        # Create offer
        offer = AdvertiserOffer.objects.create(
            advertiser=self.advertiser,
            name='Quality Test Offer',
            description='Test offer description',
            offer_type='cpa',
            payout_amount=Decimal('10.00'),
            currency='USD',
            landing_page='https://example.com/offer',
            target_countries=['US', 'CA', 'UK'],
            status='active'
        )
        
        # Create conversions with varying quality
        conversion_service = ConversionTrackingService()
        for i in range(10):
            conversion = conversion_service.record_conversion({
                'conversion_id': f'conv_{i}',
                'revenue': Decimal('15.00'),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'offer': offer,
                'custom_parameters': {
                    'session_duration': 300 - (i * 20),  # Decreasing quality
                    'pages_visited': 5 - (i // 2),
                    'device_type': 'desktop' if i % 2 == 0 else 'mobile'
                }
            })
            
            conversion_service.approve_conversion(conversion)
        
        # Calculate quality scores
        try:
            from ..services import ConversionQualityService
        except ImportError:
            ConversionQualityService = None
        quality_service = ConversionQualityService()
        
        quality_stats = quality_service.get_quality_statistics(self.advertiser, days=30)
        
        self.assertIn('average_quality_score', quality_stats)
        self.assertIn('high_quality_conversions', quality_stats)
        self.assertIn('low_quality_conversions', quality_stats)


class TrackingIntegrationTestCase(APITestCase):
    """Integration tests for tracking workflows."""
    
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
            company_size='medium',
            verification_status='verified'
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
        
        self.offer = AdvertiserOffer.objects.create(
            advertiser=self.advertiser,
            name='Test Offer',
            description='Test offer description',
            offer_type='cpa',
            payout_amount=Decimal('10.00'),
            currency='USD',
            landing_page='https://example.com/offer',
            target_countries=['US', 'CA', 'UK'],
            status='active'
        )
    
    def test_complete_tracking_workflow(self):
        """Test complete tracking workflow."""
        # 1. Create tracking pixel
        pixel_service = TrackingPixelService()
        pixel = pixel_service.create_tracking_pixel(
            self.advertiser,
            {
                'name': 'Test Pixel',
                'pixel_type': 'conversion',
                'description': 'Test conversion pixel',
                'target_url': 'https://example.com/thank-you',
                'status': 'active',
            }
        )
        
        # 2. Create S2S postback
        try:
            from ..services import S2SPostbackService
        except ImportError:
            S2SPostbackService = None
        postback_service = S2SPostbackService()
        
        postback = postback_service.create_s2s_postback(
            self.advertiser,
            {
                'name': 'Test Postback',
                'postback_type': 'conversion',
                'description': 'Test conversion postback',
                'postback_url': 'https://example.com/postback',
                'method': 'POST',
                'status': 'active',
            }
        )
        
        # 3. Fire pixel and create conversion
        conversion_service = ConversionTrackingService()
        
        conversion_data = {
            'conversion_id': 'conv_12345',
            'revenue': Decimal('25.00'),
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'pixel': pixel,
            'campaign': self.campaign,
            'offer': self.offer,
            'custom_parameters': {
                'affiliate_id': '12345',
                'campaign_id': '67890',
                'sub_id': 'abc123'
            },
            'attribution_data': {
                'click_id': 'click_12345',
                'click_time': timezone.now() - timezone.timedelta(hours=2),
                'source': 'google',
                'medium': 'cpc'
            }
        }
        
        conversion = conversion_service.record_conversion(conversion_data)
        self.assertEqual(conversion.status, 'pending')
        
        # 4. Validate conversion
        validation_result = conversion_service.validate_conversion(conversion)
        self.assertTrue(validation_result['valid'])
        
        # 5. Approve conversion
        approved_conversion = conversion_service.approve_conversion(conversion)
        self.assertEqual(approved_conversion.status, 'approved')
        
        # 6. Send S2S postback
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            postback_result = postback_service.send_s2s_postback(postback, approved_conversion)
            self.assertTrue(postback_result['success'])
        
        # 7. Check pixel analytics
        pixel_analytics = pixel_service.get_pixel_analytics(pixel, days=30)
        self.assertIn('total_fires', pixel_analytics)
        self.assertIn('conversion_count', pixel_analytics)
        self.assertIn('conversion_rate', pixel_analytics)
        
        # 8. Check conversion analytics
        conversion_analytics = conversion_service.get_conversion_analytics(self.advertiser, days=30)
        self.assertIn('total_conversions', conversion_analytics)
        self.assertIn('approved_conversions', conversion_analytics)
        self.assertIn('total_revenue', conversion_analytics)
        
        # 9. Check campaign impact
        self.campaign.refresh_from_db()
        self.assertGreater(self.campaign.spend_amount, Decimal('0.00'))
        self.assertGreater(self.campaign.conversions, 0)
        
        # 10. Check offer performance
        self.offer.refresh_from_db()
        self.assertGreater(self.offer.total_conversions, 0)
        self.assertGreater(self.offer.total_payout, Decimal('0.00'))
    
    def test_fraud_detection_integration(self):
        """Test fraud detection integration."""
        # Create tracking pixel
        pixel_service = TrackingPixelService()
        pixel = pixel_service.create_tracking_pixel(
            self.advertiser,
            {
                'name': 'Fraud Test Pixel',
                'pixel_type': 'conversion',
                'description': 'Fraud test pixel',
                'target_url': 'https://example.com/thank-you',
                'status': 'active',
            }
        )
        
        # Create conversions with fraud indicators
        conversion_service = ConversionTrackingService()
        try:
            from ..services import AdvertiserFraudService
        except ImportError:
            AdvertiserFraudService = None
        
        fraud_service = AdvertiserFraudService()
        
        # Create fraud rule
        fraud_rule = fraud_service.create_fraud_rule(
            self.advertiser,
            {
                'name': 'High Velocity Rule',
                'description': 'Detect high velocity conversions',
                'rule_type': 'velocity',
                'conditions': {
                    'max_conversions_per_hour': 5,
                    'time_window': 3600
                },
                'actions': {
                    'flag_conversion': True,
                    'block_ip': False,
                    'notify_admin': True
                },
                'severity': 'medium',
                'is_active': True,
            }
        )
        
        # Create multiple conversions from same IP (should trigger fraud rule)
        for i in range(10):
            conversion = conversion_service.record_conversion({
                'conversion_id': f'conv_{i}',
                'revenue': Decimal('25.00'),
                'ip_address': '192.168.1.100',  # Same IP
                'user_agent': 'Mozilla/5.0',
                'pixel': pixel,
            })
            
            # Apply fraud rules
            fraud_result = fraud_service.apply_fraud_rules(conversion)
            
            if fraud_result['is_flagged']:
                conversion.is_flagged = True
                conversion.fraud_score = fraud_result['fraud_score']
                conversion.save()
        
        # Check fraud statistics
        fraud_stats = fraud_service.get_fraud_statistics(self.advertiser, days=30)
        self.assertIn('total_conversions', fraud_stats)
        self.assertIn('flagged_conversions', fraud_stats)
        self.assertIn('average_fraud_score', fraud_stats)
        
        # Should have flagged conversions
        self.assertGreater(fraud_stats['flagged_conversions'], 0)


class BillingIntegrationTestCase(APITestCase):
    """Integration tests for billing workflows."""
    
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
            company_size='medium',
            verification_status='verified'
        )
        
        self.billing_service = AdvertiserBillingService()
    
    def test_complete_billing_workflow(self):
        """Test complete billing workflow."""
        # 1. Fund wallet
        deposit_result = self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('1000.00'),
            'credit_card',
            'payment_12345'
        )
        
        self.assertEqual(deposit_result.status, 'completed')
        
        # 2. Create campaign and generate charges
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Billing Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('500.00'),
            daily_budget=Decimal('50.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        # Generate charges over time
        total_charges = Decimal('0.00')
        for i in range(10):
            charge_amount = Decimal('25.00')
            charge = self.billing_service.charge_funds(
                self.advertiser,
                charge_amount,
                f'Campaign spend {i+1}'
            )
            
            self.assertEqual(charge.status, 'completed')
            total_charges += charge_amount
            
            campaign.spend_amount += charge_amount
            campaign.save()
        
        # 3. Check wallet balance
        wallet = self.advertiser.wallet
        wallet.refresh_from_db()
        expected_balance = Decimal('1000.00') - total_charges
        self.assertEqual(wallet.balance, expected_balance)
        
        # 4. Generate invoice
        try:
            from ..services import AdvertiserBillingService
        except ImportError:
            AdvertiserBillingService = None
        billing_service = AdvertiserBillingService()
        
        invoice = billing_service.create_invoice(
            self.advertiser,
            timezone.now().date().replace(day=1)
        )
        
        self.assertIsNotNone(invoice)
        self.assertGreater(invoice.total_amount, Decimal('0.00'))
        
        # 5. Finalize invoice
        finalized_invoice = billing_service.finalize_invoice(invoice)
        self.assertEqual(finalized_invoice.status, 'sent')
        
        # 6. Pay invoice
        paid_invoice = billing_service.pay_invoice(
            finalized_invoice,
            'credit_card',
            'invoice_payment_12345'
        )
        
        self.assertEqual(paid_invoice.status, 'paid')
        
        # 7. Check transaction history
        transactions = billing_service.get_transaction_history(self.advertiser)
        self.assertGreater(len(transactions), 0)
        
        # 8. Check billing statistics
        stats = billing_service.get_billing_statistics(self.advertiser)
        self.assertIn('total_deposits', stats)
        self.assertIn('total_charges', stats)
        self.assertIn('net_balance', stats)
        
        self.assertEqual(stats['total_deposits'], Decimal('1000.00'))
        self.assertEqual(stats['total_charges'], total_charges)
    
    def test_auto_refill_integration(self):
        """Test auto-refill integration."""
        # Fund wallet with low amount
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('100.00')
        wallet.save()
        
        # Enable auto-refill
        try:
            from ..services import AutoRefillService
        except ImportError:
            AutoRefillService = None
        auto_refill_service = AutoRefillService()
        
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('150.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
            'max_monthly_refill': Decimal('2000.00'),
        }
        
        auto_refill_service.enable_auto_refill(wallet, refill_config)
        
        # Make charges that trigger auto-refill
        for i in range(5):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('30.00'),
                f'Campaign spend {i+1}'
            )
        
        # Check auto-refill trigger
        with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
            mock_deposit.return_value = Mock(
                id=1,
                amount=Decimal('500.00'),
                status='completed'
            )
            
            refill_result = auto_refill_service.check_auto_refill(wallet)
            
            self.assertTrue(refill_result['triggered'])
            self.assertEqual(refill_result['refill_amount'], Decimal('500.00'))
            
            mock_deposit.assert_called_once()
        
        # Check auto-refill history
        refill_history = auto_refill_service.get_auto_refill_history(wallet, days=30)
        self.assertGreater(len(refill_history), 0)
        
        # Check auto-refill statistics
        refill_stats = auto_refill_service.get_auto_refill_statistics(wallet, days=30)
        self.assertIn('total_refills', refill_stats)
        self.assertIn('total_refilled_amount', refill_stats)


class ReportingIntegrationTestCase(APITestCase):
    """Integration tests for reporting workflows."""
    
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
            company_size='medium',
            verification_status='verified'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Reporting Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        self.offer = AdvertiserOffer.objects.create(
            advertiser=self.advertiser,
            name='Reporting Test Offer',
            description='Test offer description',
            offer_type='cpa',
            payout_amount=Decimal('10.00'),
            currency='USD',
            landing_page='https://example.com/offer',
            target_countries=['US', 'CA', 'UK'],
            status='active'
        )
    
    def test_complete_reporting_workflow(self):
        """Test complete reporting workflow."""
        # 1. Generate data for reporting
        # Create conversions
        conversion_service = ConversionTrackingService()
        
        for i in range(20):
            conversion = conversion_service.record_conversion({
                'conversion_id': f'conv_{i}',
                'revenue': Decimal(str(10.00 + i)),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'campaign': self.campaign,
                'offer': self.offer,
                'custom_parameters': {
                    'country': ['US', 'CA', 'UK', 'DE', 'FR'][i % 5],
                    'device_type': ['desktop', 'mobile', 'tablet'][i % 3],
                    'source': 'google' if i % 2 == 0 else 'facebook'
                },
                'created_at': timezone.now() - timezone.timedelta(hours=i)
            })
            
            conversion_service.approve_conversion(conversion)
        
        # 2. Generate performance report
        try:
            from ..services import AdvertiserReportService
        except ImportError:
            AdvertiserReportService = None
        report_service = AdvertiserReportService()
        
        performance_report = report_service.generate_performance_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('summary', performance_report)
        self.assertIn('campaign_performance', performance_report)
        self.assertIn('offer_performance', performance_report)
        
        # 3. Generate financial report
        financial_report = report_service.generate_financial_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('revenue_summary', financial_report)
        self.assertIn('cost_analysis', financial_report)
        self.assertIn('profitability', financial_report)
        
        # 4. Generate geographic report
        geographic_report = report_service.generate_geographic_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('geographic_breakdown', geographic_report)
        self.assertIn('country_performance', geographic_report)
        
        # 5. Generate device report
        device_report = report_service.generate_device_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('device_breakdown', device_report)
        self.assertIn('device_performance', device_report)
        
        # 6. Export reports
        try:
            from ..services import ReportExportService
        except ImportError:
            ReportExportService = None
        export_service = ReportExportService()
        
        # Export to JSON
        json_export = export_service.export_to_json(
            self.advertiser,
            performance_report,
            'Performance Report'
        )
        
        self.assertTrue(json_export['success'])
        self.assertEqual(json_export['file_type'], 'json')
        
        # 7. Schedule reports
        schedule_data = {
            'report_type': 'performance',
            'frequency': 'daily',
            'recipients': ['test@example.com'],
            'format': 'pdf',
            'is_active': True,
        }
        
        schedule = report_service.schedule_report(self.advertiser, schedule_data)
        self.assertIn('schedule_id', schedule)
        
        # 8. Get report history
        report_history = report_service.get_report_history(self.advertiser, days=30)
        self.assertIsInstance(report_history, list)
        
        # 9. Test realtime dashboard
        try:
            from ..services import RealtimeDashboardService
        except ImportError:
            RealtimeDashboardService = None
        dashboard_service = RealtimeDashboardService()
        
        # Get realtime metrics
        realtime_metrics = dashboard_service.get_realtime_metrics(self.advertiser)
        self.assertIn('total_conversions', realtime_metrics)
        self.assertIn('total_revenue', realtime_metrics)
        
        # Get campaign performance
        campaign_performance = dashboard_service.get_campaign_performance(self.advertiser, hours=24)
        self.assertIn('campaigns', campaign_performance)
        
        # Get conversion trends
        conversion_trends = dashboard_service.get_conversion_trends(self.advertiser, hours=24)
        self.assertIn('hourly_data', conversion_trends)
        
        # 10. Test dashboard summary
        dashboard_summary = dashboard_service.get_dashboard_summary(self.advertiser)
        self.assertIn('overview', dashboard_summary)
        self.assertIn('performance', dashboard_summary)
        self.assertIn('trends', dashboard_summary)


class SystemIntegrationTestCase(APITestCase):
    """Integration tests for system-wide workflows."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )
    
    def test_complete_advertiser_portal_workflow(self):
        """Test complete advertiser portal workflow."""
        # 1. Advertiser registration and verification
        advertiser_data = {
            'company_name': 'Complete Test Company',
            'contact_email': 'contact@completetest.com',
            'contact_phone': '+1234567890',
            'website': 'https://completetest.com',
            'industry': 'technology',
            'company_size': 'medium',
        }
        
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-list')
        response = self.client.post(url, advertiser_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        advertiser = Advertiser.objects.get(pk=response.data['id'])
        
        # 2. Complete verification
        verification_data = {
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'status': 'pending',
        }
        
        url = reverse('advertiserverification-list')
        response = self.client.post(url, verification_data, format='json')
        
        # Approve as staff
        self.client.force_authenticate(user=self.staff_user)
        verification = AdvertiserVerification.objects.get(advertiser=advertiser)
        url = reverse('advertiserverification-approve', kwargs={'pk': verification.pk})
        response = self.client.post(url, {}, format='json')
        
        # 3. Fund wallet
        wallet_data = {
            'amount': '5000.00',
            'payment_method': 'credit_card',
            'payment_reference': 'initial_funding'
        }
        
        self.client.force_authenticate(user=self.user)
        url = reverse('wallet-deposit', kwargs={'pk': advertiser.wallet.pk})
        response = self.client.post(url, wallet_data, format='json')
        
        # 4. Create multiple campaigns
        campaigns = []
        for i in range(3):
            campaign_data = {
                'name': f'Campaign {i+1}',
                'campaign_type': ['display', 'video', 'native'][i],
                'budget_limit': '1000.00',
                'daily_budget': '100.00',
                'start_date': timezone.now().date(),
                'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
            }
            
            url = reverse('campaign-list')
            response = self.client.post(url, campaign_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            campaigns.append(AdCampaign.objects.get(pk=response.data['id']))
            
            # Start campaign
            url = reverse('campaign-start', kwargs={'pk': campaigns[i].pk})
            response = self.client.post(url, {}, format='json')
        
        # 5. Create offers
        offers = []
        for i in range(2):
            offer_data = {
                'name': f'Offer {i+1}',
                'offer_type': 'cpa',
                'payout_amount': '15.00',
                'landing_page': f'https://example.com/offer{i+1}',
                'target_countries': ['US', 'CA'],
                'tracking_method': 'postback',
            }
            
            url = reverse('offer-list')
            response = self.client.post(url, offer_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            offers.append(AdvertiserOffer.objects.get(pk=response.data['id']))
            
            # Submit and approve
            url = reverse('offer-submit-for-review', kwargs={'pk': offers[i].pk})
            response = self.client.post(url, {}, format='json')
            
            self.client.force_authenticate(user=self.staff_user)
            url = reverse('offer-approve', kwargs={'pk': offers[i].pk})
            response = self.client.post(url, {}, format='json')
            
            self.client.force_authenticate(user=self.user)
            url = reverse('offer-publish', kwargs={'pk': offers[i].pk})
            response = self.client.post(url, {}, format='json')
        
        # 6. Set up tracking
        tracking_service = TrackingPixelService()
        pixels = []
        
        for i, offer in enumerate(offers):
            pixel = tracking_service.create_tracking_pixel(
                advertiser,
                {
                    'name': f'Pixel for {offer.name}',
                    'pixel_type': 'conversion',
                    'target_url': offer.landing_page,
                    'status': 'active',
                }
            )
            pixels.append(pixel)
        
        # 7. Generate conversions and revenue
        conversion_service = ConversionTrackingService()
        total_revenue = Decimal('0.00')
        
        for i in range(50):
            campaign = campaigns[i % len(campaigns)]
            offer = offers[i % len(offers)]
            pixel = pixels[i % len(pixels)]
            
            conversion = conversion_service.record_conversion({
                'conversion_id': f'conv_{i}',
                'revenue': Decimal(str(20.00 + (i % 10))),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'campaign': campaign,
                'offer': offer,
                'pixel': pixel,
                'custom_parameters': {
                    'country': ['US', 'CA', 'UK'][i % 3],
                    'device_type': ['desktop', 'mobile'][i % 2],
                    'source': 'google' if i % 3 == 0 else ('facebook' if i % 3 == 1 else 'email')
                },
                'created_at': timezone.now() - timezone.timedelta(hours=i)
            })
            
            conversion_service.approve_conversion(conversion)
            total_revenue += conversion.revenue
        
        # 8. Generate comprehensive reports
        try:
            from ..services import AdvertiserReportService
        except ImportError:
            AdvertiserReportService = None
        report_service = AdvertiserReportService()
        
        # Performance report
        performance_report = report_service.generate_performance_report(
            advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        # Financial report
        financial_report = report_service.generate_financial_report(
            advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        # 9. Check system health
        try:
            from ..services import RealtimeDashboardService
        except ImportError:
            RealtimeDashboardService = None
        dashboard_service = RealtimeDashboardService()
        
        dashboard_summary = dashboard_service.get_dashboard_summary(advertiser)
        
        # 10. Verify complete workflow
        self.assertEqual(advertiser.verification_status, 'verified')
        self.assertEqual(advertiser.wallet.balance, Decimal('5000.00'))
        self.assertEqual(len(campaigns), 3)
        self.assertEqual(len(offers), 2)
        self.assertEqual(len(pixels), 2)
        
        # Check campaign status
        for campaign in campaigns:
            campaign.refresh_from_db()
            self.assertEqual(campaign.status, 'active')
            self.assertGreater(campaign.spend_amount, Decimal('0.00'))
        
        # Check offer status
        for offer in offers:
            offer.refresh_from_db()
            self.assertEqual(offer.status, 'active')
            self.assertGreater(offer.total_conversions, 0)
        
        # Check report data
        self.assertGreater(performance_report['summary']['total_conversions'], 0)
        self.assertGreater(performance_report['summary']['total_revenue'], Decimal('0.00'))
        
        # Check dashboard data
        self.assertGreater(dashboard_summary['overview']['total_conversions'], 0)
        self.assertGreater(dashboard_summary['overview']['total_revenue'], Decimal('0.00'))
        
        # 11. Test API endpoints
        # Get advertiser details
        url = reverse('advertiser-detail', kwargs={'pk': advertiser.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get campaign list
        url = reverse('campaign-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        
        # Get offer list
        url = reverse('offer-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Get conversion analytics
        url = reverse('conversion-analytics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analytics', response.data)
        
        # Get wallet details
        url = reverse('wallet-detail', kwargs={'pk': advertiser.wallet.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['balance'], '5000.00')
        
        print(f"Complete workflow test passed:")
        print(f"  - Advertiser: {advertiser.company_name}")
        print(f"  - Campaigns: {len(campaigns)}")
        print(f"  - Offers: {len(offers)}")
        print(f"  - Conversions: {performance_report['summary']['total_conversions']}")
        print(f"  - Revenue: {performance_report['summary']['total_revenue']}")
        print(f"  - Wallet Balance: {advertiser.wallet.balance}")
