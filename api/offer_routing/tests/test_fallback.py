"""
Test Fallback

Tests for the fallback service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.fallback import FallbackService
from ..models import FallbackRule, DefaultOfferPool, EmptyResultHandler
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestFallback(TestCase):
    """Test cases for FallbackService."""
    
    def setUp(self):
        """Set up test environment."""
        self.fallback_service = FallbackService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_get_fallback_offers_basic(self):
        """Test basic fallback offer retrieval."""
        try:
            # Create test fallback rule
            rule = FallbackRule.objects.create(
                name='Test Fallback Rule',
                fallback_type='offer_pool',
                priority=1,
                is_active=True
            )
            
            # Create test offer pool
            pool = DefaultOfferPool.objects.create(
                name='Test Pool',
                is_active=True
            )
            
            # Add offers to pool
            offers = []
            for i in range(5):
                offers.append(OfferRoute.objects.create(
                    name=f'Fallback Offer {i+1}',
                    description=f'Fallback offer {i+1}',
                    is_active=True,
                    price=10.0 * (i+1)
                ))
            
            pool.offers.add(*offers)
            pool.save()
            
            # Mock routing engine to return no offers
            with patch('..services.core.OfferRoutingEngine') as mock_routing:
                mock_routing.route_offers.return_value = {
                    'success': False,
                    'offers': []
                }
                
                # Get fallback offers
                result = self.fallback_service.get_fallback_offers(
                    user_id=self.test_user.id,
                    context={},
                    fallback_rules=[rule]
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['offers']), 5)
                self.assertEqual(result['metadata']['fallback_used'], True)
                self.assertEqual(result['metadata']['fallback_rule'], rule.id)
                
        except Exception as e:
            self.fail(f"Error in test_get_fallback_offers_basic: {e}")
    
    def test_get_fallback_offers_no_fallback(self):
        """Test fallback when no fallback rules."""
        try:
            # Mock routing engine to return no offers
            with patch('..services.core.OfferRoutingEngine') as mock_routing:
                mock_routing.route_offers.return_value = {
                    'success': False,
                    'offers': []
                }
                
                # Get fallback offers with no rules
                result = self.fallback_service.get_fallback_offers(
                    user_id=self.test_user.id,
                    context={},
                    fallback_rules=[]
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['offers']), 0)
                self.assertEqual(result['metadata']['fallback_used'], False)
                
        except Exception as e:
            self.fail(f"Error in test_get_fallback_offers_no_fallback: {e}")
    
    def test_get_fallback_offers_with_empty_pool(self):
        """Test fallback when offer pool is empty."""
        try:
            # Create test fallback rule
            rule = FallbackRule.objects.create(
                name='Test Fallback Rule',
                fallback_type='offer_pool',
                priority=1,
                is_active=True
            )
            
            # Create empty offer pool
            pool = DefaultOfferPool.objects.create(
                name='Empty Pool',
                is_active=True
            )
            
            # Mock routing engine to return no offers
            with patch('..services.core.OfferRoutingEngine') as mock_routing:
                mock_routing.route_offers.return_value = {
                    'success': False,
                    'offers': []
                }
                
                # Get fallback offers
                result = self.fallback_service.get_fallback_offers(
                    user_id=self.test_user.id,
                    context={},
                    fallback_rules=[rule]
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['offers']), 0)
                self.assertEqual(result['metadata']['fallback_used'], True)
                self.assertEqual(result['metadata']['fallback_rule'], rule.id)
                self.assertEqual(result['metadata']['warning'], 'Fallback pool is empty')
                
        except Exception as e:
            self.fail(f"Error in test_get_fallback_offers_with_empty_pool: {e}")
    
    def test_get_fallback_offers_priority_ordering(self):
        """Test fallback offers priority ordering."""
        try:
            # Create test fallback rules with different priorities
            high_priority_rule = FallbackRule.objects.create(
                name='High Priority Rule',
                fallback_type='offer_pool',
                priority=1,
                is_active=True
            )
            
            low_priority_rule = FallbackRule.objects.create(
                name='Low Priority Rule',
                fallback_type='offer_pool',
                priority=10,
                is_active=True
            )
            
            # Create offer pools
            high_pool = DefaultOfferPool.objects.create(
                name='High Priority Pool',
                is_active=True
            )
            low_pool = DefaultOfferPool.objects.create(
                name='Low Priority Pool',
                is_active=True
            )
            
            # Add offers to pools
            high_pool.offers.add(OfferRoute.objects.create(
                name='High Priority Offer',
                is_active=True,
                price=100.0
            ))
            
            low_pool.offers.add(OfferRoute.objects.create(
                name='Low Priority Offer',
                is_active=True,
                price=10.0
            ))
            
            # Mock routing engine to return no offers
            with patch('..services.core.OfferRoutingEngine') as mock_routing:
                mock_routing.route_offers.return_value = {
                    'success': False,
                    'offers': []
                }
                
                # Get fallback offers
                result = self.fallback_service.get_fallback_offers(
                    user_id=self.test_user.id,
                    context={},
                    fallback_rules=[high_priority_rule, low_priority_rule]
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['offers']), 2)  # One from each pool
                # High priority rule should be first
                self.assertEqual(result['offers'][0]['fallback_rule'], high_priority_rule.id)
                
        except Exception as e:
            self.fail(f"Error in test_get_fallback_offers_priority_ordering: {e}")
    
    def test_handle_empty_result_basic(self):
        """Test basic empty result handling."""
        try:
            # Create test empty result handler
            handler = EmptyResultHandler.objects.create(
                name='Test Handler',
                handler_type='default_offer',
                config={'default_offer_id': 1},
                is_active=True
            )
            
            # Mock routing engine to return no offers
            with patch('..services.core.OfferRoutingEngine') as mock_routing:
                mock_routing.route_offers.return_value = {
                    'success': False,
                    'offers': []
                }
                
                # Handle empty result
                result = self.fallback_service.handle_empty_result(
                    user_id=self.test_user.id,
                    context={},
                    empty_result_handlers=[handler]
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['offers']), 1)  # Default offer returned
                self.assertEqual(result['offers'][0]['id'], 1)  # Default offer ID
                self.assertEqual(result['metadata']['empty_result_used'], True)
                self.assertEqual(result['metadata']['empty_result_handler'], handler.id)
                
        except Exception as e:
            self.fail(f"Error in test_handle_empty_result_basic: {e}")
    
    def test_handle_empty_result_no_handlers(self):
        """Test empty result handling with no handlers."""
        try:
            # Mock routing engine to return no offers
            with patch('..services.core.OfferRoutingEngine') as mock_routing:
                mock_routing.route_offers.return_value = {
                    'success': False,
                    'offers': []
                }
                
                # Handle empty result with no handlers
                result = self.fallback_service.handle_empty_result(
                    user_id=self.test_user.id,
                    context={},
                    empty_result_handlers=[]
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['offers']), 0)
                self.assertEqual(result['metadata']['empty_result_used'], False)
                
        except Exception as e:
            self.fail(f"Error in test_handle_empty_result_no_handlers: {e}")
    
    def test_validate_fallback_rule_basic(self):
        """Test basic fallback rule validation."""
        try:
            # Test valid configuration
            valid_config = {
                'name': 'Test Rule',
                'fallback_type': 'offer_pool',
                'priority': 1,
                'is_active': True
            }
            
            result = self.fallback_service.validate_fallback_rule(valid_config)
            
            # Assertions
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
            
        except Exception as e:
            self.fail(f"Error in test_validate_fallback_rule_basic: {e}")
    
    def test_validate_fallback_rule_invalid(self):
        """Test invalid fallback rule validation."""
        try:
            # Test invalid configuration
            invalid_config = {
                'name': '',  # Missing name
                'fallback_type': 'invalid_type',  # Invalid fallback type
                'priority': 0,  # Invalid priority
                'is_active': True
            }
            
            result = self.fallback_service.validate_fallback_rule(invalid_config)
            
            # Assertions
            self.assertFalse(result['valid'])
            self.assertIn('name', result['errors'])
            self.assertIn('fallback_type', result['errors'])
            self.assertIn('priority', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_validate_fallback_rule_invalid: {e}")
    
    def test_validate_empty_result_handler_basic(self):
        """Test basic empty result handler validation."""
        try:
            # Test valid configuration
            valid_config = {
                'name': 'Test Handler',
                'handler_type': 'default_offer',
                'config': {'default_offer_id': 1},
                'is_active': True
            }
            
            result = self.fallback_service.validate_empty_result_handler(valid_config)
            
            # Assertions
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
            
        except Exception as e:
            self.fail(f"Error in test_validate_empty_result_handler_basic: {e}")
    
    def test_validate_empty_result_handler_invalid(self):
        """Test invalid empty result handler validation."""
        try:
            # Test invalid configuration
            invalid_config = {
                'name': '',  # Missing name
                'handler_type': 'invalid_type',  # Invalid handler type
                'config': {},  # Empty config
                'is_active': True
            }
            
            result = self.fallback_service.validate_empty_result_handler(invalid_config)
            
            # Assertions
            self.assertFalse(result['valid'])
            self.assertIn('name', result['errors'])
            self.assertIn('handler_type', result['errors'])
            self.assertIn('config', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_validate_empty_result_handler_invalid: {e}")
    
    def test_get_fallback_statistics_basic(self):
        """Test basic fallback statistics retrieval."""
        try:
            # Create test fallback rules and pools
            rules = [
                FallbackRule.objects.create(
                    name='Rule 1',
                    fallback_type='offer_pool',
                    priority=1,
                    is_active=True
                ),
                FallbackRule.objects.create(
                    name='Rule 2',
                    fallback_type='default_offer',
                    priority=2,
                    is_active=True
                )
            ]
            
            pools = [
                DefaultOfferPool.objects.create(
                    name='Pool 1',
                    is_active=True
                ),
                DefaultOfferPool.objects.create(
                    name='Pool 2',
                    is_active=False
                )
            ]
            
            # Get statistics
            result = self.fallback_service.get_fallback_statistics()
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['total_rules'], 2)
            self.assertEqual(result['active_rules'], 2)
            self.assertEqual(result['inactive_rules'], 0)
            self.assertEqual(result['total_pools'], 2)
            self.assertEqual(result['active_pools'], 1)
            self.assertEqual(result['inactive_pools'], 1)
            
        except Exception as e:
            self.fail(f"Error in test_get_fallback_statistics_basic: {e}")
    
    def test_health_check(self):
        """Test fallback service health check."""
        try:
            # Test health check
            health = self.fallback_service.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('fallback_rules', health)
            self.assertIn('offer_pools', health)
            self.assertIn('empty_result_handlers', health)
            self.assertIn('cache_status', health)
            
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")
    
    def test_performance_under_load(self):
        """Test fallback service performance under load."""
        try:
            # Create many fallback rules
            rules = []
            for i in range(100):
                rules.append(FallbackRule.objects.create(
                    name=f'Performance Test Rule {i+1}',
                    fallback_type='offer_pool',
                    priority=i+1,
                    is_active=True
                ))
            
            # Mock routing engine
            with patch('..services.core.OfferRoutingEngine') as mock_routing:
                mock_routing.route_offers.return_value = {
                    'success': False,
                    'offers': []
                }
                
                # Measure performance
                start_time = timezone.now()
                result = self.fallback_service.get_fallback_offers(
                    user_id=self.test_user.id,
                    context={},
                    fallback_rules=rules
                )
                elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertLess(elapsed_ms, 1000)  # Should complete in under 1 second
                
        except Exception as e:
            self.fail(f"Error in test_performance_under_load: {e}")


if __name__ == '__main__':
    pytest.main()
