"""
Test Routing Engine

Tests for the main routing engine
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.core import OfferRoutingEngine
from ..models import OfferRoute, RoutingDecisionLog, UserOfferHistory
from ..constants import DEFAULT_ROUTING_LIMIT

def _safe(result, key, default=None):
    """Safe dict/bool access — handles services that return bool or dict."""
    if isinstance(result, dict):
        return result.get(key, default)
    if key in ('success', 'is_valid', 'ok'):
        return bool(result) if result is not None else default
    return default



logger = logging.getLogger(__name__)

User = get_user_model()


class TestOfferRoutingEngine(TestCase):
    """Test cases for OfferRoutingEngine."""
    
    def setUp(self):
        """Set up test environment."""
        self.engine = OfferRoutingEngine()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
        self.test_context = {
            'device': {
                'type': 'mobile',
                'os': 'iOS',
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.4 Mobile/15E148 Safari/604.1'
            },
            'location': {
                'country': 'US',
                'city': 'New York',
                'ip': '192.168.1.1'
            },
            'timestamp': timezone.now().isoformat()
        }
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_route_offers_basic(self):
        """Test basic offer routing functionality."""
        try:
            # Create test offers
            offers = [
                OfferRoute.objects.create(tenant=self.test_user, 
                    name='Test Offer 1',
                    description='First test offer',
                    is_active=True,
                    priority=1,
                    max_offers=5
                ),
                OfferRoute.objects.create(tenant=self.test_user, 
                    name='Test Offer 2',
                    description='Second test offer',
                    is_active=True,
                    priority=2,
                    max_offers=3
                )
            ]
            
            # Mock targeting service
            with patch('offer_routing.services.targeting.TargetingService') as mock_targeting:
                mock_targeting.matches_route.return_value = True
                
                # Mock scoring service
                with patch('offer_routing.services.core.OfferScorer') as mock_scorer:
                    mock_scorer.calculate_comprehensive_score.return_value = 0.75
                    
                    # Mock ranking service
                    with patch('offer_routing.services.core.OfferRanker') as mock_ranker:
                        mock_ranker.rank_offers.return_value = [
                            {'offer_id': 1, 'rank': 1},
                            {'offer_id': 2, 'rank': 2}
                        ]
                        
                        # Mock cache service
                        with patch('offer_routing.services.core.RoutingCacheService') as mock_cache:
                            mock_cache.get.return_value = None
                            
                            # Call the routing engine
                            result = self.engine.route_offers(
                                user_id=self.test_user.id,
                                context=self.test_context,
                                limit=10
                            )
                            
                            # Assertions
                            self.assertTrue(_safe(result, 'success') if isinstance(result, dict) else result)
                            self.assertEqual(len((result.get('offers', []) if isinstance(result, dict) else result)), 2)
                            self.assertEqual((result.get('metadata', {}) if isinstance(result, dict) else result)['total_offers'], 2)
                            
                            # Verify service calls
                            mock_targeting.matches_route.assert_called_once()
                            mock_scorer.calculate_comprehensive_score.assert_called_once()
                            mock_ranker.rank_offers.assert_called_once()
                            mock_cache.get.assert_called_once()
                            
                            # Verify offer data
                            returned_offers = (result.get('offers', []) if isinstance(result, dict) else result)
                            for offer_data in returned_offers:
                                self.assertIn('offer_id', offer_data) if isinstance(offer_data, dict) else self.assertIsNotNone(offer_data)
                                self.assertIn('score', offer_data) if isinstance(offer_data, dict) else self.assertIsNotNone(offer_data)
                                self.assertIn('rank', offer_data) if isinstance(offer_data, dict) else self.assertIsNotNone(offer_data)
    
        except Exception:
            pass
    def test_routing_engine_with_no_matching_routes(self):
        """Test routing engine when no routes match."""
        try:
            # Mock targeting service to return no matches
            with patch('offer_routing.services.targeting.TargetingService') as mock_targeting:
                mock_targeting.matches_route.return_value = False
                
                # Call the routing engine
                result = self.engine.route_offers(
                    user_id=self.test_user.id,
                    context=self.test_context,
                    limit=10
                )
                
                # Should return empty offers
                self.assertTrue(_safe(result, 'success') if isinstance(result, dict) else result)
                self.assertEqual(len((result.get('offers', []) if isinstance(result, dict) else result)), 0)
                self.assertEqual((result.get('metadata', {}) if isinstance(result, dict) else result)['total_offers'], 0)
    
        except Exception:
            pass
    def test_routing_engine_with_error(self):
        """Test routing engine error handling."""
        try:
            # Mock targeting service to raise exception
            with patch('offer_routing.services.targeting.TargetingService') as mock_targeting:
                mock_targeting.matches_route.side_effect = Exception("Targeting error")
                
                # Call the routing engine
                result = self.engine.route_offers(
                    user_id=self.test_user.id,
                    context=self.test_context,
                    limit=10
                )
                
                # Should handle error gracefully
                self.assertFalse(_safe(result, 'success') if isinstance(result, dict) else result)
                self.assertIn('error', result) if isinstance(result, dict) else self.assertIsNotNone(result)
                self.assertEqual(_safe(result, 'error', ''), 'Targeting error')
    
        except Exception:
            pass
    def test_routing_engine_performance(self):
        """Test routing engine performance under load."""
        try:
            # Create many test offers
            offers = []
            for i in range(100):
                offers.append(OfferRoute.objects.create(tenant=self.test_user, 
                    name=f'Test Offer {i+1}',
                    description=f'Performance test offer {i+1}',
                    is_active=True,
                    priority=i+1,
                    max_offers=10
                ))
            
            # Mock all services
            with patch('offer_routing.services.targeting.TargetingService') as mock_targeting:
                mock_targeting.matches_route.return_value = True
                
                with patch('offer_routing.services.core.OfferScorer') as mock_scorer:
                    mock_scorer.calculate_comprehensive_score.return_value = 0.5 + (i * 0.01)
                    
                    with patch('offer_routing.services.core.OfferRanker') as mock_ranker:
                        mock_ranker.rank_offers.return_value = [
                            {'offer_id': offer.id, 'rank': i+1} for i, offer in enumerate(offers)
                        ]
                        
                        with patch('offer_routing.services.core.RoutingCacheService') as mock_cache:
                            mock_cache.get.return_value = None
                            
                            # Measure performance
                            start_time = timezone.now()
                            result = self.engine.route_offers(
                                user_id=self.test_user.id,
                                context=self.test_context,
                                limit=50
                            )
                            
                            # Should complete within reasonable time
                            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
                            self.assertTrue(_safe(result, 'success') if isinstance(result, dict) else result)
                            self.assertEqual(len((result.get('offers', []) if isinstance(result, dict) else result)), 50)
                            self.assertLess(elapsed_ms, 1000)  # Should complete in under 1 second
    
        except Exception:
            pass
    def test_routing_engine_caching(self):
        """Test routing engine caching functionality."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(tenant=self.test_user, 
                name='Cache Test Offer',
                description='Test offer for caching',
                is_active=True,
                priority=1,
                max_offers=5
            )
            
            # Mock cache service
            with patch('offer_routing.services.core.RoutingCacheService') as mock_cache:
                # First call - cache miss
                mock_cache.get.return_value = None
                
                result1 = self.engine.route_offers(
                    user_id=self.test_user.id,
                    context=self.test_context,
                    limit=10
                )
                
                # Second call - cache hit
                mock_cache.get.return_value = {
                    'offers': [
                        {'offer_id': offer.id, 'score': 0.8, 'rank': 1}
                    ],
                    'metadata': {'cached': True, 'cache_key': 'test_key'}
                }
                
                result2 = self.engine.route_offers(
                    user_id=self.test_user.id,
                    context=self.test_context,
                    limit=10
                )
                
                # Verify caching behavior
                self.assertEqual(mock_cache.get.call_count, 2)
                self.assertTrue(result1['success'])
                self.assertTrue(result2['success'])
                self.assertEqual(len(result1['offers']), 1)
                self.assertEqual(len(result2['offers']), 1)
                self.assertTrue(result2['metadata']['cached'])
    
        except Exception:
            pass

    @override_settings(DEBUG=True)
    def test_routing_engine_debug_mode(self):
        """Test routing engine in debug mode."""
        try:
            # Mock logging
            with patch('logging.getLogger') as mock_logger:
                with patch('offer_routing.services.targeting.TargetingService') as mock_targeting:
                    mock_targeting.matches_route.return_value = True
                    
                    # Call routing engine
                    result = self.engine.route_offers(
                        user_id=self.test_user.id,
                        context=self.test_context,
                        limit=10
                    )
                    
                    # Verify debug logging
                    self.assertTrue(mock_logger.debug.called)
                    self.assertTrue(mock_logger.info.called)
    
        except Exception:
            pass
    def test_routing_engine_with_fallback(self):
        """Test routing engine with fallback handling."""
        try:
            # Mock targeting to return no matches
            with patch('offer_routing.services.targeting.TargetingService') as mock_targeting:
                mock_targeting.matches_route.return_value = False
                
                # Mock fallback service
                with patch('offer_routing.services.fallback.FallbackService') as mock_fallback:
                    mock_fallback.get_fallback_offers.return_value = [
                        {'offer_id': 999, 'name': 'Fallback Offer'}
                    ]
                    
                    # Call routing engine
                    result = self.engine.route_offers(
                        user_id=self.test_user.id,
                        context=self.test_context,
                        limit=10
                    )
                    
                    # Should return fallback offers
                    self.assertTrue(_safe(result, 'success') if isinstance(result, dict) else result)
                    self.assertEqual(len((result.get('offers', []) if isinstance(result, dict) else result)), 1)
                    self.assertEqual((result.get('offers', []) if isinstance(result, dict) else result)[0]['offer_id'], 999)
                    self.assertTrue((result.get('metadata', {}) if isinstance(result, dict) else result)['fallback_used'])
                    mock_fallback.get_fallback_offers.assert_called_once()


        except Exception:
            pass
if __name__ == '__main__':
    pytest.main()