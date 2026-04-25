"""
Integration Tests for Offer Routing System

This module contains integration tests that test the complete
offer routing system workflow and component interactions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.core import routing_engine
from ..services.scoring import scoring_service
from ..services.personalization import personalization_service
from ..services.targeting import targeting_service
from ..services.cap import cap_service
from ..services.fallback import fallback_service
from ..services.ab_test import ab_test_service
from ..services.analytics import analytics_service
from ..models import OfferRoute, RoutingDecisionLog, UserOfferHistory
from ..exceptions import RoutingError, ValidationError

User = get_user_model()


class EndToEndRoutingTestCase(TestCase):
    """Test cases for end-to-end routing workflow."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offers
        self.offers = []
        for i in range(5):
            offer = OfferRoute.objects.create(
                name=f'Test Offer {i}',
                description=f'Test offer {i} for integration testing',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
        
        # Create targeting rules
        from ..models import GeoRouteRule, DeviceRouteRule
        
        for offer in self.offers:
            GeoRouteRule.objects.create(
                route=offer,
                country='US',
                is_include=True
            )
            
            DeviceRouteRule.objects.create(
                route=offer,
                device_type='desktop',
                is_include=True
            )
    
    def test_complete_routing_workflow(self):
        """Test complete routing workflow from request to response."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0'
        }
        
        # Route offers
        result = routing_engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5
        )
        
        self.assertTrue(result['success'])
        self.assertIn('offers', result)
        self.assertIn('metadata', result)
        self.assertLessEqual(len(result['offers']), 5)
        
        # Check if decision was logged
        decision = RoutingDecisionLog.objects.filter(user=self.user).first()
        self.assertIsNotNone(decision)
        self.assertEqual(decision.user, self.user)
        
        # Check if offers have required fields
        for offer in result['offers']:
            self.assertIn('id', offer)
            self.assertIn('name', offer)
            self.assertIn('score', offer)
    
    def test_routing_with_all_components(self):
        """Test routing with all components enabled."""
        # Enable personalization
        from ..models import PersonalizationConfig
        PersonalizationConfig.objects.create(
            tenant=self.tenant,
            user=self.user,
            algorithm='hybrid',
            collaborative_weight=0.4,
            content_based_weight=0.3,
            hybrid_weight=0.3,
            real_time_enabled=True,
            context_signals_enabled=True
        )
        
        # Create caps
        from ..models import OfferRoutingCap
        for offer in self.offers:
            OfferRoutingCap.objects.create(
                tenant=self.tenant,
                offer=offer,
                cap_type='daily',
                cap_value=100,
                current_count=0
            )
        
        # Create fallback rule
        from ..models import FallbackRule
        FallbackRule.objects.create(
            tenant=self.tenant,
            name='Test Fallback',
            description='Test fallback rule',
            fallback_type='default',
            priority=5,
            is_active=True
        )
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        result = routing_engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5
        )
        
        self.assertTrue(result['success'])
        self.assertIn('offers', result)
        self.assertIn('metadata', result)
        
        # Check metadata for component usage
        metadata = result['metadata']
        self.assertIn('personalization_applied', metadata)
        self.assertIn('caps_checked', metadata)
        self.assertIn('fallback_used', metadata)
    
    def test_routing_with_ab_testing(self):
        """Test routing with A/B testing enabled."""
        # Create A/B test
        from ..models import RoutingABTest
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Integration A/B Test',
            description='Integration test for A/B testing',
            control_route=self.offers[0],
            variant_route=self.offers[1],
            split_percentage=50,
            min_sample_size=10,
            duration_hours=24,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.tenant
        )
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        result = routing_engine.route_offers(
            user_id=self.user.id,
            context=context,
            limit=5
        )
        
        self.assertTrue(result['success'])
        self.assertIn('offers', result)
        
        # Check if A/B test assignment was created
        from ..models import ABTestAssignment
        assignment = ABTestAssignment.objects.filter(
            user=self.user,
            test=test
        ).first()
        
        self.assertIsNotNone(assignment)
        self.assertIn(assignment.variant, ['control', 'variant'])
    
    def test_routing_with_analytics(self):
        """Test routing with analytics collection."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        # Make multiple routing requests
        for i in range(10):
            result = routing_engine.route_offers(
                user_id=self.user.id,
                context=context,
                limit=3
            )
            
            self.assertTrue(result['success'])
        
        # Check if analytics data was collected
        decisions = RoutingDecisionLog.objects.filter(user=self.user)
        self.assertEqual(decisions.count(), 10)
        
        # Get analytics summary
        analytics_summary = analytics_service.get_performance_metrics(
            tenant_id=self.tenant.id,
            days=1
        )
        
        self.assertIsInstance(analytics_summary, dict)
        self.assertIn('total_decisions', analytics_summary)
        self.assertEqual(analytics_summary['total_decisions'], 10)
    
    def test_routing_error_handling(self):
        """Test routing error handling."""
        # Test with invalid user
        with self.assertRaises(Exception):
            routing_engine.route_offers(
                user_id=999999,
                context={},
                limit=5
            )
        
        # Test with invalid context
        with self.assertRaises(Exception):
            routing_engine.route_offers(
                user_id=self.user.id,
                context=None,
                limit=5
            )
        
        # Test with invalid limit
        with self.assertRaises(Exception):
            routing_engine.route_offers(
                user_id=self.user.id,
                context={},
                limit=-1
            )
    
    def test_routing_performance(self):
        """Test routing performance under load."""
        import time
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        # Measure routing time for multiple requests
        start_time = time.time()
        
        for i in range(50):
            result = routing_engine.route_offers(
                user_id=self.user.id,
                context=context,
                limit=5
            )
            
            self.assertTrue(result['success'])
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000  # Convert to ms
        avg_time = total_time / 50
        
        # Should complete within reasonable time per request
        self.assertLess(avg_time, 100)  # Within 100ms per request


class ComponentIntegrationTestCase(TestCase):
    """Test cases for component integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer
        self.offer = OfferRoute.objects.create(
            name='Test Offer',
            description='Test offer for component integration',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_scoring_personalization_integration(self):
        """Test scoring and personalization integration."""
        # Create personalization config
        from ..models import PersonalizationConfig
        config = PersonalizationConfig.objects.create(
            tenant=self.tenant,
            user=self.user,
            algorithm='hybrid',
            collaborative_weight=0.4,
            content_based_weight=0.3,
            hybrid_weight=0.3,
            real_time_enabled=True,
            context_signals_enabled=True
        )
        
        # Update user preferences
        interaction_data = [
            {
                'offer_id': self.offer.id,
                'interaction_type': 'view',
                'timestamp': timezone.now().isoformat(),
                'value': 1.0
            }
        ]
        
        success = personalization_service.update_user_preferences(
            user=self.user,
            interaction_data=interaction_data
        )
        
        self.assertTrue(success)
        
        # Calculate score with personalization
        score_data = scoring_service.calculate_offer_score(
            offer=self.offer,
            user=self.user,
            context={'location': {'country': 'US'}}
        )
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
        self.assertIn('personalized_score', score_data)
        
        # Personalized score should be different from base score
        self.assertNotEqual(score_data['personalized_score'], score_data['score'])
    
    def test_targeting_scoring_integration(self):
        """Test targeting and scoring integration."""
        # Create targeting rules
        from ..models import GeoRouteRule, DeviceRouteRule
        
        GeoRouteRule.objects.create(
            route=self.offer,
            country='US',
            is_include=True
        )
        
        DeviceRouteRule.objects.create(
            route=self.offer,
            device_type='desktop',
            is_include=True
        )
        
        # Test matching with scoring
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        matching_routes = targeting_service.get_matching_routes(
            user_id=self.user.id,
            context=context
        )
        
        self.assertIsInstance(matching_routes, list)
        self.assertIn(self.offer, matching_routes)
        
        # Score the matched route
        if matching_routes:
            score_data = scoring_service.calculate_offer_score(
                offer=self.offer,
                user=self.user,
                context=context
            )
            
            self.assertIsInstance(score_data, dict)
            self.assertIn('score', score_data)
    
    def test_cap_scoring_integration(self):
        """Test cap and scoring integration."""
        # Create caps
        from ..models import OfferRoutingCap, UserOfferCap
        
        global_cap = OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer,
            cap_type='daily',
            cap_value=100,
            current_count=0
        )
        
        user_cap = UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer,
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=0
        )
        
        # Calculate score
        score_data = scoring_service.calculate_offer_score(
            offer=self.offer,
            user=self.user,
            context={'location': {'country': 'US'}}
        )
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
        
        # Check caps
        cap_result = cap_service.check_offer_cap(self.user, self.offer)
        
        self.assertIsInstance(cap_result, dict)
        self.assertIn('cap_exceeded', cap_result)
        self.assertFalse(cap_result['cap_exceeded'])
        
        # Increment cap usage
        success = cap_service.increment_cap_usage(self.user, self.offer)
        
        self.assertTrue(success)
        
        # Check updated cap
        user_cap.refresh_from_db()
        self.assertEqual(user_cap.shown_today, 1)
    
    def test_fallback_scoring_integration(self):
        """Test fallback and scoring integration."""
        # Create fallback rule
        from ..models import FallbackRule
        fallback_rule = FallbackRule.objects.create(
            tenant=self.tenant,
            name='Test Fallback',
            description='Test fallback rule',
            fallback_type='default',
            priority=5,
            is_active=True
        )
        
        # Test with no offers (should trigger fallback)
        fallback_offers = fallback_service.get_fallback_offers(
            user=self.user,
            offers=[],
            context={'location': {'country': 'US'}}
        )
        
        self.assertIsInstance(fallback_offers, list)
        
        # Score fallback offers if any
        if fallback_offers:
            for offer in fallback_offers:
                score_data = scoring_service.calculate_offer_score(
                    offer=offer,
                    user=self.user,
                    context={'location': {'country': 'US'}}
                )
                
                self.assertIsInstance(score_data, dict)
                self.assertIn('score', score_data)
    
    def test_ab_test_scoring_integration(self):
        """Test A/B testing and scoring integration."""
        # Create A/B test
        from ..models import RoutingABTest, ABTestAssignment
        
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Integration Test',
            description='Integration test for A/B testing',
            control_route=self.offer,
            variant_route=self.offer,  # Same offer for simplicity
            split_percentage=50,
            min_sample_size=10,
            duration_hours=24,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.tenant
        )
        
        # Assign user to test
        assignment = ab_test_service.assign_user_to_test(self.user, self.offer)
        
        self.assertIsInstance(assignment, ABTestAssignment)
        self.assertEqual(assignment.user, self.user)
        self.assertEqual(assignment.test, test)
        
        # Record interaction
        success = ab_test_service.record_assignment_event(
            self.user, self.offer, 'impression', 0.0
        )
        
        self.assertTrue(success)
        
        # Check assignment was updated
        assignment.refresh_from_db()
        self.assertEqual(assignment.impressions, 1)
        
        # Calculate score
        score_data = scoring_service.calculate_offer_score(
            offer=self.offer,
            user=self.user,
            context={'location': {'country': 'US'}}
        )
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
    
    def test_analytics_all_components(self):
        """Test analytics integration with all components."""
        # Create comprehensive test data
        from ..models import (
            PersonalizationConfig, OfferRoutingCap, FallbackRule,
            RoutingABTest, UserOfferHistory
        )
        
        # Personalization
        PersonalizationConfig.objects.create(
            tenant=self.tenant,
            user=self.user,
            algorithm='hybrid',
            collaborative_weight=0.4,
            content_based_weight=0.3,
            hybrid_weight=0.3
        )
        
        # Caps
        OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer,
            cap_type='daily',
            cap_value=100,
            current_count=50
        )
        
        # Fallback
        FallbackRule.objects.create(
            tenant=self.tenant,
            name='Test Fallback',
            description='Test fallback rule',
            fallback_type='default',
            priority=5,
            is_active=True
        )
        
        # A/B Test
        RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Analytics Test',
            description='Integration test for analytics',
            control_route=self.offer,
            variant_route=self.offer,
            split_percentage=50,
            min_sample_size=10,
            duration_hours=24,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.tenant
        )
        
        # User interactions
        for i in range(10):
            UserOfferHistory.objects.create(
                user=self.user,
                offer=self.offer,
                route=self.offer,
                viewed_at=timezone.now(),
                clicked_at=timezone.now() if i % 3 == 0 else None,
                completed_at=timezone.now() if i % 5 == 0 else None,
                conversion_value=10.0 if i % 5 == 0 else None
            )
        
        # Get comprehensive analytics
        analytics = analytics_service.get_performance_metrics(
            tenant_id=self.tenant.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
        self.assertIn('total_decisions', analytics)
        self.assertIn('avg_response_time', analytics)
        self.assertIn('cache_hit_rate', analytics)
        self.assertIn('personalization_rate', analytics)
        self.assertIn('fallback_rate', analytics)
        
        # Get user analytics
        user_analytics = analytics_service.get_user_analytics(
            user_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(user_analytics, dict)
        self.assertIn('total_decisions', user_analytics)
        self.assertIn('avg_score', user_analytics)
        self.assertIn('conversion_rate', user_analytics)


class PerformanceIntegrationTestCase(TestCase):
    """Test cases for performance integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offers
        self.offers = []
        for i in range(10):
            offer = OfferRoute.objects.create(
                name=f'Test Offer {i}',
                description=f'Test offer {i} for performance testing',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_high_volume_routing(self):
        """Test routing under high volume."""
        import time
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        # Measure performance for high volume requests
        start_time = time.time()
        
        success_count = 0
        error_count = 0
        
        for i in range(100):
            try:
                result = routing_engine.route_offers(
                    user_id=self.user.id,
                    context=context,
                    limit=5
                )
                
                if result['success']:
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000  # Convert to ms
        avg_time = total_time / 100
        
        # Performance assertions
        self.assertGreater(success_count, 95)  # At least 95% success rate
        self.assertLess(avg_time, 50)  # Average under 50ms per request
        self.assertLess(error_count, 5)  # Less than 5% error rate
        
        # Check if all decisions were logged
        decisions = RoutingDecisionLog.objects.filter(user=self.user)
        self.assertEqual(decisions.count(), success_count)
    
    def test_concurrent_routing(self):
        """Test concurrent routing requests."""
        import threading
        import time
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        results = []
        errors = []
        
        def route_request():
            try:
                result = routing_engine.route_offers(
                    user_id=self.user.id,
                    context=context,
                    limit=5
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=route_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Check results
        self.assertEqual(len(results), 10)
        self.assertEqual(len(errors), 0)
        
        # All results should be successful
        for result in results:
            self.assertTrue(result['success'])
        
        # Should complete within reasonable time
        self.assertLess(total_time, 1000)  # Within 1 second total
    
    def test_memory_usage(self):
        """Test memory usage during routing."""
        import gc
        import time
        
        # Force garbage collection
        gc.collect()
        
        # Get initial memory usage
        initial_objects = len(gc.get_objects())
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        # Make many routing requests
        for i in range(50):
            result = routing_engine.route_offers(
                user_id=self.user.id,
                context=context,
                limit=10
            )
            
            self.assertTrue(result['success'])
        
        # Force garbage collection
        gc.collect()
        
        # Get final memory usage
        final_objects = len(gc.get_objects())
        
        # Memory usage should be reasonable
        object_increase = final_objects - initial_objects
        self.assertLess(object_increase, 10000)  # Less than 10k new objects
    
    def test_cache_performance(self):
        """Test cache performance impact."""
        import time
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        # Test without cache
        start_time = time.time()
        
        for i in range(20):
            result = routing_engine.route_offers(
                user_id=self.user.id,
                context=context,
                limit=5,
                cache_enabled=False
            )
            
            self.assertTrue(result['success'])
        
        no_cache_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Test with cache
        start_time = time.time()
        
        for i in range(20):
            result = routing_engine.route_offers(
                user_id=self.user.id,
                context=context,
                limit=5,
                cache_enabled=True
            )
            
            self.assertTrue(result['success'])
        
        with_cache_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Cache should improve performance
        improvement = (no_cache_time - with_cache_time) / no_cache_time * 100
        self.assertGreater(improvement, 10)  # At least 10% improvement


class ErrorHandlingIntegrationTestCase(TestCase):
    """Test cases for error handling integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer
        self.offer = OfferRoute.objects.create(
            name='Test Offer',
            description='Test offer for error handling',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_robust_error_handling(self):
        """Test robust error handling throughout the system."""
        # Test various error conditions
        error_conditions = [
            # Invalid user ID
            {'user_id': 999999, 'context': {}, 'limit': 5},
            # Invalid context
            {'user_id': self.user.id, 'context': None, 'limit': 5},
            # Invalid limit
            {'user_id': self.user.id, 'context': {}, 'limit': -1},
            # Empty context
            {'user_id': self.user.id, 'context': {}, 'limit': 5}
        ]
        
        for condition in error_conditions:
            with self.assertRaises(Exception):
                routing_engine.route_offers(**condition)
    
    def test_service_fallback(self):
        """Test service fallback behavior."""
        # Mock service failure
        with patch('api.offer_routing.services.scoring.scoring_service') as mock_scoring:
            mock_scoring.calculate_offer_score.side_effect = Exception("Scoring service failed")
            
            context = {'location': {'country': 'US'}}
            
            # Should handle error gracefully
            with self.assertRaises(Exception):
                routing_engine.route_offers(
                    user_id=self.user.id,
                    context=context,
                    limit=5
                )
    
    def test_partial_failure_recovery(self):
        """Test recovery from partial failures."""
        # Create multiple offers
        offers = []
        for i in range(5):
            offer = OfferRoute.objects.create(
                name=f'Test Offer {i}',
                description=f'Test offer {i}',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            offers.append(offer)
        
        # Mock scoring to fail for some offers
        with patch('api.offer_routing.services.scoring.scoring_service') as mock_scoring:
            def side_effect(*args, **kwargs):
                if kwargs.get('offer').id == offers[2].id:
                    raise Exception("Scoring failed for this offer")
                return {'score': 85.5}
            
            mock_scoring.calculate_offer_score.side_effect = side_effect
            
            context = {'location': {'country': 'US'}}
            
            # Should still return results for other offers
            result = routing_engine.route_offers(
                user_id=self.user.id,
                context=context,
                limit=5
            )
            
            self.assertTrue(result['success'])
            self.assertLess(len(result['offers']), 5)  # Some offers failed
    
    def test_timeout_handling(self):
        """Test timeout handling."""
        # Mock slow operation
        with patch('api.offer_routing.services.targeting.targeting_service') as mock_targeting:
            import time
            
            def slow_operation(*args, **kwargs):
                time.sleep(0.1)  # Simulate slow operation
                return []
            
            mock_targeting.get_matching_routes.side_effect = slow_operation
            
            context = {'location': {'country': 'US'}}
            
            # Should handle timeout gracefully
            with self.assertRaises(Exception):
                routing_engine.route_offers(
                    user_id=self.user.id,
                    context=context,
                    limit=5,
                    timeout=0.05  # Very short timeout
                )
    
    def test_data_validation_errors(self):
        """Test data validation error handling."""
        # Create invalid targeting rule
        from ..models import GeoRouteRule
        invalid_rule = GeoRouteRule.objects.create(
            route=self.offer,
            country='',  # Invalid empty country
            is_include=True
        )
        
        context = {'location': {'country': 'US'}}
        
        # Should handle validation error
        with self.assertRaises(Exception):
            routing_engine.route_offers(
                user_id=self.user.id,
                context=context,
                limit=5
            )
    
    def test_database_error_handling(self):
        """Test database error handling."""
        # Mock database operation to fail
        with patch('api.offer_routing.models.RoutingDecisionLog.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            context = {'location': {'country': 'US'}}
            
            # Should handle database error
            with self.assertRaises(Exception):
                routing_engine.route_offers(
                    user_id=self.user.id,
                    context=context,
                    limit=5
                )
