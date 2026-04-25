"""Test Filter Service for Webhooks System

This module contains tests for the webhook filter service
including filter evaluation, complex operators, and nested field access.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model

from ..services.filtering import FilterService
from ..models import (
    WebhookEndpoint, WebhookFilter, WebhookSubscription, WebhookDeliveryLog
)
from ..constants import FilterOperator

User = get_user_model()


class FilterServiceTest(TestCase):
    """Test cases for FilterService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            created_by=self.user,
        )
        self.filter_service = FilterService()
    
    def test_evaluate_filter_equals(self):
        """Test filter evaluation with equals operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_equals_false(self):
        """Test filter evaluation with equals operator (false case)."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'different@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_evaluate_filter_contains(self):
        """Test filter evaluation with contains operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_contains_false(self):
        """Test filter evaluation with contains operator (false case)."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@other.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_evaluate_filter_greater_than(self):
        """Test filter evaluation with greater than operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.GREATER_THAN,
            value=100,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 150}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_greater_than_false(self):
        """Test filter evaluation with greater than operator (false case)."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.GREATER_THAN,
            value=100,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 50}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_evaluate_filter_less_than(self):
        """Test filter evaluation with less than operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.LESS_THAN,
            value=200,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 150}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_less_than_false(self):
        """Test filter evaluation with less than operator (false case)."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.LESS_THAN,
            value=100,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 150}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_evaluate_filter_not_equals(self):
        """Test filter evaluation with not equals operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.NOT_EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'different@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_not_equals_false(self):
        """Test filter evaluation with not equals operator (false case)."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.NOT_EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_evaluate_filter_not_contains(self):
        """Test filter evaluation with not contains operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.NOT_CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@other.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_not_contains_false(self):
        """Test filter evaluation with not contains operator (false case)."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.NOT_CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_evaluate_filters_multiple_all_pass(self):
        """Test multiple filter evaluation (all pass)."""
        # Create multiple filters
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.status',
            operator=FilterOperator.EQUALS,
            value='active',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_email': 'test@example.com',
            'user_status': 'active'
        }
        
        result = self.filter_service.evaluate_filters(self.endpoint, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filters_multiple_one_fails(self):
        """Test multiple filter evaluation (one fails)."""
        # Create multiple filters
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.status',
            operator=FilterOperator.EQUALS,
            value='active',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_email': 'test@example.com',
            'user_status': 'inactive'  # This will fail
        }
        
        result = self.filter_service.evaluate_filters(self.endpoint, event_data)
        
        self.assertFalse(result)
    
    def test_evaluate_filters_no_filters(self):
        """Test filter evaluation with no filters."""
        event_data = {'user_email': 'test@example.com'}
        
        result = self.filter_service.evaluate_filters(self.endpoint, event_data)
        
        self.assertTrue(result)  # Should pass by default
    
    def test_evaluate_filters_inactive_filters(self):
        """Test filter evaluation with inactive filters."""
        # Create inactive filter
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=False,  # Inactive
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@other.com'}  # Would fail if active
        
        result = self.filter_service.evaluate_filters(self.endpoint, event_data)
        
        self.assertTrue(result)  # Should pass by default
    
    def test_nested_field_access(self):
        """Test nested field access in filters."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='profile.settings.notifications.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'profile': {
                'settings': {
                    'notifications': {
                        'email': 'test@example.com'
                    }
                }
            }
        }
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_nested_field_access_deep(self):
        """Test deep nested field access."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='data.user.profile.settings.theme.colors.primary',
            operator=FilterOperator.EQUALS,
            value='#000000',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'data': {
                'user': {
                    'profile': {
                        'settings': {
                            'theme': {
                                'colors': {
                                    'primary': '#000000'
                                }
                            }
                        }
                    }
                }
            }
        }
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_nested_field_access_missing_field(self):
        """Test nested field access with missing field."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='profile.settings.notifications.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'profile': {
                'settings': {
                    # notifications field is missing
                }
            }
        }
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_nested_field_access_null_value(self):
        """Test nested field access with null value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='profile.settings.notifications.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'profile': {
                'settings': {
                    'notifications': {
                        'email': None
                    }
                }
            }
        }
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_filter_with_list_field(self):
        """Test filter evaluation with list field."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='tags',
            operator=FilterOperator.CONTAINS,
            value='important',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'tags': ['important', 'urgent', 'test']}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_list_field_not_contains(self):
        """Test filter evaluation with list field (not contains)."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='tags',
            operator=FilterOperator.NOT_CONTAINS,
            value='spam',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'tags': ['important', 'urgent', 'test']}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_numeric_string_value(self):
        """Test filter evaluation with numeric string value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.id',
            operator=FilterOperator.EQUALS,
            value='12345',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_string_numeric_value(self):
        """Test filter evaluation with string numeric value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.id',
            operator=FilterOperator.EQUALS,
            value=12345,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': '12345'}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_boolean_value(self):
        """Test filter evaluation with boolean value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.active',
            operator=FilterOperator.EQUALS,
            value=True,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_active': True}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_boolean_string_value(self):
        """Test filter evaluation with boolean string value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.active',
            operator=FilterOperator.EQUALS,
            value='true',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_active': True}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_date_value(self):
        """Test filter evaluation with date value."""
        from datetime import datetime
        
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='event.created_at',
            operator=FilterOperator.EQUALS,
            value='2024-01-01T00:00:00Z',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'event_created_at': '2024-01-01T00:00:00Z'}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_regex_pattern(self):
        """Test filter evaluation with regex-like pattern."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@.*\.com$',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_case_insensitive(self):
        """Test filter evaluation case insensitive."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='EXAMPLE.COM',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_empty_string_value(self):
        """Test filter evaluation with empty string value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': ''}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_zero_value(self):
        """Test filter evaluation with zero value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.EQUALS,
            value=0,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 0}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_negative_value(self):
        """Test filter evaluation with negative value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.balance',
            operator=FilterOperator.LESS_THAN,
            value=0,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_balance': -100}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_float_value(self):
        """Test filter evaluation with float value."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.GREATER_THAN,
            value=99.99,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 100.50}
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_performance_large_payload(self):
        """Test filter performance with large payload."""
        import time
        
        # Create filter
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        # Create large payload
        large_event_data = {
            'user_email': 'test@example.com',
            'large_data': ['x' * 1000] * 1000  # ~1MB of data
        }
        
        start_time = time.time()
        result = self.filter_service.evaluate_filter(filter_obj, large_event_data)
        end_time = time.time()
        
        self.assertTrue(result)
        self.assertLess(end_time - start_time, 1.0)  # Should complete in < 1 second
    
    def test_filter_performance_multiple_filters(self):
        """Test filter performance with multiple filters."""
        import time
        
        # Create multiple filters
        for i in range(10):
            WebhookFilter.objects.create(
                endpoint=self.endpoint,
                field_path=f'field_{i}',
                operator=FilterOperator.EQUALS,
                value=f'value_{i}',
                is_active=True,
                created_by=self.user,
            )
        
        # Create event data
        event_data = {}
        for i in range(10):
            event_data[f'field_{i}'] = f'value_{i}'
        
        start_time = time.time()
        result = self.filter_service.evaluate_filters(self.endpoint, event_data)
        end_time = time.time()
        
        self.assertTrue(result)
        self.assertLess(end_time - start_time, 1.0)  # Should complete in < 1 second
    
    def test_filter_error_handling_invalid_field_path(self):
        """Test filter error handling with invalid field path."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='',  # Invalid empty field path
            operator=FilterOperator.EQUALS,
            value='test',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        # Should handle gracefully and return False
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_filter_error_handling_invalid_operator(self):
        """Test filter error handling with invalid operator."""
        # Create filter with invalid operator
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator='invalid_operator',
            value='test',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        # Should handle gracefully and return False
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertFalse(result)
    
    def test_filter_with_subscription_filter_config(self):
        """Test filter evaluation with subscription filter config."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={
                'user.email': {
                    'operator': 'contains',
                    'value': '@example.com'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        result = self.filter_service.evaluate_subscription_filter(subscription, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_subscription_filter_config_multiple(self):
        """Test filter evaluation with subscription filter config (multiple filters)."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={
                'user.email': {
                    'operator': 'contains',
                    'value': '@example.com'
                },
                'user.status': {
                    'operator': 'equals',
                    'value': 'active'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_email': 'test@example.com',
            'user_status': 'active'
        }
        
        result = self.filter_service.evaluate_subscription_filter(subscription, event_data)
        
        self.assertTrue(result)
    
    def test_filter_with_subscription_filter_config_one_fails(self):
        """Test filter evaluation with subscription filter config (one fails)."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={
                'user.email': {
                    'operator': 'contains',
                    'value': '@example.com'
                },
                'user.status': {
                    'operator': 'equals',
                    'value': 'active'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_email': 'test@example.com',
            'user_status': 'inactive'  # This will fail
        }
        
        result = self.filter_service.evaluate_subscription_filter(subscription, event_data)
        
        self.assertFalse(result)
    
    def test_filter_with_subscription_filter_config_empty(self):
        """Test filter evaluation with empty subscription filter config."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={},
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        result = self.filter_service.evaluate_subscription_filter(subscription, event_data)
        
        self.assertTrue(result)  # Should pass by default
    
    def test_filter_with_subscription_filter_config_none(self):
        """Test filter evaluation with None subscription filter config."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config=None,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        result = self.filter_service.evaluate_subscription_filter(subscription, event_data)
        
        self.assertTrue(result)  # Should pass by default
    
    def test_filter_cache_behavior(self):
        """Test filter caching behavior."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        
        # First evaluation
        result1 = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        # Second evaluation (should use cache)
        result2 = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result1)
        self.assertTrue(result2)
    
    def test_filter_concurrent_safety(self):
        """Test filter evaluation concurrent safety."""
        import threading
        
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        results = []
        
        def evaluate_filter():
            event_data = {'user_email': 'test@example.com'}
            result = self.filter_service.evaluate_filter(filter_obj, event_data)
            results.append(result)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=evaluate_filter)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All evaluations should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result for result in results))
