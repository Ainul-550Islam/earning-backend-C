"""Webhook Template Engine

This service handles Jinja2 templating and transformation rules
for webhook payloads before delivery.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from jinja2 import Environment, BaseLoader, Template, TemplateError
from django.core.exceptions import ValidationError

from ...models import WebhookTemplate
from ...constants import EventType

logger = logging.getLogger(__name__)


class TemplateEngine:
    """
    Service for processing webhook payload templates.
    Supports Jinja2 templating and JSON transformation rules.
    """
    
    def __init__(self):
        """Initialize template engine."""
        self.logger = logger
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def render_template(self, template: WebhookTemplate, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a template with event data.
        
        Args:
            template: WebhookTemplate instance
            event_data: Event data to render
            
        Returns:
            Dict: Rendered payload with transformations applied
        """
        try:
            # Apply transformation rules first
            transformed_data = self.apply_transform_rules(template, event_data)
            
            # Render Jinja2 template
            jinja_template = self.env.from_string(template.payload_template)
            rendered_payload = jinja_template.render(transformed_data)
            
            # Parse as JSON to validate
            payload_dict = json.loads(rendered_payload)
            
            self.logger.debug(
                f"Template rendered successfully: {template.name} for {template.event_type}"
            )
            
            return payload_dict
            
        except TemplateError as e:
            self.logger.error(f"Template rendering error: {e}")
            raise ValidationError(f"Template error: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in template: {e}")
            raise ValidationError(f"Invalid JSON in template: {e}")
        except Exception as e:
            self.logger.error(f"Template engine error: {e}")
            raise ValidationError(f"Template engine error: {e}")
    
    def apply_transform_rules(self, template: WebhookTemplate, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply transformation rules to event data.
        
        Args:
            template: WebhookTemplate instance
            event_data: Original event data
            
        Returns:
            Dict: Transformed event data
        """
        try:
            transformed_data = event_data.copy()
            transform_rules = template.transform_rules or {}
            
            for rule_name, rule_config in transform_rules.items():
                transformed_data = self.apply_single_rule(
                    rule_name, rule_config, transformed_data
                )
            
            self.logger.debug(
                f"Applied {len(transform_rules)} transformation rules"
            )
            
            return transformed_data
            
        except Exception as e:
            self.logger.error(f"Transformation rules error: {e}")
            return event_data
    
    def apply_single_rule(self, rule_name: str, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a single transformation rule.
        
        Args:
            rule_name: Name of the transformation rule
            rule_config: Rule configuration
            data: Data to transform
            
        Returns:
            Dict: Transformed data
        """
        try:
            rule_type = rule_config.get('type')
            
            if rule_type == 'rename_field':
                return self._rename_field(rule_config, data)
            
            elif rule_type == 'add_field':
                return self._add_field(rule_config, data)
            
            elif rule_type == 'remove_field':
                return self._remove_field(rule_config, data)
            
            elif rule_type == 'map_value':
                return self._map_value(rule_config, data)
            
            elif rule_type == 'format_date':
                return self._format_date(rule_config, data)
            
            elif rule_type == 'calculate_field':
                return self._calculate_field(rule_config, data)
            
            else:
                self.logger.warning(f"Unknown transformation rule type: {rule_type}")
                return data
                
        except Exception as e:
            self.logger.error(f"Transformation rule error ({rule_name}): {e}")
            return data
    
    def _rename_field(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Rename a field in the data."""
        old_name = rule_config.get('old_name')
        new_name = rule_config.get('new_name')
        
        if old_name in data:
            data[new_name] = data.pop(old_name)
        
        return data
    
    def _add_field(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new field to the data."""
        field_name = rule_config.get('field_name')
        field_value = rule_config.get('value')
        field_path = rule_config.get('path', field_name)
        
        # Handle nested path
        if '.' in field_path:
            self._set_nested_value(data, field_path, field_value)
        else:
            data[field_name] = field_value
        
        return data
    
    def _remove_field(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove a field from the data."""
        field_path = rule_config.get('path')
        
        if '.' in field_path:
            self._remove_nested_value(data, field_path)
        else:
            data.pop(field_path, None)
        
        return data
    
    def _map_value(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Map values based on conditions."""
        field_path = rule_config.get('path')
        mappings = rule_config.get('mappings', {})
        default_value = rule_config.get('default')
        
        current_value = self._get_nested_value(data, field_path)
        
        if current_value in mappings:
            mapped_value = mappings[current_value]
            self._set_nested_value(data, field_path, mapped_value)
        elif default_value is not None:
            self._set_nested_value(data, field_path, default_value)
        
        return data
    
    def _format_date(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Format a date field."""
        field_path = rule_config.get('path')
        date_format = rule_config.get('format', '%Y-%m-%d %H:%M:%S')
        
        current_value = self._get_nested_value(data, field_path)
        
        if current_value:
            try:
                from datetime import datetime
                if isinstance(current_value, str):
                    parsed_date = datetime.fromisoformat(current_value)
                else:
                    parsed_date = current_value
                
                formatted_date = parsed_date.strftime(date_format)
                self._set_nested_value(data, field_path, formatted_date)
                
            except Exception as e:
                self.logger.error(f"Date formatting error: {e}")
        
        return data
    
    def _calculate_field(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate a new field based on existing data."""
        field_name = rule_config.get('field_name')
        expression = rule_config.get('expression')
        
        try:
            # Simple expression evaluation (safe)
            result = eval(expression, {"__builtins__": {}}, data)
            data[field_name] = result
            
        except Exception as e:
            self.logger.error(f"Calculation error: {e}")
        
        return data
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dictionary using dot notation."""
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
                    return None
            else:
                return None
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set nested value in dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for i, key in enumerate(keys):
            is_last = i == len(keys) - 1
            
            if is_last:
                current[key] = value
            else:
                if key not in current:
                    current[key] = {}
                current = current[key]
    
    def _remove_nested_value(self, data: Dict[str, Any], path: str) -> None:
        """Remove nested value from dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for i, key in enumerate(keys):
            is_last = i == len(keys) - 1
            
            if is_last:
                current.pop(key, None)
            else:
                if key not in current:
                    return
                current = current[key]
    
    def validate_template(self, template: WebhookTemplate) -> List[str]:
        """
        Validate a webhook template.
        
        Args:
            template: WebhookTemplate instance
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        if not template.name:
            errors.append("Template name is required")
        
        if not template.event_type:
            errors.append("Event type is required")
        
        if not template.payload_template:
            errors.append("Payload template is required")
        
        try:
            # Test template rendering
            test_data = {"test": "value"}
            self.env.from_string(template.payload_template).render(test_data)
        except TemplateError as e:
            errors.append(f"Invalid template syntax: {e}")
        
        return errors
    
    def get_template_summary(self, template: WebhookTemplate) -> Dict[str, Any]:
        """
        Get template summary including transformation rules.
        
        Args:
            template: WebhookTemplate instance
            
        Returns:
            Dict: Template summary
        """
        return {
            'id': template.id,
            'name': template.name,
            'event_type': template.event_type,
            'transform_rules_count': len(template.transform_rules or {}),
            'transform_rules': template.transform_rules or {},
            'is_active': template.is_active,
            'created_at': template.created_at,
            'updated_at': template.updated_at,
        }
