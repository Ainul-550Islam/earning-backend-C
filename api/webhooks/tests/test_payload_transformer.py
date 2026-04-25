"""Test Payload Transformer for Webhooks System

This module contains tests for the webhook payload transformer
including template rendering, transformation rules, and Jinja2 processing.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model

from ..services.core import TemplateEngine
from ..models import (
    WebhookEndpoint, WebhookTemplate, WebhookSubscription, WebhookDeliveryLog
)

User = get_user_model()


class TemplateEngineTest(TestCase):
    """Test cases for TemplateEngine."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.template_engine = TemplateEngine()
        
        self.template = WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email": {{user_email}}}',
            is_active=True,
            created_by=self.user,
        )
    
    def test_render_template_simple(self):
        """Test simple template rendering."""
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com'
        }
        
        rendered = self.template_engine.render_template(self.template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('email": "test@example.com"', rendered)
    
    def test_render_template_with_conditionals(self):
        """Test template rendering with conditionals."""
        template = WebhookTemplate.objects.create(
            name='Conditional Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "is_premium": {% if user_premium %}true{% else %}false{% endif %}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_premium': True
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('is_premium": true', rendered)
    
    def test_render_template_with_loops(self):
        """Test template rendering with loops."""
        template = WebhookTemplate.objects.create(
            name='Loop Template',
            event_type='order.created',
            payload_template='{"user_id": {{user_id}}, "items": [{% for item in items %}{{item}}{% if not loop.last %},{% endif %}{% endfor %}]}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'items': ['apple', 'banana', 'orange']
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('"items": ["apple","banana","orange"]', rendered)
    
    def test_render_template_with_filters(self):
        """Test template rendering with filters."""
        template = WebhookTemplate.objects.create(
            name='Filter Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email_upper": {{user_email | upper}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('email_upper": "TEST@EXAMPLE.COM"', rendered)
    
    def test_render_template_with_math_operations(self):
        """Test template rendering with math operations."""
        template = WebhookTemplate.objects.create(
            name='Math Template',
            event_type='order.created',
            payload_template='{"total": {{item_count * price}}, "tax": {{total * 0.1}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'item_count': 5,
            'price': 10.50,
            'total': 52.50
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('"total": 52.5', rendered)
        self.assertIn('"tax": 5.25', rendered)
    
    def test_render_template_with_nested_data(self):
        """Test template rendering with nested data."""
        template = WebhookTemplate.objects.create(
            name='Nested Template',
            event_type='user.created',
            payload_template='{"user_id": {{user.id}}, "profile_name": {{profile.name}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user': {
                'id': 12345,
                'email': 'test@example.com'
            },
            'profile': {
                'name': 'Test User',
                'age': 30
            }
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('profile_name": "Test User"', rendered)
    
    def test_render_template_with_missing_variable(self):
        """Test template rendering with missing variable."""
        template = WebhookTemplate.objects.create(
            name='Missing Variable Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "missing": {{missing_var}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345
            # missing_var is not provided
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        # Missing variable should be handled gracefully
        self.assertIn('missing": ""', rendered)
    
    def test_render_template_with_none_value(self):
        """Test template rendering with None value."""
        template = WebhookTemplate.objects.create(
            name='None Value Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email": {{user_email}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': None
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('email": None', rendered)
    
    def test_render_template_with_boolean_values(self):
        """Test template rendering with boolean values."""
        template = WebhookTemplate.objects.create(
            name='Boolean Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "is_active": {{is_active}}, "is_premium": {{is_premium}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'is_active': True,
            'is_premium': False
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('is_active": True', rendered)
        self.assertIn('is_premium": False', rendered)
    
    def test_render_template_with_numeric_values(self):
        """Test template rendering with numeric values."""
        template = WebhookTemplate.objects.create(
            name='Numeric Template',
            event_type='order.created',
            payload_template='{"order_id": {{order_id}}, "amount": {{amount}}, "quantity": {{quantity}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'order_id': 12345,
            'amount': 99.99,
            'quantity': 5
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('order_id": 12345', rendered)
        self.assertIn('amount": 99.99', rendered)
        self.assertIn('quantity": 5', rendered)
    
    def test_render_template_with_date_values(self):
        """Test template rendering with date values."""
        template = WebhookTemplate.objects.create(
            name='Date Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "created_at": "{{created_at}}", "formatted_date": "{{created_at | date(\'%Y-%m-%d\')}}"}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'created_at': '2024-01-01T00:00:00Z'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('created_at": "2024-01-01T00:00:00Z"', rendered)
        self.assertIn('formatted_date": "2024-01-01"', rendered)
    
    def test_render_template_with_list_values(self):
        """Test template rendering with list values."""
        template = WebhookTemplate.objects.create(
            name='List Template',
            event_type='order.created',
            payload_template='{"order_id": {{order_id}}, "items": {{items | length}}, "first_item": {{items[0]}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'order_id': 12345,
            'items': ['apple', 'banana', 'orange']
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('order_id": 12345', rendered)
        self.assertIn('items": 3', rendered)
        self.assertIn('first_item": "apple"', rendered)
    
    def test_render_template_with_dict_values(self):
        """Test template rendering with dict values."""
        template = WebhookTemplate.objects.create(
            name='Dict Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "profile_keys": {{profile | length}}, "profile_name": {{profile.name}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'profile': {
                'name': 'Test User',
                'age': 30
            }
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('profile_keys": 2', rendered)
        self.assertIn('profile_name": "Test User"', rendered)
    
    def test_apply_transform_rules_add_field(self):
        """Test transformation rule for adding field."""
        template = WebhookTemplate.objects.create(
            name='Add Field Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email": {{user_email}}}',
            transform_rules={
                'add_profile': {
                    'type': 'add_field',
                    'field_name': 'profile',
                    'value': {'name': 'Test User', 'age': 30}
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('email": "test@example.com"', rendered)
        self.assertIn('profile": {"name": "Test User", "age": 30}', rendered)
    
    def test_apply_transform_rules_remove_field(self):
        """Test transformation rule for removing field."""
        template = WebhookTemplate.objects.create(
            name='Remove Field Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email": {{user_email}}, "password": {{user_password}}}',
            transform_rules={
                'remove_password': {
                    'type': 'remove_field',
                    'path': 'user_password'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com',
            'user_password': 'secret123'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('email": "test@example.com"', rendered)
        self.assertNotIn('password', rendered)
    
    def test_apply_transform_rules_rename_field(self):
        """Test transformation rule for renaming field."""
        template = WebhookTemplate.objects.create(
            name='Rename Field Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email": {{user_email}}}',
            transform_rules={
                'rename_email': {
                    'type': 'rename_field',
                    'old_name': 'user_email',
                    'new_name': 'email_address'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('email_address": "test@example.com"', rendered)
        self.assertNotIn('user_email', rendered)
    
    def test_apply_transform_rules_map_value(self):
        """Test transformation rule for mapping values."""
        template = WebhookTemplate.objects.create(
            name='Map Value Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "status": {{user_status}}}',
            transform_rules={
                'map_status': {
                    'type': 'map_value',
                    'path': 'user_status',
                    'mappings': {
                        'active': 'ACTIVE',
                        'inactive': 'INACTIVE',
                        'pending': 'PENDING'
                    }
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_status': 'active'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('status": "ACTIVE"', rendered)
    
    def test_apply_transform_rules_format_date(self):
        """Test transformation rule for formatting dates."""
        template = WebhookTemplate.objects.create(
            name='Format Date Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "created_at": "{{created_at}}"}',
            transform_rules={
                'format_date': {
                    'type': 'format_date',
                    'path': 'created_at',
                    'format': '%Y-%m-%d %H:%M:%S'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'created_at': '2024-01-01T00:00:00Z'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('created_at": "2024-01-01 00:00:00"', rendered)
    
    def test_apply_transform_rules_calculate_field(self):
        """Test transformation rule for calculating fields."""
        template = WebhookTemplate.objects.create(
            name='Calculate Field Template',
            event_type='order.created',
            payload_template='{"order_id": {{order_id}}, "subtotal": {{subtotal}}, "tax": {{tax}}}',
            transform_rules={
                'calculate_total': {
                    'type': 'calculate_field',
                    'field_name': 'total',
                    'expression': 'subtotal + tax'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'order_id': 12345,
            'subtotal': 100.00,
            'tax': 10.00
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('order_id": 12345', rendered)
        self.assertIn('subtotal": 100.0', rendered)
        self.assertIn('tax": 10.0', rendered)
        self.assertIn('total": 110.0', rendered)
    
    def test_apply_transform_rules_multiple_rules(self):
        """Test applying multiple transformation rules."""
        template = WebhookTemplate.objects.create(
            name='Multiple Rules Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email": {{user_email}}, "status": {{user_status}}}',
            transform_rules={
                'map_status': {
                    'type': 'map_value',
                    'path': 'user_status',
                    'mappings': {
                        'active': 'ACTIVE',
                        'inactive': 'INACTIVE'
                    }
                },
                'add_timestamp': {
                    'type': 'add_field',
                    'field_name': 'timestamp',
                    'value': '2024-01-01T00:00:00Z'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com',
            'user_status': 'active'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('email": "test@example.com"', rendered)
        self.assertIn('status": "ACTIVE"', rendered)
        self.assertIn('timestamp": "2024-01-01T00:00:00Z"', rendered)
    
    def test_render_template_with_invalid_jinja_syntax(self):
        """Test template rendering with invalid Jinja syntax."""
        template = WebhookTemplate.objects.create(
            name='Invalid Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, {% invalid syntax %}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        # Should handle gracefully and return original template
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": {{user_id}}', rendered)
    
    def test_render_template_with_empty_template(self):
        """Test template rendering with empty template."""
        template = WebhookTemplate.objects.create(
            name='Empty Template',
            event_type='user.created',
            payload_template='',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertEqual(rendered, '')
    
    def test_render_template_with_none_template(self):
        """Test template rendering with None template."""
        template = WebhookTemplate.objects.create(
            name='None Template',
            event_type='user.created',
            payload_template=None,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertEqual(rendered, '')
    
    def test_render_template_performance_large_template(self):
        """Test template rendering performance with large template."""
        import time
        
        # Create large template
        large_template_content = '{'
        for i in range(1000):
            large_template_content += f'"field_{i}": "{{field_{i}}}"'
            if i < 999:
                large_template_content += ','
        large_template_content += '}'
        
        template = WebhookTemplate.objects.create(
            name='Large Template',
            event_type='user.created',
            payload_template=large_template_content,
            is_active=True,
            created_by=self.user,
        )
        
        # Create large event data
        event_data = {}
        for i in range(1000):
            event_data[f'field_{i}'] = f'value_{i}'
        
        start_time = time.time()
        rendered = self.template_engine.render_template(template, event_data)
        end_time = time.time()
        
        self.assertIn('field_0": "value_0"', rendered)
        self.assertIn('field_999": "value_999"', rendered)
        self.assertLess(end_time - start_time, 5.0)  # Should complete in < 5 seconds
    
    def test_render_template_performance_complex_logic(self):
        """Test template rendering performance with complex logic."""
        import time
        
        template = WebhookTemplate.objects.create(
            name='Complex Template',
            event_type='order.created',
            payload_template='''{% set total = 0 %}
{% for item in items %}
    {% set total = total + (item.price * item.quantity) %}
{% endfor %}
{
    "order_id": {{order_id}},
    "total": {{total}},
    "tax": {{total * 0.1}},
    "grand_total": {{total * 1.1}},
    "item_count": {{items | length}},
    "has_items": {% if items | length > 0 %}true{% else %}false{% endif %}
}''',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'order_id': 12345,
            'items': [
                {'price': 10.50, 'quantity': 2},
                {'price': 5.25, 'quantity': 4},
                {'price': 15.75, 'quantity': 1}
            ]
        }
        
        start_time = time.time()
        rendered = self.template_engine.render_template(template, event_data)
        end_time = time.time()
        
        self.assertIn('order_id": 12345', rendered)
        self.assertIn('total": 52.5', rendered)
        self.assertIn('tax": 5.25', rendered)
        self.assertIn('grand_total": 57.75', rendered)
        self.assertIn('item_count": 3', rendered)
        self.assertIn('has_items": true', rendered)
        self.assertLess(end_time - start_time, 1.0)  # Should complete in < 1 second
    
    def test_render_template_concurrent_safety(self):
        """Test template rendering concurrent safety."""
        import threading
        
        results = []
        
        def render_template():
            event_data = {
                'user_id': 12345,
                'user_email': 'test@example.com'
            }
            rendered = self.template_engine.render_template(self.template, event_data)
            results.append(rendered)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=render_template)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All renderings should succeed and be identical
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result == results[0] for result in results))
    
    def test_render_template_memory_efficiency(self):
        """Test template rendering memory efficiency."""
        import sys
        
        # Create large event data
        large_event_data = {
            'user_id': 12345,
            'large_data': ['x' * 1000] * 1000  # ~1MB of data
        }
        
        # Get memory usage before rendering
        initial_memory = sys.getsizeof(large_event_data)
        
        # Render template
        rendered = self.template_engine.render_template(self.template, large_event_data)
        
        # Get memory usage after rendering
        final_memory = sys.getsizeof(large_event_data) + sys.getsizeof(rendered)
        
        # Memory usage should be reasonable
        self.assertLess(final_memory, initial_memory * 2)
        self.assertIsInstance(rendered, str)
    
    def test_render_template_with_unicode_characters(self):
        """Test template rendering with unicode characters."""
        template = WebhookTemplate.objects.create(
            name='Unicode Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "message": "Hello {{user_name}}! ñáéíóú", "emoji": "{{emoji}}"}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_name': 'Test User',
            'emoji': 'Hello World! emoji test'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('message": "Hello Test User! ñáéíóú"', rendered)
        self.assertIn('emoji": "Hello World! emoji test"', rendered)
    
    def test_render_template_with_special_characters(self):
        """Test template rendering with special characters."""
        template = WebhookTemplate.objects.create(
            name='Special Characters Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "message": "Hello @#$%^&*()_+-=[]{}|;:,.<>?!"}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('message": "Hello @#$%^&*()_+-=[]{}|;:,.<>?!"', rendered)
    
    def test_render_template_with_json_escape(self):
        """Test template rendering with JSON escape characters."""
        template = WebhookTemplate.objects.create(
            name='JSON Escape Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "message": "Hello \\"World\\"! \nNew line \\t Tab"}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('message': "Hello \\"World\\"! \nNew line \\t Tab"', rendered)
    
    def test_render_template_with_custom_filter(self):
        """Test template rendering with custom filter."""
        template = WebhookTemplate.objects.create(
            name='Custom Filter Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email_domain": {{user_email | custom_domain_filter}}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com'
        }
        
        # Mock custom filter
        with patch('api.webhooks.services.core.TemplateEngine._get_jinja_environment') as mock_env:
            mock_env_instance = Mock()
            mock_env_instance.filters = {'custom_domain_filter': lambda x: x.split('@')[1] if '@' in x else x}
            mock_env_instance.from_string.return_value.render.return_value = '{"user_id": 12345, "email_domain": "example.com"}'
            mock_env.return_value = mock_env_instance
            
            rendered = self.template_engine.render_template(template, event_data)
            
            self.assertIn('email_domain": "example.com"', rendered)
    
    def test_render_template_with_macro(self):
        """Test template rendering with macro."""
        template = WebhookTemplate.objects.create(
            name='Macro Template',
            event_type='user.created',
            payload_template='''{% macro user_info(user) %}
{"id": {{user.id}}, "email": {{user.email}}}
{% endmacro %}
{
    "user_id": {{user_id}},
    "user_info": {{ user_info({"id": user_id, "email": user_email}) }}
}''',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com'
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('user_id": 12345', rendered)
        self.assertIn('user_info": {"id": 12345, "email": "test@example.com"}', rendered)
    
    def test_render_template_with_include(self):
        """Test template rendering with include."""
        template = WebhookTemplate.objects.create(
            name='Include Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "footer": {% include "footer_template" %}}',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        # Mock include template
        with patch('api.webhooks.services.core.TemplateEngine._get_jinja_environment') as mock_env:
            mock_env_instance = Mock()
            mock_env_instance.get_template.return_value.render.return_value = 'Footer content'
            mock_env_instance.from_string.return_value.render.return_value = '{"user_id": 12345, "footer": Footer content}'
            mock_env.return_value = mock_env_instance
            
            rendered = self.template_engine.render_template(template, event_data)
            
            self.assertIn('user_id": 12345', rendered)
            self.assertIn('footer": Footer content', rendered)
    
    def test_render_template_with_extends(self):
        """Test template rendering with extends."""
        template = WebhookTemplate.objects.create(
            name='Extends Template',
            event_type='user.created',
            payload_template='''{% extends "base_template" %}
{% block content %}
{"user_id": {{user_id}}}
{% endblock %}''',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_id': 12345}
        
        # Mock base template
        with patch('api.webhooks.services.core.TemplateEngine._get_jinja_environment') as mock_env:
            mock_env_instance = Mock()
            mock_env_instance.get_template.return_value.render.return_value = '{"user_id": 12345}'
            mock_env_instance.from_string.return_value.render.return_value = '{"user_id": 12345}'
            mock_env.return_value = mock_env_instance
            
            rendered = self.template_engine.render_template(template, event_data)
            
            self.assertIn('user_id": 12345', rendered)
