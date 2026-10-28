# api/rate_limit/transformer.py
"""
Data transformer system for rate limit module.

Provides data transformation and mapping capabilities.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import json
import re

logger = logging.getLogger(__name__)


class BaseTransformer:
    """
    Base class for data transformers.
    """
    
    def __init__(self, name: str, source_format: str, target_format: str):
        self.name = name
        self.source_format = source_format
        self.target_format = target_format
        self.transformation_count = 0
        self.error_count = 0
    
    def transform(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Transform data from source format to target format.
        
        Args:
            data: Source data
            context: Transformation context
            
        Returns:
            Transformed data
        """
        raise NotImplementedError("Subclasses must implement transform()")
    
    def validate_source(self, data: Dict[str, Any]) -> bool:
        """
        Validate source data format.
        
        Args:
            data: Source data
            
        Returns:
            True if valid
        """
        return True
    
    def validate_target(self, data: Dict[str, Any]) -> bool:
        """
        Validate target data format.
        
        Args:
            data: Target data
            
        Returns:
            True if valid
        """
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get transformation statistics."""
        return {
            'name': self.name,
            'source_format': self.source_format,
            'target_format': self.target_format,
            'transformation_count': self.transformation_count,
            'error_count': self.error_count,
            'success_rate': (
                self.transformation_count / max(self.transformation_count + self.error_count, 1)
            ) * 100
        }


class FieldMappingTransformer(BaseTransformer):
    """
    Transformer that maps fields between formats.
    """
    
    def __init__(self, name: str, source_format: str, target_format: str,
                 field_mappings: Dict[str, str], default_values: Dict[str, Any] = None):
        super().__init__(name, source_format, target_format)
        self.field_mappings = field_mappings
        self.default_values = default_values or {}
    
    def transform(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transform data using field mappings."""
        try:
            if not self.validate_source(data):
                raise ValueError("Invalid source data format")
            
            transformed_data = {}
            
            # Apply field mappings
            for source_field, target_field in self.field_mappings.items():
                if source_field in data:
                    transformed_data[target_field] = data[source_field]
                elif target_field in self.default_values:
                    transformed_data[target_field] = self.default_values[target_field]
            
            # Add unmapped fields if needed
            if context and context.get('include_unmapped', False):
                for field, value in data.items():
                    if field not in self.field_mappings and field not in transformed_data:
                        transformed_data[field] = value
            
            if not self.validate_target(transformed_data):
                raise ValueError("Invalid target data format")
            
            self.transformation_count += 1
            return transformed_data
            
        except Exception as e:
            self.error_count += 1
            logger.error("Field mapping transformation failed: %s", str(e), exc_info=True)
            raise
    
    def add_mapping(self, source_field: str, target_field: str):
        """Add a field mapping."""
        self.field_mappings[source_field] = target_field
    
    def remove_mapping(self, source_field: str):
        """Remove a field mapping."""
        if source_field in self.field_mappings:
            del self.field_mappings[source_field]


