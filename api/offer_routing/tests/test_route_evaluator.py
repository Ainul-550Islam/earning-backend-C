"""
Test Route Evaluator

Tests for the route evaluator service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.core import RouteEvaluator
from ..models import OfferRoute, RouteCondition
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestRouteEvaluator(TestCase):
    """Test cases for RouteEvaluator service."""
    
    def setUp(self):
        """Set up test environment."""
        self.evaluator = RouteEvaluator()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_evaluate_single_condition(self):
        """Test evaluating a single condition."""
        try:
            # Create test condition
            condition = RouteCondition.objects.create(
                field_name='test_field',
                operator='equals',
                value='test_value',
                logic='AND'
            )
            
            # Create test context
            context = {
                'test_field': 'test_value',
                'user_agent': 'Mozilla/5.0'
            }
            
            # Evaluate condition
            result = self.evaluator.evaluate_condition(
                condition=condition,
                context=context
            )
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['result'], True)
            self.assertEqual(result['condition_id'], condition.id)
            
        except Exception as e:
            self.fail(f"Error in evaluate_single_condition: {e}")
    
    def test_evaluate_multiple_conditions(self):
        """Test evaluating multiple conditions."""
        try:
            # Create test conditions
            conditions = [
                RouteCondition.objects.create(
                    field_name='field1',
                    operator='equals',
                    value='value1',
                    logic='AND'
                ),
                RouteCondition.objects.create(
                    field_name='field2',
                    operator='greater_than',
                    value='100',
                    logic='OR'
                )
            ]
            
            # Create test context
            context = {
                'field1': 'value1',
                'field2': '150'
            }
            
            # Evaluate conditions
            result = self.evaluator.evaluate_conditions(
                conditions=conditions,
                context=context
            )
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['result'], True)  # field1 == value1 AND field2 > 100
            self.assertEqual(result['condition_ids'], [c.id for c in conditions])
            
        except Exception as e:
            self.fail(f"Error in evaluate_multiple_conditions: {e}")
    
    def test_evaluate_route_conditions(self):
        """Test evaluating route conditions."""
        try:
            # Create test route with conditions
            route = OfferRoute.objects.create(
                name='Test Route',
                is_active=True,
                priority=1
            )
            
            # Create conditions
            conditions = [
                RouteCondition.objects.create(
                    field_name='country',
                    operator='equals',
                    value='US',
                    logic='AND',
                    route=route
                ),
                RouteCondition.objects.create(
                    field_name='price',
                    operator='less_than',
                    value='100',
                    logic='AND',
                    route=route
                )
            ]
            
            # Add conditions to route
            route.conditions.add(*conditions)
            route.save()
            
            # Create test context
            context = {
                'country': 'US',
                'price': 50
            }
            
            # Evaluate route conditions
            result = self.evaluator.evaluate_route(
                route=route,
                context=context
            )
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['result'], True)  # country == US AND price < 100
            self.assertEqual(result['condition_ids'], [c.id for c in conditions])
            
        except Exception as e:
            self.fail(f"Error in evaluate_route_conditions: {e}")
    
    def test_parse_condition_value(self):
        """Test parsing condition values."""
        try:
            # Test string values
            result = self.evaluator.parse_condition_value('test_string')
            self.assertEqual(result, 'test_string')
            
            # Test numeric values
            result = self.evaluator.parse_condition_value('100')
            self.assertEqual(result, 100)
            
            # Test boolean values
            result = self.evaluator.parse_condition_value('true')
            self.assertEqual(result, True)
            
            # Test list values
            result = self.evaluator.parse_condition_value('["item1", "item2"]')
            self.assertEqual(result, ["item1", "item2"])
            
        except Exception as e:
            self.fail(f"Error in parse_condition_value: {e}")
    
    def test_apply_operator(self):
        """Test applying operators."""
        try:
            # Test equals operator
            result = self.evaluator.apply_operator('equals', 'test_value', 'test_value')
            self.assertTrue(result)
            
            # Test not equals operator
            result = self.evaluator.apply_operator('not_equals', 'test_value', 'other_value')
            self.assertTrue(result)
            
            # Test greater than operator
            result = self.evaluator.apply_operator('greater_than', 100, 50)
            self.assertTrue(result)
            
            # Test less than operator
            result = self.evaluator.apply_operator('less_than', 100, 150)
            self.assertFalse(result)
            
            # Test contains operator
            result = self.evaluator.apply_operator('contains', 'test_string', 'test')
            self.assertTrue(result)
            
            # Test in operator
            result = self.evaluator.apply_operator('in', 'test_value', ['item1', 'item2'])
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"Error in apply_operator: {e}")
    
    def test_validate_condition_config(self):
        """Test condition configuration validation."""
        try:
            # Test valid configuration
            valid_config = {
                'field_name': 'test_field',
                'operator': 'equals',
                'value': 'test_value',
                'logic': 'AND'
            }
            
            result = self.evaluator.validate_condition_config(valid_config)
            self.assertTrue(result['valid'])
            
            # Test invalid configuration
            invalid_config = {
                'field_name': '',  # Missing field name
                'operator': 'invalid_op',  # Invalid operator
                'value': 'test_value',
                'logic': 'invalid_logic'  # Invalid logic
            }
            
            result = self.evaluator.validate_condition_config(invalid_config)
            self.assertFalse(result['valid'])
            self.assertIn('field_name', result['errors'])
            self.assertIn('operator', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in validate_condition_config: {e}")
    
    def test_evaluate_logic_operators(self):
        """Test logic operator evaluation."""
        try:
            # Test AND operator
            conditions = [
                {'result': True, 'field': 'field1'},
                {'result': False, 'field': 'field2'}
            ]
            
            result = self.evaluator.evaluate_logic_operators('AND', conditions)
            self.assertTrue(result)  # Both must be True for AND
            
            # Test OR operator
            conditions = [
                {'result': True, 'field': 'field1'},
                {'result': False, 'field': 'field2'}
            ]
            
            result = self.evaluator.evaluate_logic_operators('OR', conditions)
            self.assertTrue(result)  # At least one must be True for OR
            
            # Test NOT operator
            conditions = [
                {'result': False, 'field': 'field1'},
                {'result': True, 'field': 'field2'}
            ]
            
            result = self.evaluator.evaluate_logic_operators('NOT', conditions)
            self.assertFalse(result)  # All must be False for NOT
            
        except Exception as e:
            self.fail(f"Error in evaluate_logic_operators: {e}")
    
    def test_get_supported_operators(self):
        """Test getting supported operators."""
        try:
            operators = self.evaluator.get_supported_operators()
            
            # Check for required operators
            required_operators = ['equals', 'not_equals', 'greater_than', 'less_than', 'contains', 'not_contains', 'in', 'not_in']
            
            for op in required_operators:
                self.assertIn(op, operators)
            
            # Check for logic operators
            logic_operators = ['AND', 'OR', 'NOT']
            
            for op in logic_operators:
                self.assertIn(op, operators)
            
        except Exception as e:
            self.fail(f"Error in get_supported_operators: {e}")
    
    def test_get_supported_fields(self):
        """Test getting supported fields."""
        try:
            fields = self.evaluator.get_supported_fields()
            
            # Check for common fields
            common_fields = [
                'country', 'region', 'city', 'device_type', 'os', 'browser',
                'price', 'category', 'score', 'created_at', 'updated_at'
            ]
            
            for field in common_fields:
                self.assertIn(field, fields)
            
        except Exception as e:
            self.fail(f"Error in get_supported_fields: {e}")
    
    def test_health_check(self):
        """Test route evaluator health check."""
        try:
            # Test health check
            health = self.evaluator.health_check()
            
            self.assertTrue(health['status'] == 'healthy')
            self.assertIn('supported_operators', health)
            self.assertIn('supported_fields', health)
            self.assertIn('cache_status', health)
            self.assertIn('performance_stats', health)
            
        except Exception as e:
            self.fail(f"Error in health_check: {e}")


if __name__ == '__main__':
    pytest.main()
