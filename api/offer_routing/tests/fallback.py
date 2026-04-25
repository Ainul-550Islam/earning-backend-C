"""
Fallback Tests for Offer Routing System

This module contains unit tests for fallback functionality,
including fallback rules, default pools, and empty result handlers.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.fallback import FallbackService, fallback_service
from ..models import FallbackRule, DefaultOfferPool, EmptyResultHandler
from ..exceptions import FallbackError, ValidationError

User = get_user_model()


class FallbackServiceTestCase(TestCase):
    """Test cases for FallbackService."""
    
    def setUp(self):
        """Set up test data."""
        self.fallback_service = FallbackService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer routes
        from ..models import OfferRoute
        self.offers = []
        for i in range(3):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for unit testing',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_get_fallback_offers_empty(self):
        """Test getting fallback offers when no offers are provided."""
        offers = []
        context = {'location': {'country': 'US'}}
        
        fallback_offers = self.fallback_service.get_fallback_offers(
            user=self.user,
            offers=offers,
            context=context
        )
        
        self.assertIsInstance(fallback_offers, list)
        # Should return fallback offers if available
    
    def test_get_fallback_offers_with_offers(self):
        """Test getting fallback offers when offers are provided."""
        offers = self.offers
        context = {'location': {'country': 'US'}}
        
        fallback_offers = self.fallback_service.get_fallback_offers(
            user=self.user,
            offers=offers,
            context=context
        )
        
        self.assertIsInstance(fallback_offers, list)
        # Should return original offers if no fallback needed
    
    def test_get_fallback_offers_with_context(self):
        """Test getting fallback offers with specific context."""
        offers = []
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'mobile'},
            'current_time': timezone.now()
        }
        
        fallback_offers = self.fallback_service.get_fallback_offers(
            user=self.user,
            offers=offers,
            context=context
        )
        
        self.assertIsInstance(fallback_offers, list)
    
    def test_handle_empty_results(self):
        """Test handling empty results."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'mobile'}
        }
        
        result = self.fallback_service.handle_empty_results(
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('action', result)
        self.assertIn('offers', result)
    
    def test_get_matching_fallback_rules(self):
        """Test getting matching fallback rules."""
        # Create fallback rule
        FallbackRule.objects.create(
            tenant=self.tenant,
            name='Test Rule',
            description='Test fallback rule',
            fallback_type='category',
            priority=5,
            is_active=True,
            start_time=timezone.now() - timezone.timedelta(hours=1),
            end_time=timezone.now() + timezone.timedelta(hours=1)
        )
        
        context = {
            'location': {'country': 'US'},
            'current_time': timezone.now()
        }
        
        matching_rules = self.fallback_service.get_matching_fallback_rules(
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(matching_rules, list)
    
    def test_get_category_fallback_offers(self):
        """Test getting category fallback offers."""
        # Create fallback rule
        rule = FallbackRule.objects.create(
            tenant=self.tenant,
            name='Category Rule',
            description='Category fallback rule',
            fallback_type='category',
            priority=5,
            is_active=True,
            category='tech'
        )
        
        context = {'location': {'country': 'US'}}
        
        offers = self.fallback_service._get_category_fallback_offers(
            user=self.user,
            rule=rule,
            context=context
        )
        
        self.assertIsInstance(offers, list)
    
    def test_get_network_fallback_offers(self):
        """Test getting network fallback offers."""
        # Create fallback rule
        rule = FallbackRule.objects.create(
            tenant=self.tenant,
            name='Network Rule',
            description='Network fallback rule',
            fallback_type='network',
            priority=5,
            is_active=True,
            network='premium'
        )
        
        context = {'location': {'country': 'US'}}
        
        offers = self.fallback_service._get_network_fallback_offers(
            user=self.user,
            rule=rule,
            context=context
        )
        
        self.assertIsInstance(offers, list)
    
    def test_get_default_fallback_offers(self):
        """Test getting default fallback offers."""
        # Create fallback rule
        rule = FallbackRule.objects.create(
            tenant=self.tenant,
            name='Default Rule',
            description='Default fallback rule',
            fallback_type='default',
            priority=5,
            is_active=True
        )
        
        context = {'location': {'country': 'US'}}
        
        offers = self.fallback_service._get_default_fallback_offers(
            user=self.user,
            rule=rule,
            context=context
        )
        
        self.assertIsInstance(offers, list)
    
    def test_get_promotion_fallback_offers(self):
        """Test getting promotion fallback offers."""
        # Create fallback rule
        rule = FallbackRule.objects.create(
            tenant=self.tenant,
            name='Promotion Rule',
            description='Promotion fallback rule',
            fallback_type='promotion',
            priority=5,
            is_active=True,
            promotion_code='SPECIAL10'
        )
        
        context = {'location': {'country': 'US'}}
        
        offers = self.fallback_service._get_promotion_fallback_offers(
            user=self.user,
            rule=rule,
            context=context
        )
        
        self.assertIsInstance(offers, list)
    
    def test_handle_hide_section(self):
        """Test handling hide section fallback."""
        # Create fallback rule
        rule = FallbackRule.objects.create(
            tenant=self.tenant,
            name='Hide Rule',
            description='Hide section fallback rule',
            fallback_type='hide_section',
            priority=5,
            is_active=True
        )
        
        context = {'location': {'country': 'US'}}
        
        result = self.fallback_service._handle_hide_section(
            user=self.user,
            rule=rule,
            context=context
        )
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['action'], 'hide_section')
    
    def test_check_fallback_health(self):
        """Test fallback health checking."""
        # Create fallback rules
        FallbackRule.objects.create(
            tenant=self.tenant,
            name='Test Rule 1',
            description='Test fallback rule 1',
            fallback_type='category',
            priority=5,
            is_active=True
        )
        
        FallbackRule.objects.create(
            tenant=self.tenant,
            name='Test Rule 2',
            description='Test fallback rule 2',
            fallback_type='default',
            priority=3,
            is_active=True
        )
        
        # Create default offer pool
        pool = DefaultOfferPool.objects.create(
            tenant=self.tenant,
            name='Test Pool',
            description='Test default pool',
            pool_type='general',
            max_offers=10,
            is_active=True
        )
        pool.offers.add(*self.offers)
        
        health_status = self.fallback_service.check_fallback_health()
        
        self.assertIsInstance(health_status, dict)
        self.assertIn('overall_status', health_status)
    
    def test_get_fallback_analytics(self):
        """Test getting fallback analytics."""
        # Create fallback rules and usage data
        FallbackRule.objects.create(
            tenant=self.tenant,
            name='Test Rule',
            description='Test fallback rule',
            fallback_type='category',
            priority=5,
            is_active=True
        )
        
        analytics = self.fallback_service.get_fallback_analytics(
            user_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
        self.assertIn('usage_stats', analytics)
        self.assertIn('rule_performance', analytics)


class DefaultOfferPoolTestCase(TestCase):
    """Test cases for DefaultOfferPool."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offers
        from ..models import OfferRoute
        self.offers = []
        for i in range(5):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for unit testing',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
        
        # Create default offer pool
        self.pool = DefaultOfferPool.objects.create(
            tenant=self.tenant,
            name='Test Pool',
            description='Test default pool',
            pool_type='general',
            max_offers=10,
            is_active=True
        )
        self.pool.offers.add(*self.offers)
    
    def test_get_random_offers(self):
        """Test getting random offers from pool."""
        offers = self.pool.get_random_offers(limit=3)
        
        self.assertIsInstance(offers, list)
        self.assertLessEqual(len(offers), 3)
        
        # All offers should be from the pool
        for offer in offers:
            self.assertIn(offer, self.offers)
    
    def test_get_weighted_offers(self):
        """Test getting weighted offers from pool."""
        # Set weights for offers
        for i, offer in enumerate(self.offers):
            offer.priority = i + 1
            offer.save()
        
        offers = self.pool.get_weighted_offers(limit=3)
        
        self.assertIsInstance(offers, list)
        self.assertLessEqual(len(offers), 3)
    
    def test_get_priority_offers(self):
        """Test getting priority offers from pool."""
        offers = self.pool.get_priority_offers(limit=3)
        
        self.assertIsInstance(offers, list)
        self.assertLessEqual(len(offers), 3)
        
        # Should be ordered by priority (descending)
        for i in range(len(offers) - 1):
            self.assertGreaterEqual(
                offers[i].priority,
                offers[i + 1].priority
            )
    
    def test_get_round_robin_offers(self):
        """Test getting round robin offers from pool."""
        offers = self.pool.get_round_robin_offers(limit=3)
        
        self.assertIsInstance(offers, list)
        self.assertLessEqual(len(offers), 3)
    
    def test_add_offers(self):
        """Test adding offers to pool."""
        # Create new offer
        from ..models import OfferRoute
        new_offer = OfferRoute.objects.create(
            name='New Route',
            description='New test route',
            tenant=self.tenant,
            priority=10,
            max_offers=10,
            is_active=True
        )
        
        self.pool.offers.add(new_offer)
        
        # Check if offer was added
        self.assertIn(new_offer, self.pool.offers.all())
    
    def test_remove_offers(self):
        """Test removing offers from pool."""
        offer_to_remove = self.offers[0]
        
        self.pool.offers.remove(offer_to_remove)
        
        # Check if offer was removed
        self.assertNotIn(offer_to_remove, self.pool.offers.all())
    
    def test_get_offers_by_rotation_strategy(self):
        """Test getting offers by rotation strategy."""
        # Test random strategy
        offers = self.pool.get_offers_by_rotation_strategy('random', limit=3)
        self.assertIsInstance(offers, list)
        
        # Test weighted strategy
        offers = self.pool.get_offers_by_rotation_strategy('weighted', limit=3)
        self.assertIsInstance(offers, list)
        
        # Test priority strategy
        offers = self.pool.get_offers_by_rotation_strategy('priority', limit=3)
        self.assertIsInstance(offers, list)
        
        # Test round robin strategy
        offers = self.pool.get_offers_by_rotation_strategy('round_robin', limit=3)
        self.assertIsInstance(offers, list)


class EmptyResultHandlerTestCase(TestCase):
    """Test cases for EmptyResultHandler."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        # Create empty result handler
        self.handler = EmptyResultHandler.objects.create(
            tenant=self.tenant,
            name='Test Handler',
            description='Test empty result handler',
            action_type='show_promo',
            action_value='Special promotion for you!',
            priority=5,
            is_active=True
        )
    
    def test_should_apply(self):
        """Test checking if handler should apply."""
        context = {'location': {'country': 'US'}}
        
        should_apply = self.handler.should_apply(context)
        
        self.assertIsInstance(should_apply, bool)
    
    def test_should_apply_with_conditions(self):
        """Test checking if handler should apply with conditions."""
        # Create handler with conditions
        handler_with_conditions = EmptyResultHandler.objects.create(
            tenant=self.tenant,
            name='Handler with Conditions',
            description='Handler with conditions',
            action_type='show_promo',
            action_value='Special promotion!',
            priority=5,
            is_active=True,
            conditions={'device_type': 'mobile'}
        )
        
        context = {'device': {'type': 'mobile'}}
        
        should_apply = handler_with_conditions.should_apply(context)
        
        self.assertIsInstance(should_apply, bool)
    
    def test_execute_action(self):
        """Test executing handler action."""
        context = {'location': {'country': 'US'}}
        
        result = self.handler.execute_action(context)
        
        self.assertIsInstance(result, dict)
        self.assertIn('action', result)
        self.assertIn('action_type', result)
    
    def test_execute_show_promo_action(self):
        """Test executing show promo action."""
        context = {'location': {'country': 'US'}}
        
        result = self.handler._execute_show_promo_action(context)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['action'], 'show_promo')
        self.assertIn('message', result)
    
    def test_execute_redirect_url_action(self):
        """Test executing redirect URL action."""
        # Create handler with redirect URL
        redirect_handler = EmptyResultHandler.objects.create(
            tenant=self.tenant,
            name='Redirect Handler',
            description='Redirect handler',
            action_type='redirect_url',
            redirect_url='https://example.com/offers',
            priority=5,
            is_active=True
        )
        
        context = {'location': {'country': 'US'}}
        
        result = redirect_handler._execute_redirect_url_action(context)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['action'], 'redirect_url')
        self.assertIn('redirect_url', result)
    
    def test_execute_show_default_action(self):
        """Test executing show default action."""
        # Create default pool
        from ..models import DefaultOfferPool
        pool = DefaultOfferPool.objects.create(
            tenant=self.tenant,
            name='Test Pool',
            description='Test default pool',
            pool_type='general',
            max_offers=10,
            is_active=True
        )
        pool.offers.add(self.offer_route)
        
        context = {'location': {'country': 'US'}}
        
        result = self.handler._execute_show_default_action(context)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['action'], 'show_default')
        self.assertIn('offers', result)
    
    def test_execute_hide_section_action(self):
        """Test executing hide section action."""
        # Create handler with hide section action
        hide_handler = EmptyResultHandler.objects.create(
            tenant=self.tenant,
            name='Hide Handler',
            description='Hide section handler',
            action_type='hide_section',
            priority=5,
            is_active=True
        )
        
        context = {'location': {'country': 'US'}}
        
        result = hide_handler._execute_hide_section_action(context)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['action'], 'hide_section')
    
    def test_execute_custom_message_action(self):
        """Test executing custom message action."""
        # Create handler with custom message
        message_handler = EmptyResultHandler.objects.create(
            tenant=self.tenant,
            name='Message Handler',
            description='Custom message handler',
            action_type='custom_message',
            custom_message='No offers available at this time. Please check back later.',
            priority=5,
            is_active=True
        )
        
        context = {'location': {'country': 'US'}}
        
        result = message_handler._execute_custom_message_action(context)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['action'], 'custom_message')
        self.assertIn('message', result)


