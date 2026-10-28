"""
Data Transformer - Data Transformation and Mapping System

Transform and map data between different formats, schemas, and structures
for seamless integration between various systems and services.
"""

import logging
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from xml.dom import minidom
import csv
import io
from django.utils import timezone

from .integ_constants import IntegrationDataType
from .integ_exceptions import IntegrationError, TransformationError

logger = logging.getLogger(__name__)


class TransformationType(Enum):
    """Types of data transformations."""
    FORMAT_CONVERSION = "format_conversion"
    SCHEMA_MAPPING = "schema_mapping"
    FIELD_MAPPING = "field_mapping"
    VALUE_MAPPING = "value_mapping"
    DATA_ENRICHMENT = "data_enrichment"
    DATA_VALIDATION = "data_validation"
    DATA_AGGREGATION = "data_aggregation"
    DATA_FILTERING = "data_filtering"


class MappingDirection(Enum):
    """Direction of field mapping."""
    SOURCE_TO_TARGET = "source_to_target"
    TARGET_TO_SOURCE = "target_to_source"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class FieldMapping:
    """Field mapping configuration."""
    source_field: str
    target_field: str
    transformation: Optional[str] = None
    default_value: Any = None
    required: bool = False
    validation_rule: Optional[str] = None
    data_type: Optional[str] = None


@dataclass
class ValueMapping:
    """Value mapping configuration."""
    source_value: Any
    target_value: Any
    condition: Optional[str] = None


@dataclass
class TransformationRule:
    """Transformation rule configuration."""
    name: str
    transformation_type: TransformationType
    source_format: IntegrationDataType
    target_format: IntegrationDataType
    field_mappings: List[FieldMapping] = field(default_factory=list)
    value_mappings: List[ValueMapping] = field(default_factory=list)
    custom_transformer: Optional[str] = None
    validation_rules: Dict[str, str] = field(default_factory=dict)
    enrichment_data: Dict[str, Any] = field(default_factory=dict)
    filters: List[str] = field(default_factory=list)


@dataclass
class TransformationResult:
    """Result of data transformation."""
    success: bool
    data: Any = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    transformation_time: float = 0.0


