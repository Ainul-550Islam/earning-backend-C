"""
Webhook Filter Service

This service evaluates webhook filter rules before dispatching events.
Implements complex filtering logic with multiple operators and conditions.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from ...models import WebhookFilter
from ...constants import FilterOperator

logger = logging.getLogger(__name__)


class FilterService:
    """
    Service for evaluating webhook filter rules.
    Supports complex filtering with multiple operators and conditions.
    """
    
    def __init__(self):
        """Initialize filter service."""
        self.logger = logger
    
    def evaluate_filter(self, webhook_filter: WebhookFilter, event_data: Dict[str, Any]) -> bool:
        """
        Evaluate a single filter against event data.
        
        Args:
            webhook_filter: WebhookFilter instance
            event_data: Event data to filter
            
        Returns:
            bool: True if event matches filter criteria
        """
        try:
            field_path = webhook_filter.field_path
            operator = webhook_filter.operator
            filter_value = webhook_filter.value
            
            # Get the actual value from event data
            actual_value = self._get_nested_value(event_data, field_path)
            
            # Compare based on operator
            result = self._compare_values(actual_value, operator, filter_value)
            
            self.logger.debug(
                f"Filter evaluation: {field_path} {operator} {filter_value} -> {result}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Filter evaluation error: {e}")
            return False
    
    def evaluate_filters(self, endpoint, event_data: Dict[str, Any]) -> bool:
        """
        Evaluate all active filters for an endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            event_data: Event data to filter
            
        Returns:
            bool: True if event passes all filters
        """
        if not endpoint.filters.exists():
            return True
        
        # All filters must pass (AND logic)
        for webhook_filter in endpoint.filters.filter(is_active=True):
            if not self.evaluate_filter(webhook_filter, event_data):
                self.logger.info(
                    f"Event filtered out by {webhook_filter.field_path} {webhook_filter.operator}"
                )
                return False
        
        return True
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get nested value from dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            path: Dot-separated path (e.g., "user.email", "amount")
            
        Returns:
            Any: Value at the path or None
        """
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
    
    def _compare_values(self, actual: Any, operator: str, expected: Any) -> bool:
        """
        Compare values based on operator.
        
        Args:
            actual: Actual value from event data
            operator: Comparison operator
            expected: Expected value from filter
            
        Returns:
            bool: Comparison result
        """
        if actual is None:
            return False
        
        try:
            if operator == FilterOperator.EQUALS:
                return str(actual) == str(expected)
            
            elif operator == FilterOperator.NOT_EQUALS:
                return str(actual) != str(expected)
            
            elif operator == FilterOperator.CONTAINS:
                return str(expected).lower() in str(actual).lower()
            
            elif operator == FilterOperator.NOT_CONTAINS:
                return str(expected).lower() not in str(actual).lower()
            
            elif operator == FilterOperator.GREATER_THAN:
                return float(actual) > float(expected)
            
            elif operator == FilterOperator.LESS_THAN:
                return float(actual) < float(expected)
            
            else:
                self.logger.warning(f"Unsupported operator: {operator}")
                return False
                
        except (ValueError, TypeError) as e:
            self.logger.error(f"Value comparison error: {e}")
            return False
    
    def validate_filter_config(self, webhook_filter: WebhookFilter) -> List[str]:
        """
        Validate filter configuration.
        
        Args:
            webhook_filter: WebhookFilter instance
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        if not webhook_filter.field_path:
            errors.append("Field path is required")
        
        if webhook_filter.operator not in [choice[0] for choice in FilterOperator.CHOICES]:
            errors.append(f"Invalid operator: {webhook_filter.operator}")
        
        if not webhook_filter.value:
            errors.append("Filter value is required")
        
        return errors
    
    def get_filter_summary(self, endpoint) -> Dict[str, Any]:
        """
        Get summary of active filters for an endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            
        Returns:
            Dict: Filter summary
        """
        filters = endpoint.filters.filter(is_active=True)
        
        return {
            'total_filters': filters.count(),
            'filters': [
                {
                    'field_path': f.field_path,
                    'operator': f.operator,
                    'value': f.value,
                }
                for f in filters
            ]
        }
    
    def test_filter(self, webhook_filter: WebhookFilter, test_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test a filter against multiple events.
        
        Args:
            webhook_filter: WebhookFilter instance
            test_events: List of test events
            
        Returns:
            Dict: Test results
        """
        results = {
            'filter': {
                'field_path': webhook_filter.field_path,
                'operator': webhook_filter.operator,
                'value': webhook_filter.value,
            },
            'test_results': []
        }
        
        for i, event_data in enumerate(test_events):
            passed = self.evaluate_filter(webhook_filter, event_data)
            results['test_results'].append({
                'event_index': i,
                'passed': passed,
                'event_data': event_data
            })
        
        return results
