# engagement/integration_system/transformer.py
"""
Data transformation system for integrations.
Provides data transformation, mapping, and validation capabilities.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta

from django.utils import timezone
from django.conf import settings

from .integ_constants import (
    DataType, TRANSFORMATION_RULES, VALIDATION_RULES,
    ERROR_CODES
)

logger = logging.getLogger(__name__)


class TransformationType(Enum):
    """Types of transformations."""
    FIELD_MAPPING = "field_mapping"
    TYPE_CONVERSION = "type_conversion"
    VALUE_MAPPING = "value_mapping"
    CONDITIONAL = "conditional"
    AGGREGATION = "aggregation"
    FILTERING = "filtering"
    SORTING = "sorting"
    GROUPING = "grouping"
    CALCULATION = "calculation"
    CUSTOM = "custom"


class ValidationType(Enum):
    """Types of validation."""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    FORMAT_CHECK = "format_check"
    RANGE_CHECK = "range_check"
    LENGTH_CHECK = "length_check"
    REGEX_CHECK = "regex_check"
    CUSTOM = "custom"


@dataclass
class TransformationRule:
    """Transformation rule definition."""
    id: str
    name: str
    type: TransformationType
    description: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationRule:
    """Validation rule definition."""
    id: str
    name: str
    type: ValidationType
    field: str
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformationContext:
    """Context for transformation execution."""
    source_format: DataType
    target_format: DataType
    rules: List[TransformationRule] = field(default_factory=list)
    validation_rules: List[ValidationRule] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)


class BaseTransformer(ABC):
    """Base transformer class."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform data."""
        pass
    
    @abstractmethod
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate data."""
        pass
    
    def can_transform(self, source_format: DataType, target_format: DataType) -> bool:
        """Check if transformer can handle formats."""
        return True


class FieldMappingTransformer(BaseTransformer):
    """Field mapping transformer."""
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform data using field mappings."""
        if not isinstance(data, dict):
            return data
        
        transformed_data = {}
        
        # Apply field mapping rules
        for rule in context.rules:
            if rule.type == TransformationType.FIELD_MAPPING and rule.enabled:
                mapping = rule.config.get('mapping', {})
                keep_unmapped = rule.config.get('keep_unmapped', True)
                
                for source_field, target_field in mapping.items():
                    if source_field in data:
                        transformed_data[target_field] = data[source_field]
                
                # Keep unmapped fields if specified
                if keep_unmapped:
                    for field, value in data.items():
                        if field not in mapping:
                            transformed_data[field] = value
        
        return transformed_data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate field mapping."""
        return isinstance(data, dict)


class TypeConversionTransformer(BaseTransformer):
    """Type conversion transformer."""
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform data using type conversions."""
        if not isinstance(data, dict):
            return data
        
        transformed_data = data.copy()
        
        # Apply type conversion rules
        for rule in context.rules:
            if rule.type == TransformationType.TYPE_CONVERSION and rule.enabled:
                conversions = rule.config.get('conversions', {})
                
                for field, target_type in conversions.items():
                    if field in transformed_data:
                        try:
                            value = transformed_data[field]
                            transformed_data[field] = self._convert_type(value, target_type)
                        except (ValueError, TypeError) as exc:
                            self.logger.warning(f"Type conversion failed for field {field}: {exc}")
        
        return transformed_data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate type conversions."""
        return isinstance(data, dict)
    
    def _convert_type(self, value: Any, target_type: str) -> Any:
        """Convert value to target type."""
        if target_type == 'int':
            return int(value)
        elif target_type == 'float':
            return float(value)
        elif target_type == 'str':
            return str(value)
        elif target_type == 'bool':
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        elif target_type == 'datetime':
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            elif isinstance(value, (int, float)):
                return datetime.fromtimestamp(value)
            return value
        elif target_type == 'date':
            if isinstance(value, str):
                return datetime.fromisoformat(value).date()
            return value
        else:
            return value


class ValueMappingTransformer(BaseTransformer):
    """Value mapping transformer."""
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform data using value mappings."""
        if not isinstance(data, dict):
            return data
        
        transformed_data = data.copy()
        
        # Apply value mapping rules
        for rule in context.rules:
            if rule.type == TransformationType.VALUE_MAPPING and rule.enabled:
                mappings = rule.config.get('mappings', {})
                
                for field, field_mappings in mappings.items():
                    if field in transformed_data:
                        value = transformed_data[field]
                        
                        # Apply mapping
                        if value in field_mappings:
                            transformed_data[field] = field_mappings[value]
                        elif 'default' in field_mappings:
                            transformed_data[field] = field_mappings['default']
        
        return transformed_data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate value mappings."""
        return isinstance(data, dict)


class ConditionalTransformer(BaseTransformer):
    """Conditional transformer."""
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform data using conditional rules."""
        if not isinstance(data, dict):
            return data
        
        transformed_data = data.copy()
        
        # Apply conditional rules
        for rule in context.rules:
            if rule.type == TransformationType.CONDITIONAL and rule.enabled:
                conditions = rule.config.get('conditions', [])
                actions = rule.config.get('actions', [])
                
                if self._evaluate_conditions(conditions, transformed_data):
                    for action in actions:
                        transformed_data = self._apply_action(action, transformed_data)
        
        return transformed_data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate conditional rules."""
        return isinstance(data, dict)
    
    def _evaluate_conditions(self, conditions: List[Dict[str, Any]], data: Dict[str, Any]) -> bool:
        """Evaluate conditions."""
        for condition in conditions:
            field = condition.get('field')
            operator = condition.get('operator', 'equals')
            value = condition.get('value')
            
            if field not in data:
                return False
            
            field_value = data[field]
            
            if operator == 'equals':
                if field_value != value:
                    return False
            elif operator == 'not_equals':
                if field_value == value:
                    return False
            elif operator == 'greater_than':
                if not (field_value > value):
                    return False
            elif operator == 'less_than':
                if not (field_value < value):
                    return False
            elif operator == 'in':
                if field_value not in value:
                    return False
            elif operator == 'not_in':
                if field_value in value:
                    return False
            elif operator == 'contains':
                if value not in str(field_value):
                    return False
            elif operator == 'regex':
                if not re.match(value, str(field_value)):
                    return False
        
        return True
    
    def _apply_action(self, action: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply action to data."""
        action_type = action.get('type')
        
        if action_type == 'set_field':
            field = action.get('field')
            value = action.get('value')
            data[field] = value
        elif action_type == 'delete_field':
            field = action.get('field')
            data.pop(field, None)
        elif action_type == 'rename_field':
            old_field = action.get('old_field')
            new_field = action.get('new_field')
            if old_field in data:
                data[new_field] = data.pop(old_field)
        elif action_type == 'copy_field':
            source_field = action.get('source_field')
            target_field = action.get('target_field')
            if source_field in data:
                data[target_field] = data[source_field]
        
        return data


