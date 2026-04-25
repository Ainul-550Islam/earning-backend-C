"""Payload Transformer Service

This module provides payload transformation using Jinja2 templates.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from django.template import Template, Context
from django.utils import timezone

logger = logging.getLogger(__name__)


class PayloadTransformer:
    """Service for transforming webhook payloads using Jinja2 templates."""
    
    def __init__(self):
        """Initialize the payload transformer service."""
        self.logger = logger
    
    def transform_payload(self, template_str: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform payload using Jinja2 template.
        
        Args:
            template_str: Jinja2 template string
            data: Data to use in template
            
        Returns:
            Transformed payload dictionary
        """
        try:
            # Create Jinja2 template
            template = Template(template_str)
            
            # Create context with additional helper functions
            context = Context({
                'data': data,
                'now': timezone.now(),
                'json': json,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'len': len,
                'upper': str.upper,
                'lower': str.lower,
                'title': str.title,
                'capitalize': str.capitalize,
                'format_currency': self._format_currency,
                'format_date': self._format_date,
                'format_datetime': self._format_datetime,
                'get_nested': self._get_nested,
                'default': self._default,
                'coalesce': self._coalesce,
            })
            
            # Render template
            rendered = template.render(context)
            
            # Parse rendered result as JSON
            try:
                transformed_data = json.loads(rendered)
                if not isinstance(transformed_data, dict):
                    raise ValueError("Template must render to a JSON object")
                return transformed_data
            except json.JSONDecodeError as e:
                # If not valid JSON, try to wrap in object
                try:
                    return {'value': rendered}
                except Exception as wrapper_error:
                    raise ValueError(f"Template rendered invalid JSON: {e}")
            
        except Exception as e:
            logger.error(f"Error transforming payload: {str(e)}")
            raise ValueError(f"Payload transformation failed: {str(e)}")
    
    def validate_template(self, template_str: str) -> Dict[str, Any]:
        """
        Validate a Jinja2 template.
        
        Args:
            template_str: Template string to validate
            
        Returns:
            Validation result dictionary
        """
        try:
            # Try to create template
            template = Template(template_str)
            
            # Test rendering with sample data
            sample_data = {
                'test': True,
                'timestamp': timezone.now().isoformat(),
                'user': {
                    'id': 123,
                    'email': 'test@example.com',
                    'name': 'Test User'
                },
                'amount': 100.50,
                'status': 'active'
            }
            
            context = Context({
                'data': sample_data,
                'now': timezone.now(),
                'json': json,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'len': len,
                'upper': str.upper,
                'lower': str.lower,
                'title': str.title,
                'capitalize': str.capitalize,
                'format_currency': self._format_currency,
                'format_date': self._format_date,
                'format_datetime': self._format_datetime,
                'get_nested': self._get_nested,
                'default': self._default,
                'coalesce': self._coalesce,
            })
            
            rendered = template.render(context)
            
            # Try to parse as JSON
            try:
                json.loads(rendered)
                return {
                    'valid': True,
                    'template': template_str,
                    'sample_render': rendered,
                    'message': 'Template is valid'
                }
            except json.JSONDecodeError:
                return {
                    'valid': False,
                    'template': template_str,
                    'sample_render': rendered,
                    'message': 'Template does not render to valid JSON'
                }
            
        except Exception as e:
            return {
                'valid': False,
                'template': template_str,
                'message': f'Template validation failed: {str(e)}'
            }
    
    def get_template_variables(self, template_str: str) -> List[str]:
        """
        Extract variable names from template.
        
        Args:
            template_str: Template string
            
        Returns:
            List of variable names used in template
        """
        try:
            import re
            
            # Find all variable references
            pattern = r'\{\{\s*([^}]+)\s*\}\}'
            matches = re.findall(pattern, template_str)
            
            variables = set()
            for match in matches:
                # Split by pipes and dots to get variable names
                parts = match.split('|')[0].strip().split('.')
                if parts:
                    variables.add(parts[0])
            
            return sorted(list(variables))
            
        except Exception as e:
            logger.error(f"Error extracting template variables: {str(e)}")
            return []
    
    def preview_template(self, template_str: str, sample_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preview template transformation with sample data.
        
        Args:
            template_str: Template string
            sample_data: Sample data for preview
            
        Returns:
            Preview result dictionary
        """
        try:
            # Validate template first
            validation = self.validate_template(template_str)
            if not validation['valid']:
                return validation
            
            # Transform with sample data
            transformed = self.transform_payload(template_str, sample_data)
            
            return {
                'valid': True,
                'template': template_str,
                'sample_data': sample_data,
                'transformed': transformed,
                'message': 'Template preview successful'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'template': template_str,
                'sample_data': sample_data,
                'message': f'Template preview failed: {str(e)}'
            }
    
    def _format_currency(self, amount: float, currency: str = 'USD') -> str:
        """Format amount as currency."""
        try:
            if currency == 'USD':
                return f"${amount:.2f}"
            elif currency == 'EUR':
                return f"EUR {amount:.2f}"
            elif currency == 'GBP':
                return f"£{amount:.2f}"
            else:
                return f"{amount:.2f} {currency}"
        except Exception:
            return f"{amount:.2f}"
    
    def _format_date(self, date_obj, format_str: str = '%Y-%m-%d') -> str:
        """Format date object."""
        try:
            if hasattr(date_obj, 'strftime'):
                return date_obj.strftime(format_str)
            return str(date_obj)
        except Exception:
            return str(date_obj)
    
    def _format_datetime(self, datetime_obj, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
        """Format datetime object."""
        try:
            if hasattr(datetime_obj, 'strftime'):
                return datetime_obj.strftime(format_str)
            return str(datetime_obj)
        except Exception:
            return str(datetime_obj)
    
    def _get_nested(self, data: Dict[str, Any], path: str, default_value: Any = None) -> Any:
        """Get nested value from dictionary."""
        try:
            keys = path.split('.')
            current = data
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif isinstance(current, list) and key.isdigit():
                    index = int(key)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return default_value
                else:
                    return default_value
            
            return current
        except Exception:
            return default_value
    
    def _default(self, value: Any, default_value: Any) -> Any:
        """Return default value if value is None or empty."""
        if value is None or value == '':
            return default_value
        return value
    
    def _coalesce(self, *args) -> Any:
        """Return first non-None value."""
        for arg in args:
            if arg is not None and arg != '':
                return arg
        return None
    
    def get_common_templates(self) -> Dict[str, str]:
        """
        Get common template patterns.
        
        Returns:
            Dictionary of common templates
        """
        return {
            'basic': {
                'user': '{{ data.user.id }}',
                'email': '{{ data.user.email }}',
                'amount': '{{ data.amount }}',
                'status': '{{ data.status }}',
                'timestamp': '{{ now|date:"Y-m-d H:M:S" }}'
            },
            'user_created': {
                'user_id': '{{ data.user.id }}',
                'username': '{{ data.user.username }}',
                'email': '{{ data.user.email }}',
                'created_at': '{{ data.user.created_at }}',
                'event_type': 'user.created'
            },
            'payment_success': {
                'payment_id': '{{ data.payment.id }}',
                'amount': '{{ data.amount | format_currency }}',
                'currency': '{{ data.currency }}',
                'status': 'completed',
                'timestamp': '{{ now|date:"Y-m-d H:M:S" }}',
                'event_type': 'payment.success'
            },
            'order_completed': {
                'order_id': '{{ data.order.id }}',
                'customer': '{{ data.order.customer.name }}',
                'total': '{{ data.order.total | format_currency }}',
                'items': '{{ data.order.items|length }}',
                'completed_at': '{{ data.order.completed_at }}',
                'event_type': 'order.completed'
            }
        }
    
    def create_template_from_example(self, example_data: Dict[str, Any]) -> str:
        """
        Create a basic template from example data.
        
        Args:
            example_data: Example data structure
            
        Returns:
            Basic template string
        """
        try:
            template_fields = {}
            
            def extract_fields(data, prefix=''):
                if isinstance(data, dict):
                    for key, value in data.items():
                        field_name = f"{prefix}.{key}" if prefix else key
                        if isinstance(value, (str, int, float, bool)):
                            template_fields[field_name] = f"{{{{ data.{field_name} }}}}"
                        elif isinstance(value, dict):
                            extract_fields(value, field_name)
                        elif isinstance(value, list):
                            template_fields[field_name] = f"{{{{ data.{field_name} }}}}"
            
            extract_fields(example_data)
            
            # Create JSON template
            template = '{\n'
            for field, template_var in template_fields.items():
                template += f'  "{field}": {template_var},\n'
            template = template.rstrip(',\n') + '\n}'
            
            return template
            
        except Exception as e:
            logger.error(f"Error creating template from example: {str(e)}")
            return '{"data": {{ data }}}'
    
    def get_template_suggestions(self, event_type: str) -> List[str]:
        """
        Get template suggestions for specific event types.
        
        Args:
            event_type: Event type to get suggestions for
            
        Returns:
            List of template suggestions
        """
        suggestions = []
        
        if event_type == 'user.created':
            suggestions.extend([
                '{"user_id": {{ data.user.id }}, "email": {{ data.user.email }}}',
                '{"event": "user.created", "user": {{ data.user }}}',
                '{"user": {{ data.user }}, "timestamp": {{ now|date:"Y-m-d H:M:S" }}}'
            ])
        elif event_type == 'payment.success':
            suggestions.extend([
                '{"payment_id": {{ data.payment.id }}, "amount": {{ data.amount | format_currency }}}',
                '{"event": "payment.success", "payment": {{ data.payment }}}',
                '{"payment": {{ data.payment }}, "timestamp": {{ now|date:"Y-m-d H:M:S" }}}'
            ])
        elif event_type == 'order.completed':
            suggestions.extend([
                '{"order_id": {{ data.order.id }}, "total": {{ data.order.total | format_currency }}}',
                '{"event": "order.completed", "order": {{ data.order }}}',
                '{"order": {{ data.order }}, "timestamp": {{ now|date:"Y-m-d H:M:S" }}}'
            ])
        else:
            suggestions.extend([
                '{"event": "' + event_type + '", "data": {{ data }}}',
                '{"event_type": "' + event_type + '", "payload": {{ data }}}',
                '{"data": {{ data }}, "timestamp": {{ now|date:"Y-m-d H:M:S" }}}'
            ])
        
        return suggestions
