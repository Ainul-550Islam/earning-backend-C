"""
Test Offer Ranker

Tests for the offer ranker service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.core import OfferRanker
from ..models import OfferRoute, GlobalOfferRank
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestOfferRanker(TestCase):
    """Test cases for OfferRanker service."""
    
    def setUp(self):
        """Set up test environment."""
        self.ranker = OfferRanker()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_rank_offers_basic(self):
        """Test basic offer ranking functionality."""
        try:
            # Create test offers
            offers = [
                OfferRoute.objects.create(
                    name='High Score Offer',
                    description='High scoring test offer',
                    is_active=True,
                    price=100.0,
                    category='test'
                ),
                OfferRoute.objects.create(
                    name='Medium Score Offer',
                    description='Medium scoring test offer',
                    is_active=True,
                    price=50.0,
                    category='test'
                ),
                OfferRoute.objects.create(
                    name='Low Score Offer',
                    description='Low scoring test offer',
                    is_active=True,
                    price=25.0,
                    category='test'
                )
            ]
            
            # Mock scoring service
            with patch('..services.core.OfferScorer') as mock_scorer:
                mock_scorer.calculate_comprehensive_score.side_effect = [
                    {'final_score': 0.9},  # High score
                    {'final_score': 0.6},  # Medium score
                    {'final_score': 0.3}   # Low score
                ]
                
                # Mock analytics service
                with patch('..services.analytics.analytics_service') as mock_analytics:
                    mock_analytics.get_route_analytics.side_effect = [
                        {'performance_score': 0.8},
                        {'performance_score': 0.5},
                        {'performance_score': 0.2}
                    ]
                    
                    # Call ranker
                    result = self.ranker.rank_offers(offers)
                    
                    # Assertions
                    self.assertTrue(result['success'])
                    self.assertEqual(len(result['ranked_offers']), 3)
                    
                    # Verify ranking order (highest score first)
                    ranked_offers = result['ranked_offers']
                    self.assertEqual(ranked_offers[0]['offer_id'], offers[0].id)  # High score
                    self.assertEqual(ranked_offers[1]['offer_id'], offers[1].id)  # Medium score
                    self.assertEqual(ranked_offers[2]['offer_id'], offers[2].id)  # Low score
                    
                    # Verify ranking data
                    for i, ranked_offer in enumerate(ranked_offers):
                        self.assertEqual(ranked_offer['rank'], i + 1)
                        self.assertIn('score', ranked_offer)
                        self.assertIn('performance_score', ranked_offer)
                        
        except Exception as e:
            self.fail(f"Error in test_rank_offers_basic: {e}")
    
    def test_rank_offers_with_limit(self):
        """Test offer ranking with limit."""
        try:
            # Create test offers
            offers = []
            for i in range(10):
                offers.append(OfferRoute.objects.create(
                    name=f'Offer {i+1}',
                    description=f'Test offer {i+1}',
                    is_active=True,
                    price=10.0 * (i+1),
                    category='test'
                ))
            
            # Mock scoring service
            with patch('..services.core.OfferScorer') as mock_scorer:
                mock_scorer.calculate_comprehensive_score.side_effect = [
                    {'final_score': 0.9 - (i * 0.1)} for i in range(10)
                ]
                
                # Call ranker with limit
                result = self.ranker.rank_offers(offers, limit=5)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['ranked_offers']), 5)
                self.assertEqual(result['metadata']['total_offers'], 10)
                self.assertEqual(result['metadata']['limit'], 5)
                
        except Exception as e:
            self.fail(f"Error in test_rank_offers_with_limit: {e}")
    
    def test_rank_offers_by_category(self):
        """Test offer ranking by category."""
        try:
            # Create test offers in different categories
            offers = [
                OfferRoute.objects.create(
                    name='Electronics Offer',
                    description='Electronics test offer',
                    is_active=True,
                    price=100.0,
                    category='electronics'
                ),
                OfferRoute.objects.create(
                    name='Fashion Offer',
                    description='Fashion test offer',
                    is_active=True,
                    price=50.0,
                    category='fashion'
                ),
                OfferRoute.objects.create(
                    name='Home Offer',
                    description='Home test offer',
                    is_active=True,
                    price=25.0,
                    category='home'
                )
            ]
            
            # Mock scoring service
            with patch('..services.core.OfferScorer') as mock_scorer:
                mock_scorer.calculate_comprehensive_score.side_effect = [
                    {'final_score': 0.9},
                    {'final_score': 0.6},
                    {'final_score': 0.3}
                ]
                
                # Call ranker with category filter
                result = self.ranker.rank_offers(offers, category='electronics')
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['ranked_offers']), 1)  # Only electronics
                self.assertEqual(result['ranked_offers'][0]['offer_id'], offers[0].id)
                self.assertEqual(result['metadata']['category'], 'electronics')
                
        except Exception as e:
            self.fail(f"Error in test_rank_offers_by_category: {e}")
    
    def test_rank_offers_with_tie_handling(self):
        """Test offer ranking with tie handling."""
        try:
            # Create test offers with same score
            offers = [
                OfferRoute.objects.create(
                    name='Tie Offer 1',
                    description='First tie offer',
                    is_active=True,
                    price=100.0,
                    category='test'
                ),
                OfferRoute.objects.create(
                    name='Tie Offer 2',
                    description='Second tie offer',
                    is_active=True,
                    price=100.0,
                    category='test'
                )
            ]
            
            # Mock scoring service to return same score
            with patch('..services.core.OfferScorer') as mock_scorer:
                mock_scorer.calculate_comprehensive_score.return_value = {'final_score': 0.8}
                
                # Call ranker
                result = self.ranker.rank_offers(offers)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['ranked_offers']), 2)
                
                # Both should have same rank or tie-breaking logic
                ranked_offers = result['ranked_offers']
                self.assertEqual(ranked_offers[0]['score'], 0.8)
                self.assertEqual(ranked_offers[1]['score'], 0.8)
                
        except Exception as e:
            self.fail(f"Error in test_rank_offers_with_tie_handling: {e}")
    
    def test_calculate_global_ranking(self):
        """Test global ranking calculation."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Global Rank Test Offer',
                description='Test offer for global ranking',
                is_active=True,
                price=100.0,
                category='test'
            )
            
            # Mock analytics service
            with patch('..services.analytics.analytics_service') as mock_analytics:
                mock_analytics.get_route_analytics.return_value = {
                    'total_views': 1000,
                    'total_clicks': 100,
                    'total_conversions': 10,
                    'total_revenue': 500.0,
                    'performance_score': 0.8
                }
                
                # Mock category analytics
                mock_analytics.get_category_analytics.return_value = {
                    'category_rank': 3,
                    'category_performance': 0.7
                }
                
                # Mock regional analytics
                mock_analytics.get_regional_analytics.return_value = {
                    'regional_rank': 2,
                    'regional_performance': 0.9
                }
                
                # Calculate global ranking
                ranking = self.ranker.calculate_global_ranking(offer)
                
                # Assertions
                self.assertIsInstance(ranking, dict)
                self.assertIn('global_rank', ranking)
                self.assertIn('category_rank', ranking)
                self.assertIn('regional_rank', ranking)
                self.assertIn('performance_score', ranking)
                self.assertIn('overall_score', ranking)
                
                # Verify ranking values are reasonable
                self.assertGreaterEqual(ranking['global_rank'], 1)
                self.assertGreaterEqual(ranking['category_rank'], 1)
                self.assertGreaterEqual(ranking['regional_rank'], 1)
                self.assertGreaterEqual(ranking['performance_score'], 0.0)
                self.assertLessEqual(ranking['performance_score'], 1.0)
                
        except Exception as e:
            self.fail(f"Error in test_calculate_global_ranking: {e}")
    
    def test_update_global_rankings(self):
        """Test updating global rankings."""
        try:
            # Create test offers
            offers = []
            for i in range(5):
                offers.append(OfferRoute.objects.create(
                    name=f'Rank Update Test Offer {i+1}',
                    description=f'Test offer {i+1} for rank update',
                    is_active=True,
                    price=10.0 * (i+1),
                    category='test'
                ))
            
            # Mock ranking calculation
            with patch.object(self.ranker, 'calculate_global_ranking') as mock_ranking:
                mock_ranking.side_effect = [
                    {'global_rank': 1, 'overall_score': 0.9},
                    {'global_rank': 2, 'overall_score': 0.8},
                    {'global_rank': 3, 'overall_score': 0.7},
                    {'global_rank': 4, 'overall_score': 0.6},
                    {'global_rank': 5, 'overall_score': 0.5}
                ]
                
                # Update global rankings
                result = self.ranker.update_global_rankings(offers)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(result['updated_count'], 5)
                
                # Verify GlobalOfferRank records were created
                rankings = GlobalOfferRank.objects.filter(offer__in=offers).count()
                self.assertEqual(rankings, 5)
                
        except Exception as e:
            self.fail(f"Error in test_update_global_rankings: {e}")
    
    def test_rank_offers_performance(self):
        """Test ranking performance under load."""
        try:
            # Create many test offers
            offers = []
            for i in range(100):
                offers.append(OfferRoute.objects.create(
                    name=f'Performance Test Offer {i+1}',
                    description=f'Performance test offer {i+1}',
                    is_active=True,
                    price=10.0 * (i+1),
                    category='test'
                ))
            
            # Mock scoring service
            with patch('..services.core.OfferScorer') as mock_scorer:
                mock_scorer.calculate_comprehensive_score.return_value = {
                    'final_score': 0.8
                }
                
                # Measure performance
                start_time = timezone.now()
                result = self.ranker.rank_offers(offers)
                elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['ranked_offers']), 100)
                self.assertLess(elapsed_ms, 1000)  # Should complete in under 1 second
                
        except Exception as e:
            self.fail(f"Error in test_rank_offers_performance: {e}")
    
    def test_health_check(self):
        """Test ranker health check."""
        try:
            # Mock scoring service
            with patch('..services.core.OfferScorer') as mock_scorer:
                mock_scorer.health_check.return_value = {'status': 'healthy'}
                
                # Mock analytics service
                with patch('..services.analytics.analytics_service') as mock_analytics:
                    mock_analytics.health_check.return_value = {'status': 'healthy'}
                    
                    # Test health check
                    health = self.ranker.health_check()
                    
                    # Assertions
                    self.assertIsInstance(health, dict)
                    self.assertIn('status', health)
                    self.assertIn('scorer_health', health)
                    self.assertIn('analytics_health', health)
                    self.assertIn('cache_health', health)
                    self.assertIn('performance_stats', health)
                    self.assertIn('timestamp', health)
                    
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")


if __name__ == '__main__':
    pytest.main()
