# integration_system/data_bridge.py
"""
Data Bridge — Data transformation/mapping between module schemas.
Converts data from one module's format to another's expected format.
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from .integ_exceptions import DataTransformationFailed, DataTypeMismatch
logger = logging.getLogger(__name__)

class FieldMapper:
    """Maps fields from source schema to target schema."""
    def __init__(self):
        self._mappings: Dict[str, Any] = {}  # target_field: source_field_or_callable

    def map(self, source_field: str, target_field: Optional[str] = None, transform: Optional[Callable] = None):
        """Map source_field → target_field with optional transform."""
        target = target_field or source_field
        self._mappings[target] = (source_field, transform)
        return self

    def apply(self, data: Dict) -> Dict:
        result = {}
        for target_field, (source_field, transform) in self._mappings.items():
            val = data.get(source_field)
            if transform and val is not None:
                try:
                    val = transform(val)
                except Exception as exc:
                    raise DataTransformationFailed(source_field, target_field, str(exc))
            result[target_field] = val
        return result


class DataBridge:
    """Central data transformation service between module schemas."""

    # Pre-registered transformation schemas
    SCHEMAS: Dict[str, Dict] = {
        'task_reward→notification': {
            'user_id': ('user_id', None),
            'title': ('reward_amount', lambda x: f'Task Reward +৳{x} 🎉'),
            'message': ('task_title', lambda x: f'Your task "{x}" was approved.'),
            'notification_type': (None, lambda _: 'task_approved'),
            'priority': (None, lambda _: 'high'),
        },
        'withdrawal→notification': {
            'user_id': ('user_id', None),
            'title': ('amount', lambda x: f'Withdrawal ৳{x} Processed 💰'),
            'message': ('status', lambda s: f'Withdrawal status: {s}'),
            'notification_type': ('status', lambda s: f'withdrawal_{s}'),
            'priority': (None, lambda _: 'high'),
        },
        'referral→notification': {
            'user_id': ('referrer_id', None),
            'title': ('bonus_amount', lambda x: f'Referral Bonus +৳{x} 🎁'),
            'message': ('friend_name', lambda n: f'{n} completed a task!'),
            'notification_type': (None, lambda _: 'referral_reward'),
            'priority': (None, lambda _: 'high'),
        },
    }

    def transform(self, data: Dict, schema_name: str) -> Dict:
        """Transform data using a named schema."""
        schema = self.SCHEMAS.get(schema_name)
        if not schema:
            raise DataTransformationFailed(schema_name, schema_name, 'Schema not found')

        result = {}
        for target_field, (source_field, transform_fn) in schema.items():
            if source_field is None:
                val = transform_fn(None) if transform_fn else None
            else:
                val = data.get(source_field)
                if transform_fn and val is not None:
                    try:
                        val = transform_fn(val)
                    except Exception as exc:
                        raise DataTransformationFailed(source_field, target_field, str(exc))
            result[target_field] = val
        return result

    def register_schema(self, name: str, schema: Dict):
        """Register a custom transformation schema."""
        self.SCHEMAS[name] = schema
        logger.debug(f'DataBridge: registered schema "{name}"')

    def create_mapper(self) -> FieldMapper:
        """Create a fluent field mapper for ad-hoc transformations."""
        return FieldMapper()

    def safe_transform(self, data: Dict, schema_name: str, fallback: Optional[Dict] = None) -> Dict:
        """Transform with fallback on error."""
        try:
            return self.transform(data, schema_name)
        except Exception as exc:
            logger.warning(f'DataBridge.safe_transform "{schema_name}": {exc}')
            return fallback or data


data_bridge = DataBridge()
