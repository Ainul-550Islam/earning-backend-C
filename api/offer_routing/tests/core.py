"""
Core Tests for Offer Routing System

This module contains unit tests for core routing functionality,
including the routing engine, cache service, and basic operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.core import OfferRoutingEngine, routing_engine
from ..services.cache import RoutingCacheService, cache_service
from ..models import OfferRoute, RoutingDecisionLog
from ..exceptions import (
    RouteNotFoundError, OfferNotFoundError, ValidationError,
    RoutingTimeoutError, CacheError
)

User = get_user_model()


class OfferRoutingEngineTestCase(TestCase):
    """Test cases for OfferRoutingEngine."""
    
    def setUp(self):
        """Set up test data."""
        self.engine = OfferRoutingEngine()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer route
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_route_offers_success(self):
        """Test successful offer routing."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        result = self.engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5
        )
        
        self.assertTrue(result['success'])
        self.assertIn('offers', result)
        self.assertIn('metadata', result)
        self.assertLessEqual(len(result['offers']), 5)
    
    def test_route_offers_invalid_user(self):
        """Test routing with invalid user ID."""
        context = {'location': {'country': 'US'}}
        
        with self.assertRaises(User.DoesNotExist):
            self.engine.route_offers(
                user_id=999999,
                context=context,
                limit=5
            )
    
    def test_route_offers_empty_context(self):
        """Test routing with empty context."""
        result = self.engine.route_offers(
            user_id=self.user.id,
            context={},
            limit=5
        )
        
        self.assertTrue(result['success'])
        self.assertIn('offers', result)
    
    @patch('api.offer_routing.services.core.routing_engine')
    def test_route_offers_timeout(self, mock_engine):
        """Test routing timeout handling."""
        mock_engine.route_offers.side_effect = RoutingTimeoutError("Routing timeout")
        
        with self.assertRaises(RoutingTimeoutError):
            self.engine.route_offers(
                user_id=self.user.id,
                context={},
                limit=5
            )
    
    def test_route_offers_cache_enabled(self):
        """Test routing with cache enabled."""
        context = {'location': {'country': 'US'}}
        
        result = self.engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5,
            cache_enabled=True
        )
        
        self.assertTrue(result['success'])
        self.assertIn('cache_hit', result['metadata'])
    
    def test_route_offers_cache_disabled(self):
        """Test routing with cache disabled."""
        context = {'location': {'country': 'US'}}
        
        result = self.engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5,
            cache_enabled=False
        )
        
        self.assertTrue(result['success'])
        self.assertFalse(result['metadata'].get('cache_hit', False))
    
    def test_get_matching_routes(self):
        """Test getting matching routes for user."""
        context = {'location': {'country': 'US'}}
        
        routes = self.engine.get_matching_routes(
            user_id=self.user.id,
            context=context
        )
        
        self.assertIsInstance(routes, list)
        # Should include our test route
        route_ids = [route.id for route in routes]
        self.assertIn(self.offer_route.id, route_ids)
    
    def test_score_offers(self):
        """Test offer scoring."""
        offers = [self.offer_route]
        context = {'location': {'country': 'US'}}
        
        scored_offers = self.engine.score_offers(
            user_id=self.user.id,
            offers=offers,
            context=context
        )
        
        self.assertIsInstance(scored_offers, list)
        self.assertEqual(len(scored_offers), len(offers))
        
        # Each scored offer should have a score
        for scored_offer in scored_offers:
            self.assertIn('score', scored_offer)
            self.assertIsInstance(scored_offer['score'], (int, float))
    
    def test_apply_personalization(self):
        """Test personalization application."""
        offers = [self.offer_route]
        score_data = {'score': 85.5}
        context = {'location': {'country': 'US'}}
        
        personalized_offers = self.engine.apply_personalization(
            user_id=self.user.id,
            offers=offers,
            score_data=score_data,
            context=context
        )
        
        self.assertIsInstance(personalized_offers, list)
        self.assertEqual(len(personalized_offers), len(offers))
    
    def test_check_caps(self):
        """Test cap checking."""
        offers = [self.offer_route]
        
        filtered_offers = self.engine.check_caps(
            user_id=self.user.id,
            offers=offers
        )
        
        self.assertIsInstance(filtered_offers, list)
        # Should return offers if caps are not exceeded
    
    def test_apply_ab_testing(self):
        """Test A/B testing application."""
        offers = [self.offer_route]
        
        filtered_offers = self.engine.apply_ab_testing(
            user_id=self.user.id,
            offers=offers
        )
        
        self.assertIsInstance(filtered_offers, list)
        self.assertEqual(len(filtered_offers), len(offers))
    
    def test_apply_fallback(self):
        """Test fallback application."""
        offers = []  # Empty offers list to trigger fallback
        
        fallback_offers = self.engine.apply_fallback(
            user_id=self.user.id,
            offers=offers,
            context={}
        )
        
        self.assertIsInstance(fallback_offers, list)
    
    def test_create_routing_result(self):
        """Test routing result creation."""
        offers = [self.offer_route]
        metadata = {'response_time_ms': 45.2}
        
        result = self.engine.create_routing_result(
            success=True,
            offers=offers,
            metadata=metadata
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['offers']), len(offers))
        self.assertEqual(result['metadata'], metadata)
    
    def test_log_routing_decision(self):
        """Test routing decision logging."""
        offers = [self.offer_route]
        metadata = {'response_time_ms': 45.2}
        
        # Log decision
        decision = self.engine.log_routing_decision(
            user_id=self.user.id,
            offers=offers,
            metadata=metadata
        )
        
        self.assertIsInstance(decision, RoutingDecisionLog)
        self.assertEqual(decision.user, self.user)
        self.assertEqual(decision.response_time_ms, metadata['response_time_ms'])
    
    def test_validate_routing_data(self):
        """Test routing data validation."""
        valid_data = {
            'user_id': self.user.id,
            'context': {'location': {'country': 'US'}},
            'limit': 5
        }
        
        is_valid, errors, warnings = self.engine.validate_routing_data(valid_data)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_routing_data_invalid(self):
        """Test routing data validation with invalid data."""
        invalid_data = {
            'user_id': None,  # Invalid user ID
            'context': {},  # Empty context
            'limit': -1  # Invalid limit
        }
        
        is_valid, errors, warnings = self.engine.validate_routing_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_get_routing_stats(self):
        """Test routing statistics retrieval."""
        stats = self.engine.get_routing_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_routes', stats)
        self.assertIn('active_routes', stats)
    
    def test_optimize_configuration(self):
        """Test configuration optimization."""
        result = self.engine.optimize_configuration()
        
        self.assertTrue(result.get('success', False))
    
    def test_clear_cache(self):
        """Test cache clearing."""
        result = self.engine.clear_cache()
        
        self.assertTrue(result.get('success', False))


