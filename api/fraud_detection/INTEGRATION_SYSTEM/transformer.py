# =============================================================================
# INTEGRATION_SYSTEM/transformer.py
# =============================================================================
"""
Data Transformation Utilities.

Provides data transformation capabilities for different formats,
protocols, and integration requirements.
"""

from __future__ import annotations

import logging
import json
import xml.etree.ElementTree as ET
import yaml
import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

from .integ_constants import DataFormat
from .integ_exceptions import TransformationError, TransformationValidationError

logger = logging.getLogger(__name__)


class TransformationDirection(Enum):
    """Transformation direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass
class TransformationRule:
    """Data transformation rule."""
    name: str
    source_format: DataFormat
    target_format: DataFormat
    direction: TransformationDirection
    transformer_func: Callable
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FieldMapping:
    """Field mapping configuration."""
    source_field: str
    target_field: str
    transform_func: Optional[Callable] = None
    default_value: Any = None
    required: bool = True
    validation_func: Optional[Callable] = None


@dataclass
class TransformationContext:
    """Transformation context information."""
    integration_name: str
    version: str
    direction: TransformationDirection
    timestamp: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataTransformer(ABC):
    """
    Abstract base class for data transformers.
    """
    
    @abstractmethod
    async def transform(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform data according to context."""
        pass
    
    @abstractmethod
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        pass
    
    @abstractmethod
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate output data."""
        pass


class JSONTransformer(DataTransformer):
    """JSON data transformer."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize JSON transformer."""
        self.config = config or {}
    
    async def transform(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform JSON data."""
        try:
            # Validate input
            if not self.validate_input(data):
                raise TransformationValidationError("Invalid JSON input data")
            
            transformed_data = data.copy()
            
            # Apply transformations based on context
            if context.direction == TransformationDirection.OUTBOUND:
                transformed_data = await self._transform_outbound(transformed_data, context)
            else:
                transformed_data = await self._transform_inbound(transformed_data, context)
            
            # Validate output
            if not self.validate_output(transformed_data):
                raise TransformationValidationError("Invalid JSON output data")
            
            return transformed_data
            
        except Exception as e:
            raise TransformationError(f"JSON transformation failed: {e}")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate JSON input data."""
        return isinstance(data, dict)
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate JSON output data."""
        return isinstance(data, dict)
    
    async def _transform_outbound(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform outbound JSON data."""
        # Add metadata
        if self.config.get('add_metadata', True):
            data['_metadata'] = {
                'transformed_at': timezone.now().isoformat(),
                'integration': context.integration_name,
                'version': context.version
            }
        
        # Remove sensitive fields
        sensitive_fields = self.config.get('sensitive_fields', [])
        for field in sensitive_fields:
            data.pop(field, None)
        
        # Apply field mappings
        field_mappings = self.config.get('field_mappings', [])
        for mapping in field_mappings:
            if mapping.source_field in data:
                value = data[mapping.source_field]
                if mapping.transform_func:
                    value = mapping.transform_func(value)
                data[mapping.target_field] = value
                if mapping.source_field != mapping.target_field:
                    data.pop(mapping.source_field, None)
            elif mapping.default_value is not None:
                data[mapping.target_field] = mapping.default_value
        
        return data
    
    async def _transform_inbound(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform inbound JSON data."""
        # Remove metadata
        data.pop('_metadata', None)
        
        # Apply field mappings (reverse)
        field_mappings = self.config.get('field_mappings', [])
        for mapping in field_mappings:
            if mapping.target_field in data:
                value = data[mapping.target_field]
                if mapping.transform_func:
                    value = mapping.transform_func(value)
                data[mapping.source_field] = value
                if mapping.target_field != mapping.source_field:
                    data.pop(mapping.target_field, None)
        
        return data


class XMLTransformer(DataTransformer):
    """XML data transformer."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize XML transformer."""
        self.config = config or {}
    
    async def transform(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform XML data."""
        try:
            if context.direction == TransformationDirection.OUTBOUND:
                return await self._dict_to_xml(data, context)
            else:
                return await self._xml_to_dict(data, context)
                
        except Exception as e:
            raise TransformationError(f"XML transformation failed: {e}")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate XML input data."""
        return isinstance(data, dict)
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate XML output data."""
        return isinstance(data, dict)
    
    async def _dict_to_xml(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Convert dictionary to XML."""
        root_element = self.config.get('root_element', 'data')
        root = ET.Element(root_element)
        
        def build_xml(element: ET.Element, data: Any) -> None:
            if isinstance(data, dict):
                for key, value in data.items():
                    child = ET.SubElement(element, key)
                    build_xml(child, value)
            elif isinstance(data, list):
                for item in data:
                    child = ET.SubElement(element, 'item')
                    build_xml(child, item)
            else:
                element.text = str(data)
        
        build_xml(root, data)
        
        xml_string = ET.tostring(root, encoding='unicode')
        return {'xml': xml_string}
    
    async def _xml_to_dict(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Convert XML to dictionary."""
        xml_string = data.get('xml', '')
        if not xml_string:
            return {}
        
        try:
            root = ET.fromstring(xml_string)
            return self._element_to_dict(root)
            
        except ET.ParseError as e:
            raise TransformationError(f"XML parsing failed: {e}")
    
    def _element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary."""
        result = {}
        
        # Handle attributes
        if element.attrib:
            result.update(element.attrib)
        
        # Handle text content
        if element.text and element.text.strip():
            if len(element) == 0:  # No children
                return element.text.strip()
        
        # Handle children
        for child in element:
            child_data = self._element_to_dict(child)
            
            if child.tag in result:
                # Multiple children with same tag
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result


class CSVTransformer(DataTransformer):
    """CSV data transformer."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize CSV transformer."""
        self.config = config or {}
    
    async def transform(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform CSV data."""
        try:
            if context.direction == TransformationDirection.OUTBOUND:
                return await self._dict_to_csv(data, context)
            else:
                return await self._csv_to_dict(data, context)
                
        except Exception as e:
            raise TransformationError(f"CSV transformation failed: {e}")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate CSV input data."""
        return isinstance(data, dict)
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate CSV output data."""
        return isinstance(data, dict)
    
    async def _dict_to_csv(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Convert dictionary to CSV."""
        records = data.get('records', [])
        if not records:
            return {'csv': ''}
        
        delimiter = self.config.get('delimiter', ',')
        quote_char = self.config.get('quote_char', '"')
        
        output = io.StringIO()
        
        if records:
            # Get headers from first record or config
            headers = self.config.get('headers', list(records[0].keys()))
            
            writer = csv.DictWriter(
                output,
                fieldnames=headers,
                delimiter=delimiter,
                quotechar=quote_char
            )
            
            writer.writeheader()
            writer.writerows(records)
        
        csv_string = output.getvalue()
        output.close()
        
        return {'csv': csv_string}
    
    async def _csv_to_dict(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Convert CSV to dictionary."""
        csv_string = data.get('csv', '')
        if not csv_string:
            return {'records': []}
        
        delimiter = self.config.get('delimiter', ',')
        quote_char = self.config.get('quote_char', '"')
        
        input_stream = io.StringIO(csv_string)
        
        reader = csv.DictReader(
            input_stream,
            delimiter=delimiter,
            quotechar=quote_char
        )
        
        records = list(reader)
        input_stream.close()
        
        return {'records': records}


class YAMLTransformer(DataTransformer):
    """YAML data transformer."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize YAML transformer."""
        self.config = config or {}
    
    async def transform(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform YAML data."""
        try:
            if context.direction == TransformationDirection.OUTBOUND:
                return await self._dict_to_yaml(data, context)
            else:
                return await self._yaml_to_dict(data, context)
                
        except Exception as e:
            raise TransformationError(f"YAML transformation failed: {e}")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate YAML input data."""
        return isinstance(data, dict)
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate YAML output data."""
        return isinstance(data, dict)
    
    async def _dict_to_yaml(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Convert dictionary to YAML."""
        yaml_string = yaml.dump(
            data,
            default_flow_style=False,
            sort_keys=self.config.get('sort_keys', False)
        )
        
        return {'yaml': yaml_string}
    
    async def _yaml_to_dict(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Convert YAML to dictionary."""
        yaml_string = data.get('yaml', '')
        if not yaml_string:
            return {}
        
        try:
            yaml_data = yaml.safe_load(yaml_string)
            return yaml_data if isinstance(yaml_data, dict) else {}
            
        except yaml.YAMLError as e:
            raise TransformationError(f"YAML parsing failed: {e}")


class FieldMappingTransformer(DataTransformer):
    """Field mapping transformer."""
    
    def __init__(self, field_mappings: List[FieldMapping]):
        """Initialize field mapping transformer."""
        self.field_mappings = field_mappings
    
    async def transform(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform data using field mappings."""
        try:
            transformed_data = {}
            
            for mapping in self.field_mappings:
                source_value = data.get(mapping.source_field)
                
                if source_value is not None:
                    # Apply transformation function
                    if mapping.transform_func:
                        source_value = mapping.transform_func(source_value)
                    
                    # Apply validation
                    if mapping.validation_func and not mapping.validation_func(source_value):
                        if mapping.required:
                            raise TransformationValidationError(
                                f"Field validation failed for {mapping.source_field}"
                            )
                        continue
                    
                    transformed_data[mapping.target_field] = source_value
                
                elif mapping.default_value is not None:
                    transformed_data[mapping.target_field] = mapping.default_value
                
                elif mapping.required:
                    raise TransformationValidationError(
                        f"Required field missing: {mapping.source_field}"
                    )
            
            return transformed_data
            
        except Exception as e:
            raise TransformationError(f"Field mapping transformation failed: {e}")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        return isinstance(data, dict)
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate output data."""
        return isinstance(data, dict)


class CompositeTransformer(DataTransformer):
    """Composite transformer that chains multiple transformers."""
    
    def __init__(self, transformers: List[DataTransformer]):
        """Initialize composite transformer."""
        self.transformers = transformers
    
    async def transform(self, data: Dict[str, Any], context: TransformationContext) -> Dict[str, Any]:
        """Transform data using multiple transformers in sequence."""
        transformed_data = data.copy()
        
        for transformer in self.transformers:
            transformed_data = await transformer.transform(transformed_data, context)
        
        return transformed_data
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        if not self.transformers:
            return True
        
        return self.transformers[0].validate_input(data)
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate output data."""
        if not self.transformers:
            return True
        
        return self.transformers[-1].validate_output(data)


class TransformationRegistry:
    """Registry for data transformation rules and transformers."""
    
    def __init__(self):
        """Initialize transformation registry."""
        self.transformers: Dict[str, DataTransformer] = {}
        self.rules: List[TransformationRule] = []
        
        # Register built-in transformers
        self._register_builtin_transformers()
        
        logger.info("TransformationRegistry initialized")
    
    def _register_builtin_transformers(self) -> None:
        """Register built-in transformers."""
        self.transformers['json'] = JSONTransformer()
        self.transformers['xml'] = XMLTransformer()
        self.transformers['csv'] = CSVTransformer()
        self.transformers['yaml'] = YAMLTransformer()
    
    def register_transformer(self, name: str, transformer: DataTransformer) -> None:
        """Register a custom transformer."""
        self.transformers[name] = transformer
        logger.info(f"Registered transformer: {name}")
    
    def register_rule(self, rule: TransformationRule) -> None:
        """Register a transformation rule."""
        self.rules.append(rule)
        logger.info(f"Registered transformation rule: {rule.name}")
    
    def get_transformer(self, name: str) -> Optional[DataTransformer]:
        """Get transformer by name."""
        return self.transformers.get(name)
    
    def find_rules(self, source_format: DataFormat, target_format: DataFormat,
                   direction: TransformationDirection) -> List[TransformationRule]:
        """Find transformation rules matching criteria."""
        matching_rules = [
            rule for rule in self.rules
            if (rule.source_format == source_format and
                rule.target_format == target_format and
                rule.direction == direction and
                rule.enabled)
        ]
        
        # Sort by priority
        matching_rules.sort(key=lambda r: r.priority)
        return matching_rules
    
    async def transform(self, data: Dict[str, Any], source_format: DataFormat,
                      target_format: DataFormat, direction: TransformationDirection,
                      context: TransformationContext) -> Dict[str, Any]:
        """Transform data using registered rules."""
        rules = self.find_rules(source_format, target_format, direction)
        
        if not rules:
            raise TransformationError(
                f"No transformation rule found for {source_format.value} -> {target_format.value}"
            )
        
        # Use first matching rule
        rule = rules[0]
        return await rule.transformer_func(data, context)


# Global transformation registry
_transformation_registry = None


def get_transformation_registry() -> TransformationRegistry:
    """Get global transformation registry instance."""
    global _transformation_registry
    if _transformation_registry is None:
        _transformation_registry = TransformationRegistry()
    return _transformation_registry


# Convenience functions
async def transform_data(data: Dict[str, Any], source_format: DataFormat,
                       target_format: DataFormat, direction: TransformationDirection,
                       integration_name: str, version: str = "1.0") -> Dict[str, Any]:
    """
    Convenience function for data transformation.
    
    Args:
        data: Data to transform
        source_format: Source data format
        target_format: Target data format
        direction: Transformation direction
        integration_name: Integration name
        version: Integration version
        
    Returns:
        Transformed data
    """
    registry = get_transformation_registry()
    
    context = TransformationContext(
        integration_name=integration_name,
        version=version,
        direction=direction
    )
    
    return await registry.transform(data, source_format, target_format, direction, context)


async def transform_request(data: Dict[str, Any], integration_name: str,
                          version: str = "1.0") -> Dict[str, Any]:
    """
    Transform request data (outbound transformation).
    
    Args:
        data: Request data
        integration_name: Integration name
        version: Integration version
        
    Returns:
        Transformed request data
    """
    return await transform_data(
        data, DataFormat.JSON, DataFormat.JSON,
        TransformationDirection.OUTBOUND, integration_name, version
    )


async def transform_response(data: Dict[str, Any], integration_name: str,
                           version: str = "1.0") -> Dict[str, Any]:
    """
    Transform response data (inbound transformation).
    
    Args:
        data: Response data
        integration_name: Integration name
        version: Integration version
        
    Returns:
        Transformed response data
    """
    return await transform_data(
        data, DataFormat.JSON, DataFormat.JSON,
        TransformationDirection.INBOUND, integration_name, version
    )


# Utility functions for common transformations
def snake_case_to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])


def camel_case_to_snake_case(camel_str: str) -> str:
    """Convert camelCase to snake_case."""
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def normalize_timestamp(timestamp: Any) -> datetime:
    """Normalize timestamp to datetime object."""
    if isinstance(timestamp, datetime):
        return timestamp
    elif isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return timezone.now()
    elif isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    else:
        return timezone.now()


def sanitize_string(value: Any) -> str:
    """Sanitize string value."""
    if value is None:
        return ""
    
    str_value = str(value)
    # Remove potentially dangerous characters
    import re
    sanitized = re.sub(r'[<>"\']', '', str_value)
    return sanitized.strip()


def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_url(url: str) -> bool:
    """Validate URL format."""
    import re
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return re.match(pattern, url) is not None
