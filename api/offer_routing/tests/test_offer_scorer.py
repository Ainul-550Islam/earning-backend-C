"""
Test Offer Scorer

Tests for the offer scorer service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.core import OfferScorer
from ..models import OfferRoute, OfferScore, UserOfferHistory
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestOfferScorer(TestCase):
    """Test cases for OfferScorer service."""
    
    def setUp(self):
        """Set up test environment."""
        self.scorer = OfferScorer()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_calculate_comprehensive_score(self):
        """Test comprehensive score calculation."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Test Offer',
                description='Test offer for scoring',
                is_active=True,
                price=99.99,
                category='test'
            )
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer=offer,
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1),
                completed_at=timezone.now() - timezone.timedelta(hours=2)
                conversion_value=50.0
            )
            
            # Test score calculation
            score = self.scorer.calculate_comprehensive_score(offer)
            
            # Assertions
            self.assertIsInstance(score, dict)
            self.assertIn('total_score', score)
            self.assertIn('epc_score', score)
            self.assertIn('cr_score', score)
            self.assertIn('freshness_score', score)
            self.assertIn('personalization_score', score)
            self.assertIn('final_score', score)
            self.assertGreaterEqual(score['final_score'], 0.0)
            self.assertLessEqual(score['final_score'], 1.0)
            
            # Verify score components are reasonable
            self.assertGreaterEqual(score['epc_score'], 0.0)
            self.assertLessEqual(score['epc_score'], 1.0)
            self.assertGreaterEqual(score['cr_score'], 0.0)
            self.assertLessEqual(score['cr_score'], 1.0)
            self.assertGreaterEqual(score['freshness_score'], 0.0)
            self.assertLessEqual(score['freshness_score'], 1.0)
            
        except Exception as e:
            self.fail(f"Error in calculate_comprehensive_score: {e}")
    
    def test_calculate_epc_score(self):
        """Test EPC score calculation."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Test Offer',
                description='Test offer for EPC',
                is_active=True,
                price=100.0
                category='test'
            )
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer=offer,
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1),
                completed_at=timezone.now() - timezone.timedelta(hours=2),
                conversion_value=20.0
            )
            
            # Test EPC calculation
            epc_score = self.scorer.calculate_epc_score(offer)
            
            # Assertions
            self.assertIsInstance(epc_score, dict)
            self.assertIn('epc_score', epc_score)
            self.assertIn('total_revenue', epc_score)
            self.assertIn('total_conversions', epc_score)
            self.assertIn('total_clicks', epc_score)
            self.assertIn('epc_value', epc_score)
            
            # Verify EPC calculation
            expected_epc = epc_score['total_revenue'] / epc_score['total_conversions']
            self.assertAlmostEqual(epc_score['epc_value'], expected_epc, places=2)
            
        except Exception as e:
            self.fail(f"Error in calculate_epc_score: {e}")
    
    def test_calculate_cr_score(self):
        """Test conversion rate score calculation."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Test Offer',
                description='Test offer for CR',
                is_active=True,
                price=100.0,
                category='test'
            )
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer=offer,
                score_at_time=0.7,
                clicked_at=timezone.now() - timezone.timedelta(hours=1),
                completed_at=timezone.now() - timezone.timedelta(hours=2),
                conversion_value=30.0
            )
            
            # Test CR calculation
            cr_score = self.scorer.calculate_cr_score(offer)
            
            # Assertions
            self.assertIsInstance(cr_score, dict)
            self.assertIn('cr_score', cr_score)
            self.assertIn('total_clicks', cr_score)
            self.assertIn('total_conversions', cr_score)
            self.assertIn('cr_value', cr_score)
            
            # Verify CR calculation
            expected_cr = cr_score['total_conversions'] / cr_score['total_clicks']
            self.assertAlmostEqual(cr_score['cr_value'], expected_cr, places=2)
            
        except Exception as e:
            self.fail(f"Error in calculate_cr_score: {e}")
    
    def test_calculate_freshness_score(self):
        """Test freshness score calculation."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Test Offer',
                description='Test offer for freshness',
                is_active=True,
                price=100.0,
                category='test',
                created_at=timezone.now() - timezone.timedelta(days=7)
            )
            
            # Test freshness calculation
            freshness_score = self.scorer.calculate_freshness_score(offer)
            
            # Assertions
            self.assertIsInstance(freshness_score, dict)
            self.assertIn('freshness_score', freshness_score)
            self.assertIn('days_since_creation', freshness_score)
            self.assertIn('freshness_factor', freshness_score)
            
            # Verify freshness calculation
            expected_days = 7
            self.assertAlmostEqual(freshness_score['days_since_creation'], expected_days, places=0)
            expected_factor = 0.5  # 50% freshness factor for 7 days
            self.assertAlmostEqual(freshness_score['freshness_factor'], expected_factor, places=2)
            
        except Exception as e:
            self.fail(f"Error in calculate_freshness_score: {e}")
    
    def test_calculate_personalization_score(self):
        """Test personalization score calculation."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Test Offer',
                description='Test offer for personalization',
                is_active=True,
                price=100.0,
                category='test'
            )
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer=offer,
                score_at_time=0.9,
                clicked_at=timezone.now() - timezone.timedelta(hours=1),
                completed_at=timezone.now() - timezone.timedelta(hours=2),
                conversion_value=40.0
            )
            
            # Test personalization calculation
            personalization_score = self.scorer.calculate_personalization_score(offer)
            
            # Assertions
            self.assertIsInstance(personalization_score, dict)
            self.assertIn('personalization_score', personalization_score)
            self.assertIn('user_affinity', personalization_score)
            self.assertIn('category_affinity', personalization_score)
            self.assertIn('behavioral_score', personalization_score)
            self.assertIn('final_score', personalization_score)
            
        except Exception as e:
            self.fail(f"Error in calculate_personalization_score: {e}")
    
    def test_score_with_no_history(self):
        """Test score calculation with no user history."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Test Offer',
                description='Test offer with no history',
                is_active=True,
                price=100.0,
                category='test'
            )
            
            # Test score calculation
            score = self.scorer.calculate_comprehensive_score(offer)
            
            # Assertions
            self.assertIsInstance(score, dict)
            self.assertIn('final_score', score)
            self.assertLessEqual(score['final_score'], 0.5)  # Should be lower without history
            
        except Exception as e:
            self.fail(f"Error in test_score_with_no_history: {e}")
    
    def test_health_check(self):
        """Test scorer health check."""
        try:
            # Test health check
            health = self.scorer.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('stats', health)
            
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")


if __name__ == '__main__':
    pytest.main()