class DataTypeTransformer(BaseTransformer):
    """
    Transformer that converts data types.
    """
    
    def __init__(self, name: str, source_format: str, target_format: str,
                 type_conversions: Dict[str, str]):
        super().__init__(name, source_format, target_format)
        self.type_conversions = type_conversions
    
    def transform(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transform data types."""
        try:
            if not self.validate_source(data):
                raise ValueError("Invalid source data format")
            
            transformed_data = data.copy()
            
            # Apply type conversions
            for field, target_type in self.type_conversions.items():
                if field in transformed_data:
                    transformed_data[field] = self._convert_type(
                        transformed_data[field], target_type
                    )
            
            if not self.validate_target(transformed_data):
                raise ValueError("Invalid target data format")
            
            self.transformation_count += 1
            return transformed_data
            
        except Exception as e:
            self.error_count += 1
            logger.error("Data type transformation failed: %s", str(e), exc_info=True)
            raise
    
    def _convert_type(self, value: Any, target_type: str) -> Any:
        """Convert value to target type."""
        try:
            if target_type == 'string':
                return str(value)
            elif target_type == 'integer':
                return int(value)
            elif target_type == 'float':
                return float(value)
            elif target_type == 'boolean':
                return bool(value)
            elif target_type == 'datetime':
                if isinstance(value, str):
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                elif isinstance(value, (int, float)):
                    return datetime.fromtimestamp(value)
                return value
            elif target_type == 'json':
                if isinstance(value, str):
                    return json.loads(value)
                return value
            elif target_type == 'list':
                if isinstance(value, str):
                    return value.split(',')
                return list(value) if hasattr(value, '__iter__') else [value]
            else:
                return value
                
        except Exception as e:
            logger.warning(f"Type conversion failed for value {value} to {target_type}: {str(e)}")
            return value


class ValidationTransformer(BaseTransformer):
    """
    Transformer that validates and cleans data.
    """
    
    def __init__(self, name: str, source_format: str, target_format: str,
                 validation_rules: Dict[str, Dict[str, Any]]):
        super().__init__(name, source_format, target_format)
        self.validation_rules = validation_rules
    
    def transform(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate and clean data."""
        try:
            if not self.validate_source(data):
                raise ValueError("Invalid source data format")
            
            transformed_data = data.copy()
            
            # Apply validation rules
            for field, rules in self.validation_rules.items():
                if field in transformed_data:
                    value = transformed_data[field]
                    
                    # Apply validation
                    if not self._validate_field(value, rules):
                        # Apply default value or remove field
                        if 'default' in rules:
                            transformed_data[field] = rules['default']
                        elif rules.get('required', False):
                            raise ValueError(f"Required field {field} is invalid")
                        else:
                            del transformed_data[field]
            
            if not self.validate_target(transformed_data):
                raise ValueError("Invalid target data format")
            
            self.transformation_count += 1
            return transformed_data
            
        except Exception as e:
            self.error_count += 1
            logger.error("Validation transformation failed: %s", str(e), exc_info=True)
            raise
    
    def _validate_field(self, value: Any, rules: Dict[str, Any]) -> bool:
        """Validate a field value."""
        try:
            # Type validation
            if 'type' in rules:
                expected_type = rules['type']
                if expected_type == 'string' and not isinstance(value, str):
                    return False
                elif expected_type == 'integer' and not isinstance(value, int):
                    return False
                elif expected_type == 'float' and not isinstance(value, (int, float)):
                    return False
                elif expected_type == 'boolean' and not isinstance(value, bool):
                    return False
                elif expected_type == 'datetime' and not isinstance(value, (datetime, str)):
                    return False
            
            # Length validation
            if 'min_length' in rules and len(str(value)) < rules['min_length']:
                return False
            
            if 'max_length' in rules and len(str(value)) > rules['max_length']:
                return False
            
            # Range validation
            if 'min_value' in rules and value < rules['min_value']:
                return False
            
            if 'max_value' in rules and value > rules['max_value']:
                return False
            
            # Pattern validation
            if 'pattern' in rules:
                pattern = re.compile(rules['pattern'])
                if not pattern.match(str(value)):
                    return False
            
            # Enum validation
            if 'choices' in rules and value not in rules['choices']:
                return False
            
            return True
            
        except Exception:
            return False


class AggregationTransformer(BaseTransformer):
    """
    Transformer that aggregates data fields.
    """
    
    def __init__(self, name: str, source_format: str, target_format: str,
                 aggregations: Dict[str, Dict[str, Any]]):
        super().__init__(name, source_format, target_format)
        self.aggregations = aggregations
    
    def transform(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Aggregate data fields."""
        try:
            if not self.validate_source(data):
                raise ValueError("Invalid source data format")
            
            transformed_data = data.copy()
            
            # Apply aggregations
            for target_field, aggregation_config in self.aggregations.items():
                source_fields = aggregation_config['fields']
                operation = aggregation_config['operation']
                
                values = []
                for field in source_fields:
                    if field in data:
                        values.append(data[field])
                
                if values:
                    aggregated_value = self._aggregate_values(values, operation)
                    transformed_data[target_field] = aggregated_value
            
            if not self.validate_target(transformed_data):
                raise ValueError("Invalid target data format")
            
            self.transformation_count += 1
            return transformed_data
            
        except Exception as e:
            self.error_count += 1
            logger.error("Aggregation transformation failed: %s", str(e), exc_info=True)
            raise
    
    def _aggregate_values(self, values: List[Any], operation: str) -> Any:
        """Aggregate values using specified operation."""
        try:
            if operation == 'sum':
                return sum(values)
            elif operation == 'avg':
                return sum(values) / len(values)
            elif operation == 'min':
                return min(values)
            elif operation == 'max':
                return max(values)
            elif operation == 'count':
                return len(values)
            elif operation == 'concat':
                return ' '.join(str(v) for v in values)
            elif operation == 'first':
                return values[0]
            elif operation == 'last':
                return values[-1]
            else:
                return values
                
        except Exception as e:
            logger.warning(f"Aggregation failed for operation {operation}: {str(e)}")
            return values


class NormalizationTransformer(BaseTransformer):
    """
    Transformer that normalizes data.
    """
    
    def __init__(self, name: str, source_format: str, target_format: str,
                 normalization_rules: Dict[str, Dict[str, Any]]):
        super().__init__(name, source_format, target_format)
        self.normalization_rules = normalization_rules
    
    def transform(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Normalize data."""
        try:
            if not self.validate_source(data):
                raise ValueError("Invalid source data format")
            
            transformed_data = data.copy()
            
            # Apply normalization rules
            for field, rules in self.normalization_rules.items():
                if field in transformed_data:
                    value = transformed_data[field]
                    normalized_value = self._normalize_value(value, rules)
                    transformed_data[field] = normalized_value
            
            if not self.validate_target(transformed_data):
                raise ValueError("Invalid target data format")
            
            self.transformation_count += 1
            return transformed_data
            
        except Exception as e:
            self.error_count += 1
            logger.error("Normalization transformation failed: %s", str(e), exc_info=True)
            raise
    
    def _normalize_value(self, value: Any, rules: Dict[str, Any]) -> Any:
        """Normalize a value."""
        try:
            # String normalization
            if isinstance(value, str):
                if rules.get('lowercase', False):
                    value = value.lower()
                
                if rules.get('uppercase', False):
                    value = value.upper()
                
                if rules.get('trim', False):
                    value = value.strip()
                
                if rules.get('remove_special_chars', False):
                    value = re.sub(r'[^a-zA-Z0-9\s]', '', value)
                
                if rules.get('replace_spaces', False):
                    value = value.replace(' ', rules['replace_spaces'])
            
            # Numeric normalization
            elif isinstance(value, (int, float)):
                if 'round_to' in rules:
                    value = round(value, rules['round_to'])
                
                if 'min_value' in rules and value < rules['min_value']:
                    value = rules['min_value']
                
                if 'max_value' in rules and value > rules['max_value']:
                    value = rules['max_value']
            
            # Date normalization
            elif isinstance(value, datetime):
                if 'timezone' in rules:
                    # Convert to specified timezone
                    pass  # Implementation would depend on timezone handling
                
                if 'format' in rules:
                    value = value.strftime(rules['format'])
            
            return value
            
        except Exception as e:
            logger.warning(f"Normalization failed: {str(e)}")
            return value


class CompositeTransformer(BaseTransformer):
    """
    Transformer that combines multiple transformers.
    """
    
    def __init__(self, name: str, source_format: str, target_format: str,
                 transformers: List[BaseTransformer]):
        super().__init__(name, source_format, target_format)
        self.transformers = transformers
    
    def transform(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Apply multiple transformations."""
        try:
            if not self.validate_source(data):
                raise ValueError("Invalid source data format")
            
            transformed_data = data.copy()
            
            # Apply transformers in sequence
            for transformer in self.transformers:
                transformed_data = transformer.transform(transformed_data, context)
            
            if not self.validate_target(transformed_data):
                raise ValueError("Invalid target data format")
            
            self.transformation_count += 1
            return transformed_data
            
        except Exception as e:
            self.error_count += 1
            logger.error("Composite transformation failed: %s", str(e), exc_info=True)
            raise
    
    def add_transformer(self, transformer: BaseTransformer):
        """Add a transformer to the composite."""
        self.transformers.append(transformer)
    
    def remove_transformer(self, transformer_name: str):
        """Remove a transformer from the composite."""
        self.transformers = [
            t for t in self.transformers
            if t.name != transformer_name
        ]


class TransformerRegistry:
    """
    Registry for managing transformers.
    """
    
    def __init__(self):
        self.transformers: Dict[str, BaseTransformer] = {}
        self.transformation_chains: Dict[str, List[str]] = {}
    
    def register_transformer(self, transformer: BaseTransformer):
        """
        Register a transformer.
        
        Args:
            transformer: Transformer instance
        """
        self.transformers[transformer.name] = transformer
        logger.info(f"Registered transformer: {transformer.name}")
    
    def unregister_transformer(self, name: str):
        """
        Unregister a transformer.
        
        Args:
            name: Transformer name
        """
        if name in self.transformers:
            del self.transformers[name]
            logger.info(f"Unregistered transformer: {name}")
    
    def get_transformer(self, name: str) -> Optional[BaseTransformer]:
        """
        Get a transformer by name.
        
        Args:
            name: Transformer name
            
        Returns:
            Transformer instance or None
        """
        return self.transformers.get(name)
    
    def create_transformation_chain(self, chain_name: str, transformer_names: List[str]):
        """
        Create a transformation chain.
        
        Args:
            chain_name: Chain name
            transformer_names: List of transformer names
        """
        # Validate all transformers exist
        for name in transformer_names:
            if name not in self.transformers:
                raise ValueError(f"Transformer not found: {name}")
        
        self.transformation_chains[chain_name] = transformer_names
        logger.info(f"Created transformation chain: {chain_name}")
    
    def execute_chain(self, chain_name: str, data: Dict[str, Any], 
                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a transformation chain.
        
        Args:
            chain_name: Chain name
            data: Input data
            context: Transformation context
            
        Returns:
            Transformed data
        """
        if chain_name not in self.transformation_chains:
            raise ValueError(f"Transformation chain not found: {chain_name}")
        
        transformer_names = self.transformation_chains[chain_name]
        transformed_data = data
        
        for transformer_name in transformer_names:
            transformer = self.transformers[transformer_name]
            transformed_data = transformer.transform(transformed_data, context)
        
        return transformed_data
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get transformer statistics."""
        stats = {}
        
        for name, transformer in self.transformers.items():
            stats[name] = transformer.get_statistics()
        
        return stats
    
    def list_transformers(self) -> List[Dict[str, Any]]:
        """List all transformers."""
        return [
            {
                'name': transformer.name,
                'source_format': transformer.source_format,
                'target_format': transformer.target_format,
                'transformation_count': transformer.transformation_count,
                'error_count': transformer.error_count
            }
            for transformer in self.transformers.values()
        ]


# Create default transformers for rate limit integration
def create_default_transformers() -> Dict[str, BaseTransformer]:
    """Create default transformers for rate limit integration."""
    transformers = {}
    
    # Rate limit to analytics transformer
    rate_limit_to_analytics = FieldMappingTransformer(
        name='rate_limit_to_analytics',
        source_format='rate_limit',
        target_format='analytics',
        field_mappings={
            'user_id': 'user_id',
            'ip_address': 'client_ip',
            'endpoint': 'api_endpoint',
            'status': 'request_status',
            'suspicion_score': 'risk_score',
            'timestamp': 'event_timestamp'
        },
        default_values={
            'risk_score': 0,
            'request_status': 'unknown'
        }
    )
    
    # Rate limit to security transformer
    rate_limit_to_security = CompositeTransformer(
        name='rate_limit_to_security',
        source_format='rate_limit',
        target_format='security',
        transformers=[
            FieldMappingTransformer(
                name='security_field_mapping',
                source_format='rate_limit',
                target_format='security',
                field_mappings={
                    'user_id': 'subject_id',
                    'ip_address': 'source_ip',
                    'endpoint': 'target_resource',
                    'event_type': 'alert_type',
                    'suspicion_score': 'threat_level'
                }
            ),
            DataTypeTransformer(
                name='security_type_conversion',
                source_format='rate_limit',
                target_format='security',
                type_conversions={
                    'threat_level': 'integer',
                    'event_timestamp': 'datetime'
                }
            )
        ]
    )
    
    # Rate limit to notification transformer
    rate_limit_to_notification = CompositeTransformer(
        name='rate_limit_to_notification',
        source_format='rate_limit',
        target_format='notification',
        transformers=[
            FieldMappingTransformer(
                name='notification_field_mapping',
                source_format='rate_limit',
                target_format='notification',
                field_mappings={
                    'event_type': 'notification_type',
                    'ip_address': 'client_address',
                    'endpoint': 'affected_endpoint',
                    'suspicion_score': 'severity_score'
                }
            ),
            ValidationTransformer(
                name='notification_validation',
                source_format='rate_limit',
                target_format='notification',
                validation_rules={
                    'notification_type': {
                        'type': 'string',
                        'required': True,
                        'choices': ['rate_limit_exceeded', 'abuse_detected', 'security_alert']
                    },
                    'severity_score': {
                        'type': 'integer',
                        'min_value': 0,
                        'max_value': 100
                    }
                }
            )
        ]
    )
    
    transformers['rate_limit_to_analytics'] = rate_limit_to_analytics
    transformers['rate_limit_to_security'] = rate_limit_to_security
    transformers['rate_limit_to_notification'] = rate_limit_to_notification
    
    return transformers


# Global transformer registry instance
transformer_registry = TransformerRegistry()

# Register default transformers
default_transformers = create_default_transformers()
for transformer in default_transformers.values():
    transformer_registry.register_transformer(transformer)

# Create default transformation chains
transformer_registry.create_transformation_chain(
    'rate_limit_to_all',
    ['rate_limit_to_analytics', 'rate_limit_to_security', 'rate_limit_to_notification']
)


# Export classes and functions
__all__ = [
    'BaseTransformer',
    'FieldMappingTransformer',
    'DataTypeTransformer',
    'ValidationTransformer',
    'AggregationTransformer',
    'NormalizationTransformer',
    'CompositeTransformer',
    'TransformerRegistry',
    'transformer_registry',
    'create_default_transformers'
]
