"""
Evaluator Tests for Offer Routing System

This module contains unit tests for evaluator functionality,
including route evaluation, testing, and validation operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.evaluator import RouteEvaluator, route_evaluator
from ..models import OfferRoute, RouteCondition, RouteAction
from ..exceptions import EvaluationError, ValidationError

User = get_user_model()


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
        
        # Create route conditions
        self.condition1 = RouteCondition.objects.create(
            route=self.offer_route,
            field_name='country',
            operator='equals',
            value='US',
            is_required=True
        )
        
        self.condition2 = RouteCondition.objects.create(
            route=self.offer_route,
            field_name='device_type',
            operator='in',
            value='desktop,mobile',
            is_required=False
        )
        
        # Create route actions
        self.action1 = RouteAction.objects.create(
            route=self.offer_route,
            action_type='show_offer',
            action_value='1',
            priority=1
        )
        
        self.action2 = RouteAction.objects.create(
            route=self.offer_route,
            action_type='set_score',
            action_value='85.5',
            priority=2
        )
    
    def test_validate_route(self):
        """Test route validation."""
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('is_valid', validation_result)
        self.assertIn('errors', validation_result)
        self.assertIn('warnings', validation_result)
        self.assertIn('recommendations', validation_result)
        self.assertIn('validation_timestamp', validation_result)
        
        # Should be valid with our test data
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_route_basic_fields(self):
        """Test basic field validation."""
        # Test valid route
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        self.assertTrue(validation_result['is_valid'])
        
        # Test invalid route (empty name)
        self.offer_route.name = ''
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
        
        # Restore name
        self.offer_route.name = 'Test Route'
    
    def test_validate_route_conditions(self):
        """Test condition validation."""
        # Add invalid condition
        invalid_condition = RouteCondition.objects.create(
            route=self.offer_route,
            field_name='',  # Empty field name
            operator='equals',
            value='US',
            is_required=True
        )
        
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        self.assertFalse(validation_result['is_valid'])
        
        # Check for condition error
        condition_errors = [e for e in validation_result['errors'] if 'condition' in e.lower()]
        self.assertGreater(len(condition_errors), 0)
        
        # Remove invalid condition
        invalid_condition.delete()
    
    def test_validate_route_actions(self):
        """Test action validation."""
        # Add invalid action
        invalid_action = RouteAction.objects.create(
            route=self.offer_route,
            action_type='',  # Empty action type
            action_value='1',
            priority=1
        )
        
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        self.assertFalse(validation_result['is_valid'])
        
        # Check for action error
        action_errors = [e for e in validation_result['errors'] if 'action' in e.lower()]
        self.assertGreater(len(action_errors), 0)
        
        # Remove invalid action
        invalid_action.delete()
    
    def test_validate_route_targeting_rules(self):
        """Test targeting rule validation."""
        # Create targeting rules
        from ..models import GeoRouteRule, DeviceRouteRule
        
        geo_rule = GeoRouteRule.objects.create(
            route=self.offer_route,
            country='US',
            is_include=True
        )
        
        device_rule = DeviceRouteRule.objects.create(
            route=self.offer_route,
            device_type='desktop',
            is_include=True
        )
        
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        
        # Should be valid with proper targeting rules
        self.assertTrue(validation_result['is_valid'])
        
        # Check for targeting validation results
        self.assertIn('targeting_validation', validation_result)
    
    def test_validate_route_logical_issues(self):
        """Test logical issue validation."""
        # Create conflicting conditions
        conflicting_condition = RouteCondition.objects.create(
            route=self.offer_route,
            field_name='country',
            operator='equals',
            value='CA',  # Conflicts with US condition
            is_required=True
        )
        
        validation_result = self.route_evaluator.validate_route(self.offer_route)
        
        # Should have warning about logical conflict
        logical_warnings = [w for w in validation_result['warnings'] if 'conflict' in w.lower()]
        self.assertGreater(len(logical_warnings), 0)
        
        # Remove conflicting condition
        conflicting_condition.delete()
    
    def test_test_route_with_user(self):
        """Test route testing with user."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'user_agent': 'Mozilla/5.0'
        }
        
        test_result = self.route_evaluator.test_route_with_user(
            route=self.offer_route,
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(test_result, dict)
        self.assertIn('matches', test_result)
        self.assertIn('conditions_matched', test_result)
        self.assertIn('conditions_failed', test_result)
        self.assertIn('actions_applied', test_result)
        self.assertIn('score', test_result)
        self.assertIn('recommendations', test_result)
        self.assertIn('test_timestamp', test_result)
    
    def test_test_route_with_user_no_match(self):
        """Test route testing with user when conditions don't match."""
        context = {
            'location': {'country': 'CA'},  # Doesn't match US condition
            'device': {'type': 'mobile'},
            'user_agent': 'Mozilla/5.0'
        }
        
        test_result = self.route_evaluator.test_route_with_user(
            route=self.offer_route,
            user=self.user,
            context=context
        )
        
        self.assertFalse(test_result['matches'])
        self.assertGreater(len(test_result['conditions_failed']), 0)
    
    def test_test_route_with_user_missing_context(self):
        """Test route testing with missing context."""
        context = {}  # Missing location data
        
        test_result = self.route_evaluator.test_route_with_user(
            route=self.offer_route,
            user=self.user,
            context=context
        )
        
        self.assertFalse(test_result['matches'])
        self.assertIn('error', test_result)
    
    def test_validate_all_routes(self):
        """Test validation of all routes."""
        # Create additional routes
        from ..models import OfferRoute
        additional_routes = []
        
        for i in range(2):
            route = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for batch validation',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            additional_routes.append(route)
        
        validation_results = self.route_evaluator.validate_all_routes(tenant_id=self.tenant.id)
        
        self.assertIsInstance(validation_results, dict)
        self.assertIn('total_routes', validation_results)
        self.assertIn('valid_routes', validation_results)
        self.assertIn('invalid_routes', validation_results)
        self.assertIn('routes_with_warnings', validation_results)
        self.assertIn('summary', validation_results)
        self.assertIn('route_results', validation_results)
        self.assertIn('validation_timestamp', validation_results)
        
        # Should include all routes
        self.assertEqual(validation_results['total_routes'], 3)
        
        # Check individual route results
        self.assertEqual(len(validation_results['route_results']), 3)
        
        for route_id, result in validation_results['route_results'].items():
            self.assertIsInstance(result, dict)
            self.assertIn('is_valid', result)
            self.assertIn('errors', result)
            self.assertIn('warnings', result)
    
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
        
        # Create additional users
        users = [self.user]
        for i in range(2):
            user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'testuser{i}@example.com',
                password='testpass123'
            )
            users.append(user)
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        test_results = self.route_evaluator.batch_test_routes(
            route_ids=[route.id for route in routes],
            user_ids=[user.id for user in users],
            context=context
        )
        
        self.assertIsInstance(test_results, dict)
        self.assertIn('total_routes', test_results)
        self.assertIn('total_users', test_results)
        self.assertIn('total_tests', test_results)
        self.assertIn('test_results', test_results)
        self.assertIn('test_timestamp', test_results)
        
        # Should test all combinations
        self.assertEqual(test_results['total_routes'], 3)
        self.assertEqual(test_results['total_users'], 3)
        self.assertEqual(test_results['total_tests'], 9)
        self.assertEqual(len(test_results['test_results']), 9)
    
    def test_generate_route_recommendations(self):
        """Test route recommendations generation."""
        recommendations = self.route_evaluator.generate_route_recommendations(tenant_id=self.tenant.id)
        
        self.assertIsInstance(recommendations, dict)
        self.assertIn('total_routes', recommendations)
        self.assertIn('routes_with_recommendations', recommendations)
        self.assertIn('recommendations', recommendations)
        self.assertIn('generation_timestamp', recommendations)
        
        # Should include our test route
        self.assertGreaterEqual(recommendations['total_routes'], 1)
        
        # Check recommendation structure
        for recommendation in recommendations['recommendations']:
            self.assertIsInstance(recommendation, dict)
            self.assertIn('route_id', recommendation)
            self.assertIn('route_name', recommendation)
            self.assertIn('recommendations', recommendation)
            
            for rec in recommendation['recommendations']:
                self.assertIsInstance(rec, dict)
                self.assertIn('type', rec)
                self.assertIn('message', rec)
                self.assertIn('priority', rec)
    
    def test_check_route_conflicts(self):
        """Test route conflict checking."""
        # Create conflicting route
        from ..models import OfferRoute
        conflicting_route = OfferRoute.objects.create(
            name='Conflicting Route',
            description='Route with same priority and conditions',
            tenant=self.tenant,
            priority=5,  # Same priority as test route
            max_offers=10,
            is_active=True
        )
        
        # Add same conditions
        RouteCondition.objects.create(
            route=conflicting_route,
            field_name='country',
            operator='equals',
            value='US',
            is_required=True
        )
        
        conflicts = self.route_evaluator.check_route_conflicts(tenant_id=self.tenant.id)
        
        self.assertIsInstance(conflicts, dict)
        self.assertIn('total_routes', conflicts)
        self.assertIn('conflicts_found', conflicts)
        self.assertIn('conflicts', conflicts)
        self.assertIn('check_timestamp', conflicts)
        
        # Should find conflicts
        self.assertGreater(conflicts['conflicts_found'], 0)
        self.assertGreater(len(conflicts['conflicts']), 0)
        
        # Check conflict structure
        for conflict in conflicts['conflicts']:
            self.assertIsInstance(conflict, dict)
            self.assertIn('route1_id', conflict)
            self.assertIn('route2_id', conflict)
            self.assertIn('conflicts', conflict)
            
            for conflict_detail in conflict['conflicts']:
                self.assertIsInstance(conflict_detail, dict)
                self.assertIn('type', conflict_detail)
                self.assertIn('message', conflict_detail)
                self.assertIn('severity', conflict_detail)
    
    def test_export_evaluation_report(self):
        """Test evaluation report export."""
        report = self.route_evaluator.export_evaluation_report(tenant_id=self.tenant.id)
        
        self.assertIsInstance(report, dict)
        self.assertIn('generated_at', report)
        self.assertIn('validation_results', report)
        self.assertIn('evaluation_summary', report)
        self.assertIn('route_recommendations', report)
        self.assertIn('conflict_analysis', report)
        self.assertIn('summary', report)
        
        # Check validation results
        self.assertIn('total_routes', report['validation_results'])
        self.assertIn('valid_routes', report['validation_results'])
        self.assertIn('invalid_routes', report['validation_results'])
        
        # Check evaluation summary
        self.assertIn('overall_health', report['evaluation_summary'])
        self.assertIn('priority_distribution', report['evaluation_summary'])
        self.assertIn('condition_usage', report['evaluation_summary'])
        self.assertIn('action_usage', report['evaluation_summary'])
        
        # Check summary
        self.assertIn('total_routes_evaluated', report['summary'])
        self.assertIn('routes_with_issues', report['summary'])
        self.assertIn('total_recommendations', report['summary'])
        self.assertIn('total_conflicts', report['summary'])
    
    def test_evaluate_route_performance(self):
        """Test route performance evaluation."""
        performance_data = self.route_evaluator.evaluate_route_performance(
            route_id=self.offer_route.id,
            days=30
        )
        
        self.assertIsInstance(performance_data, dict)
        self.assertIn('route_id', performance_data)
        self.assertIn('performance_metrics', performance_data)
        self.assertIn('evaluation_period', performance_data)
        self.assertIn('evaluation_timestamp', performance_data)
        
        # Check performance metrics
        metrics = performance_data['performance_metrics']
        self.assertIn('total_requests', metrics)
        self.assertIn('avg_response_time', metrics)
        self.assertIn('success_rate', metrics)
        self.assertIn('conversion_rate', metrics)
    
    def test_get_route_health_score(self):
        """Test route health score calculation."""
        health_score = self.route_evaluator._get_route_health_score(self.offer_route)
        
        self.assertIsInstance(health_score, (int, float))
        self.assertGreaterEqual(health_score, 0)
        self.assertLessEqual(health_score, 100)
    
    def test_analyze_route_usage_patterns(self):
        """Test route usage pattern analysis."""
        patterns = self.route_evaluator._analyze_route_usage_patterns(self.offer_route)
        
        self.assertIsInstance(patterns, dict)
        self.assertIn('usage_frequency', patterns)
        self.assertIn('peak_hours', patterns)
        self.assertIn('user_segments', patterns)
        self.assertIn('geographic_distribution', patterns)
    
    def test_suggest_route_improvements(self):
        """Test route improvement suggestions."""
        suggestions = self.route_evaluator._suggest_route_improvements(self.offer_route)
        
        self.assertIsInstance(suggestions, list)
        
        for suggestion in suggestions:
            self.assertIsInstance(suggestion, dict)
            self.assertIn('type', suggestion)
            self.assertIn('title', suggestion)
            self.assertIn('description', suggestion)
            self.assertIn('priority', suggestion)
            self.assertIn('estimated_impact', suggestion)


