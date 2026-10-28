"""
transformer.py – Data transformation engine for postback module.

Provides comprehensive data transformation functionality including:
- Request/response transformation
- Data format conversion
- Field mapping and filtering
- Validation and sanitization
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json
import re

from django.utils import timezone
from django.core.exceptions import ValidationError

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class TransformationType(Enum):
    """Transformation type enumeration."""
    FIELD_MAPPING = "field_mapping"
    DATA_FILTERING = "data_filtering"
    VALUE_MAPPING = "value_mapping"
    DATA_VALIDATION = "data_validation"
    DATA_SANITIZATION = "data_sanitization"
    FORMAT_CONVERSION = "format_conversion"
    AGGREGATION = "aggregation"
    SPLITTING = "splitting"
    CALCULATION = "calculation"
    ENRICHMENT = "enrichment"


class ValidationRule(Enum):
    """Validation rule enumeration."""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    REGEX = "regex"
    RANGE = "range"
    LENGTH = "length"
    CUSTOM = "custom"


@dataclass
class TransformationRule:
    """Transformation rule data structure."""
    name: str
    type: TransformationType
    config: Dict[str, Any]
    enabled: bool = True
    priority: int = 50
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, data: Dict[str, Any]) -> bool:
        """Check if rule matches data."""
        for field, value in self.conditions.items():
            if field not in data or data[field] != value:
                return False
        return True


@dataclass
class ValidationConfig:
    """Validation configuration."""
    field: str
    rules: List[Dict[str, Any]]
    error_message: str
    required: bool = False
    default_value: Any = None


class DataTransformer:
    """
    Data transformation engine.
    
    Handles data transformation, validation,
    and enrichment operations.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.transformation_rules: List[TransformationRule] = []
        self.validation_rules: List[ValidationConfig] = []
        self.field_mappings: Dict[str, str] = {}
        self.value_mappings: Dict[str, Dict[str, Any]] = {}
        self.filters: Dict[str, Any] = {}
        self.calculations: Dict[str, Callable] = {}
        self.enrichers: Dict[str, Callable] = {}
        self._setup_transformations()
    
    def _setup_transformations(self):
        """Setup transformation rules from configuration."""
        # Setup field mappings
        if 'field_mappings' in self.config:
            self.field_mappings = self.config['field_mappings']
        
        # Setup value mappings
        if 'value_mappings' in self.config:
            self.value_mappings = self.config['value_mappings']
        
        # Setup filters
        if 'filters' in self.config:
            self.filters = self.config['filters']
        
        # Setup validation rules
        if 'validation_rules' in self.config:
            for rule_config in self.config['validation_rules']:
                validation_config = ValidationConfig(
                    field=rule_config['field'],
                    rules=rule_config['rules'],
                    error_message=rule_config.get('error_message', 'Validation failed'),
                    required=rule_config.get('required', False),
                    default_value=rule_config.get('default_value')
                )
                self.validation_rules.append(validation_config)
        
        # Setup calculations
        if 'calculations' in self.config:
            for calc_name, calc_config in self.config['calculations'].items():
                self.calculations[calc_name] = self._create_calculation_function(calc_config)
        
        # Setup enrichers
        if 'enrichers' in self.config:
            for enrich_name, enrich_config in self.config['enrichers'].items():
                self.enrichers[enrich_name] = self._create_enrichment_function(enrich_config)
    
    def transform_request(self, request_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Transform request data.
        
        Args:
            request_data: Original request data
            context: Transformation context
            
        Returns:
            Transformed request data
        """
        context = context or {}
        transformed_data = request_data.copy()
        
        try:
            # Apply field mappings
            transformed_data = self._apply_field_mappings(transformed_data)
            
            # Apply value mappings
            transformed_data = self._apply_value_mappings(transformed_data)
            
            # Apply filters
            transformed_data = self._apply_filters(transformed_data)
            
            # Apply calculations
            transformed_data = self._apply_calculations(transformed_data, context)
            
            # Apply enrichments
            transformed_data = self._apply_enrichments(transformed_data, context)
            
            # Validate data
            self._validate_data(transformed_data)
            
            return transformed_data
        
        except Exception as e:
            logger.error(f"Error transforming request: {str(e)}")
            raise IntegrationException(f"Request transformation failed: {str(e)}")
    
    def transform_response(self, response_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Transform response data.
        
        Args:
            response_data: Original response data
            context: Transformation context
            
        Returns:
            Transformed response data
        """
        context = context or {}
        transformed_data = response_data.copy()
        
        try:
            # Apply field mappings (reverse for response)
            transformed_data = self._apply_reverse_field_mappings(transformed_data)
            
            # Apply value mappings (reverse for response)
            transformed_data = self._apply_reverse_value_mappings(transformed_data)
            
            # Apply filters
            transformed_data = self._apply_filters(transformed_data)
            
            # Apply calculations
            transformed_data = self._apply_calculations(transformed_data, context)
            
            # Validate data
            self._validate_data(transformed_data)
            
            return transformed_data
        
        except Exception as e:
            logger.error(f"Error transforming response: {str(e)}")
            raise IntegrationException(f"Response transformation failed: {str(e)}")
    
    def _apply_field_mappings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field mappings to data."""
        mapped_data = {}
        
        for old_field, new_field in self.field_mappings.items():
            if old_field in data:
                mapped_data[new_field] = data[old_field]
        
        # Keep unmapped fields
        for field, value in data.items():
            if field not in self.field_mappings:
                mapped_data[field] = value
        
        return mapped_data
    
    def _apply_reverse_field_mappings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply reverse field mappings to data."""
        reverse_mappings = {v: k for k, v in self.field_mappings.items()}
        mapped_data = {}
        
        for old_field, new_field in reverse_mappings.items():
            if old_field in data:
                mapped_data[new_field] = data[old_field]
        
        # Keep unmapped fields
        for field, value in data.items():
            if field not in reverse_mappings:
                mapped_data[field] = value
        
        return mapped_data
    
    def _apply_value_mappings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply value mappings to data."""
        mapped_data = data.copy()
        
        for field, mapping in self.value_mappings.items():
            if field in mapped_data:
                value = mapped_data[field]
                if value in mapping:
                    mapped_data[field] = mapping[value]
        
        return mapped_data
    
    def _apply_reverse_value_mappings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply reverse value mappings to data."""
        mapped_data = data.copy()
        
        for field, mapping in self.value_mappings.items():
            if field in mapped_data:
                value = mapped_data[field]
                # Find reverse mapping
                reverse_mapping = {v: k for k, v in mapping.items()}
                if value in reverse_mapping:
                    mapped_data[field] = reverse_mapping[value]
        
        return mapped_data
    
    def _apply_filters(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply filters to data."""
        filtered_data = data.copy()
        
        # Include only specified fields
        if 'include_fields' in self.filters:
            include_fields = self.filters['include_fields']
            filtered_data = {k: v for k, v in filtered_data.items() if k in include_fields}
        
        # Exclude specified fields
        if 'exclude_fields' in self.filters:
            exclude_fields = self.filters['exclude_fields']
            filtered_data = {k: v for k, v in filtered_data.items() if k not in exclude_fields}
        
        # Filter by field values
        if 'field_filters' in self.filters:
            field_filters = self.filters['field_filters']
            for field, filter_config in field_filters.items():
                if field in filtered_data:
                    value = filtered_data[field]
                    
                    # Apply filter conditions
                    if 'equals' in filter_config and value != filter_config['equals']:
                        del filtered_data[field]
                    elif 'not_equals' in filter_config and value == filter_config['not_equals']:
                        del filtered_data[field]
                    elif 'in' in filter_config and value not in filter_config['in']:
                        del filtered_data[field]
                    elif 'not_in' in filter_config and value in filter_config['not_in']:
                        del filtered_data[field]
        
        return filtered_data
    
    def _apply_calculations(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply calculations to data."""
        calculated_data = data.copy()
        
        for field, calculation_func in self.calculations.items():
            try:
                calculated_value = calculation_func(calculated_data, context)
                calculated_data[field] = calculated_value
            except Exception as e:
                logger.error(f"Error in calculation {field}: {str(e)}")
        
        return calculated_data
    
    def _apply_enrichments(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply enrichments to data."""
        enriched_data = data.copy()
        
        for field, enricher_func in self.enrichers.items():
            try:
                enriched_value = enricher_func(enriched_data, context)
                enriched_data[field] = enriched_value
            except Exception as e:
                logger.error(f"Error in enrichment {field}: {str(e)}")
        
        return enriched_data
    
    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate data against validation rules."""
        for validation_config in self.validation_rules:
            field = validation_config.field
            rules = validation_config.rules
            
            # Check required fields
            if validation_config.required and field not in data:
                if validation_config.default_value is not None:
                    data[field] = validation_config.default_value
                else:
                    raise ValidationError(f"Required field '{field}' is missing")
            
            # Skip validation if field not present and not required
            if field not in data:
                continue
            
            value = data[field]
            
            # Apply validation rules
            for rule in rules:
                rule_type = rule.get('type')
                
                if rule_type == ValidationRule.TYPE_CHECK.value:
                    expected_type = rule.get('type')
                    if not self._check_type(value, expected_type):
                        raise ValidationError(f"Field '{field}' must be of type {expected_type}")
                
                elif rule_type == ValidationRule.REGEX.value:
                    pattern = rule.get('pattern')
                    if not re.match(pattern, str(value)):
                        raise ValidationError(f"Field '{field}' does not match required pattern")
                
                elif rule_type == ValidationRule.RANGE.value:
                    min_value = rule.get('min')
                    max_value = rule.get('max')
                    if min_value is not None and value < min_value:
                        raise ValidationError(f"Field '{field}' must be >= {min_value}")
                    if max_value is not None and value > max_value:
                        raise ValidationError(f"Field '{field}' must be <= {max_value}")
                
                elif rule_type == ValidationRule.LENGTH.value:
                    min_length = rule.get('min_length')
                    max_length = rule.get('max_length')
                    value_length = len(str(value))
                    if min_length is not None and value_length < min_length:
                        raise ValidationError(f"Field '{field}' length must be >= {min_length}")
                    if max_length is not None and value_length > max_length:
                        raise ValidationError(f"Field '{field}' length must be <= {max_length}")
                
                elif rule_type == ValidationRule.CUSTOM.value:
                    custom_validator = rule.get('validator')
                    if custom_validator and not custom_validator(value):
                        raise ValidationError(f"Field '{field}' failed custom validation")
        
        return True
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        if expected_type == 'string':
            return isinstance(value, str)
        elif expected_type == 'integer':
            return isinstance(value, int)
        elif expected_type == 'float':
            return isinstance(value, (int, float))
        elif expected_type == 'boolean':
            return isinstance(value, bool)
        elif expected_type == 'list':
            return isinstance(value, list)
        elif expected_type == 'dict':
            return isinstance(value, dict)
        elif expected_type == 'datetime':
            return isinstance(value, (datetime, str))
        else:
            return True
    
    def _create_calculation_function(self, config: Dict[str, Any]) -> Callable:
        """Create calculation function from configuration."""
        calc_type = config.get('type')
        
        if calc_type == 'sum':
            fields = config.get('fields', [])
            return lambda data, context: sum(data.get(f, 0) for f in fields)
        
        elif calc_type == 'average':
            fields = config.get('fields', [])
            return lambda data, context: sum(data.get(f, 0) for f in fields) / len(fields) if fields else 0
        
        elif calc_type == 'concat':
            fields = config.get('fields', [])
            separator = config.get('separator', '')
            return lambda data, context: separator.join(str(data.get(f, '')) for f in fields)
        
        elif calc_type == 'conditional':
            condition = config.get('condition')
            true_value = config.get('true_value')
            false_value = config.get('false_value')
            return lambda data, context: true_value if self._evaluate_condition(data, condition) else false_value
        
        elif calc_type == 'timestamp':
            return lambda data, context: timezone.now().isoformat()
        
        else:
            return lambda data, context: None
    
    def _create_enrichment_function(self, config: Dict[str, Any]) -> Callable:
        """Create enrichment function from configuration."""
        enrich_type = config.get('type')
        
        if enrich_type == 'lookup':
            lookup_table = config.get('lookup_table', {})
            source_field = config.get('source_field')
            return lambda data, context: lookup_table.get(data.get(source_field))
        
        elif enrich_type == 'format':
            template = config.get('template')
            fields = config.get('fields', [])
            return lambda data, context: template.format(**{f: data.get(f) for f in fields})
        
        elif enrich_type == 'hash':
            algorithm = config.get('algorithm', 'md5')
            source_field = config.get('source_field')
            return lambda data, context: self._hash_value(data.get(source_field), algorithm)
        
        elif enrich_type == 'extract':
            source_field = config.get('source_field')
            pattern = config.get('pattern')
            group = config.get('group', 0)
            return lambda data, context: self._extract_pattern(data.get(source_field), pattern, group)
        
        else:
            return lambda data, context: None
    
    def _evaluate_condition(self, data: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """Evaluate condition against data."""
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')
        
        if field not in data:
            return False
        
        data_value = data[field]
        
        if operator == 'equals':
            return data_value == value
        elif operator == 'not_equals':
            return data_value != value
        elif operator == 'greater_than':
            return data_value > value
        elif operator == 'less_than':
            return data_value < value
        elif operator == 'greater_equal':
            return data_value >= value
        elif operator == 'less_equal':
            return data_value <= value
        elif operator == 'in':
            return data_value in value
        elif operator == 'not_in':
            return data_value not in value
        else:
            return False
    
    def _hash_value(self, value: Any, algorithm: str) -> str:
        """Hash value using specified algorithm."""
        import hashlib
        
        if value is None:
            return ''
        
        value_str = str(value)
        
        if algorithm == 'md5':
            return hashlib.md5(value_str.encode()).hexdigest()
        elif algorithm == 'sha1':
            return hashlib.sha1(value_str.encode()).hexdigest()
        elif algorithm == 'sha256':
            return hashlib.sha256(value_str.encode()).hexdigest()
        else:
            return value_str
    
    def _extract_pattern(self, value: str, pattern: str, group: int) -> str:
        """Extract pattern from string."""
        if not value or not pattern:
            return ''
        
        match = re.search(pattern, value)
        if match:
            return match.group(group) if group <= len(match.groups()) else ''
        
        return ''
    
    def add_transformation_rule(self, rule: TransformationRule):
        """Add transformation rule."""
        self.transformation_rules.append(rule)
        logger.info(f"Transformation rule added: {rule.name}")
    
    def remove_transformation_rule(self, rule_name: str):
        """Remove transformation rule."""
        self.transformation_rules = [r for r in self.transformation_rules if r.name != rule_name]
        logger.info(f"Transformation rule removed: {rule_name}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get transformer statistics."""
        return {
            'field_mappings': len(self.field_mappings),
            'value_mappings': len(self.value_mappings),
            'validation_rules': len(self.validation_rules),
            'calculations': len(self.calculations),
            'enrichers': len(self.enrichers),
            'transformation_rules': len(self.transformation_rules),
        }


class TransformationPipeline:
    """
    Pipeline for chaining multiple transformations.
    
    Allows complex transformation workflows
    with multiple steps.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.steps: List[DataTransformer] = []
        self.logger = logging.getLogger(f"pipeline.{name}")
    
    def add_step(self, transformer: DataTransformer):
        """Add transformation step to pipeline."""
        self.steps.append(transformer)
        self.logger.info(f"Step added to pipeline: {transformer}")
    
    def remove_step(self, index: int):
        """Remove transformation step from pipeline."""
        if 0 <= index < len(self.steps):
            removed = self.steps.pop(index)
            self.logger.info(f"Step removed from pipeline: {removed}")
    
    def execute(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute transformation pipeline."""
        context = context or {}
        transformed_data = data.copy()
        
        for i, step in enumerate(self.steps):
            try:
                transformed_data = step.transform_request(transformed_data, context)
                self.logger.debug(f"Step {i+1} completed")
            except Exception as e:
                self.logger.error(f"Error in step {i+1}: {str(e)}")
                raise IntegrationException(f"Pipeline step {i+1} failed: {str(e)}")
        
        return transformed_data
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            'name': self.name,
            'steps': len(self.steps),
            'step_statistics': [step.get_statistics() for step in self.steps],
        }


# Factory functions
def create_transformer(config: Dict[str, Any]) -> DataTransformer:
    """Create data transformer from configuration."""
    return DataTransformer(config)


def create_pipeline(name: str) -> TransformationPipeline:
    """Create transformation pipeline."""
    return TransformationPipeline(name)


# Convenience functions
def transform_data(data: Dict[str, Any], config: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Transform data using configuration."""
    transformer = DataTransformer(config)
    return transformer.transform_request(data, context)


def validate_data(data: Dict[str, Any], validation_rules: List[Dict[str, Any]]) -> bool:
    """Validate data against rules."""
    transformer = DataTransformer({'validation_rules': validation_rules})
    return transformer._validate_data(data)