class RoutingCacheServiceTestCase(TestCase):
    """Test cases for RoutingCacheService."""
    
    def setUp(self):
        """Set up test data."""
        self.cache_service = RoutingCacheService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer route
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_cache_routing_result(self):
        """Test caching routing results."""
        cache_key = f"routing_result:{self.user.id}:test_hash"
        result_data = {'offers': [{'id': self.offer_route.id}], 'success': True}
        
        # Cache result
        self.cache_service.cache_routing_result(
            user_id=self.user.id,
            context_hash='test_hash',
            result=result_data
        )
        
        # Retrieve cached result
        cached_result = self.cache_service.get_cached_routing_result(
            user_id=self.user.id,
            context_hash='test_hash'
        )
        
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result['success'], result_data['success'])
    
    def test_get_cached_routing_result_miss(self):
        """Test cache miss for routing result."""
        cached_result = self.cache_service.get_cached_routing_result(
            user_id=self.user.id,
            context_hash='nonexistent_hash'
        )
        
        self.assertIsNone(cached_result)
    
    def test_cache_offer_score(self):
        """Test caching offer scores."""
        score_data = {'score': 85.5, 'epc': 2.5, 'cr': 3.2}
        
        # Cache score
        self.cache_service.cache_offer_score(
            offer_id=self.offer_route.id,
            user_id=self.user.id,
            score_data=score_data
        )
        
        # Retrieve cached score
        cached_score = self.cache_service.get_cached_offer_score(
            offer_id=self.offer_route.id,
            user_id=self.user.id
        )
        
        self.assertIsNotNone(cached_score)
        self.assertEqual(cached_score['score'], score_data['score'])
    
    def test_cache_user_cap(self):
        """Test caching user caps."""
        cap_data = {'shown_today': 5, 'max_shows_per_day': 10}
        
        # Cache cap
        self.cache_service.cache_user_cap(
            user_id=self.user.id,
            offer_id=self.offer_route.id,
            cap_data=cap_data
        )
        
        # Retrieve cached cap
        cached_cap = self.cache_service.get_cached_user_cap(
            user_id=self.user.id,
            offer_id=self.offer_route.id
        )
        
        self.assertIsNotNone(cached_cap)
        self.assertEqual(cached_cap['shown_today'], cap_data['shown_today'])
    
    def test_cache_affinity_score(self):
        """Test caching affinity scores."""
        affinity_data = {'score': 0.75, 'confidence': 0.9}
        
        # Cache affinity
        self.cache_service.cache_affinity_score(
            user_id=self.user.id,
            category='test_category',
            affinity_data=affinity_data
        )
        
        # Retrieve cached affinity
        cached_affinity = self.cache_service.get_cached_affinity_score(
            user_id=self.user.id,
            category='test_category'
        )
        
        self.assertIsNotNone(cached_affinity)
        self.assertEqual(cached_affinity['score'], affinity_data['score'])
    
    def test_cache_preference_vector(self):
        """Test caching preference vectors."""
        vector_data = {'category_weights': {'tech': 0.8, 'finance': 0.6}}
        
        # Cache vector
        self.cache_service.cache_preference_vector(
            user_id=self.user.id,
            vector_data=vector_data
        )
        
        # Retrieve cached vector
        cached_vector = self.cache_service.get_cached_preference_vector(
            user_id=self.user.id
        )
        
        self.assertIsNotNone(cached_vector)
        self.assertEqual(cached_vector['category_weights'], vector_data['category_weights'])
    
    def test_cache_contextual_signal(self):
        """Test caching contextual signals."""
        signal_data = {'signal_type': 'time', 'value': 'morning'}
        
        # Cache signal
        self.cache_service.cache_contextual_signal(
            user_id=self.user.id,
            signal_type='time',
            signal_data=signal_data
        )
        
        # Retrieve cached signal
        cached_signal = self.cache_service.get_cached_contextual_signal(
            user_id=self.user.id,
            signal_type='time'
        )
        
        self.assertIsNotNone(cached_signal)
        self.assertEqual(cached_signal['signal_type'], signal_data['signal_type'])
    
    def test_invalidate_user_cache(self):
        """Test user cache invalidation."""
        # Cache some data first
        self.cache_service.cache_routing_result(
            user_id=self.user.id,
            context_hash='test_hash',
            result={'offers': []}
        )
        
        # Invalidate user cache
        invalidated_count = self.cache_service.invalidate_user_cache(self.user.id)
        
        self.assertGreater(invalidated_count, 0)
    
    def test_invalidate_offer_cache(self):
        """Test offer cache invalidation."""
        # Cache some data first
        self.cache_service.cache_offer_score(
            offer_id=self.offer_route.id,
            user_id=self.user.id,
            score_data={'score': 85.5}
        )
        
        # Invalidate offer cache
        invalidated_count = self.cache_service.invalidate_offer_cache(self.offer_route.id)
        
        self.assertGreater(invalidated_count, 0)
    
    def test_cleanup_expired_cache(self):
        """Test cleanup of expired cache entries."""
        # This would clean up expired entries
        cleaned_count = self.cache_service.cleanup_expired_cache()
        
        self.assertIsInstance(cleaned_count, int)
        self.assertGreaterEqual(cleaned_count, 0)
    
    def test_get_cache_stats(self):
        """Test cache statistics retrieval."""
        stats = self.cache_service.get_cache_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_keys', stats)
        self.assertIn('memory_usage', stats)
    
    def test_warm_up_cache(self):
        """Test cache warming."""
        result = self.cache_service.warm_up_cache()
        
        self.assertIsInstance(result, dict)
        self.assertIn('warmed_entries', result)
    
    def test_optimize_cache(self):
        """Test cache optimization."""
        result = self.cache_service.optimize_cache()
        
        self.assertTrue(result.get('success', False))