class FallbackIntegrationTestCase(TestCase):
    """Integration tests for fallback functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
        from ..models import OfferRoute
        self.offers = []
        for i in range(3):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for integration testing',
                tenant=self.user,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_fallback_workflow(self):
        """Test complete fallback workflow."""
        # Create fallback rule
        FallbackRule.objects.create(
            tenant=self.user,
            name='Test Rule',
            description='Test fallback rule',
            fallback_type='category',
            priority=5,
            is_active=True,
            category='tech'
        )
        
        # Create default offer pool
        pool = DefaultOfferPool.objects.create(
            tenant=self.user,
            name='Test Pool',
            description='Test default pool',
            pool_type='general',
            max_offers=10,
            is_active=True
        )
        pool.offers.add(*self.offers)
        
        # Create empty result handler
        EmptyResultHandler.objects.create(
            tenant=self.user,
            name='Test Handler',
            description='Test empty result handler',
            action_type='show_promo',
            action_value='Special promotion!',
            priority=5,
            is_active=True
        )
        
        # Test fallback with empty offers
        result = fallback_service.get_fallback_offers(
            user=self.user,
            offers=[],
            context={'location': {'country': 'US'}}
        )
        
        self.assertIsInstance(result, list)
    
    def test_fallback_with_pools(self):
        """Test fallback with offer pools."""
        # Create multiple pools
        for i in range(2):
            pool = DefaultOfferPool.objects.create(
                tenant=self.user,
                name=f'Test Pool {i}',
                description=f'Test default pool {i}',
                pool_type='general',
                max_offers=5,
                is_active=True
            )
            pool.offers.add(*self.offers)
        
        # Create fallback rule
        FallbackRule.objects.create(
            tenant=self.user,
            name='Test Rule',
            description='Test fallback rule',
            fallback_type='default',
            priority=5,
            is_active=True
        )
        
        fallback_offers = fallback_service.get_fallback_offers(
            user=self.user,
            offers=[],
            context={'location': {'country': 'US'}}
        )
        
        self.assertIsInstance(fallback_offers, list)
    
    def test_fallback_priority_ordering(self):
        """Test fallback priority ordering."""
        # Create fallback rules with different priorities
        FallbackRule.objects.create(
            tenant=self.user,
            name='High Priority Rule',
            description='High priority fallback rule',
            fallback_type='category',
            priority=1,
            is_active=True,
            category='tech'
        )
        
        FallbackRule.objects.create(
            tenant=self.user,
            name='Low Priority Rule',
            description='Low priority fallback rule',
            fallback_type='default',
            priority=10,
            is_active=True
        )
        
        context = {'location': {'country': 'US'}}
        
        matching_rules = fallback_service.get_matching_fallback_rules(
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(matching_rules, list)
        # Should be ordered by priority (ascending)
        for i in range(len(matching_rules) - 1):
            self.assertLessEqual(
                matching_rules[i].priority,
                matching_rules[i + 1].priority
            )
    
    def test_fallback_performance(self):
        """Test fallback performance."""
        import time
        
        # Create fallback configuration
        FallbackRule.objects.create(
            tenant=self.user,
            name='Test Rule',
            description='Test fallback rule',
            fallback_type='category',
            priority=5,
            is_active=True
        )
        
        pool = DefaultOfferPool.objects.create(
            tenant=self.user,
            name='Test Pool',
            description='Test default pool',
            pool_type='general',
            max_offers=10,
            is_active=True
        )
        pool.offers.add(*self.offers)
        
        # Measure fallback time
        start_time = time.time()
        
        for _ in range(10):
            fallback_service.get_fallback_offers(
                user=self.user,
                offers=[],
                context={'location': {'country': 'US'}}
            )
        
        end_time = time.time()
        fallback_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(fallback_time, 500)  # Within 500ms
    
    def test_fallback_error_handling(self):
        """Test error handling in fallback."""
        # Test with invalid user
        with self.assertRaises(Exception):
            fallback_service.get_fallback_offers(
                user=None,
                offers=[],
                context={'location': {'country': 'US'}}
            )
        
        # Test with invalid context
        with self.assertRaises(Exception):
            fallback_service.get_fallback_offers(
                user=self.user,
                offers=[],
                context=None
            )