class AggregationTransformer(BaseTransformer):
    """Aggregation transformer."""
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform data using aggregation rules."""
        if not isinstance(data, list):
            return data
        
        transformed_data = {}
        
        # Apply aggregation rules
        for rule in context.rules:
            if rule.type == TransformationType.AGGREGATION and rule.enabled:
                field = rule.config.get('field')
                operation = rule.config.get('operation', 'sum')
                target_field = rule.config.get('target_field', f"{field}_{operation}")
                
                values = []
                for item in data:
                    if isinstance(item, dict) and field in item:
                        values.append(item[field])
                
                if operation == 'sum':
                    transformed_data[target_field] = sum(values)
                elif operation == 'avg':
                    transformed_data[target_field] = sum(values) / len(values) if values else 0
                elif operation == 'min':
                    transformed_data[target_field] = min(values) if values else 0
                elif operation == 'max':
                    transformed_data[target_field] = max(values) if values else 0
                elif operation == 'count':
                    transformed_data[target_field] = len(values)
        
        return transformed_data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate aggregation."""
        return isinstance(data, list)


class FilteringTransformer(BaseTransformer):
    """Filtering transformer."""
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform data using filtering rules."""
        if not isinstance(data, list):
            return data
        
        filtered_data = data.copy()
        
        # Apply filtering rules
        for rule in context.rules:
            if rule.type == TransformationType.FILTERING and rule.enabled:
                conditions = rule.config.get('conditions', [])
                
                filtered_data = [
                    item for item in filtered_data
                    if isinstance(item, dict) and self._evaluate_conditions(conditions, item)
                ]
        
        return filtered_data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate filtering."""
        return isinstance(data, list)


class CustomTransformer(BaseTransformer):
    """Custom transformer with user-defined logic."""
    
    def __init__(self, name: str, transform_func: Callable = None, validate_func: Callable = None):
        super().__init__(name)
        self.transform_func = transform_func
        self.validate_func = validate_func
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Transform using custom function."""
        if self.transform_func:
            return self.transform_func(data, context)
        return data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate using custom function."""
        if self.validate_func:
            return self.validate_func(data, context)
        return True