class IntegrationTestCase(TestCase):
    """Integration tests for core functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for integration testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_end_to_end_routing(self):
        """Test end-to-end routing process."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'user_agent': 'Mozilla/5.0'
        }
        
        # Route offers
        result = routing_engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5
        )
        
        self.assertTrue(result['success'])
        self.assertIn('offers', result)
        
        # Check if decision was logged
        decision = RoutingDecisionLog.objects.filter(
            user=self.user
        ).first()
        
        self.assertIsNotNone(decision)
        self.assertEqual(decision.user, self.user)
    
    def test_cache_integration(self):
        """Test cache integration with routing."""
        context = {'location': {'country': 'US'}}
        
        # First call should cache result
        result1 = routing_engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5,
            cache_enabled=True
        )
        
        # Second call should use cache
        result2 = routing_engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5,
            cache_enabled=True
        )
        
        self.assertTrue(result1['success'])
        self.assertTrue(result2['success'])
        self.assertEqual(result1['offers'], result2['offers'])
    
    def test_routing_with_error_handling(self):
        """Test routing with error handling."""
        # Test with invalid context
        with self.assertRaises(ValidationError):
            routing_engine.route_offers(
                user_id=self.user.id,
                context={'invalid': 'data'},
                limit=5
            )
    
    def test_routing_performance(self):
        """Test routing performance."""
        import time
        
        context = {'location': {'country': 'US'}}
        
        # Measure routing time
        start_time = time.time()
        result = routing_engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=10
        )
        end_time = time.time()
        
        routing_time = (end_time - start_time) * 1000  # Convert to ms
        
        self.assertTrue(result['success'])
        self.assertLess(routing_time, 1000)  # Should complete within 1 second