class RouteEvaluatorIntegrationTestCase(TestCase):
    """Integration tests for RouteEvaluator."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
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
    
    def test_evaluator_workflow(self):
        """Test complete evaluator workflow."""
        # Validate all routes
        validation_results = route_evaluator.validate_all_routes(tenant_id=self.user.id)
        
        self.assertIsInstance(validation_results, dict)
        self.assertIn('total_routes', validation_results)
        self.assertEqual(validation_results['total_routes'], 3)
        
        # Test routes with user
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        for offer in self.offers:
            test_result = route_evaluator.test_route_with_user(
                route=offer,
                user=self.user,
                context=context
            )
            
            self.assertIsInstance(test_result, dict)
            self.assertIn('matches', test_result)
        
        # Generate recommendations
        recommendations = route_evaluator.generate_route_recommendations(tenant_id=self.user.id)
        
        self.assertIsInstance(recommendations, dict)
        self.assertIn('total_routes', recommendations)
        
        # Check for conflicts
        conflicts = route_evaluator.check_route_conflicts(tenant_id=self.user.id)
        
        self.assertIsInstance(conflicts, dict)
        self.assertIn('total_routes', conflicts)
        
        # Export evaluation report
        report = route_evaluator.export_evaluation_report(tenant_id=self.user.id)
        
        self.assertIsInstance(report, dict)
        self.assertIn('generated_at', report)
    
    def test_route_validation_with_conditions(self):
        """Test route validation with complex conditions."""
        # Add conditions to first route
        RouteCondition.objects.create(
            route=self.offers[0],
            field_name='country',
            operator='equals',
            value='US',
            is_required=True
        )
        
        RouteCondition.objects.create(
            route=self.offers[0],
            field_name='device_type',
            operator='in',
            value='desktop,mobile',
            is_required=False
        )
        
        RouteCondition.objects.create(
            route=self.offers[0],
            field_name='user_segment',
            operator='equals',
            value='premium',
            is_required=False
        )
        
        # Add actions
        RouteAction.objects.create(
            route=self.offers[0],
            action_type='show_offer',
            action_value='1',
            priority=1
        )
        
        RouteAction.objects.create(
            route=self.offers[0],
            action_type='set_score',
            action_value='85.5',
            priority=2
        )
        
        validation_result = route_evaluator.validate_route(self.offers[0])
        
        self.assertTrue(validation_result['is_valid'])
        
        # Test with user
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'user_segment': 'premium'
        }
        
        test_result = route_evaluator.test_route_with_user(
            route=self.offers[0],
            user=self.user,
            context=context
        )
        
        self.assertTrue(test_result['matches'])
        self.assertGreater(len(test_result['conditions_matched']), 0)
    
    def test_route_conflict_detection(self):
        """Test route conflict detection."""
        # Create conflicting routes
        for i in range(2):
            route = OfferRoute.objects.create(
                name=f'Conflicting Route {i}',
                description=f'Route with same priority {i}',
                tenant=self.user,
                priority=5,  # Same priority
                max_offers=10,
                is_active=True
            )
            
            # Add same conditions
            RouteCondition.objects.create(
                route=route,
                field_name='country',
                operator='equals',
                value='US',
                is_required=True
            )
        
        # Check for conflicts
        conflicts = route_evaluator.check_route_conflicts(tenant_id=self.user.id)
        
        self.assertIsInstance(conflicts, dict)
        self.assertIn('conflicts', conflicts)
        
        # Should find priority conflicts
        priority_conflicts = [
            c for c in conflicts['conflicts']
            if any(detail['type'] == 'priority_conflict' for detail in c['conflicts'])
        ]
        
        self.assertGreater(len(priority_conflicts), 0)
    
    def test_batch_route_testing(self):
        """Test batch route testing."""
        # Create additional users
        users = [self.user]
        for i in range(2):
            user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'testuser{i}@example.com',
                password='testpass123'
            )
            users.append(user)
        
        # Add conditions to routes
        for offer in self.offers:
            RouteCondition.objects.create(
                route=offer,
                field_name='country',
                operator='equals',
                value='US',
                is_required=True
            )
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        test_results = route_evaluator.batch_test_routes(
            route_ids=[offer.id for offer in self.offers],
            user_ids=[user.id for user in users],
            context=context
        )
        
        self.assertIsInstance(test_results, dict)
        self.assertEqual(test_results['total_routes'], 3)
        self.assertEqual(test_results['total_users'], 3)
        self.assertEqual(test_results['total_tests'], 9)
        self.assertEqual(len(test_results['test_results']), 9)
        
        # Check test result structure
        for test_result in test_results['test_results']:
            self.assertIsInstance(test_result, dict)
            self.assertIn('route_id', test_result)
            self.assertIn('user_id', test_result)
            self.assertIn('matches', test_result)
            self.assertIn('conditions_matched', test_result)
            self.assertIn('conditions_failed', test_result)
    
    def test_evaluation_report_generation(self):
        """Test comprehensive evaluation report generation."""
        # Add conditions and actions to routes
        for offer in self.offers:
            RouteCondition.objects.create(
                route=offer,
                field_name='country',
                operator='equals',
                value='US',
                is_required=True
            )
            
            RouteAction.objects.create(
                route=offer,
                action_type='show_offer',
                action_value=str(offer.id),
                priority=1
            )
        
        # Generate report
        report = route_evaluator.export_evaluation_report(tenant_id=self.user.id)
        
        self.assertIsInstance(report, dict)
        self.assertIn('generated_at', report)
        self.assertIn('validation_results', report)
        self.assertIn('evaluation_summary', report)
        self.assertIn('route_recommendations', report)
        self.assertIn('conflict_analysis', report)
        self.assertIn('summary', report)
        
        # Check validation results
        validation_results = report['validation_results']
        self.assertEqual(validation_results['total_routes'], 3)
        self.assertGreaterEqual(validation_results['valid_routes'], 0)
        
        # Check evaluation summary
        evaluation_summary = report['evaluation_summary']
        self.assertIn('overall_health', evaluation_summary)
        self.assertIn('priority_distribution', evaluation_summary)
        
        # Check summary
        summary = report['summary']
        self.assertIn('total_routes_evaluated', summary)
        self.assertEqual(summary['total_routes_evaluated'], 3)
    
    def test_evaluator_performance(self):
        """Test evaluator performance."""
        import time
        
        # Add conditions to routes
        for offer in self.offers:
            RouteCondition.objects.create(
                route=offer,
                field_name='country',
                operator='equals',
                value='US',
                is_required=True
            )
        
        # Measure validation time
        start_time = time.time()
        
        validation_results = route_evaluator.validate_all_routes(tenant_id=self.user.id)
        
        end_time = time.time()
        validation_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(validation_time, 1000)  # Within 1 second
        
        # Measure testing time
        context = {'location': {'country': 'US'}}
        
        start_time = time.time()
        
        for offer in self.offers:
            route_evaluator.test_route_with_user(
                route=offer,
                user=self.user,
                context=context
            )
        
        end_time = time.time()
        testing_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(testing_time, 500)  # Within 500ms
    
    def test_evaluator_error_handling(self):
        """Test error handling in evaluator."""
        # Test with invalid route ID
        with self.assertRaises(Exception):
            route_evaluator.validate_route(999999)
        
        # Test with invalid user ID
        context = {'location': {'country': 'US'}}
        
        with self.assertRaises(Exception):
            route_evaluator.test_route_with_user(
                route=self.offers[0],
                user=None,
                context=context
            )
        
        # Test with invalid context
        with self.assertRaises(Exception):
            route_evaluator.test_route_with_user(
                route=self.offers[0],
                user=self.user,
                context=None
            )
        
        # Test with invalid tenant ID
        with self.assertRaises(Exception):
            route_evaluator.validate_all_routes(tenant_id=999999)
        
        # Test with invalid route IDs for batch testing
        with self.assertRaises(Exception):
            route_evaluator.batch_test_routes(
                route_ids=[999999],
                user_ids=[self.user.id],
                context={'location': {'country': 'US'}}
            )
