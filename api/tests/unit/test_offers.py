"""
Unit tests for Offerwall app.
Tests offer models, completions, and business logic.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.test import APITestCase

from api.offerwall.models import (
    Offer, OfferCategory, OfferProvider, UserOfferCompletion,
    OfferImpression, UserOfferFavorite
)
from api.offerwall.serializers import (
    OfferSerializer, OfferCategorySerializer, UserOfferCompletionSerializer,
    OfferProviderSerializer, OfferImpressionSerializer
)
from api.offerwall.services import (
    OfferService, OfferCompletionService, OfferRecommendationService,
    OfferAnalyticsService
)
from api.offerwall.factories import (
    OfferFactory, OfferCategoryFactory, OfferProviderFactory,
    UserOfferCompletionFactory, OfferImpressionFactory
)
from api.tests.factories.UserFactory import UserFactory


# ==================== MODEL TESTS ====================
class TestOfferCategoryModel(APITestCase):
    """Test OfferCategory model functionality"""
    
    def test_create_offer_category(self):
        """Test creating offer category"""
        category = OfferCategoryFactory.create(
            name='Mobile Apps',
            slug='mobile-apps',
            description='Mobile application offers',
            is_active=True
        )
        
        self.assertEqual(category.name, 'Mobile Apps')
        self.assertEqual(category.slug, 'mobile-apps')
        self.assertEqual(category.description, 'Mobile application offers')
        self.assertTrue(category.is_active)
    
    def test_category_str_representation(self):
        """Test string representation of category"""
        category = OfferCategoryFactory.create(name='Surveys')
        self.assertEqual(str(category), 'Surveys')
    
    def test_category_slug_auto_generation(self):
        """Test automatic slug generation"""
        category = OfferCategory.objects.create(
            name='Gaming Offers',
            description='Game related offers'
        )
        
        self.assertEqual(category.slug, 'gaming-offers')
    
    def test_category_ordering(self):
        """Test category ordering"""
        category1 = OfferCategoryFactory.create(name='B', sort_order=2)
        category2 = OfferCategoryFactory.create(name='A', sort_order=1)
        category3 = OfferCategoryFactory.create(name='C', sort_order=3)
        
        categories = OfferCategory.objects.all()
        
        self.assertEqual(categories[0], category2)  # sort_order=1
        self.assertEqual(categories[1], category1)  # sort_order=2
        self.assertEqual(categories[2], category3)  # sort_order=3
    
    def test_category_active_offers_count(self):
        """Test active offers count property"""
        category = OfferCategoryFactory.create()
        
        # Create active offers
        for i in range(3):
            OfferFactory.create(category=category, is_active=True)
        
        # Create inactive offers
        for i in range(2):
            OfferFactory.create(category=category, is_active=False)
        
        self.assertEqual(category.active_offers_count, 3)


class TestOfferProviderModel(APITestCase):
    """Test OfferProvider model functionality"""
    
    def test_create_offer_provider(self):
        """Test creating offer provider"""
        provider = OfferProviderFactory.create(
            name='OfferToro',
            slug='offertoro',
            is_active=True,
            rating=4.5
        )
        
        self.assertEqual(provider.name, 'OfferToro')
        self.assertEqual(provider.slug, 'offertoro')
        self.assertTrue(provider.is_active)
        self.assertEqual(provider.rating, 4.5)
    
    def test_provider_str_representation(self):
        """Test string representation of provider"""
        provider = OfferProviderFactory.create(name='AdGate')
        self.assertEqual(str(provider), 'AdGate')
    
    def test_provider_payout_calculation(self):
        """Test payout calculation"""
        provider = OfferProviderFactory.create(
            payout_rate=Decimal('0.85')  # 85%
        )
        
        offer_payout = Decimal('100.00')
        expected_earnings = offer_payout * Decimal('0.85')
        
        calculated = provider.calculate_earnings(offer_payout)
        self.assertEqual(calculated, expected_earnings)
    
    def test_provider_trust_score(self):
        """Test provider trust score"""
        provider = OfferProviderFactory.create()
        
        # Test different rating scenarios
        test_cases = [
            (5.0, 'Excellent'),
            (4.0, 'Good'),
            (3.0, 'Average'),
            (2.0, 'Poor'),
            (1.0, 'Very Poor')
        ]
        
        for rating, expected_level in test_cases:
            provider.rating = rating
            self.assertEqual(provider.trust_level, expected_level)


class TestOfferModel(APITestCase):
    """Test Offer model functionality"""
    
    def setUp(self):
        self.category = OfferCategoryFactory.create()
        self.provider = OfferProviderFactory.create()
    
    def test_create_offer(self):
        """Test creating offer"""
        offer = OfferFactory.create(
            title='Install Mobile App',
            category=self.category,
            provider=self.provider,
            payout=Decimal('150.00'),
            is_active=True,
            is_featured=True
        )
        
        self.assertEqual(offer.title, 'Install Mobile App')
        self.assertEqual(offer.category, self.category)
        self.assertEqual(offer.provider, self.provider)
        self.assertEqual(offer.payout, Decimal('150.00'))
        self.assertTrue(offer.is_active)
        self.assertTrue(offer.is_featured)
    
    def test_offer_str_representation(self):
        """Test string representation of offer"""
        offer = OfferFactory.create(title='Test Offer')
        self.assertEqual(str(offer), 'Test Offer')
    
    def test_offer_availability(self):
        """Test offer availability checks"""
        # Active offer within date range
        active_offer = OfferFactory.create(
            is_active=True,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
            available_completions=10
        )
        self.assertTrue(active_offer.is_available)
        
        # Inactive offer
        inactive_offer = OfferFactory.create(is_active=False)
        self.assertFalse(inactive_offer.is_available)
        
        # Expired offer
        expired_offer = OfferFactory.create(
            is_active=True,
            end_date=timezone.now() - timedelta(days=1)
        )
        self.assertFalse(expired_offer.is_available)
        
        # No available completions
        no_completions_offer = OfferFactory.create(
            is_active=True,
            available_completions=0
        )
        self.assertFalse(no_completions_offer.is_available)
    
    def test_offer_difficulty_level(self):
        """Test offer difficulty level"""
        test_cases = [
            ('very_easy', 'Very Easy', '#4CAF50'),
            ('easy', 'Easy', '#8BC34A'),
            ('medium', 'Medium', '#FFC107'),
            ('hard', 'Hard', '#FF9800'),
            ('very_hard', 'Very Hard', '#F44336')
        ]
        
        for difficulty, expected_label, expected_color in test_cases:
            offer = OfferFactory.create(difficulty=difficulty)
            self.assertEqual(offer.difficulty_label, expected_label)
            self.assertEqual(offer.difficulty_color, expected_color)
    
    def test_offer_completion_rate(self):
        """Test offer completion rate calculation"""
        offer = OfferFactory.create(
            max_completions=100,
            total_completions=75
        )
        
        expected_rate = 75.0  # 75/100 * 100
        self.assertEqual(offer.completion_rate, expected_rate)
    
    def test_offer_estimated_time_parsing(self):
        """Test estimated time parsing"""
        offer = OfferFactory.create(estimated_time='5 minutes')
        
        self.assertEqual(offer.estimated_minutes, 5)
        self.assertEqual(offer.estimated_seconds, 300)
    
    def test_offer_payout_with_commission(self):
        """Test payout calculation with commission"""
        offer = OfferFactory.create(
            payout=Decimal('100.00'),
            provider__payout_rate=Decimal('0.85')  # 85% commission
        )
        
        expected_earnings = Decimal('85.00')  # 100 * 0.85
        self.assertEqual(offer.user_earnings, expected_earnings)
    
    def test_offer_tags_handling(self):
        """Test offer tags handling"""
        offer = OfferFactory.create(tags=['mobile', 'android', 'game'])
        
        self.assertEqual(len(offer.tags), 3)
        self.assertIn('mobile', offer.tags)
        self.assertIn('android', offer.tags)
        self.assertIn('game', offer.tags)
        
        # Test tag display
        self.assertEqual(offer.display_tags, 'mobile, android, game')
    
    def test_offer_statistics_update(self):
        """Test offer statistics update"""
        offer = OfferFactory.create(
            total_completions=50,
            success_rate=80.0
        )
        
        # Simulate new completion
        offer.update_statistics(success=True)
        
        self.assertEqual(offer.total_completions, 51)
        # Success rate should be updated (implementation specific)


class TestUserOfferCompletionModel(APITestCase):
    """Test UserOfferCompletion model functionality"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.offer = OfferFactory.create()
    
    def test_create_offer_completion(self):
        """Test creating offer completion"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending',
            earned_amount=Decimal('100.00')
        )
        
        self.assertEqual(completion.user, self.user)
        self.assertEqual(completion.offer, self.offer)
        self.assertEqual(completion.status, 'pending')
        self.assertEqual(completion.earned_amount, Decimal('100.00'))
    
    def test_completion_str_representation(self):
        """Test string representation of completion"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer
        )
        expected = f"{self.user.username} - {self.offer.title} - pending"
        self.assertEqual(str(completion), expected)
    
    def test_completion_approval(self):
        """Test completion approval"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending'
        )
        
        completion.approve('Proof verified successfully')
        
        self.assertEqual(completion.status, 'approved')
        self.assertIsNotNone(completion.approved_at)
        self.assertEqual(completion.verification_notes, 'Proof verified successfully')
    
    def test_completion_rejection(self):
        """Test completion rejection"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending'
        )
        
        completion.reject('Proof verification failed')
        
        self.assertEqual(completion.status, 'rejected')
        self.assertEqual(completion.verification_notes, 'Proof verification failed')
    
    def test_completion_net_amount_calculation(self):
        """Test net amount calculation with commission"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            earned_amount=Decimal('100.00'),
            commission_rate=Decimal('0.90')  # 90% commission
        )
        
        expected_net = Decimal('90.00')  # 100 * 0.90
        self.assertEqual(completion.net_amount, expected_net)
    
    def test_completion_duration_calculation(self):
        """Test completion duration calculation"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            started_at=timezone.now() - timedelta(minutes=30),
            completed_at=timezone.now()
        )
        
        self.assertEqual(completion.duration_minutes, 30)
        self.assertEqual(completion.duration_seconds, 1800)
    
    def test_completion_device_info(self):
        """Test completion device info handling"""
        device_info = {
            'device_id': 'device123',
            'device_model': 'Samsung Galaxy S21',
            'os_version': 'Android 11',
            'app_version': '2.5.0'
        }
        
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            device_info=device_info
        )
        
        self.assertEqual(completion.device_info, device_info)
        self.assertEqual(completion.device_model, 'Samsung Galaxy S21')
        self.assertEqual(completion.os_version, 'Android 11')


