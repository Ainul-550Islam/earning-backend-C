"""
Test Views

Comprehensive tests for API viewsets and endpoints
including permissions, authentication, and response handling.
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

User = get_user_model()


class AdvertiserViewSetTestCase(APITestCase):
    """Test cases for AdvertiserViewSet."""
    
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
            'company_name': 'New Company',
            'contact_email': 'new@company.com',
            'contact_phone': '+1234567890',
            'website': 'https://newcompany.com',
            'industry': 'finance',
            'company_size': 'large',
        }
    
    def test_list_advertisers_unauthorized(self):
        """Test listing advertisers without authentication."""
        url = reverse('advertiser-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_advertisers_authorized(self):
        """Test listing advertisers with authentication."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['company_name'], 'Test Company')
    
    def test_list_advertisers_staff(self):
        """Test listing all advertisers as staff user."""
        # Create additional advertiser
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        other_advertiser = Advertiser.objects.create(
            user=other_user,
            company_name='Other Company',
            contact_email='contact@othercompany.com',
            contact_phone='+1234567890',
            website='https://othercompany.com',
            industry='technology',
            company_size='small'
        )
        
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('advertiser-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_create_advertiser_success(self):
        """Test successful advertiser creation."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['company_name'], 'New Company')
        self.assertEqual(response.data['verification_status'], 'pending')
    
    def test_create_advertiser_unauthorized(self):
        """Test advertiser creation without authentication."""
        url = reverse('advertiser-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_advertiser_invalid_data(self):
        """Test advertiser creation with invalid data."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-list')
        
        invalid_data = self.valid_data.copy()
        invalid_data['company_name'] = ''  # Empty name
        
        response = self.client.post(url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('company_name', response.data)
    
    def test_retrieve_advertiser_success(self):
        """Test successful advertiser retrieval."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['company_name'], 'Test Company')
    
    def test_retrieve_advertiser_unauthorized(self):
        """Test advertiser retrieval without authentication."""
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_retrieve_advertiser_not_owner(self):
        """Test advertiser retrieval by non-owner."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        self.client.force_authenticate(user=other_user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_advertiser_success(self):
        """Test successful advertiser update."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        
        update_data = {
            'company_name': 'Updated Company',
            'industry': 'finance'
        }
        
        response = self.client.patch(url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['company_name'], 'Updated Company')
        self.assertEqual(response.data['industry'], 'finance')
    
    def test_update_advertiser_unauthorized(self):
        """Test advertiser update without authentication."""
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        
        update_data = {
            'company_name': 'Updated Company'
        }
        
        response = self.client.patch(url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_delete_advertiser_success(self):
        """Test successful advertiser deletion."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        with self.assertRaises(Advertiser.DoesNotExist):
            Advertiser.objects.get(pk=self.advertiser.pk)
    
    def test_delete_advertiser_unauthorized(self):
        """Test advertiser deletion without authentication."""
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_advertiser_statistics_action(self):
        """Test advertiser statistics action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-statistics', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
    
    def test_advertiser_suspend_action(self):
        """Test advertiser suspend action."""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('advertiser-suspend', kwargs={'pk': self.advertiser.pk})
        
        suspend_data = {
            'reason': 'Policy violation'
        }
        
        response = self.client.post(url, suspend_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'suspended')
    
    def test_advertiser_suspend_action_non_staff(self):
        """Test advertiser suspend action by non-staff user."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-suspend', kwargs={'pk': self.advertiser.pk})
        
        suspend_data = {
            'reason': 'Policy violation'
        }
        
        response = self.client.post(url, suspend_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdCampaignViewSetTestCase(APITestCase):
    """Test cases for AdCampaignViewSet."""
    
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
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='draft'
        )
        
        self.valid_data = {
            'name': 'New Campaign',
            'description': 'New campaign description',
            'campaign_type': 'video',
            'budget_limit': '500.00',
            'daily_budget': '50.00',
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
            'target_ctr': '2.0',
            'target_cpa': '5.0',
        }
    
    def test_list_campaigns_success(self):
        """Test successful campaign listing."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Campaign')
    
    def test_create_campaign_success(self):
        """Test successful campaign creation."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Campaign')
        self.assertEqual(response.data['status'], 'draft')
    
    def test_create_campaign_insufficient_balance(self):
        """Test campaign creation with insufficient balance."""
        # Set wallet balance to 0
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('0.00')
        wallet.save()
        
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient wallet balance', str(response.data))
    
    def test_start_campaign_action(self):
        """Test campaign start action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-start', kwargs={'pk': self.campaign.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
    
    def test_pause_campaign_action(self):
        """Test campaign pause action."""
        # Start campaign first
        self.campaign.status = 'active'
        self.campaign.save()
        
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-pause', kwargs={'pk': self.campaign.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'paused')
    
    def test_campaign_statistics_action(self):
        """Test campaign statistics action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-statistics', kwargs={'pk': self.campaign.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
    
    def test_clone_campaign_action(self):
        """Test campaign clone action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-clone', kwargs={'pk': self.campaign.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cloned_campaign', response.data)
        
        # Verify cloned campaign
        cloned_campaign = response.data['cloned_campaign']
        self.assertEqual(cloned_campaign['name'], 'Test Campaign (Clone)')
        self.assertEqual(cloned_campaign['status'], 'draft')


class AdvertiserOfferViewSetTestCase(APITestCase):
    """Test cases for AdvertiserOfferViewSet."""
    
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
        
        self.offer = AdvertiserOffer.objects.create(
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
        
        self.valid_data = {
            'name': 'New Offer',
            'description': 'New offer description',
            'offer_type': 'cps',
            'payout_amount': '15.00',
            'currency': 'USD',
            'landing_page': 'https://example.com/new-offer',
            'target_countries': ['US', 'CA'],
            'tracking_method': 'postback',
            'cookie_duration': 30,
        }
    
    def test_list_offers_success(self):
        """Test successful offer listing."""
        self.client.force_authenticate(user=self.user)
        url = reverse('offer-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Offer')
    
    def test_create_offer_success(self):
        """Test successful offer creation."""
        self.client.force_authenticate(user=self.user)
        url = reverse('offer-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Offer')
        self.assertEqual(response.data['status'], 'draft')
    
    def test_submit_for_review_action(self):
        """Test offer submit for review action."""
        # Add requirement first
        OfferRequirement.objects.create(
            offer=self.offer,
            requirement_type='minimum_age',
            value='18',
            description='Users must be 18 or older'
        )
        
        self.client.force_authenticate(user=self.user)
        url = reverse('offer-submit-for-review', kwargs={'pk': self.offer.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'pending_review')
    
    def test_approve_offer_action(self):
        """Test offer approve action (staff only)."""
        staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )
        
        # Submit for review first
        self.offer.status = 'pending_review'
        self.offer.save()
        
        self.client.force_authenticate(user=staff_user)
        url = reverse('offer-approve', kwargs={'pk': self.offer.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'approved')
    
    def test_approve_offer_action_non_staff(self):
        """Test offer approve action by non-staff user."""
        self.client.force_authenticate(user=self.user)
        url = reverse('offer-approve', kwargs={'pk': self.offer.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_publish_offer_action(self):
        """Test offer publish action."""
        # Approve offer first
        self.offer.status = 'approved'
        self.offer.save()
        
        self.client.force_authenticate(user=self.user)
        url = reverse('offer-publish', kwargs={'pk': self.offer.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
        self.assertTrue(response.data['is_published'])


class TrackingPixelViewSetTestCase(APITestCase):
    """Test cases for TrackingPixelViewSet."""
    
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
            pixel_code='pixel_12345',
            status='active'
        )
        
        self.valid_data = {
            'name': 'New Pixel',
            'pixel_type': 'impression',
            'description': 'New impression pixel',
            'target_url': 'https://example.com/impression',
            'status': 'active',
        }
    
    def test_list_pixels_success(self):
        """Test successful pixel listing."""
        self.client.force_authenticate(user=self.user)
        url = reverse('trackingpixel-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Pixel')
    
    def test_create_pixel_success(self):
        """Test successful pixel creation."""
        self.client.force_authenticate(user=self.user)
        url = reverse('trackingpixel-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Pixel')
        self.assertEqual(response.data['pixel_type'], 'impression')
        self.assertIsNotNone(response.data['pixel_code'])
    
    def test_test_pixel_action(self):
        """Test pixel test action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('trackingpixel-test', kwargs={'pk': self.pixel.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('test_url', response.data)
        self.assertIn('pixel_code', response.data)
    
    def test_pixel_analytics_action(self):
        """Test pixel analytics action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('trackingpixel-analytics', kwargs={'pk': self.pixel.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analytics', response.data)
    
    def test_get_pixel_code_action(self):
        """Test get pixel code action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('trackingpixel-get-code', kwargs={'pk': self.pixel.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('pixel_code', response.data)
        self.assertIn('pixel_url', response.data)


class AdvertiserWalletViewSetTestCase(APITestCase):
    """Test cases for AdvertiserWalletViewSet."""
    
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
    
    def test_get_wallet_success(self):
        """Test successful wallet retrieval."""
        self.client.force_authenticate(user=self.user)
        url = reverse('wallet-detail', kwargs={'pk': self.wallet.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['balance'], '1000.00')
        self.assertEqual(response.data['credit_limit'], '2000.00')
        self.assertIn('available_balance', response.data)
    
    def test_deposit_funds_action(self):
        """Test deposit funds action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('wallet-deposit', kwargs={'pk': self.wallet.pk})
        
        deposit_data = {
            'amount': '500.00',
            'payment_method': 'credit_card',
            'payment_reference': 'payment_12345'
        }
        
        response = self.client.post(url, deposit_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('transaction', response.data)
        
        # Check updated balance
        updated_wallet = AdvertiserWallet.objects.get(pk=self.wallet.pk)
        self.assertEqual(updated_wallet.balance, Decimal('1500.00'))
    
    def test_get_transaction_history_action(self):
        """Test get transaction history action."""
        # Create some transactions
        for i in range(3):
            AdvertiserTransaction.objects.create(
                advertiser=self.advertiser,
                transaction_type='deposit',
                amount=Decimal('100.00'),
                payment_method='credit_card',
                payment_reference=f'payment_{i}',
                status='completed'
            )
        
        self.client.force_authenticate(user=self.user)
        url = reverse('wallet-transactions', kwargs={'pk': self.wallet.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
    
    def test_get_wallet_statistics_action(self):
        """Test get wallet statistics action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('wallet-statistics', kwargs={'pk': self.wallet.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)


class ConversionViewSetTestCase(APITestCase):
    """Test cases for ConversionViewSet."""
    
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
        
        self.conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            pixel=self.pixel,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            status='pending'
        )
    
    def test_list_conversions_success(self):
        """Test successful conversion listing."""
        self.client.force_authenticate(user=self.user)
        url = reverse('conversion-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['conversion_id'], 'conv_12345')
    
    def test_approve_conversion_action(self):
        """Test approve conversion action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('conversion-approve', kwargs={'pk': self.conversion.pk})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'approved')
    
    def test_reject_conversion_action(self):
        """Test reject conversion action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('conversion-reject', kwargs={'pk': self.conversion.pk})
        
        reject_data = {
            'reason': 'Invalid conversion'
        }
        
        response = self.client.post(url, reject_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'rejected')
        self.assertEqual(response.data['rejection_reason'], 'Invalid conversion')
    
    def test_bulk_approve_conversions_action(self):
        """Test bulk approve conversions action."""
        # Create additional conversions
        for i in range(2):
            Conversion.objects.create(
                advertiser=self.advertiser,
                pixel=self.pixel,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                status='pending'
            )
        
        self.client.force_authenticate(user=self.user)
        url = reverse('conversion-bulk-approve')
        
        bulk_data = {
            'conversion_ids': ['conv_0', 'conv_1']
        }
        
        response = self.client.post(url, bulk_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['approved_count'], 2)
    
    def test_get_conversion_analytics_action(self):
        """Test get conversion analytics action."""
        self.client.force_authenticate(user=self.user)
        url = reverse('conversion-analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analytics', response.data)


class PermissionTestCase(APITestCase):
    """Test cases for API permissions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
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
    
    def test_owner_can_access_own_resources(self):
        """Test that owner can access their own resources."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_non_owner_cannot_access_others_resources(self):
        """Test that non-owner cannot access others' resources."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_staff_can_access_all_resources(self):
        """Test that staff can access all resources."""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_unauthenticated_cannot_access_resources(self):
        """Test that unauthenticated users cannot access resources."""
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_owner_can_update_own_resources(self):
        """Test that owner can update their own resources."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        
        update_data = {
            'company_name': 'Updated Company'
        }
        
        response = self.client.patch(url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['company_name'], 'Updated Company')
    
    def test_non_owner_cannot_update_others_resources(self):
        """Test that non-owner cannot update others' resources."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        
        update_data = {
            'company_name': 'Updated Company'
        }
        
        response = self.client.patch(url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_owner_can_delete_own_resources(self):
        """Test that owner can delete their own resources."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_non_owner_cannot_delete_others_resources(self):
        """Test that non-owner cannot delete others' resources."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PaginationTestCase(APITestCase):
    """Test cases for API pagination."""
    
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
        
        # Create multiple campaigns
        for i in range(25):
            AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'Campaign {i}',
                campaign_type='display',
                budget_limit=Decimal('100.00'),
                daily_budget=Decimal('10.00'),
                start_date=timezone.now().date(),
                end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
                status='draft'
            )
    
    def test_pagination_default_page_size(self):
        """Test default pagination page size."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        
        # Default page size should be 20
        self.assertEqual(len(response.data['results']), 20)
        self.assertEqual(response.data['count'], 25)
    
    def test_pagination_custom_page_size(self):
        """Test custom pagination page size."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.get(url, {'page_size': 10})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['count'], 25)
    
    def test_pagination_page_navigation(self):
        """Test pagination page navigation."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        
        # Get first page
        response = self.client.get(url, {'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        
        # Get second page
        next_url = response.data['next']
        response = self.client.get(next_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        
        # Get third page
        next_url = response.data['next']
        response = self.client.get(next_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
        # No next page
        self.assertIsNone(response.data['next'])


class FilteringTestCase(APITestCase):
    """Test cases for API filtering."""
    
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
        
        # Create campaigns with different statuses
        statuses = ['draft', 'active', 'paused', 'ended']
        for i, status in enumerate(statuses):
            AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'Campaign {status}',
                campaign_type='display',
                budget_limit=Decimal('100.00'),
                daily_budget=Decimal('10.00'),
                start_date=timezone.now().date(),
                end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
                status=status
            )
    
    def test_filter_by_status(self):
        """Test filtering by status."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.get(url, {'status': 'active'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'active')
    
    def test_filter_by_multiple_statuses(self):
        """Test filtering by multiple statuses."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.get(url, {'status': 'active,draft'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        statuses = [c['status'] for c in response.data['results']]
        self.assertIn('active', statuses)
        self.assertIn('draft', statuses)
    
    def test_filter_by_campaign_type(self):
        """Test filtering by campaign type."""
        # Create campaigns with different types
        types = ['display', 'video', 'native']
        for campaign_type in types:
            AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'{campaign_type.title()} Campaign',
                campaign_type=campaign_type,
                budget_limit=Decimal('100.00'),
                daily_budget=Decimal('10.00'),
                start_date=timezone.now().date(),
                end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
                status='draft'
            )
        
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.get(url, {'campaign_type': 'video'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['campaign_type'], 'video')
    
    def test_search_filtering(self):
        """Test search filtering."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        response = self.client.get(url, {'search': 'active'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'active')
    
    def test_date_range_filtering(self):
        """Test date range filtering."""
        # Create campaigns with different dates
        past_date = timezone.now().date() - timezone.timedelta(days=10)
        future_date = timezone.now().date() + timezone.timedelta(days=10)
        
        AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Past Campaign',
            campaign_type='display',
            budget_limit=Decimal('100.00'),
            daily_budget=Decimal('10.00'),
            start_date=past_date,
            end_date=past_date + timezone.timedelta(days=30),
            status='draft'
        )
        
        AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Future Campaign',
            campaign_type='display',
            budget_limit=Decimal('100.00'),
            daily_budget=Decimal('10.00'),
            start_date=future_date,
            end_date=future_date + timezone.timedelta(days=30),
            status='draft'
        )
        
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        
        # Filter by start date
        response = self.client.get(url, {'start_date_after': past_date})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should include campaigns starting from past_date onwards
        campaign_names = [c['name'] for c in response.data['results']]
        self.assertIn('Future Campaign', campaign_names)
        
        # Filter by end date
        response = self.client.get(url, {'end_date_before': future_date})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should include campaigns ending before future_date
        campaign_names = [c['name'] for c in response.data['results']]
        self.assertIn('Past Campaign', campaign_names)


class ErrorHandlingTestCase(APITestCase):
    """Test cases for API error handling."""
    
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
    
    def test_404_not_found(self):
        """Test 404 not found error."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_400_bad_request(self):
        """Test 400 bad request error."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        
        invalid_data = {
            'name': '',  # Empty name
            'campaign_type': 'invalid_type',
            'budget_limit': '-100.00'
        }
        
        response = self.client.post(url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
        self.assertIn('campaign_type', response.data)
        self.assertIn('budget_limit', response.data)
    
    def test_403_forbidden(self):
        """Test 403 forbidden error."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        self.client.force_authenticate(user=other_user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_401_unauthorized(self):
        """Test 401 unauthorized error."""
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_validation_error_format(self):
        """Test validation error format."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        
        invalid_data = {
            'name': '',
            'campaign_type': 'invalid_type',
            'budget_limit': '-100.00',
            'daily_budget': '200.00',  # Higher than budget limit
            'start_date': '2023-01-01',
            'end_date': '2022-12-31'  # End before start
        }
        
        response = self.client.post(url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check error format
        errors = response.data
        self.assertIsInstance(errors, dict)
        
        # Check that all fields have errors
        self.assertIn('name', errors)
        self.assertIn('campaign_type', errors)
        self.assertIn('budget_limit', errors)
        self.assertIn('daily_budget', errors)
        self.assertIn('end_date', errors)
        
        # Check error messages are meaningful
        self.assertIn('required', str(errors['name']))
        self.assertIn('valid', str(errors['campaign_type']))
        self.assertIn('positive', str(errors['budget_limit']))
    
    def test_method_not_allowed(self):
        """Test method not allowed error."""
        self.client.force_authenticate(user=self.user)
        url = reverse('advertiser-detail', kwargs={'pk': self.advertiser.pk})
        response = self.client.put(url, {}, format='json')
        
        # Assuming PUT is not allowed, only PATCH
        if response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_server_error_handling(self):
        """Test server error handling."""
        self.client.force_authenticate(user=self.user)
        url = reverse('campaign-list')
        
        # Mock a server error
        with patch('api.advertiser_portal.viewsets.AdCampaignViewSet.create') as mock_create:
            mock_create.side_effect = Exception('Internal server error')
            
            response = self.client.post(url, {}, format='json')
            
            # Should return 500 for unhandled exceptions
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
