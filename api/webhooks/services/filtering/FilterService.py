from api.webhooks.validators import validate_filter_config
from ...exceptions import WebhookFilterError
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
    
    def evaluate_subscription_filters(self, filters: Dict[str, Any], event_data: Dict[str, Any]) -> bool:
        """
        Evaluate a WebhookSubscription.filters JSON blob against event
        data. Format: {field_path: {'operator': ..., 'value': ...}, ...}
        — every entry must match (AND semantics), same as
        evaluate_filters() below does for WebhookFilter model rows.
        Reuses the same _get_nested_value/_compare_values helpers as
        evaluate_filter() so the two filtering mechanisms (WebhookFilter
        rows vs. this inline per-subscription blob) stay consistent.

        Args:
            filters: The subscription's filters dict (empty/None = no
                     filtering, always matches)
            event_data: Event data to filter

        Returns:
            bool: True if event matches all filter criteria (or there are none)
        """
        if not filters:
            return True

        try:
            for field_path, condition in filters.items():
                operator = condition.get('operator')
                expected_value = condition.get('value')
                actual_value = self._get_nested_value(event_data, field_path)

                if not self._compare_values(actual_value, operator, expected_value):
                    return False

            return True
        except Exception as e:
            self.logger.error(f"Error evaluating subscription filters: {str(e)}")
            return False

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
            
        except WebhookFilterError as e:
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

        Tries real nested traversal first (e.g. "user.email" against
        {"user": {"email": ...}}). If that finds nothing, falls back to
        treating the whole dotted path as a single flattened key with
        underscores in place of dots (e.g. "user.email" against
        {"user_email": ...}) — event payloads in this codebase use both
        shapes, and filters are authored with dot notation regardless of
        which shape the actual payload uses.

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
                current = None
                break

        if current is not None:
            return current

        if isinstance(data, dict) and '.' in path:
            flat_key = path.replace('.', '_')
            if flat_key in data:
                return data[flat_key]

        return None
    
    def _normalize_for_comparison(self, value: Any) -> str:
        """
        JSON-style string form for EQUALS/NOT_EQUALS comparison.

        Python's str(bool) capitalizes ('True'/'False'), but
        WebhookFilter.value is a JSONField and filter authors commonly
        write boolean intent as a lowercase JSON-style string ('true').
        Non-bool values are unaffected — this only changes representation
        for actual bool instances on either side of the comparison.
        """
        if isinstance(value, bool):
            return 'true' if value else 'false'
        return str(value)

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
                return self._normalize_for_comparison(actual) == self._normalize_for_comparison(expected)
            
            elif operator == FilterOperator.NOT_EQUALS:
                return self._normalize_for_comparison(actual) != self._normalize_for_comparison(expected)
            
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
    
