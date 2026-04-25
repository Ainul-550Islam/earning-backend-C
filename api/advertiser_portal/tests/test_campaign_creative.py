"""
Test Campaign Creative Service

Comprehensive tests for campaign creative functionality
including creative management, optimization, and performance tracking.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from unittest.mock import Mock, patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile

from ..models.campaign import AdCampaign, CampaignCreative
from ..models.advertiser import Advertiser
try:
    from ..services import CampaignService
except ImportError:
    CampaignService = None
from ..serializers import CampaignCreativeSerializer

User = get_user_model()


class CampaignCreativeServiceTestCase(APITestCase):
    """Test cases for campaign creative service."""
    
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
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            description='Test campaign description',
            status='active'
        )
        
        self.campaign_service = CampaignService()
    
    def test_create_campaign_creative(self):
        """Test creating a campaign creative."""
        # Create test image file
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative_data = {
            'campaign': self.campaign,
            'creative_type': 'banner',
            'name': 'Test Banner',
            'description': 'Test banner creative',
            'creative_file': image_file,
            'width': 300,
            'height': 250,
            'click_url': 'https://example.com/click',
            'impression_url': 'https://example.com/impression',
            'status': 'active'
        }
        
        creative = CampaignCreative.objects.create(**creative_data)
        
        self.assertEqual(creative.campaign, self.campaign)
        self.assertEqual(creative.creative_type, 'banner')
        self.assertEqual(creative.name, 'Test Banner')
        self.assertEqual(creative.width, 300)
        self.assertEqual(creative.height, 250)
        self.assertEqual(creative.click_url, 'https://example.com/click')
        self.assertEqual(creative.status, 'active')
    
    def test_update_campaign_creative(self):
        """Test updating a campaign creative."""
        # Create creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        # Update creative
        creative.name = 'Updated Banner'
        creative.click_url = 'https://updated-example.com/click'
        creative.status = 'paused'
        creative.save()
        
        creative.refresh_from_db()
        self.assertEqual(creative.name, 'Updated Banner')
        self.assertEqual(creative.click_url, 'https://updated-example.com/click')
        self.assertEqual(creative.status, 'paused')
    
    def test_creative_validation(self):
        """Test creative validation."""
        # Test invalid creative type
        with self.assertRaises(Exception):
            CampaignCreative.objects.create(
                campaign=self.campaign,
                creative_type='invalid',
                name='Test Creative'
            )
        
        # Test invalid dimensions
        with self.assertRaises(Exception):
            CampaignCreative.objects.create(
                campaign=self.campaign,
                creative_type='banner',
                name='Test Creative',
                width=-1,
                height=-1
            )
    
    def test_creative_performance_tracking(self):
        """Test creative performance tracking."""
        # Create creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        # Track performance
        performance = creative.get_performance_metrics()
        
        self.assertIn('impressions', performance)
        self.assertIn('clicks', performance)
        self.assertIn('conversions', performance)
        self.assertIn('ctr', performance)
        self.assertIn('conversion_rate', performance)
    
    def test_creative_optimization(self):
        """Test creative optimization."""
        # Create creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        # Simulate performance data
        performance_data = {
            'impressions': 1000,
            'clicks': 20,
            'conversions': 2,
            'ctr': 0.02,
            'conversion_rate': 0.10
        }
        
        # Optimize creative
        optimization_result = self.campaign_service.optimize_creative(creative, performance_data)
        
        self.assertIsNotNone(optimization_result)
        self.assertIn('recommendations', optimization_result)
        self.assertIn('performance_score', optimization_result)
    
    def test_creative_a_b_testing(self):
        """Test creative A/B testing."""
        # Create multiple creatives
        creatives = []
        for i in range(2):
            image_file = SimpleUploadedFile(
                f"test_image_{i}.jpg",
                b"fake_image_data",
                content_type="image/jpeg"
            )
            
            creative = CampaignCreative.objects.create(
                campaign=self.campaign,
                creative_type='banner',
                name=f'Test Banner {i}',
                creative_file=image_file,
                width=300,
                height=250,
                status='active'
            )
            creatives.append(creative)
        
        # Simulate A/B test results
        test_results = {
            'creative_0': {
                'impressions': 1000,
                'clicks': 20,
                'conversions': 2,
                'ctr': 0.02,
                'conversion_rate': 0.10
            },
            'creative_1': {
                'impressions': 1000,
                'clicks': 30,
                'conversions': 3,
                'ctr': 0.03,
                'conversion_rate': 0.10
            }
        }
        
        # Analyze A/B test
        winning_creative = self.campaign_service.analyze_creative_ab_test(creatives, test_results)
        
        self.assertIsNotNone(winning_creative)
        self.assertIn(winning_creative, creatives)
    
    def test_creative_compliance_check(self):
        """Test creative compliance checking."""
        # Create creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        # Check compliance
        compliance_result = self.campaign_service.check_creative_compliance(creative)
        
        self.assertIsNotNone(compliance_result)
        self.assertIn('is_compliant', compliance_result)
        self.assertIn('issues', compliance_result)
        self.assertIn('recommendations', compliance_result)
    
    def test_creative_expiry_management(self):
        """Test creative expiry management."""
        # Create creative with expiry date
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        expiry_date = timezone.now() + timezone.timedelta(days=7)
        
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            end_date=expiry_date,
            status='active'
        )
        
        # Check expiry status
        is_expiring_soon = creative.is_expiring_soon()
        is_expired = creative.is_expired()
        
        self.assertFalse(is_expired)  # Should not be expired yet
        # is_expiring_soon depends on the implementation
    
    def test_creative_file_validation(self):
        """Test creative file validation."""
        # Test invalid file type
        invalid_file = SimpleUploadedFile(
            "test_file.txt",
            b"fake_text_data",
            content_type="text/plain"
        )
        
        with self.assertRaises(Exception):
            CampaignCreative.objects.create(
                campaign=self.campaign,
                creative_type='banner',
                name='Test Creative',
                creative_file=invalid_file
            )
        
        # Test file size limit
        large_file = SimpleUploadedFile(
            "large_image.jpg",
            b"x" * (10 * 1024 * 1024 + 1),  # Over 10MB
            content_type="image/jpeg"
        )
        
        with self.assertRaises(Exception):
            CampaignCreative.objects.create(
                campaign=self.campaign,
                creative_type='banner',
                name='Test Creative',
                creative_file=large_file
            )
    
    def test_creative_third_party_tracking(self):
        """Test creative third-party tracking."""
        # Create creative with third-party tracking
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            third_party_tracking={
                'click_trackers': ['https://tracker1.com/click', 'https://tracker2.com/click'],
                'impression_trackers': ['https://tracker1.com/impression', 'https://tracker2.com/impression'],
                'conversion_trackers': ['https://tracker1.com/conversion']
            },
            status='active'
        )
        
        # Verify third-party tracking
        self.assertIn('click_trackers', creative.third_party_tracking)
        self.assertIn('impression_trackers', creative.third_party_tracking)
        self.assertIn('conversion_trackers', creative.third_party_tracking)
        self.assertEqual(len(creative.third_party_tracking['click_trackers']), 2)
    
    def test_creative_rotation(self):
        """Test creative rotation."""
        # Create multiple creatives
        creatives = []
        for i in range(3):
            image_file = SimpleUploadedFile(
                f"test_image_{i}.jpg",
                b"fake_image_data",
                content_type="image/jpeg"
            )
            
            creative = CampaignCreative.objects.create(
                campaign=self.campaign,
                creative_type='banner',
                name=f'Test Banner {i}',
                creative_file=image_file,
                width=300,
                height=250,
                status='active',
                weight=1
            )
            creatives.append(creative)
        
        # Test rotation logic
        selected_creative = self.campaign_service.select_creative_for_rotation(creatives)
        
        self.assertIsNotNone(selected_creative)
        self.assertIn(selected_creative, creatives)
    
    def test_creative_performance_prediction(self):
        """Test creative performance prediction."""
        # Create creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        # Predict performance
        predicted_performance = self.campaign_service.predict_creative_performance(creative)
        
        self.assertIn('predicted_ctr', predicted_performance)
        self.assertIn('predicted_cvr', predicted_performance)
        self.assertIn('confidence_score', predicted_performance)


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
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            description='Test campaign description',
            status='active'
        )
        
        # Create test creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        self.creative = CampaignCreative.objects.create(
            campaign=self.campaign,
            creative_type='banner',
            name='Test Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
    
    def test_creative_serialization(self):
        """Test creative serialization."""
        serializer = CampaignCreativeSerializer(self.creative)
        
        data = serializer.data
        
        self.assertEqual(data['campaign'], self.campaign.id)
        self.assertEqual(data['creative_type'], 'banner')
        self.assertEqual(data['name'], 'Test Banner')
        self.assertEqual(data['width'], 300)
        self.assertEqual(data['height'], 250)
        self.assertEqual(data['status'], 'active')
    
    def test_creative_deserialization(self):
        """Test creative deserialization."""
        image_file = SimpleUploadedFile(
            "new_test_image.jpg",
            b"new_fake_image_data",
            content_type="image/jpeg"
        )
        
        data = {
            'campaign': self.campaign.id,
            'creative_type': 'video',
            'name': 'Test Video',
            'creative_file': image_file,
            'width': 640,
            'height': 480,
            'click_url': 'https://example.com/click',
            'status': 'active'
        }
        
        serializer = CampaignCreativeSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        creative = serializer.save()
        
        self.assertEqual(creative.creative_type, 'video')
        self.assertEqual(creative.name, 'Test Video')
        self.assertEqual(creative.width, 640)
        self.assertEqual(creative.height, 480)
        self.assertEqual(creative.click_url, 'https://example.com/click')
    
    def test_creative_validation(self):
        """Test creative validation in serializer."""
        # Test invalid creative type
        data = {
            'campaign': self.campaign.id,
            'creative_type': 'invalid',
            'name': 'Test Creative'
        }
        
        serializer = CampaignCreativeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('creative_type', serializer.errors)
        
        # Test invalid dimensions
        data = {
            'campaign': self.campaign.id,
            'creative_type': 'banner',
            'name': 'Test Creative',
            'width': -1,
            'height': -1
        }
        
        serializer = CampaignCreativeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('width', serializer.errors)
        self.assertIn('height', serializer.errors)
    
    def test_creative_update_serialization(self):
        """Test creative update serialization."""
        data = {
            'name': 'Updated Banner',
            'click_url': 'https://updated-example.com/click',
            'status': 'paused'
        }
        
        serializer = CampaignCreativeSerializer(instance=self.creative, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_creative = serializer.save()
        
        self.assertEqual(updated_creative.name, 'Updated Banner')
        self.assertEqual(updated_creative.click_url, 'https://updated-example.com/click')
        self.assertEqual(updated_creative.status, 'paused')


class CampaignCreativeIntegrationTestCase(APITestCase):
    """Integration tests for campaign creatives."""
    
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
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.campaign_service = CampaignService()
    
    def test_complete_creative_lifecycle(self):
        """Test complete creative lifecycle."""
        # 1. Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Creative Lifecycle Campaign',
            description='Testing creative lifecycle',
            status='active'
        )
        
        # 2. Create creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=campaign,
            creative_type='banner',
            name='Lifecycle Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        # 3. Track performance
        performance_data = {
            'impressions': 1000,
            'clicks': 20,
            'conversions': 2,
            'ctr': 0.02,
            'conversion_rate': 0.10
        }
        
        # 4. Optimize creative
        optimization_result = self.campaign_service.optimize_creative(creative, performance_data)
        
        # 5. Update creative based on optimization
        if optimization_result.get('recommendations'):
            # Apply recommendations
            creative.status = 'optimized'
            creative.save()
        
        # Verify results
        creative.refresh_from_db()
        self.assertIsNotNone(optimization_result)
        self.assertEqual(creative.status, 'optimized')
    
    def test_multiple_creative_management(self):
        """Test managing multiple creatives."""
        # Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Multi Creative Campaign',
            description='Testing multiple creatives',
            status='active'
        )
        
        # Create multiple creatives
        creatives = []
        for i in range(3):
            image_file = SimpleUploadedFile(
                f"test_image_{i}.jpg",
                b"fake_image_data",
                content_type="image/jpeg"
            )
            
            creative = CampaignCreative.objects.create(
                campaign=campaign,
                creative_type='banner',
                name=f'Test Banner {i}',
                creative_file=image_file,
                width=300,
                height=250,
                status='active',
                weight=1
            )
            creatives.append(creative)
        
        # Test rotation
        selected_creatives = []
        for _ in range(10):
            selected = self.campaign_service.select_creative_for_rotation(creatives)
            selected_creatives.append(selected)
        
        # Verify all creatives were selected
        for creative in creatives:
            self.assertIn(creative, selected_creatives)
        
        # Test A/B testing
        test_results = {}
        for i, creative in enumerate(creatives):
            test_results[f'creative_{i}'] = {
                'impressions': 1000,
                'clicks': 20 + i * 5,
                'conversions': 2 + i,
                'ctr': 0.02 + i * 0.005,
                'conversion_rate': 0.10
            }
        
        winning_creative = self.campaign_service.analyze_creative_ab_test(creatives, test_results)
        
        self.assertIsNotNone(winning_creative)
        self.assertIn(winning_creative, creatives)
    
    def test_creative_budget_integration(self):
        """Test creative integration with budget management."""
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Budget Integration Campaign',
            description='Testing budget integration',
            daily_budget=Decimal('100.00'),
            status='active'
        )
        
        # Create creative
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=campaign,
            creative_type='banner',
            name='Budget Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        # Test creative performance impact on budget
        performance_data = {
            'impressions': 1000,
            'clicks': 20,
            'conversions': 2,
            'cost': Decimal('20.00'),
            'ctr': 0.02,
            'conversion_rate': 0.10
        }
        
        # Check if creative is within budget
        is_within_budget = self.campaign_service.check_creative_budget_impact(creative, performance_data)
        
        self.assertIsNotNone(is_within_budget)
    
    @patch('advertiser_portal.services.campaign.CampaignService.optimize_creative')
    def test_creative_optimization_integration(self, mock_optimize):
        """Test creative optimization integration."""
        mock_optimize.return_value = {
            'recommendations': ['Update creative copy', 'Adjust colors'],
            'performance_score': 0.85,
            'optimization_potential': 0.15
        }
        
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Optimization Integration Campaign',
            description='Testing optimization integration',
            status='active'
        )
        
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake_image_data",
            content_type="image/jpeg"
        )
        
        creative = CampaignCreative.objects.create(
            campaign=campaign,
            creative_type='banner',
            name='Integration Banner',
            creative_file=image_file,
            width=300,
            height=250,
            status='active'
        )
        
        performance_data = {
            'impressions': 1000,
            'clicks': 20,
            'conversions': 2,
            'ctr': 0.02,
            'conversion_rate': 0.10
        }
        
        # Optimize creative
        result = self.campaign_service.optimize_creative(creative, performance_data)
        
        # Verify optimization was called
        mock_optimize.assert_called_once_with(creative, performance_data)
        self.assertEqual(result['performance_score'], 0.85)
        self.assertIn('Update creative copy', result['recommendations'])