class TestOfferImpressionModel(APITestCase):
    """Test OfferImpression model functionality"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.offer = OfferFactory.create()
    
    def test_create_impression(self):
        """Test creating offer impression"""
        impression = OfferImpressionFactory.create(
            user=self.user,
            offer=self.offer,
            impression_type='view',
            source='organic',
            medium='mobile_app'
        )
        
        self.assertEqual(impression.user, self.user)
        self.assertEqual(impression.offer, self.offer)
        self.assertEqual(impression.impression_type, 'view')
        self.assertEqual(impression.source, 'organic')
        self.assertEqual(impression.medium, 'mobile_app')
    
    def test_impression_str_representation(self):
        """Test string representation of impression"""
        impression = OfferImpressionFactory.create(
            user=self.user,
            offer=self.offer,
            impression_type='click'
        )
        expected = f"{self.user.username} - {self.offer.title} - click"
        self.assertEqual(str(impression), expected)
    
    def test_impression_conversion_tracking(self):
        """Test conversion tracking"""
        impression = OfferImpressionFactory.create(
            user=self.user,
            offer=self.offer,
            impression_type='click'
        )
        
        # Mark as conversion
        impression.mark_as_conversion()
        
        self.assertEqual(impression.impression_type, 'conversion')
        self.assertIsNotNone(impression.converted_at)
    
    def test_impression_location_data(self):
        """Test impression location data"""
        location_data = {
            'country': 'Bangladesh',
            'city': 'Dhaka',
            'latitude': 23.8103,
            'longitude': 90.4125
        }
        
        impression = OfferImpressionFactory.create(
            user=self.user,
            offer=self.offer,
            location_data=location_data
        )
        
        self.assertEqual(impression.location_data, location_data)
        self.assertEqual(impression.country, 'Bangladesh')
        self.assertEqual(impression.city, 'Dhaka')


# ==================== SERIALIZER TESTS ====================
class TestOfferSerializer(APITestCase):
    """Test OfferSerializer"""
    
    def setUp(self):
        self.offer = OfferFactory.create(
            title='Test Offer',
            payout=Decimal('100.00'),
            is_active=True,
            is_featured=True
        )
    
    def test_offer_serialization(self):
        """Test offer serialization"""
        serializer = OfferSerializer(self.offer)
        
        expected_fields = [
            'id', 'title', 'description', 'category', 'provider',
            'payout', 'currency', 'payout_type', 'required_action',
            'platform', 'device_requirements', 'is_active', 'is_featured',
            'is_hot', 'is_new', 'start_date', 'end_date', 'max_completions',
            'available_completions', 'daily_limit', 'user_daily_limit',
            'difficulty', 'estimated_time', 'thumbnail', 'banner_image',
            'screenshots', 'tracking_url', 'proof_required', 'proof_type',
            'instructions', 'total_completions', 'success_rate',
            'total_payout', 'tags', 'metadata', 'completion_rate',
            'user_earnings', 'is_available', 'difficulty_label',
            'difficulty_color', 'estimated_minutes', 'display_tags',
            'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
    
    def test_offer_filtering(self):
        """Test offer filtering in serializer context"""
        # Create offers with different statuses
        active_offer = OfferFactory.create(is_active=True, is_featured=True)
        inactive_offer = OfferFactory.create(is_active=False)
        featured_offer = OfferFactory.create(is_active=True, is_featured=True)
        
        # Filter active offers
        active_offers = Offer.objects.filter(is_active=True)
        serializer = OfferSerializer(active_offers, many=True)
        
        self.assertEqual(len(serializer.data), 2)
        for offer_data in serializer.data:
            self.assertTrue(offer_data['is_active'])


class TestOfferCategorySerializer(APITestCase):
    """Test OfferCategorySerializer"""
    
    def setUp(self):
        self.category = OfferCategoryFactory.create()
    
    def test_category_serialization(self):
        """Test category serialization"""
        serializer = OfferCategorySerializer(self.category)
        
        expected_fields = [
            'id', 'name', 'slug', 'description', 'icon', 'is_active',
            'sort_order', 'total_offers', 'total_completions',
            'total_payout', 'metadata', 'active_offers_count',
            'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
    
    def test_category_with_offers(self):
        """Test category serialization with offers"""
        # Create offers for category
        for i in range(3):
            OfferFactory.create(category=self.category)
        
        serializer = OfferCategorySerializer(self.category)
        
        self.assertEqual(serializer.data['total_offers'], 3)
        self.assertEqual(serializer.data['active_offers_count'], 3)


class TestUserOfferCompletionSerializer(APITestCase):
    """Test UserOfferCompletionSerializer"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.offer = OfferFactory.create()
        self.completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer
        )
    
    def test_completion_serialization(self):
        """Test completion serialization"""
        serializer = UserOfferCompletionSerializer(self.completion)
        
        expected_fields = [
            'id', 'completion_id', 'user', 'offer', 'status', 'earned_amount',
            'currency', 'commission_rate', 'net_amount', 'started_at',
            'completed_at', 'approved_at', 'proof', 'proof_type',
            'verification_notes', 'tracking_id', 'click_id', 'conversion_id',
            'ip_address', 'user_agent', 'device_info', 'location_data',
            'metadata', 'duration_minutes', 'duration_seconds',
            'device_model', 'os_version', 'country', 'city',
            'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
    
    def test_completion_creation(self):
        """Test completion creation through serializer"""
        data = {
            'offer_id': self.offer.id,
            'proof': 'proof.jpg',
            'notes': 'Completed successfully'
        }
        
        serializer = UserOfferCompletionSerializer(
            data=data,
            context={'user': self.user}
        )
        
        self.assertTrue(serializer.is_valid())
        
        completion = serializer.save()
        
        self.assertEqual(completion.user, self.user)
        self.assertEqual(completion.offer, self.offer)
        self.assertEqual(completion.status, 'pending')
        self.assertEqual(completion.verification_notes, 'Completed successfully')


# ==================== SERVICE TESTS ====================
class TestOfferService(APITestCase):
    """Test OfferService functionality"""
    
    def setUp(self):
        self.offer_service = OfferService()
        self.user = UserFactory.create()
    
    def test_get_available_offers(self):
        """Test getting available offers"""
        # Create available offers
        for i in range(5):
            OfferFactory.create(
                is_active=True,
                available_completions=10
            )
        
        # Create unavailable offers
        for i in range(3):
            OfferFactory.create(is_active=False)
        
        offers = self.offer_service.get_available_offers()
        
        self.assertEqual(len(offers), 5)
        for offer in offers:
            self.assertTrue(offer.is_available)
    
    def test_get_offers_by_category(self):
        """Test getting offers by category"""
        category1 = OfferCategoryFactory.create()
        category2 = OfferCategoryFactory.create()
        
        # Create offers for category1
        for i in range(3):
            OfferFactory.create(category=category1, is_active=True)
        
        # Create offers for category2
        for i in range(2):
            OfferFactory.create(category=category2, is_active=True)
        
        offers = self.offer_service.get_offers_by_category(category1.id)
        
        self.assertEqual(len(offers), 3)
        for offer in offers:
            self.assertEqual(offer.category, category1)
    
    def test_get_featured_offers(self):
        """Test getting featured offers"""
        # Create featured offers
        for i in range(4):
            OfferFactory.create(is_active=True, is_featured=True)
        
        # Create non-featured offers
        for i in range(6):
            OfferFactory.create(is_active=True, is_featured=False)
        
        offers = self.offer_service.get_featured_offers()
        
        self.assertEqual(len(offers), 4)
        for offer in offers:
            self.assertTrue(offer.is_featured)
    
    def test_get_hot_offers(self):
        """Test getting hot offers"""
        # Create hot offers
        for i in range(3):
            OfferFactory.create(is_active=True, is_hot=True)
        
        offers = self.offer_service.get_hot_offers()
        
        self.assertEqual(len(offers), 3)
        for offer in offers:
            self.assertTrue(offer.is_hot)
    
    def test_get_new_offers(self):
        """Test getting new offers"""
        # Create new offers (created within last 7 days)
        for i in range(5):
            OfferFactory.create(
                is_active=True,
                is_new=True,
                created_at=timezone.now() - timedelta(days=3)
            )
        
        # Create old offers
        for i in range(3):
            OfferFactory.create(
                is_active=True,
                is_new=False,
                created_at=timezone.now() - timedelta(days=10)
            )
        
        offers = self.offer_service.get_new_offers(days=7)
        
        self.assertEqual(len(offers), 5)
        for offer in offers:
            self.assertTrue(offer.is_new)
    
    def test_search_offers(self):
        """Test offer search"""
        # Create offers with specific titles
        OfferFactory.create(title='Install Facebook App', is_active=True)
        OfferFactory.create(title='Complete Survey About Social Media', is_active=True)
        OfferFactory.create(title='Play Mobile Game', is_active=True)
        OfferFactory.create(title='Watch YouTube Videos', is_active=True)
        
        # Search by keyword
        results = self.offer_service.search_offers('facebook')
        self.assertEqual(len(results), 1)
        self.assertIn('Facebook', results[0].title)
        
        # Search by partial keyword
        results = self.offer_service.search_offers('mobile')
        self.assertEqual(len(results), 2)  # 'Install Facebook App' and 'Play Mobile Game'
        
        # Search by tag
        offer_with_tag = OfferFactory.create(
            title='Test Offer',
            tags=['social', 'media'],
            is_active=True
        )
        results = self.offer_service.search_offers('social')
        self.assertGreaterEqual(len(results), 1)
    
    def test_filter_offers(self):
        """Test offer filtering"""
        # Create offers with different attributes
        OfferFactory.create(
            title='High Payout Offer',
            payout=Decimal('500.00'),
            difficulty='hard',
            is_active=True
        )
        OfferFactory.create(
            title='Easy Mobile Offer',
            payout=Decimal('50.00'),
            difficulty='easy',
            platform='mobile',
            is_active=True
        )
        OfferFactory.create(
            title='Medium Survey',
            payout=Decimal('150.00'),
            difficulty='medium',
            required_action='survey',
            is_active=True
        )
        
        # Filter by payout range
        filtered = self.offer_service.filter_offers(
            min_payout=Decimal('100.00'),
            max_payout=Decimal('600.00')
        )
        self.assertEqual(len(filtered), 2)
        
        # Filter by difficulty
        filtered = self.offer_service.filter_offers(difficulty='easy')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].difficulty, 'easy')
        
        # Filter by platform
        filtered = self.offer_service.filter_offers(platform='mobile')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].platform, 'mobile')
        
        # Filter by action type
        filtered = self.offer_service.filter_offers(action_type='survey')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].required_action, 'survey')
        
        # Multiple filters
        filtered = self.offer_service.filter_offers(
            min_payout=Decimal('100.00'),
            difficulty='hard'
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payout, Decimal('500.00'))
    
    def test_get_offer_statistics(self):
        """Test offer statistics"""
        category = OfferCategoryFactory.create()
        
        # Create offers with different statuses
        for i in range(5):
            OfferFactory.create(
                category=category,
                is_active=True,
                payout=Decimal('100.00'),
                total_completions=10
            )
        
        for i in range(2):
            OfferFactory.create(
                category=category,
                is_active=False,
                payout=Decimal('50.00')
            )
        
        stats = self.offer_service.get_offer_statistics()
        
        self.assertIn('total_offers', stats)
        self.assertIn('active_offers', stats)
        self.assertIn('total_payout', stats)
        self.assertIn('avg_payout', stats)
        self.assertIn('by_category', stats)
        self.assertIn('by_difficulty', stats)
        
        self.assertEqual(stats['total_offers'], 7)
        self.assertEqual(stats['active_offers'], 5)
        self.assertEqual(stats['total_payout'], Decimal('600.00'))  # 5*100 + 2*50
    
    def test_update_offer_availability(self):
        """Test offer availability update"""
        offer = OfferFactory.create(
            available_completions=10,
            daily_limit=5
        )
        
        # User completes offer
        self.offer_service.update_offer_availability(
            offer_id=offer.id,
            user_id=self.user.id
        )
        
        offer.refresh_from_db()
        self.assertEqual(offer.available_completions, 9)
        
        # Check user daily limit
        user_daily_count = self.offer_service.get_user_daily_completions(
            user_id=self.user.id,
            offer_id=offer.id
        )
        self.assertEqual(user_daily_count, 1)
    
    def test_sync_offers_from_provider(self):
        """Test syncing offers from provider"""
        provider = OfferProviderFactory.create(
            api_url='https://api.example.com/offers',
            api_key='test_key'
        )
        
        # Mock API response
        mock_offers = [
            {
                'id': 'offer_1',
                'title': 'Test Offer 1',
                'description': 'Test description 1',
                'payout': '100.00',
                'currency': 'BDT',
                'category': 'Mobile Apps'
            },
            {
                'id': 'offer_2',
                'title': 'Test Offer 2',
                'description': 'Test description 2',
                'payout': '150.00',
                'currency': 'BDT',
                'category': 'Surveys'
            }
        ]
        
        # This would be mocked in real test
        # For now, we'll test the logic without actual API call
        result = self.offer_service.sync_offers_from_provider(provider.id)
        
        # In real implementation, this would create/update offers
        # For this test, we'll verify the method exists and returns expected structure
        self.assertIsInstance(result, dict)
        self.assertIn('synced', result)
        self.assertIn('created', result)
        self.assertIn('updated', result)
        self.assertIn('failed', result)