class DataTransformer:
    """Main data transformer class."""
    
    def __init__(self):
        self.transformation_rules: Dict[str, TransformationRule] = {}
        self.custom_transformers: Dict[str, Callable] = {}
        self.validation_functions: Dict[str, Callable] = {}
        self._register_default_transformers()
        self._register_default_validators()
    
    def _register_default_transformers(self):
        """Register default transformation functions."""
        self.custom_transformers.update({
            'timestamp_to_iso': self._transform_timestamp_to_iso,
            'iso_to_timestamp': self._transform_iso_to_timestamp,
            'uppercase': self._transform_uppercase,
            'lowercase': self._transform_lowercase,
            'phone_normalize': self._transform_phone_normalize,
            'email_normalize': self._transform_email_normalize,
            'url_normalize': self._transform_url_normalize,
            'currency_format': self._transform_currency_format,
            'percentage_format': self._transform_percentage_format,
            'date_format': self._transform_date_format,
            'json_extract': self._transform_json_extract,
            'array_to_string': self._transform_array_to_string,
            'string_to_array': self._transform_string_to_array
        })
    
    def _register_default_validators(self):
        """Register default validation functions."""
        self.validation_functions.update({
            'email': self._validate_email,
            'phone': self._validate_phone,
            'url': self._validate_url,
            'numeric': self._validate_numeric,
            'positive': self._validate_positive,
            'non_empty': self._validate_non_empty,
            'max_length': self._validate_max_length,
            'min_length': self._validate_min_length,
            'regex': self._validate_regex,
            'date_range': self._validate_date_range
        })
    
    def register_transformation_rule(self, rule: TransformationRule):
        """Register a transformation rule."""
        self.transformation_rules[rule.name] = rule
        logger.info(f"Registered transformation rule: {rule.name}")
    
    def register_custom_transformer(self, name: str, transformer: Callable):
        """Register custom transformer function."""
        self.custom_transformers[name] = transformer
        logger.info(f"Registered custom transformer: {name}")
    
    def register_validation_function(self, name: str, validator: Callable):
        """Register validation function."""
        self.validation_functions[name] = validator
        logger.info(f"Registered validation function: {name}")
    
    def transform(self, data: Any, rule_name: str) -> TransformationResult:
        """Transform data using specified rule."""
        start_time = timezone.now()
        result = TransformationResult(success=False)
        
        try:
            # Get transformation rule
            rule = self.transformation_rules.get(rule_name)
            if not rule:
                result.errors.append(f"Transformation rule not found: {rule_name}")
                return result
            
            # Perform transformation based on type
            if rule.transformation_type == TransformationType.FORMAT_CONVERSION:
                result = self._transform_format(data, rule)
            elif rule.transformation_type == TransformationType.SCHEMA_MAPPING:
                result = self._transform_schema(data, rule)
            elif rule.transformation_type == TransformationType.FIELD_MAPPING:
                result = self._transform_fields(data, rule)
            elif rule.transformation_type == TransformationType.VALUE_MAPPING:
                result = self._transform_values(data, rule)
            elif rule.transformation_type == TransformationType.DATA_ENRICHMENT:
                result = self._enrich_data(data, rule)
            elif rule.transformation_type == TransformationType.DATA_VALIDATION:
                result = self._validate_data(data, rule)
            elif rule.transformation_type == TransformationType.DATA_AGGREGATION:
                result = self._aggregate_data(data, rule)
            elif rule.transformation_type == TransformationType.DATA_FILTERING:
                result = self._filter_data(data, rule)
            else:
                result.errors.append(f"Unsupported transformation type: {rule.transformation_type}")
            
            # Calculate transformation time
            result.transformation_time = (timezone.now() - start_time).total_seconds()
            result.metadata['rule_name'] = rule_name
            result.metadata['transformation_type'] = rule.transformation_type.value
            
        except Exception as e:
            logger.error(f"Transformation failed: {str(e)}")
            result.errors.append(f"Transformation error: {str(e)}")
            result.transformation_time = (timezone.now() - start_time).total_seconds()
        
        return result
    
    def _transform_format(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Transform data format."""
        result = TransformationResult(success=True)
        
        try:
            # Convert based on source and target formats
            if rule.source_format == IntegrationDataType.JSON and rule.target_format == IntegrationDataType.XML:
                result.data = self._json_to_xml(data)
            elif rule.source_format == IntegrationDataType.XML and rule.target_format == IntegrationDataType.JSON:
                result.data = self._xml_to_json(data)
            elif rule.source_format == IntegrationDataType.JSON and rule.target_format == IntegrationDataType.CSV:
                result.data = self._json_to_csv(data)
            elif rule.source_format == IntegrationDataType.CSV and rule.target_format == IntegrationDataType.JSON:
                result.data = self._csv_to_json(data)
            elif rule.source_format == IntegrationDataType.FORM and rule.target_format == IntegrationDataType.JSON:
                result.data = self._form_to_json(data)
            elif rule.source_format == IntegrationDataType.JSON and rule.target_format == IntegrationDataType.FORM:
                result.data = self._json_to_form(data)
            else:
                result.errors.append(f"Unsupported format conversion: {rule.source_format} -> {rule.target_format}")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Format conversion failed: {str(e)}")
        
        return result
    
    def _transform_schema(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Transform data schema."""
        result = TransformationResult(success=True)
        
        try:
            # Apply field mappings
            if isinstance(data, dict):
                transformed_data = {}
                
                for mapping in rule.field_mappings:
                    source_value = data.get(mapping.source_field)
                    
                    # Apply transformation if specified
                    if mapping.transformation and source_value is not None:
                        source_value = self._apply_transformation(mapping.transformation, source_value)
                    
                    # Apply validation if specified
                    if mapping.validation_rule and source_value is not None:
                        if not self._apply_validation(mapping.validation_rule, source_value):
                            result.warnings.append(f"Validation failed for field: {mapping.target_field}")
                            if mapping.required:
                                result.errors.append(f"Required field validation failed: {mapping.target_field}")
                                result.success = False
                                return result
                    
                    # Use default value if source is None and default is provided
                    if source_value is None and mapping.default_value is not None:
                        source_value = mapping.default_value
                    
                    # Check required fields
                    if mapping.required and source_value is None:
                        result.errors.append(f"Required field missing: {mapping.source_field}")
                        result.success = False
                        return result
                    
                    # Map to target field
                    if source_value is not None:
                        transformed_data[mapping.target_field] = source_value
                
                result.data = transformed_data
            else:
                result.errors.append("Schema mapping requires dictionary input")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Schema transformation failed: {str(e)}")
        
        return result
    
    def _transform_fields(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Transform fields in data."""
        result = TransformationResult(success=True)
        
        try:
            if isinstance(data, dict):
                transformed_data = data.copy()
                
                for mapping in rule.field_mappings:
                    if mapping.source_field in transformed_data:
                        value = transformed_data[mapping.source_field]
                        
                        # Apply transformation
                        if mapping.transformation:
                            value = self._apply_transformation(mapping.transformation, value)
                        
                        # Update target field
                        transformed_data[mapping.target_field] = value
                        
                        # Remove source field if different from target
                        if mapping.source_field != mapping.target_field:
                            del transformed_data[mapping.source_field]
                
                result.data = transformed_data
            else:
                result.errors.append("Field transformation requires dictionary input")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Field transformation failed: {str(e)}")
        
        return result
    
    def _transform_values(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Transform values in data."""
        result = TransformationResult(success=True)
        
        try:
            if isinstance(data, dict):
                transformed_data = data.copy()
                
                for mapping in rule.value_mappings:
                    # Find and replace values
                    self._replace_value_in_dict(transformed_data, mapping.source_value, mapping.target_value)
                
                result.data = transformed_data
            else:
                result.errors.append("Value transformation requires dictionary input")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Value transformation failed: {str(e)}")
        
        return result
    
    def _enrich_data(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Enrich data with additional information."""
        result = TransformationResult(success=True)
        
        try:
            if isinstance(data, dict):
                enriched_data = data.copy()
                
                # Add enrichment data
                for key, value in rule.enrichment_data.items():
                    if callable(value):
                        enriched_data[key] = value(data)
                    else:
                        enriched_data[key] = value
                
                result.data = enriched_data
            else:
                result.errors.append("Data enrichment requires dictionary input")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Data enrichment failed: {str(e)}")
        
        return result
    
    def _validate_data(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Validate data against rules."""
        result = TransformationResult(success=True)
        
        try:
            if isinstance(data, dict):
                validated_data = data.copy()
                
                # Apply validation rules
                for field, validation_rule in rule.validation_rules.items():
                    if field in validated_data:
                        value = validated_data[field]
                        
                        if not self._apply_validation(validation_rule, value):
                            result.warnings.append(f"Validation failed for field: {field}")
                
                result.data = validated_data
            else:
                result.errors.append("Data validation requires dictionary input")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Data validation failed: {str(e)}")
        
        return result
    
    def _aggregate_data(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Aggregate data."""
        result = TransformationResult(success=True)
        
        try:
            if isinstance(data, list):
                # Simple aggregation - combine all dictionaries
                aggregated = {}
                
                for item in data:
                    if isinstance(item, dict):
                        for key, value in item.items():
                            if key in aggregated:
                                # If same key, create list
                                if not isinstance(aggregated[key], list):
                                    aggregated[key] = [aggregated[key]]
                                aggregated[key].append(value)
                            else:
                                aggregated[key] = value
                
                result.data = aggregated
            else:
                result.errors.append("Data aggregation requires list input")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Data aggregation failed: {str(e)}")
        
        return result
    
    def _filter_data(self, data: Any, rule: TransformationRule) -> TransformationResult:
        """Filter data based on rules."""
        result = TransformationResult(success=True)
        
        try:
            if isinstance(data, list):
                filtered_data = []
                
                for item in data:
                    if isinstance(item, dict):
                        # Apply filters
                        if self._passes_filters(item, rule.filters):
                            filtered_data.append(item)
                
                result.data = filtered_data
            else:
                result.errors.append("Data filtering requires list input")
                result.success = False
        
        except Exception as e:
            result.success = False
            result.errors.append(f"Data filtering failed: {str(e)}")
        
        return result
    
    def _apply_transformation(self, transformation_name: str, value: Any) -> Any:
        """Apply transformation to value."""
        transformer = self.custom_transformers.get(transformation_name)
        if transformer:
            return transformer(value)
        else:
            logger.warning(f"Transformer not found: {transformation_name}")
            return value
    
    def _apply_validation(self, validation_rule: str, value: Any) -> bool:
        """Apply validation to value."""
        # Parse validation rule (e.g., "email", "max_length:100", "regex:^\\d+$")
        parts = validation_rule.split(":")
        rule_name = parts[0]
        rule_params = parts[1:] if len(parts) > 1 else []
        
        validator = self.validation_functions.get(rule_name)
        if validator:
            return validator(value, *rule_params)
        else:
            logger.warning(f"Validator not found: {rule_name}")
            return True
    
    def _replace_value_in_dict(self, data: Dict[str, Any], old_value: Any, new_value: Any):
        """Replace all occurrences of old_value with new_value in dictionary."""
        for key, value in data.items():
            if value == old_value:
                data[key] = new_value
            elif isinstance(value, dict):
                self._replace_value_in_dict(value, old_value, new_value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if item == old_value:
                        value[i] = new_value
                    elif isinstance(item, dict):
                        self._replace_value_in_dict(item, old_value, new_value)
    
    def _passes_filters(self, data: Dict[str, Any], filters: List[str]) -> bool:
        """Check if data passes all filters."""
        for filter_rule in filters:
            if not self._passes_filter(data, filter_rule):
                return False
        return True
    
    def _passes_filter(self, data: Dict[str, Any], filter_rule: str) -> bool:
        """Check if data passes a single filter."""
        # Parse filter rule (e.g., "status:active", "age:>18", "name:contains:john")
        parts = filter_rule.split(":")
        
        if len(parts) == 2:
            field, operator = parts
            value = data.get(field)
            if operator == "exists":
                return value is not None
            elif operator == "not_exists":
                return value is None
        elif len(parts) == 3:
            field, operator, expected_value = parts
            value = data.get(field)
            
            if operator == "equals":
                return str(value) == expected_value
            elif operator == "not_equals":
                return str(value) != expected_value
            elif operator == "contains":
                return expected_value in str(value)
            elif operator == "not_contains":
                return expected_value not in str(value)
            elif operator == ">":
                return float(value) > float(expected_value)
            elif operator == "<":
                return float(value) < float(expected_value)
            elif operator == ">=":
                return float(value) >= float(expected_value)
            elif operator == "<=":
                return float(value) <= float(expected_value)
        
        return True
    
    # Format conversion methods
    def _json_to_xml(self, data: Any) -> str:
        """Convert JSON to XML."""
        def dict_to_xml(tag, d):
            elem = ET.Element(tag)
            for key, value in d.items():
                if isinstance(value, dict):
                    child = dict_to_xml(key, value)
                    elem.append(child)
                elif isinstance(value, list):
                    for item in value:
                        child = dict_to_xml(key, item)
                        elem.append(child)
                else:
                    child = ET.SubElement(elem, key)
                    child.text = str(value)
            return elem
        
        root = dict_to_xml("root", data)
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print XML
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    def _xml_to_json(self, xml_data: str) -> Dict[str, Any]:
        """Convert XML to JSON."""
        def xml_to_dict(element):
            result = {}
            
            # Handle attributes
            if element.attrib:
                result.update(element.attrib)
            
            # Handle text content
            if element.text and element.text.strip():
                if len(element) == 0:
                    return element.text.strip()
                else:
                    result['text'] = element.text.strip()
            
            # Handle children
            for child in element:
                child_data = xml_to_dict(child)
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(child_data)
                else:
                    result[child.tag] = child_data
            
            return result
        
        root = ET.fromstring(xml_data)
        return xml_to_dict(root)
    
    def _json_to_csv(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """Convert JSON to CSV."""
        if isinstance(data, dict):
            data = [data]
        
        if not data:
            return ""
        
        # Get headers from first item
        headers = set()
        for item in data:
            headers.update(item.keys())
        
        headers = sorted(headers)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        for item in data:
            # Flatten nested dictionaries
            flattened = {}
            for key, value in item.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        flattened[f"{key}.{sub_key}"] = sub_value
                else:
                    flattened[key] = value
            
            writer.writerow(flattened)
        
        return output.getvalue()
    
    def _csv_to_json(self, csv_data: str) -> List[Dict[str, Any]]:
        """Convert CSV to JSON."""
        reader = csv.DictReader(io.StringIO(csv_data))
        return [dict(row) for row in reader]
    
    def _form_to_json(self, form_data: str) -> Dict[str, Any]:
        """Convert form data to JSON."""
        data = {}
        
        if form_data:
            pairs = form_data.split('&')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    data[key] = value
        
        return data
    
    def _json_to_form(self, json_data: Dict[str, Any]) -> str:
        """Convert JSON to form data."""
        pairs = []
        
        for key, value in json_data.items():
            if isinstance(value, list):
                for item in value:
                    pairs.append(f"{key}={item}")
            else:
                pairs.append(f"{key}={value}")
        
        return '&'.join(pairs)
    
    # Default transformer implementations
    def _transform_timestamp_to_iso(self, value: Any) -> str:
        """Transform timestamp to ISO format."""
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).isoformat()
        elif isinstance(value, datetime):
            return value.isoformat()
        else:
            return str(value)
    
    def _transform_iso_to_timestamp(self, value: Any) -> float:
        """Transform ISO format to timestamp."""
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.timestamp()
            except ValueError:
                return 0.0
        else:
            return float(value)
    
    def _transform_uppercase(self, value: Any) -> str:
        """Transform to uppercase."""
        return str(value).upper()
    
    def _transform_lowercase(self, value: Any) -> str:
        """Transform to lowercase."""
        return str(value).lower()
    
    def _transform_phone_normalize(self, value: Any) -> str:
        """Normalize phone number."""
        phone = str(value)
        # Remove all non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Add country code if missing (assuming US)
        if len(phone) == 10:
            phone = '1' + phone
        
        return phone
    
    def _transform_email_normalize(self, value: Any) -> str:
        """Normalize email address."""
        email = str(value).lower().strip()
        return email
    
    def _transform_url_normalize(self, value: Any) -> str:
        """Normalize URL."""
        url = str(value).strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url
    
    def _transform_currency_format(self, value: Any) -> str:
        """Format as currency."""
        try:
            amount = float(value)
            return f"${amount:,.2f}"
        except (ValueError, TypeError):
            return str(value)
    
    def _transform_percentage_format(self, value: Any) -> str:
        """Format as percentage."""
        try:
            percentage = float(value)
            return f"{percentage:.1f}%"
        except (ValueError, TypeError):
            return str(value)
    
    def _transform_date_format(self, value: Any) -> str:
        """Format date."""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                return str(value)
        else:
            return str(value)
    
    def _transform_json_extract(self, value: Any, path: str = None) -> Any:
        """Extract value from JSON."""
        if path and isinstance(value, dict):
            keys = path.split('.')
            current = value
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            
            return current
        
        return value
    
    def _transform_array_to_string(self, value: Any, separator: str = ",") -> str:
        """Convert array to string."""
        if isinstance(value, list):
            return separator.join(str(item) for item in value)
        else:
            return str(value)
    
    def _transform_string_to_array(self, value: Any, separator: str = ",") -> List[str]:
        """Convert string to array."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(separator) if item.strip()]
        elif isinstance(value, list):
            return [str(item) for item in value]
        else:
            return [str(value)]
    
    # Default validator implementations
    def _validate_email(self, value: Any) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, str(value)))
    
    def _validate_phone(self, value: Any) -> bool:
        """Validate phone format."""
        phone = str(value)
        # Remove all non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        return len(phone) >= 10 and len(phone) <= 15
    
    def _validate_url(self, value: Any) -> bool:
        """Validate URL format."""
        import re
        pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
        return bool(re.match(pattern, str(value)))
    
    def _validate_numeric(self, value: Any) -> bool:
        """Validate numeric value."""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_positive(self, value: Any) -> bool:
        """Validate positive value."""
        try:
            return float(value) > 0
        except (ValueError, TypeError):
            return False
    
    def _validate_non_empty(self, value: Any) -> bool:
        """Validate non-empty value."""
        return value is not None and str(value).strip() != ""
    
    def _validate_max_length(self, value: Any, max_length: str) -> bool:
        """Validate maximum length."""
        return len(str(value)) <= int(max_length)
    
    def _validate_min_length(self, value: Any, min_length: str) -> bool:
        """Validate minimum length."""
        return len(str(value)) >= int(min_length)
    
    def _validate_regex(self, value: Any, pattern: str) -> bool:
        """Validate with regex pattern."""
        import re
        return bool(re.match(pattern, str(value)))
    
    def _validate_date_range(self, value: Any, date_range: str) -> bool:
        """Validate date range."""
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, datetime):
                dt = value
            else:
                return False
            
            # Parse date range (e.g., "2020-01-01:2020-12-31")
            if ':' in date_range:
                start_str, end_str = date_range.split(':')
                start_date = datetime.fromisoformat(start_str)
                end_date = datetime.fromisoformat(end_str)
                
                return start_date <= dt <= end_date
            
            return True
        except (ValueError, TypeError):
            return False


# Global transformer instance
data_transformer = DataTransformer()