class TransformerChain:
    """Chain of transformers for complex transformations."""
    
    def __init__(self):
        self.transformers: List[BaseTransformer] = []
        self.logger = logging.getLogger(f"{__name__}.TransformerChain")
    
    def add_transformer(self, transformer: BaseTransformer):
        """Add transformer to chain."""
        self.transformers.append(transformer)
    
    def transform(self, data: Any, context: TransformationContext) -> Any:
        """Execute transformation chain."""
        current_data = data
        
        for transformer in self.transformers:
            try:
                # Validate data if transformer supports it
                if hasattr(transformer, 'validate'):
                    if not transformer.validate(current_data, context):
                        self.logger.warning(f"Transformer {transformer.name} validation failed")
                        continue
                
                # Transform data
                current_data = transformer.transform(current_data, context)
                
            except Exception as exc:
                self.logger.error(f"Transformer {transformer.name} failed: {exc}")
                # Continue with next transformer
                continue
        
        return current_data
    
    def validate(self, data: Any, context: TransformationContext) -> bool:
        """Validate all transformers in chain."""
        for transformer in self.transformers:
            if hasattr(transformer, 'validate'):
                if not transformer.validate(data, context):
                    return False
        return True


class DataValidator:
    """Data validation system."""
    
    def __init__(self):
        self.rules: List[ValidationRule] = []
        self.logger = logging.getLogger(f"{__name__}.DataValidator")
    
    def add_rule(self, rule: ValidationRule):
        """Add validation rule."""
        self.rules.append(rule)
    
    def validate(self, data: Any, context: TransformationContext = None) -> Dict[str, Any]:
        """Validate data against all rules."""
        errors = []
        warnings = []
        
        if not isinstance(data, dict):
            return {
                'valid': False,
                'errors': ['Data must be a dictionary'],
                'warnings': warnings
            }
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                if not self._validate_rule(rule, data):
                    error_msg = rule.error_message or f"Validation failed for {rule.field}"
                    errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': error_msg
                    })
            except Exception as exc:
                self.logger.error(f"Validation rule {rule.name} failed: {exc}")
                warnings.append(f"Validation rule {rule.name} failed: {exc}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _validate_rule(self, rule: ValidationRule, data: Dict[str, Any]) -> bool:
        """Validate a single rule."""
        field_value = data.get(rule.field)
        
        if rule.type == ValidationType.REQUIRED:
            return field_value is not None and field_value != ''
        
        elif rule.type == ValidationType.TYPE_CHECK:
            expected_type = rule.config.get('type')
            if expected_type == 'string':
                return isinstance(field_value, str)
            elif expected_type == 'integer':
                return isinstance(field_value, int)
            elif expected_type == 'float':
                return isinstance(field_value, float)
            elif expected_type == 'boolean':
                return isinstance(field_value, bool)
            elif expected_type == 'list':
                return isinstance(field_value, list)
            elif expected_type == 'dict':
                return isinstance(field_value, dict)
            return True
        
        elif rule.type == ValidationType.FORMAT_CHECK:
            format_type = rule.config.get('format')
            if format_type == 'email':
                import re
                email_pattern = VALIDATION_RULES.get('email', r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
                return re.match(email_pattern, str(field_value)) is not None
            elif format_type == 'phone':
                phone_pattern = VALIDATION_RULES.get('phone', r'^\+?1?-?\.?\s?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$')
                return re.match(phone_pattern, str(field_value)) is not None
            elif format_type == 'uuid':
                uuid_pattern = VALIDATION_RULES.get('uuid', r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
                return re.match(uuid_pattern, str(field_value)) is not None
            return True
        
        elif rule.type == ValidationType.RANGE_CHECK:
            min_value = rule.config.get('min')
            max_value = rule.config.get('max')
            
            if min_value is not None and field_value < min_value:
                return False
            if max_value is not None and field_value > max_value:
                return False
            return True
        
        elif rule.type == ValidationType.LENGTH_CHECK:
            min_length = rule.config.get('min_length')
            max_length = rule.config.get('max_length')
            value_length = len(str(field_value))
            
            if min_length is not None and value_length < min_length:
                return False
            if max_length is not None and value_length > max_length:
                return False
            return True
        
        elif rule.type == ValidationType.REGEX_CHECK:
            pattern = rule.config.get('pattern')
            if pattern:
                return re.match(pattern, str(field_value)) is not None
            return True
        
        elif rule.type == ValidationType.CUSTOM:
            custom_func = rule.config.get('function')
            if custom_func:
                return custom_func(field_value, data)
            return True
        
        return True


class TransformerManager:
    """Manager for transformation operations."""
    
    def __init__(self):
        self.transformers: Dict[str, BaseTransformer] = {}
        self.chains: Dict[str, TransformerChain] = {}
        self.validator = DataValidator()
        self.logger = logging.getLogger(f"{__name__}.TransformerManager")
    
    def register_transformer(self, name: str, transformer: BaseTransformer):
        """Register a transformer."""
        self.transformers[name] = transformer
        self.logger.info(f"Registered transformer: {name}")
    
    def create_chain(self, name: str, transformer_names: List[str]) -> TransformerChain:
        """Create transformer chain."""
        chain = TransformerChain()
        
        for transformer_name in transformer_names:
            transformer = self.transformers.get(transformer_name)
            if transformer:
                chain.add_transformer(transformer)
            else:
                self.logger.warning(f"Transformer {transformer_name} not found")
        
        self.chains[name] = chain
        return chain
    
    def transform(self, data: Any, source_format: DataType, target_format: DataType,
                   transformer_names: List[str] = None, rules: List[TransformationRule] = None,
                   validation_rules: List[ValidationRule] = None) -> Dict[str, Any]:
        """Transform data."""
        try:
            # Create context
            context = TransformationContext(
                source_format=source_format,
                target_format=target_format,
                rules=rules or [],
                validation_rules=validation_rules or []
            )
            
            # Validate input data
            if validation_rules:
                self.validator.rules = validation_rules
                validation_result = self.validator.validate(data, context)
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'error': 'Validation failed',
                        'validation_errors': validation_result['errors'],
                        'data': data
                    }
            
            # Transform data
            if transformer_names:
                # Use transformer chain
                chain_name = f"chain_{'_'.join(transformer_names)}"
                if chain_name not in self.chains:
                    self.create_chain(chain_name, transformer_names)
                
                transformed_data = self.chains[chain_name].transform(data, context)
            else:
                # Use default transformation
                transformed_data = self._default_transform(data, context)
            
            return {
                'success': True,
                'data': transformed_data,
                'source_format': source_format.value,
                'target_format': target_format.value
            }
            
        except Exception as exc:
            self.logger.error(f"Transformation failed: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'data': data
            }
    
    def _default_transform(self, data: Any, context: TransformationContext) -> Any:
        """Default transformation logic."""
        # Apply basic transformations based on format types
        if context.source_format == DataType.JSON and context.target_format == DataType.XML:
            return self._json_to_xml(data)
        elif context.source_format == DataType.XML and context.target_format == DataType.JSON:
            return self._xml_to_json(data)
        elif context.source_format == DataType.JSON and context.target_format == DataType.CSV:
            return self._json_to_csv(data)
        elif context.source_format == DataType.CSV and context.target_format == DataType.JSON:
            return self._csv_to_json(data)
        else:
            return data
    
    def _json_to_xml(self, data: Any) -> str:
        """Convert JSON to XML."""
        if not isinstance(data, dict):
            return str(data)
        
        root = ET.Element('root')
        
        def dict_to_xml(parent, data):
            if isinstance(data, dict):
                for key, value in data.items():
                    child = ET.SubElement(parent, key)
                    dict_to_xml(child, value)
            else:
                parent.text = str(data)
        
        dict_to_xml(root, data)
        return ET.tostring(root, encoding='unicode')
    
    def _xml_to_json(self, xml_data: str) -> Dict[str, Any]:
        """Convert XML to JSON."""
        try:
            root = ET.fromstring(xml_data)
            
            def xml_to_dict(element):
                result = {}
                
                for child in element:
                    if len(child) > 0:
                        result[child.tag] = xml_to_dict(child)
                    else:
                        result[child.tag] = child.text
                
                return result
            
            return xml_to_dict(root)
        except Exception:
            return {'error': 'Invalid XML'}
    
    def _json_to_csv(self, data: List[Dict[str, Any]]) -> str:
        """Convert JSON to CSV."""
        import csv
        import io
        
        if not data:
            return ""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    def _csv_to_json(self, csv_data: str) -> List[Dict[str, Any]]:
        """Convert CSV to JSON."""
        import csv
        import io
        
        reader = csv.DictReader(io.StringIO(csv_data))
        return list(reader)


# Global transformer manager instance
transformer_manager = TransformerManager()

# Register default transformers
transformer_manager.register_transformer('field_mapping', FieldMappingTransformer('field_mapping'))
transformer_manager.register_transformer('type_conversion', TypeConversionTransformer('type_conversion'))
transformer_manager.register_transformer('value_mapping', ValueMappingTransformer('value_mapping'))
transformer_manager.register_transformer('conditional', ConditionalTransformer('conditional'))
transformer_manager.register_transformer('aggregation', AggregationTransformer('aggregation'))
transformer_manager.register_transformer('filtering', FilteringTransformer('filtering'))