class TestOfferCompletionService(APITestCase):
    """Test OfferCompletionService functionality"""
    
    def setUp(self):
        self.completion_service = OfferCompletionService()
        self.user = UserFactory.create()
        self.offer = OfferFactory.create(
            payout=Decimal('100.00'),
            available_completions=10
        )
    
    def test_start_offer_completion(self):
        """Test starting offer completion"""
        completion = self.completion_service.start_offer_completion(
            user_id=self.user.id,
            offer_id=self.offer.id,
            device_info={
                'device_id': 'device123',
                'device_model': 'Test Device'
            }
        )
        
        self.assertEqual(completion.user, self.user)
        self.assertEqual(completion.offer, self.offer)
        self.assertEqual(completion.status, 'pending')
        self.assertIsNotNone(completion.started_at)
        self.assertIsNotNone(completion.tracking_id)
    
    def test_complete_offer(self):
        """Test completing offer"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending'
        )
        
        result = self.completion_service.complete_offer(
            completion_id=completion.id,
            proof='screenshot.jpg',
            notes='Completed successfully'
        )
        
        self.assertTrue(result['success'])
        
        completion.refresh_from_db()
        self.assertEqual(completion.status, 'pending_review')
        self.assertEqual(completion.proof, 'screenshot.jpg')
        self.assertIsNotNone(completion.completed_at)
    
    def test_approve_completion(self):
        """Test approving offer completion"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending_review',
            earned_amount=Decimal('100.00')
        )
        
        result = self.completion_service.approve_completion(
            completion_id=completion.id,
            processed_by='admin',
            notes='Proof verified'
        )
        
        self.assertTrue(result['success'])
        
        completion.refresh_from_db()
        self.assertEqual(completion.status, 'approved')
        self.assertEqual(completion.processed_by, 'admin')
        self.assertIsNotNone(completion.approved_at)
        
        # Should create wallet transaction
        from api.wallet.models import Transaction
        transaction = Transaction.objects.filter(
            user=self.user,
            source_type='offer',
            source_id=completion.id
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('100.00'))
    
    def test_reject_completion(self):
        """Test rejecting offer completion"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending_review'
        )
        
        result = self.completion_service.reject_completion(
            completion_id=completion.id,
            reason='Proof verification failed'
        )
        
        self.assertTrue(result['success'])
        
        completion.refresh_from_db()
        self.assertEqual(completion.status, 'rejected')
        self.assertEqual(completion.verification_notes, 'Proof verification failed')
    
    def test_get_user_completions(self):
        """Test getting user completions"""
        # Create completions
        for i in range(5):
            UserOfferCompletionFactory.create(
                user=self.user,
                offer=self.offer,
                status='approved'
            )
        
        completions = self.completion_service.get_user_completions(
            user_id=self.user.id
        )
        
        self.assertEqual(len(completions), 5)
        for completion in completions:
            self.assertEqual(completion.user, self.user)
    
    def test_get_pending_completions(self):
        """Test getting pending completions"""
        # Create completions with different statuses
        UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending'
        )
        UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending_review'
        )
        UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='approved'
        )
        
        pending = self.completion_service.get_pending_completions()
        
        self.assertEqual(len(pending), 2)
        for completion in pending:
            self.assertIn(completion.status, ['pending', 'pending_review'])
    
    def test_get_completion_statistics(self):
        """Test completion statistics"""
        # Create completions for different dates
        today = timezone.now()
        
        # Today's completions
        for i in range(3):
            UserOfferCompletionFactory.create(
                user=self.user,
                offer=self.offer,
                status='approved',
                approved_at=today - timedelta(hours=i),
                earned_amount=Decimal('100.00')
            )
        
        # Yesterday's completions
        for i in range(2):
            UserOfferCompletionFactory.create(
                user=self.user,
                offer=self.offer,
                status='rejected',
                approved_at=today - timedelta(days=1, hours=i),
                earned_amount=Decimal('50.00')
            )
        
        stats = self.completion_service.get_completion_statistics(days=7)
        
        self.assertIn('total_completions', stats)
        self.assertIn('total_earned', stats)
        self.assertIn('approval_rate', stats)
        self.assertIn('avg_completion_time', stats)
        self.assertIn('by_status', stats)
        self.assertIn('by_day', stats)
        
        self.assertEqual(stats['total_completions'], 5)
        self.assertEqual(stats['total_earned'], Decimal('400.00'))  # 3*100 + 2*50
        self.assertEqual(stats['approval_rate'], 60.0)  # 3 approved out of 5
    
    def test_check_user_eligibility(self):
        """Test user eligibility check for offer"""
        # User hasn't completed this offer before
        eligibility = self.completion_service.check_user_eligibility(
            user_id=self.user.id,
            offer_id=self.offer.id
        )
        
        self.assertTrue(eligibility['eligible'])
        
        # User completes offer
        UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='approved'
        )
        
        # Check again (should be ineligible if offer is single completion)
        eligibility = self.completion_service.check_user_eligibility(
            user_id=self.user.id,
            offer_id=self.offer.id
        )
        
        # Depends on offer settings
        # For single completion offers, should be False
        # For multiple completion offers, should check daily/user limits
    
    def test_auto_approve_completions(self):
        """Test automatic completion approval"""
        # Create completion for auto-approval
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=self.offer,
            status='pending_review',
            proof='screenshot.jpg'
        )
        
        # Configure offer for auto-approval
        self.offer.auto_approve = True
        self.offer.save()
        
        result = self.completion_service.auto_approve_completions()
        
        self.assertEqual(result['approved'], 1)
        self.assertEqual(result['failed'], 0)
        
        completion.refresh_from_db()
        self.assertEqual(completion.status, 'approved')
        self.assertEqual(completion.processed_by, 'auto')


class TestOfferRecommendationService(APITestCase):
    """Test OfferRecommendationService functionality"""
    
    def setUp(self):
        self.recommendation_service = OfferRecommendationService()
        self.user = UserFactory.create()
    
    def test_get_personalized_recommendations(self):
        """Test getting personalized recommendations"""
        # Create offers in different categories
        mobile_category = OfferCategoryFactory.create(name='Mobile Apps')
        survey_category = OfferCategoryFactory.create(name='Surveys')
        game_category = OfferCategoryFactory.create(name='Games')
        
        # Create offers
        mobile_offers = []
        for i in range(5):
            offer = OfferFactory.create(
                category=mobile_category,
                is_active=True,
                payout=Decimal(str(50 + i * 10))
            )
            mobile_offers.append(offer)
        
        survey_offers = []
        for i in range(3):
            offer = OfferFactory.create(
                category=survey_category,
                is_active=True,
                payout=Decimal(str(100 + i * 20))
            )
            survey_offers.append(offer)
        
        game_offers = []
        for i in range(4):
            offer = OfferFactory.create(
                category=game_category,
                is_active=True,
                payout=Decimal(str(80 + i * 15))
            )
            game_offers.append(offer)
        
        # User completes some mobile offers
        for i in range(2):
            UserOfferCompletionFactory.create(
                user=self.user,
                offer=mobile_offers[i],
                status='approved'
            )
        
        # Get recommendations
        recommendations = self.recommendation_service.get_personalized_recommendations(
            user_id=self.user.id,
            limit=10
        )
        
        # Should return offers, prioritizing categories user interacts with
        self.assertLessEqual(len(recommendations), 10)
        
        # Mobile offers should be recommended (based on user history)
        recommended_categories = [offer.category for offer in recommendations]
        self.assertIn(mobile_category, recommended_categories)
    
    def test_get_similar_offers(self):
        """Test getting similar offers"""
        main_offer = OfferFactory.create(
            title='Install Facebook App',
            category__name='Social Media',
            tags=['social', 'mobile', 'app'],
            payout=Decimal('100.00'),
            difficulty='easy'
        )
        
        # Create similar offers
        similar_offers = []
        for i in range(5):
            offer = OfferFactory.create(
                title=f'Social App {i}',
                category=main_offer.category,
                tags=['social', 'mobile'],
                payout=Decimal(str(80 + i * 10)),
                difficulty='easy'
            )
            similar_offers.append(offer)
        
        # Create different offers
        for i in range(3):
            OfferFactory.create(
                title=f'Game {i}',
                category__name='Games',
                tags=['game', 'entertainment'],
                payout=Decimal('150.00'),
                difficulty='medium'
            )
        
        similar = self.recommendation_service.get_similar_offers(
            offer_id=main_offer.id,
            limit=5
        )
        
        self.assertEqual(len(similar), 5)
        
        # Similar offers should share category or tags
        for offer in similar:
            self.assertTrue(
                offer.category == main_offer.category or
                any(tag in offer.tags for tag in main_offer.tags)
            )
    
    def test_get_trending_offers(self):
        """Test getting trending offers"""
        # Create offers with different completion rates
        trending_offer = OfferFactory.create(
            title='Trending Offer',
            total_completions=100,
            max_completions=200,  # 50% completion rate
            is_active=True
        )
        
        normal_offer = OfferFactory.create(
            title='Normal Offer',
            total_completions=20,
            max_completions=200,  # 10% completion rate
            is_active=True
        )
        
        # Create recent completions for trending offer
        for i in range(10):
            UserOfferCompletionFactory.create(
                user=UserFactory.create(),
                offer=trending_offer,
                status='approved',
                approved_at=timezone.now() - timedelta(hours=i)
            )
        
        trending = self.recommendation_service.get_trending_offers(
            days=7,
            limit=5
        )
        
        self.assertGreaterEqual(len(trending), 1)
        
        # Trending offer should be in results
        trending_ids = [offer.id for offer in trending]
        self.assertIn(trending_offer.id, trending_ids)
    
    def test_get_high_paying_offers(self):
        """Test getting high paying offers"""
        # Create offers with different payouts
        high_paying = []
        for payout in [500.00, 400.00, 300.00, 200.00, 100.00]:
            offer = OfferFactory.create(
                title=f'Offer ${payout}',
                payout=Decimal(str(payout)),
                is_active=True
            )
            high_paying.append(offer)
        
        # Create low paying offers
        for i in range(5):
            OfferFactory.create(
                title=f'Low Offer {i}',
                payout=Decimal('50.00'),
                is_active=True
            )
        
        high_paying_offers = self.recommendation_service.get_high_paying_offers(
            limit=5
        )
        
        self.assertEqual(len(high_paying_offers), 5)
        
        # Should be ordered by payout descending
        payouts = [offer.payout for offer in high_paying_offers]
        self.assertEqual(payouts, sorted(payouts, reverse=True))
        
        # Top offer should have highest payout
        self.assertEqual(high_paying_offers[0].payout, Decimal('500.00'))
    
    def test_get_quick_offers(self):
        """Test getting quick completion offers"""
        # Create quick offers (estimated time < 5 minutes)
        quick_offers = []
        for time in ['1 minute', '2 minutes', '3 minutes', '4 minutes']:
            offer = OfferFactory.create(
                title=f'Quick {time} Offer',
                estimated_time=time,
                is_active=True
            )
            quick_offers.append(offer)
        
        # Create longer offers
        for time in ['10 minutes', '15 minutes', '20 minutes']:
            OfferFactory.create(
                title=f'Long {time} Offer',
                estimated_time=time,
                is_active=True
            )
        
        quick = self.recommendation_service.get_quick_offers(
            max_minutes=5,
            limit=5
        )
        
        self.assertLessEqual(len(quick), 5)
        
        for offer in quick:
            self.assertLessEqual(offer.estimated_minutes, 5)
    
    def test_get_recommendations_based_on_history(self):
        """Test recommendations based on user history"""
        # User completes mobile app offers
        mobile_category = OfferCategoryFactory.create(name='Mobile Apps')
        
        for i in range(5):
            offer = OfferFactory.create(
                category=mobile_category,
                is_active=True
            )
            UserOfferCompletionFactory.create(
                user=self.user,
                offer=offer,
                status='approved'
            )
        
        # Get recommendations
        recommendations = self.recommendation_service.get_recommendations_based_on_history(
            user_id=self.user.id
        )
        
        # Should recommend more mobile app offers
        mobile_recommendations = [
            offer for offer in recommendations
            if offer.category == mobile_category
        ]
        
        self.assertGreater(len(mobile_recommendations), 0)
    
    def test_collaborative_filtering_recommendations(self):
        """Test collaborative filtering recommendations"""
        # Create multiple users
        users = [UserFactory.create() for _ in range(10)]
        
        # Create offers
        offers = [OfferFactory.create() for _ in range(20)]
        
        # Simulate user-offer interactions
        # User 0 completes offers 0, 1, 2
        for i in range(3):
            UserOfferCompletionFactory.create(
                user=users[0],
                offer=offers[i],
                status='approved'
            )
        
        # User 1 completes offers 1, 2, 3 (similar to user 0)
        for i in range(1, 4):
            UserOfferCompletionFactory.create(
                user=users[1],
                offer=offers[i],
                status='approved'
            )
        
        # Get recommendations for user 0
        recommendations = self.recommendation_service.get_collaborative_filtering_recommendations(
            user_id=users[0].id,
            limit=5
        )
        
        # Should recommend offer 3 (completed by similar user 1)
        recommended_offer_ids = [offer.id for offer in recommendations]
        self.assertIn(offers[3].id, recommended_offer_ids)


class TestOfferAnalyticsService(APITestCase):
    """Test OfferAnalyticsService functionality"""
    
    def setUp(self):
        self.analytics_service = OfferAnalyticsService()
        self.user = UserFactory.create()
        self.offer = OfferFactory.create()
    
    def test_track_impression(self):
        """Test impression tracking"""
        impression = self.analytics_service.track_impression(
            user_id=self.user.id,
            offer_id=self.offer.id,
            impression_type='view',
            source='organic',
            medium='web'
        )
        
        self.assertEqual(impression.user, self.user)
        self.assertEqual(impression.offer, self.offer)
        self.assertEqual(impression.impression_type, 'view')
        self.assertEqual(impression.source, 'organic')
        self.assertEqual(impression.medium, 'web')
    
    def test_track_click(self):
        """Test click tracking"""
        click = self.analytics_service.track_click(
            user_id=self.user.id,
            offer_id=self.offer.id,
            source='facebook',
            medium='social'
        )
        
        self.assertEqual(click.user, self.user)
        self.assertEqual(click.offer, self.offer)
        self.assertEqual(click.impression_type, 'click')
        self.assertEqual(click.source, 'facebook')
    
    def test_track_conversion(self):
        """Test conversion tracking"""
        # First track a click
        impression = self.analytics_service.track_click(
            user_id=self.user.id,
            offer_id=self.offer.id,
            source='direct',
            medium='web'
        )
        
        # Then track conversion
        conversion = self.analytics_service.track_conversion(
            impression_id=impression.id,
            conversion_data={'value': '100.00'}
        )
        
        self.assertEqual(conversion.impression_type, 'conversion')
        self.assertIsNotNone(conversion.converted_at)
        self.assertEqual(conversion.metadata['conversion_value'], '100.00')
    
    def test_get_offer_analytics(self):
        """Test offer analytics"""
        # Track impressions and conversions
        for i in range(100):
            impression = self.analytics_service.track_impression(
                user_id=self.user.id,
                offer_id=self.offer.id,
                impression_type='view'
            )
            
            # 10% click-through rate
            if i < 10:
                click = self.analytics_service.track_click(
                    user_id=self.user.id,
                    offer_id=self.offer.id,
                    source='organic'
                )
                
                # 50% conversion rate from clicks
                if i < 5:
                    self.analytics_service.track_conversion(
                        impression_id=click.id,
                        conversion_data={'value': str(self.offer.payout)}
                    )
        
        analytics = self.analytics_service.get_offer_analytics(
            offer_id=self.offer.id
        )
        
        self.assertIn('impressions', analytics)
        self.assertIn('clicks', analytics)
        self.assertIn('conversions', analytics)
        self.assertIn('ctr', analytics)  # Click-through rate
        self.assertIn('conversion_rate', analytics)
        self.assertIn('revenue', analytics)
        
        self.assertEqual(analytics['impressions'], 100)
        self.assertEqual(analytics['clicks'], 10)
        self.assertEqual(analytics['conversions'], 5)
        self.assertEqual(analytics['ctr'], 10.0)  # 10/100 * 100
        self.assertEqual(analytics['conversion_rate'], 50.0)  # 5/10 * 100
    
    def test_get_category_analytics(self):
        """Test category analytics"""
        category = OfferCategoryFactory.create()
        
        # Create offers in category
        offers = []
        for i in range(3):
            offer = OfferFactory.create(category=category)
            offers.append(offer)
            
            # Track some activity
            for j in range(20):
                self.analytics_service.track_impression(
                    user_id=self.user.id,
                    offer_id=offer.id,
                    impression_type='view'
                )
        
        analytics = self.analytics_service.get_category_analytics(
            category_id=category.id
        )
        
        self.assertIn('total_offers', analytics)
        self.assertIn('total_impressions', analytics)
        self.assertIn('total_clicks', analytics)
        self.assertIn('total_conversions', analytics)
        self.assertIn('total_revenue', analytics)
        self.assertIn('avg_ctr', analytics)
        self.assertIn('avg_conversion_rate', analytics)
        
        self.assertEqual(analytics['total_offers'], 3)
        self.assertEqual(analytics['total_impressions'], 60)  # 3*20
    
    def test_get_user_analytics(self):
        """Test user analytics"""
        # User interacts with offers
        for i in range(5):
            offer = OfferFactory.create()
            
            # Track impressions
            self.analytics_service.track_impression(
                user_id=self.user.id,
                offer_id=offer.id,
                impression_type='view'
            )
            
            # Some clicks
            if i < 3:
                click = self.analytics_service.track_click(
                    user_id=self.user.id,
                    offer_id=offer.id,
                    source='direct'
                )
                
                # Some conversions
                if i < 2:
                    self.analytics_service.track_conversion(
                        impression_id=click.id,
                        conversion_data={'value': str(offer.payout)}
                    )
        
        analytics = self.analytics_service.get_user_analytics(
            user_id=self.user.id
        )
        
        self.assertIn('total_impressions', analytics)
        self.assertIn('total_clicks', analytics)
        self.assertIn('total_conversions', analytics)
        self.assertIn('total_earned', analytics)
        self.assertIn('preferred_categories', analytics)
        self.assertIn('preferred_offer_types', analytics)
        
        self.assertEqual(analytics['total_impressions'], 5)
        self.assertEqual(analytics['total_clicks'], 3)
        self.assertEqual(analytics['total_conversions'], 2)
    
    def test_get_trending_analytics(self):
        """Test trending analytics"""
        # Create offers with recent activity
        trending_offer = OfferFactory.create()
        
        # Recent activity
        for i in range(20):
            self.analytics_service.track_impression(
                user_id=self.user.id,
                offer_id=trending_offer.id,
                impression_type='view'
            )
        
        # Old offer with less recent activity
        old_offer = OfferFactory.create()
        
        analytics = self.analytics_service.get_trending_analytics(
            days=7,
            limit=10
        )
        
        self.assertIn('trending_offers', analytics)
        self.assertIn('top_categories', analytics)
        self.assertIn('top_sources', analytics)
        self.assertIn('conversion_trends', analytics)
        
        # Trending offer should be in results
        trending_ids = [offer['id'] for offer in analytics['trending_offers']]
        self.assertIn(trending_offer.id, trending_ids)
    
    def test_get_conversion_funnel(self):
        """Test conversion funnel analysis"""
        offer = OfferFactory.create()
        
        # Simulate funnel: 1000 impressions -> 100 clicks -> 10 conversions
        impressions = []
        for i in range(1000):
            impression = self.analytics_service.track_impression(
                user_id=UserFactory.create().id,
                offer_id=offer.id,
                impression_type='view'
            )
            impressions.append(impression)
        
        clicks = []
        for i in range(100):
            click = self.analytics_service.track_click(
                user_id=impressions[i].user.id,
                offer_id=offer.id,
                source='organic'
            )
            clicks.append(click)
        
        for i in range(10):
            self.analytics_service.track_conversion(
                impression_id=clicks[i].id,
                conversion_data={'value': str(offer.payout)}
            )
        
        funnel = self.analytics_service.get_conversion_funnel(
            offer_id=offer.id
        )
        
        self.assertIn('impressions', funnel)
        self.assertIn('clicks', funnel)
        self.assertIn('conversions', funnel)
        self.assertIn('drop_off_rates', funnel)
        self.assertIn('conversion_rate', funnel)
        
        self.assertEqual(funnel['impressions'], 1000)
        self.assertEqual(funnel['clicks'], 100)
        self.assertEqual(funnel['conversions'], 10)
        
        # Calculate drop-off rates
        impression_to_click = (1000 - 100) / 1000 * 100  # 90%
        click_to_conversion = (100 - 10) / 100 * 100  # 90%
        
        self.assertAlmostEqual(funnel['drop_off_rates']['impression_to_click'], impression_to_click, delta=0.1)
        self.assertAlmostEqual(funnel['drop_off_rates']['click_to_conversion'], click_to_conversion, delta=0.1)
        
        # Overall conversion rate: 10/1000 * 100 = 1%
        self.assertAlmostEqual(funnel['conversion_rate'], 1.0, delta=0.1)
    
    def test_export_analytics_data(self):
        """Test analytics data export"""
        # Create some analytics data
        for i in range(10):
            offer = OfferFactory.create()
            self.analytics_service.track_impression(
                user_id=self.user.id,
                offer_id=offer.id,
                impression_type='view'
            )
        
        # Export to CSV
        csv_data = self.analytics_service.export_analytics_data(
            start_date=timezone.now() - timedelta(days=30),
            end_date=timezone.now(),
            format='csv'
        )
        
        self.assertIsInstance(csv_data, str)
        self.assertIn('Impression ID', csv_data)
        self.assertIn('User ID', csv_data)
        self.assertIn('Offer ID', csv_data)
        self.assertIn('Impression Type', csv_data)
        
        # Count lines (header + 10 impressions)
        lines = csv_data.strip().split('\n')
        self.assertEqual(len(lines), 11)


# ==================== VIEW TESTS ====================
class TestOfferView(APITestCase):
    """Test Offer API views"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_offers(self):
        """Test offers list endpoint"""
        # Create offers
        for i in range(5):
            OfferFactory.create(is_active=True)
        
        url = '/api/v1/offers/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 5)
    
    def test_get_featured_offers(self):
        """Test featured offers endpoint"""
        # Create featured offers
        for i in range(3):
            OfferFactory.create(is_active=True, is_featured=True)
        
        # Create non-featured offers
        for i in range(2):
            OfferFactory.create(is_active=True, is_featured=False)
        
        url = '/api/v1/offers/featured/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        for offer in response.data:
            self.assertTrue(offer['is_featured'])
    
    def test_get_offer_detail(self):
        """Test offer detail endpoint"""
        offer = OfferFactory.create(is_active=True)
        
        url = f'/api/v1/offers/{offer.id}/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], offer.id)
        self.assertEqual(response.data['title'], offer.title)
    
    def test_get_categories(self):
        """Test categories endpoint"""
        # Create categories
        for i in range(3):
            OfferCategoryFactory.create(is_active=True)
        
        url = '/api/v1/offers/categories/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
    
    def test_get_offers_by_category(self):
        """Test offers by category endpoint"""
        category = OfferCategoryFactory.create()
        
        # Create offers in category
        for i in range(4):
            OfferFactory.create(category=category, is_active=True)
        
        # Create offers in other category
        for i in range(2):
            OfferFactory.create(is_active=True)
        
        url = f'/api/v1/offers/category/{category.id}/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)
        for offer in response.data['results']:
            self.assertEqual(offer['category'], category.id)
    
    def test_search_offers(self):
        """Test offer search endpoint"""
        # Create searchable offers
        OfferFactory.create(title='Facebook App Install', is_active=True)
        OfferFactory.create(title='Instagram Follow', is_active=True)
        OfferFactory.create(title='WhatsApp Usage Survey', is_active=True)
        OfferFactory.create(title='Mobile Game Play', is_active=True)
        
        url = '/api/v1/offers/search/'
        params = {'q': 'facebook'}
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Facebook', response.data['results'][0]['title'])
    
    def test_filter_offers(self):
        """Test offer filtering endpoint"""
        # Create offers with different attributes
        OfferFactory.create(
            title='High Payout Offer',
            payout=Decimal('500.00'),
            difficulty='hard',
            is_active=True
        )
        OfferFactory.create(
            title='Easy Mobile Offer',
            payout=Decimal('50.00'),
            difficulty='easy',
            platform='mobile',
            is_active=True
        )
        
        url = '/api/v1/offers/filter/'
        params = {
            'min_payout': '100',
            'max_payout': '1000',
            'difficulty': 'hard'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'High Payout Offer')
    
    def test_start_offer_completion(self):
        """Test start offer completion endpoint"""
        offer = OfferFactory.create(is_active=True, available_completions=10)
        
        url = f'/api/v1/offers/{offer.id}/start/'
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['offer'], offer.id)
        self.assertEqual(response.data['user'], self.user.id)
        self.assertEqual(response.data['status'], 'pending')
        self.assertIsNotNone(response.data['tracking_id'])
    
    def test_complete_offer(self):
        """Test complete offer endpoint"""
        completion = UserOfferCompletionFactory.create(
            user=self.user,
            offer=OfferFactory.create(),
            status='pending'
        )
        
        url = f'/api/v1/offers/completions/{completion.id}/complete/'
        data = {
            'proof': 'screenshot.jpg',
            'notes': 'Completed successfully'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'pending_review')
    
    def test_get_user_completions(self):
        """Test user completions endpoint"""
        # Create completions for user
        for i in range(5):
            UserOfferCompletionFactory.create(user=self.user)
        
        # Create completions for other user
        for i in range(3):
            UserOfferCompletionFactory.create()
        
        url = '/api/v1/offers/completions/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 5)
        for completion in response.data['results']:
            self.assertEqual(completion['user'], self.user.id)
    
    def test_track_impression(self):
        """Test impression tracking endpoint"""
        offer = OfferFactory.create()
        
        url = f'/api/v1/offers/{offer.id}/track/'
        data = {
            'impression_type': 'view',
            'source': 'organic',
            'medium': 'web'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['offer'], offer.id)
        self.assertEqual(response.data['user'], self.user.id)
        self.assertEqual(response.data['impression_type'], 'view')
    
    def test_get_recommendations(self):
        """Test recommendations endpoint"""
        # Create offers for recommendations
        for i in range(10):
            OfferFactory.create(is_active=True)
        
        url = '/api/v1/offers/recommendations/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertLessEqual(len(response.data), 10)
    
    def test_get_trending_offers(self):
        """Test trending offers endpoint"""
        url = '/api/v1/offers/trending/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_get_high_paying_offers(self):
        """Test high paying offers endpoint"""
        # Create high paying offers
        for payout in [500, 400, 300]:
            OfferFactory.create(
                payout=Decimal(str(payout)),
                is_active=True
            )
        
        url = '/api/v1/offers/high-paying/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should be ordered by payout descending
        payouts = [offer['payout'] for offer in response.data]
        self.assertEqual(payouts, sorted(payouts, reverse=True))
        
        # Top offer should have highest payout
        self.assertEqual(response.data[0]['payout'], '500.00')
    
    def test_get_quick_offers(self):
        """Test quick offers endpoint"""
        url = '/api/v1/offers/quick/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


