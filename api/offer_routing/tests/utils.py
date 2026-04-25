"""
Utility Tests for Offer Routing System

This module contains unit tests for utility functionality,
including validation, testing, and helper operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.utils import RoutingUtilsService, utils_service, ValidationService, validation_service
from ..services.evaluator import RouteEvaluator, route_evaluator
from ..exceptions import ValidationError, UtilityError

User = get_user_model()


class RoutingUtilsServiceTestCase(TestCase):
    """Test cases for RoutingUtilsService."""
    
    def setUp(self):
        """Set up test data."""
        self.utils_service = RoutingUtilsService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
    
    def test_generate_user_hash(self):
        """Test user hash generation."""
        user_id = self.user.id
        additional_data = {'segment': 'premium', 'tier': 'gold'}
        
        user_hash = self.utils_service.generate_user_hash(user_id, additional_data)
        
        self.assertIsInstance(user_hash, str)
        self.assertGreater(len(user_hash), 0)
        
        # Hash should be consistent for same input
        hash2 = self.utils_service.generate_user_hash(user_id, additional_data)
        self.assertEqual(user_hash, hash2)
        
        # Hash should be different for different input
        hash3 = self.utils_service.generate_user_hash(user_id, {'segment': 'basic'})
        self.assertNotEqual(user_hash, hash3)
    
    def test_generate_context_hash(self):
        """Test context hash generation."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'time': 'morning'
        }
        
        context_hash = self.utils_service.generate_context_hash(context)
        
        self.assertIsInstance(context_hash, str)
        self.assertGreater(len(context_hash), 0)
        
        # Hash should be consistent for same input
        hash2 = self.utils_service.generate_context_hash(context)
        self.assertEqual(context_hash, hash2)
        
        # Hash should be different for different input
        context2 = context.copy()
        context2['location']['country'] = 'CA'
        hash3 = self.utils_service.generate_context_hash(context2)
        self.assertNotEqual(context_hash, hash3)
    
    def test_normalize_score(self):
        """Test score normalization."""
        score = 150.0
        min_val = 0
        max_val = 100
        
        normalized = self.utils_service.normalize_score(score, min_val, max_val)
        
        self.assertEqual(normalized, 100.0)
        
        # Test below minimum
        score = -10.0
        normalized = self.utils_service.normalize_score(score, min_val, max_val)
        self.assertEqual(normalized, 0.0)
        
        # Test within range
        score = 75.0
        normalized = self.utils_service.normalize_score(score, min_val, max_val)
        self.assertEqual(normalized, 75.0)
    
    def test_calculate_percentile(self):
        """Test percentile calculation."""
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        target_value = 50
        
        percentile = self.utils_service.calculate_percentile(values, target_value)
        
        self.assertEqual(percentile, 50.0)
        
        # Test with different target
        percentile = self.utils_service.calculate_percentile(values, 90)
        self.assertEqual(percentile, 90.0)
        
        # Test with empty list
        percentile = self.utils_service.calculate_percentile([], 50)
        self.assertEqual(percentile, 0.0)
    
    def test_validate_routing_data(self):
        """Test routing data validation."""
        valid_data = {
            'user_id': self.user.id,
            'context': {'location': {'country': 'US'}},
            'limit': 10
        }
        
        validation_result = self.utils_service.validate_routing_data(valid_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
        self.assertEqual(len(validation_result['warnings']), 0)
    
    def test_validate_routing_data_invalid(self):
        """Test routing data validation with invalid data."""
        invalid_data = {
            'user_id': None,
            'context': {},
            'limit': -1
        }
        
        validation_result = self.utils_service.validate_routing_data(invalid_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_extract_user_agent_info(self):
        """Test user agent info extraction."""
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        user_agent_info = self.utils_service.extract_user_agent_info(user_agent)
        
        self.assertIsInstance(user_agent_info, dict)
        self.assertIn('browser', user_agent_info)
        self.assertIn('browser_version', user_agent_info)
        self.assertIn('os', user_agent_info)
        self.assertIn('os_version', user_agent_info)
        self.assertIn('device_type', user_agent_info)
        self.assertIn('is_mobile', user_agent_info)
        self.assertIn('is_tablet', user_agent_info)
        self.assertIn('is_desktop', user_agent_info)
    
    def test_parse_ip_address(self):
        """Test IP address parsing."""
        ip_address = '192.168.1.1'
        
        ip_info = self.utils_service.parse_ip_address(ip_address)
        
        self.assertIsInstance(ip_info, dict)
        self.assertIn('ip', ip_info)
        self.assertIn('is_valid', ip_info)
        self.assertIn('is_private', ip_info)
        self.assertIn('is_public', ip_info)
        self.assertIn('country_code', ip_info)
        self.assertIn('city', ip_info)
        self.assertIn('latitude', ip_info)
        self.assertIn('longitude', ip_info)
    
    def test_format_routing_response(self):
        """Test routing response formatting."""
        success = True
        offers = [
            {'id': 1, 'name': 'Offer 1', 'score': 85.5},
            {'id': 2, 'name': 'Offer 2', 'score': 92.3}
        ]
        metadata = {
            'response_time_ms': 45.2,
            'cache_hit': True,
            'personalization_applied': True
        }
        
        response = self.utils_service.format_routing_response(
            success=success,
            offers=offers,
            metadata=metadata
        )
        
        self.assertIsInstance(response, dict)
        self.assertEqual(response['success'], success)
        self.assertEqual(len(response['offers']), len(offers))
        self.assertEqual(response['metadata'], metadata)
        self.assertIn('timestamp', response)
    
    def test_calculate_routing_quality_score(self):
        """Test routing quality score calculation."""
        response_time_ms = 45.2
        cache_hit_rate = 85.5
        error_rate = 2.1
        
        quality_score = self.utils_service.calculate_routing_quality_score(
            response_time_ms=response_time_ms,
            cache_hit_rate=cache_hit_rate,
            error_rate=error_rate
        )
        
        self.assertIsInstance(quality_score, (int, float))
        self.assertGreaterEqual(quality_score, 0)
        self.assertLessEqual(quality_score, 100)
        
        # Test with poor metrics
        quality_score = self.utils_service.calculate_routing_quality_score(
            response_time_ms=500.0,
            cache_hit_rate=30.0,
            error_rate=15.0
        )
        
        self.assertLess(quality_score, 50)
    
    def test_get_user_routing_history(self):
        """Test getting user routing history."""
        history = self.utils_service.get_user_routing_history(
            user_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(history, list)
        
        for entry in history:
            self.assertIsInstance(entry, dict)
            self.assertIn('timestamp', entry)
            self.assertIn('offer_id', entry)
            self.assertIn('score', entry)
            self.assertIn('response_time_ms', entry)
    
    def test_get_offer_routing_stats(self):
        """Test getting offer routing statistics."""
        # Create test offer
        from ..models import OfferRoute
        offer = OfferRoute.objects.create(
            name='Test Offer',
            description='Test offer for stats',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        stats = self.utils_service.get_offer_routing_stats(
            offer_id=offer.id,
            days=30
        )
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_requests', stats)
        self.assertIn('avg_score', stats)
        self.assertIn('avg_response_time_ms', stats)
        self.assertIn('cache_hit_rate', stats)
    
    def test_cleanup_old_data(self):
        """Test cleanup of old data."""
        days = 90
        
        deleted_count = self.utils_service.cleanup_old_data(days)
        
        self.assertIsInstance(deleted_count, int)
        self.assertGreaterEqual(deleted_count, 0)
    
    def test_export_routing_data(self):
        """Test routing data export."""
        export_data = self.utils_service.export_routing_data(
            tenant_id=self.tenant.id,
            days=30
        )
        
        self.assertIsInstance(export_data, dict)
        self.assertIn('routing_decisions', export_data)
        self.assertIn('performance_stats', export_data)
        self.assertIn('export_timestamp', export_data)
    
    def test_import_routing_data(self):
        """Test routing data import."""
        import_data = {
            'routing_decisions': [
                {
                    'user_id': self.user.id,
                    'offer_id': 1,
                    'score': 85.5,
                    'response_time_ms': 45.2,
                    'cache_hit': True,
                    'personalization_applied': False,
                    'caps_checked': True,
                    'fallback_used': False,
                    'created_at': timezone.now().isoformat()
                }
            ],
            'performance_stats': []
        }
        
        success = self.utils_service.import_routing_data(
            tenant_id=self.tenant.id,
            import_data=import_data
        )
        
        self.assertTrue(success)


class ValidationServiceTestCase(TestCase):
    """Test cases for ValidationService."""
    
    def setUp(self):
        """Set up test data."""
        self.validation_service = ValidationService()
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
            description='Test route for validation',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_validate_offer_data(self):
        """Test offer data validation."""
        offer_data = {
            'name': 'Test Offer',
            'description': 'Test offer description',
            'priority': 5,
            'max_offers': 10,
            'is_active': True
        }
        
        validation_result = self.validation_service.validate_offer_data(offer_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
        self.assertEqual(len(validation_result['warnings']), 0)
    
    def test_validate_offer_data_invalid(self):
        """Test offer data validation with invalid data."""
        offer_data = {
            'name': '',  # Empty name
            'description': '',
            'priority': -1,  # Invalid priority
            'max_offers': 0,  # Invalid max_offers
            'is_active': 'invalid'  # Invalid boolean
        }
        
        validation_result = self.validation_service.validate_offer_data(offer_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_validate_route_data(self):
        """Test route data validation."""
        route_data = {
            'name': 'Test Route',
            'description': 'Test route description',
            'priority': 5,
            'max_offers': 10,
            'is_active': True,
            'conditions': [
                {'field_name': 'country', 'operator': 'equals', 'value': 'US'}
            ],
            'actions': [
                {'action_type': 'show_offer', 'action_value': '1'}
            ]
        }
        
        validation_result = self.validation_service.validate_route_data(route_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_route_data_invalid(self):
        """Test route data validation with invalid data."""
        route_data = {
            'name': '',
            'description': '',
            'priority': -1,
            'max_offers': 0,
            'is_active': 'invalid',
            'conditions': [
                {'field_name': '', 'operator': 'equals', 'value': ''}
            ],
            'actions': [
                {'action_type': '', 'action_value': ''}
            ]
        }
        
        validation_result = self.validation_service.validate_route_data(route_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_validate_routing_request(self):
        """Test routing request validation."""
        request_data = {
            'user_id': self.user.id,
            'context': {'location': {'country': 'US'}},
            'limit': 10
        }
        
        validation_result = self.validation_service.validate_routing_request(request_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_routing_request_invalid(self):
        """Test routing request validation with invalid data."""
        request_data = {
            'user_id': None,
            'context': {},
            'limit': -1
        }
        
        validation_result = self.validation_service.validate_routing_request(request_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_validate_score_data(self):
        """Test score data validation."""
        score_data = {
            'score': 85.5,
            'epc': 2.5,
            'cr': 3.2,
            'relevance': 0.8,
            'freshness': 0.9
        }
        
        validation_result = self.validation_service.validate_score_data(score_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_score_data_invalid(self):
        """Test score data validation with invalid data."""
        score_data = {
            'score': -1.0,  # Invalid score
            'epc': -2.5,  # Invalid EPC
            'cr': 150.0,  # Invalid CR (should be percentage)
            'relevance': 1.5,  # Invalid relevance (should be 0-1)
            'freshness': -0.5  # Invalid freshness (should be 0-1)
        }
        
        validation_result = self.validation_service.validate_score_data(score_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_validate_cap_data(self):
        """Test cap data validation."""
        cap_data = {
            'cap_type': 'daily',
            'cap_value': 100,
            'is_active': True
        }
        
        validation_result = self.validation_service.validate_cap_data(cap_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_cap_data_invalid(self):
        """Test cap data validation with invalid data."""
        cap_data = {
            'cap_type': 'invalid_type',
            'cap_value': -1,
            'is_active': 'invalid'
        }
        
        validation_result = self.validation_service.validate_cap_data(cap_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_validate_ab_test_data(self):
        """Test A/B test data validation."""
        test_data = {
            'name': 'Test A/B Test',
            'control_route_id': self.offer_route.id,
            'variant_route_id': self.offer_route.id + 1,
            'split_percentage': 50,
            'min_sample_size': 100,
            'duration_hours': 168
        }
        
        # Create variant route
        from ..models import OfferRoute
        variant_route = OfferRoute.objects.create(
            name='Variant Route',
            description='Variant route for A/B testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        test_data['variant_route_id'] = variant_route.id
        
        validation_result = self.validation_service.validate_ab_test_data(test_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_ab_test_data_invalid(self):
        """Test A/B test data validation with invalid data."""
        test_data = {
            'name': '',
            'control_route_id': None,
            'variant_route_id': None,
            'split_percentage': 150,
            'min_sample_size': 0,
            'duration_hours': -1
        }
        
        validation_result = self.validation_service.validate_ab_test_data(test_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_validate_personalization_config(self):
        """Test personalization config validation."""
        config_data = {
            'algorithm': 'hybrid',
            'collaborative_weight': 0.4,
            'content_based_weight': 0.3,
            'hybrid_weight': 0.3,
            'min_affinity_score': 0.1,
            'max_offers_per_user': 50,
            'real_time_enabled': True,
            'context_signals_enabled': True
        }
        
        validation_result = self.validation_service.validate_personalization_config(config_data)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_personalization_config_invalid(self):
        """Test personalization config validation with invalid data."""
        config_data = {
            'algorithm': 'invalid_algorithm',
            'collaborative_weight': 1.5,  # Should sum to 1.0
            'content_based_weight': 0.3,
            'hybrid_weight': 0.3,
            'min_affinity_score': -0.1,
            'max_offers_per_user': 0,
            'real_time_enabled': 'invalid',
            'context_signals_enabled': 'invalid'
        }
        
        validation_result = self.validation_service.validate_personalization_config(config_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_validate_field_value(self):
        """Test individual field value validation."""
        # Valid values
        valid_cases = [
            ('name', 'Test Name', 'string'),
            ('priority', 5, 'integer'),
            ('is_active', True, 'boolean'),
            ('score', 85.5, 'float'),
            ('percentage', 75.0, 'percentage'),
            ('email', 'test@example.com', 'email'),
            ('url', 'https://example.com', 'url')
        ]
        
        for field, value, field_type in valid_cases:
            is_valid, error = self.validation_service._validate_field_value(
                field, value, field_type
            )
            self.assertTrue(is_valid, f"Validation failed for {field}: {value}")
            self.assertIsNone(error)
        
        # Invalid values
        invalid_cases = [
            ('name', '', 'string'),
            ('priority', -1, 'integer'),
            ('is_active', 'invalid', 'boolean'),
            ('score', -1.0, 'float'),
            ('percentage', 150.0, 'percentage'),
            ('email', 'invalid-email', 'email'),
            ('url', 'invalid-url', 'url')
        ]
        
        for field, value, field_type in invalid_cases:
            is_valid, error = self.validation_service._validate_field_value(
                field, value, field_type
            )
            self.assertFalse(is_valid, f"Validation should have failed for {field}: {value}")
            self.assertIsNotNone(error)


class RouteEvaluatorTestCase(TestCase):
    """Test cases for RouteEvaluator."""
    
    def setUp(self):
        """Set up test data."""
        self.route_evaluator = RouteEvaluator()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer route
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for evaluation',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_validate_route(self):
        """Test route validation."""
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('is_valid', validation_result)
        self.assertIn('errors', validation_result)
        self.assertIn('warnings', validation_result)
        self.assertIn('recommendations', validation_result)
    
    def test_test_route_with_user(self):
        """Test route testing with user."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'current_time': timezone.now()
        }
        
        test_result = self.route_evaluator.test_route_with_user(
            route=self.offer_route,
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(test_result, dict)
        self.assertIn('matches', test_result)
        self.assertIn('score', test_result)
        self.assertIn('recommendations', test_result)
    
    def test_validate_all_routes(self):
        """Test validation of all routes."""
        validation_results = self.route_evaluator.validate_all_routes(tenant_id=self.tenant.id)
        
        self.assertIsInstance(validation_results, dict)
        self.assertIn('total_routes', validation_results)
        self.assertIn('valid_routes', validation_results)
        self.assertIn('invalid_routes', validation_results)
        self.assertIn('routes_with_warnings', validation_results)
        self.assertIn('summary', validation_results)
        self.assertIn('route_results', validation_results)
    
    def test_batch_test_routes(self):
        """Test batch route testing."""
        # Create additional routes
        from ..models import OfferRoute
        routes = [self.offer_route]
        
        for i in range(2):
            route = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for batch testing',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            routes.append(route)
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        test_results = self.route_evaluator.batch_test_routes(
            route_ids=[route.id for route in routes],
            user_ids=[self.user.id],
            context=context
        )
        
        self.assertIsInstance(test_results, dict)
        self.assertIn('total_routes', test_results)
        self.assertIn('total_users', test_results)
        self.assertIn('total_tests', test_results)
        self.assertIn('test_results', test_results)
    
    def test_generate_route_recommendations(self):
        """Test route recommendations generation."""
        recommendations = self.route_evaluator.generate_route_recommendations(tenant_id=self.tenant.id)
        
        self.assertIsInstance(recommendations, dict)
        self.assertIn('total_routes', recommendations)
        self.assertIn('routes_with_recommendations', recommendations)
        self.assertIn('recommendations', recommendations)
        
        for recommendation in recommendations['recommendations']:
            self.assertIsInstance(recommendation, dict)
            self.assertIn('route_id', recommendation)
            self.assertIn('route_name', recommendation)
            self.assertIn('recommendations', recommendation)
    
    def test_check_route_conflicts(self):
        """Test route conflict checking."""
        # Create conflicting route
        from ..models import OfferRoute
        conflicting_route = OfferRoute.objects.create(
            name='Conflicting Route',
            description='Route with same priority',
            tenant=self.tenant,
            priority=5,  # Same priority as test route
            max_offers=10,
            is_active=True
        )
        
        conflicts = self.route_evaluator.check_route_conflicts(tenant_id=self.tenant.id)
        
        self.assertIsInstance(conflicts, dict)
        self.assertIn('total_routes', conflicts)
        self.assertIn('conflicts_found', conflicts)
        self.assertIn('conflicts', conflicts)
    
    def test_export_evaluation_report(self):
        """Test evaluation report export."""
        report = self.route_evaluator.export_evaluation_report(tenant_id=self.tenant.id)
        
        self.assertIsInstance(report, dict)
        self.assertIn('generated_at', report)
        self.assertIn('validation_results', report)
        self.assertIn('evaluation_summary', report)
        self.assertIn('route_recommendations', report)
        self.assertIn('summary', report)


class UtilsIntegrationTestCase(TestCase):
    """Integration tests for utility functionality."""
    
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
    
    def test_utils_workflow(self):
        """Test complete utility workflow."""
        # Generate user hash
        user_hash = utils_service.generate_user_hash(
            self.user.id,
            {'segment': 'premium'}
        )
        
        self.assertIsInstance(user_hash, str)
        self.assertGreater(len(user_hash), 0)
        
        # Generate context hash
        context = {'location': {'country': 'US'}}
        context_hash = utils_service.generate_context_hash(context)
        
        self.assertIsInstance(context_hash, str)
        self.assertGreater(len(context_hash), 0)
        
        # Validate routing data
        routing_data = {
            'user_id': self.user.id,
            'context': context,
            'limit': 10
        }
        
        validation_result = utils_service.validate_routing_data(routing_data)
        
        self.assertTrue(validation_result['is_valid'])
        
        # Extract user agent info
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0'
        user_agent_info = utils_service.extract_user_agent_info(user_agent)
        
        self.assertIsInstance(user_agent_info, dict)
        self.assertIn('browser', user_agent_info)
        
        # Parse IP address
        ip_info = utils_service.parse_ip_address('192.168.1.1')
        
        self.assertIsInstance(ip_info, dict)
        self.assertIn('is_valid', ip_info)
        
        # Format routing response
        response = utils_service.format_routing_response(
            success=True,
            offers=[{'id': 1, 'name': 'Test Offer', 'score': 85.5}],
            metadata={'response_time_ms': 45.2}
        )
        
        self.assertIsInstance(response, dict)
        self.assertEqual(response['success'], True)
    
    def test_validation_workflow(self):
        """Test complete validation workflow."""
        # Validate offer data
        offer_data = {
            'name': 'Test Offer',
            'description': 'Test offer description',
            'priority': 5,
            'max_offers': 10,
            'is_active': True
        }
        
        validation_result = validation_service.validate_offer_data(offer_data)
        
        self.assertTrue(validation_result['is_valid'])
        
        # Validate route data
        route_data = {
            'name': 'Test Route',
            'description': 'Test route description',
            'priority': 5,
            'max_offers': 10,
            'is_active': True
        }
        
        validation_result = validation_service.validate_route_data(route_data)
        
        self.assertTrue(validation_result['is_valid'])
        
        # Validate routing request
        request_data = {
            'user_id': self.user.id,
            'context': {'location': {'country': 'US'}},
            'limit': 10
        }
        
        validation_result = validation_service.validate_routing_request(request_data)
        
        self.assertTrue(validation_result['is_valid'])
    
    def test_evaluation_workflow(self):
        """Test complete evaluation workflow."""
        # Validate all routes
        validation_results = route_evaluator.validate_all_routes(tenant_id=self.user.id)
        
        self.assertIsInstance(validation_results, dict)
        self.assertIn('total_routes', validation_results)
        
        # Test route with user
        context = {'location': {'country': 'US'}}
        
        test_result = route_evaluator.test_route_with_user(
            route=self.offers[0],
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(test_result, dict)
        
        # Generate recommendations
        recommendations = route_evaluator.generate_route_recommendations(tenant_id=self.user.id)
        
        self.assertIsInstance(recommendations, dict)
        self.assertIn('total_routes', recommendations)
    
    def test_utils_performance(self):
        """Test utility performance."""
        import time
        
        # Measure hash generation time
        start_time = time.time()
        
        for i in range(100):
            utils_service.generate_user_hash(
                self.user.id,
                {'segment': f'segment_{i}'}
            )
        
        end_time = time.time()
        hash_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(hash_time, 1000)  # Within 1 second
        
        # Measure validation time
        start_time = time.time()
        
        for i in range(100):
            routing_data = {
                'user_id': self.user.id,
                'context': {'location': {'country': 'US'}},
                'limit': 10
            }
            utils_service.validate_routing_data(routing_data)
        
        end_time = time.time()
        validation_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(validation_time, 500)  # Within 500ms
    
    def test_utils_error_handling(self):
        """Test error handling in utilities."""
        # Test with invalid user ID
        with self.assertRaises(Exception):
            utils_service.generate_user_hash(999999, {})
        
        # Test with invalid context
        with self.assertRaises(Exception):
            utils_service.generate_context_hash(None)
        
        # Test with invalid routing data
        invalid_data = {
            'user_id': None,
            'context': None,
            'limit': -1
        }
        
        validation_result = utils_service.validate_routing_data(invalid_data)
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