# ==================== INTEGRATION TESTS ====================
class TestOfferIntegration(APITestCase):
    """Integration tests for offer workflows"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_complete_offer_workflow(self):
        """Test complete offer workflow"""
        # 1. Browse offers
        offer = OfferFactory.create(
            title='Test Offer',
            payout=Decimal('100.00'),
            available_completions=10,
            is_active=True
        )
        
        url = '/api/v1/offers/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 2. View offer detail
        url = f'/api/v1/offers/{offer.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Track impression
        url = f'/api/v1/offers/{offer.id}/track/'
        data = {'impression_type': 'view', 'source': 'direct'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        impression_id = response.data['id']
        
        # 4. Track click
        url = f'/api/v1/offers/{offer.id}/track/'
        data = {'impression_type': 'click', 'source': 'direct'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        click_id = response.data['id']
        
        # 5. Start completion
        url = f'/api/v1/offers/{offer.id}/start/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        completion_id = response.data['id']
        
        # 6. Complete offer
        url = f'/api/v1/offers/completions/{completion_id}/complete/'
        data = {
            'proof': 'screenshot.jpg',
            'notes': 'Completed successfully'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 7. Track conversion
        url = f'/api/v1/offers/track/{click_id}/conversion/'
        data = {'conversion_value': '100.00'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 8. Check completion status
        url = f'/api/v1/offers/completions/{completion_id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'pending_review')
        
        # 9. Admin approves completion
        admin = UserFactory.create(
            email='admin@example.com',
            user_type='admin',
            is_staff=True,
            is_superuser=True
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        
        url = f'/api/v1/admin/offers/completions/{completion_id}/approve/'
        data = {'notes': 'Proof verified'}
        response = admin_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 10. Verify wallet credit
        url = '/api/v1/wallet/balance/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Balance should be increased by offer payout (minus commission if any)
        # This depends on commission rate
        
        # 11. Verify offer availability decreased
        offer.refresh_from_db()
        self.assertEqual(offer.available_completions, 9)
        
        # 12. Check completion in history
        url = '/api/v1/offers/completions/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # The response should contain sanitized data or the original data
        # depending on your security approach
        # Either way, it shouldn't execute the script
        self.assertIsInstance(response.data['title'], str)