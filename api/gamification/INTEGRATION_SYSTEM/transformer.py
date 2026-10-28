"""
Data Transformer — Data transformation and mapping system.

This module provides comprehensive data transformation capabilities
for converting data between different formats, schemas, and structures.
"""

from __future__ import annotations
import threading

import logging
import json
import xml.etree.ElementTree as ET
import yaml
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import (
    IntegrationError, DataFormatError, ValidationError,
    DataCorruptionError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transformation Types
# ---------------------------------------------------------------------------

class TransformationType(Enum):
    """Transformation type enumeration."""
    FORMAT_CONVERSION = "format_conversion"
    SCHEMA_MAPPING = "schema_mapping"
    FIELD_MAPPING = "field_mapping"
    VALUE_MAPPING = "value_mapping"
    DATA_ENRICHMENT = "data_enrichment"
    DATA_FILTERING = "data_filtering"
    DATA_AGGREGATION = "data_aggregation"
    DATA_VALIDATION = "data_validation"
    CUSTOM = "custom"


class DataFormat(Enum):
    """Data format enumeration."""
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    CSV = "csv"
    TSV = "tsv"
    PLAIN_TEXT = "plain_text"
    BINARY = "binary"
    FORM_URLENCODED = "form_urlencoded"


class TransformationDirection(Enum):
    """Transformation direction enumeration."""
    FORWARD = "forward"
    REVERSE = "reverse"
    BIDIRECTIONAL = "bidirectional"


# ---------------------------------------------------------------------------
# Transformation Data Classes
# ---------------------------------------------------------------------------

@dataclass
class TransformationRule:
    """Rule for data transformation."""
    
    id: str
    name: str
    transformation_type: TransformationType
    source_format: Optional[DataFormat] = None
    target_format: Optional[DataFormat] = None
    field_mappings: Dict[str, str] = field(default_factory=dict)
    value_mappings: Dict[str, Dict[Any, Any]] = field(default_factory=dict)
    filters: List[Dict[str, Any]] = field(default_factory=list)
    validations: List[Dict[str, Any]] = field(default_factory=list)
    enrichment_rules: List[Dict[str, Any]] = field(default_factory=list)
    custom_function: Optional[Callable] = None
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "transformation_type": self.transformation_type.value,
            "source_format": self.source_format.value if self.source_format else None,
            "target_format": self.target_format.value if self.target_format else None,
            "field_mappings": self.field_mappings,
            "value_mappings": self.value_mappings,
            "filters": self.filters,
            "validations": self.validations,
            "enrichment_rules": self.enrichment_rules,
            "custom_function": self.custom_function.__name__ if self.custom_function else None,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": self.metadata
        }


@dataclass
class TransformationResult:
    """Result of a data transformation."""
    
    success: bool
    source_data: Any
    transformed_data: Any
    transformation_id: str
    execution_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "source_data": self.source_data,
            "transformed_data": self.transformed_data,
            "transformation_id": self.transformation_id,
            "execution_time": self.execution_time,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class TransformationMetrics:
    """Metrics for transformation operations."""
    
    transformation_id: str
    total_transformations: int = 0
    successful_transformations: int = 0
    failed_transformations: int = 0
    average_execution_time: float = 0.0
    total_execution_time: float = 0.0
    last_transformation_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_transformations == 0:
            return 0.0
        return self.successful_transformations / self.total_transformations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transformation_id": self.transformation_id,
            "total_transformations": self.total_transformations,
            "successful_transformations": self.successful_transformations,
            "failed_transformations": self.failed_transformations,
            "success_rate": self.success_rate,
            "average_execution_time": self.average_execution_time,
            "total_execution_time": self.total_execution_time,
            "last_transformation_time": self.last_transformation_time.isoformat() if self.last_transformation_time else None
        }


# ---------------------------------------------------------------------------
# Abstract Transformer Base Class
# ---------------------------------------------------------------------------

class BaseTransformer(ABC):
    """Abstract base class for data transformers."""
    
    def __init__(self, rule: TransformationRule):
        self.rule = rule
        self.metrics = TransformationMetrics(transformation_id=rule.id)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def transformation_type(self) -> TransformationType:
        """Get the transformation type."""
        pass
    
    @abstractmethod
    def transform(self, data: Any, direction: TransformationDirection = TransformationDirection.FORWARD) -> TransformationResult:
        """Transform data according to the rule."""
        pass
    
    @abstractmethod
    def validate_rule(self) -> List[str]:
        """Validate the transformation rule."""
        pass
    
    def get_metrics(self) -> TransformationMetrics:
        """Get transformation metrics."""
        return self.metrics
    
    def _update_metrics(self, success: bool, execution_time: float) -> None:
        """Update transformation metrics."""
        self.metrics.total_transformations += 1
        self.metrics.total_execution_time += execution_time
        self.metrics.last_transformation_time = datetime.now(timezone.utc)
        
        if success:
            self.metrics.successful_transformations += 1
        else:
            self.metrics.failed_transformations += 1
        
        # Update average execution time
        if self.metrics.total_transformations > 0:
            self.metrics.average_execution_time = (
                self.metrics.total_execution_time / self.metrics.total_transformations
            )


# ---------------------------------------------------------------------------
# Format Conversion Transformers
# ---------------------------------------------------------------------------

class JSONToXMLTransformer(BaseTransformer):
    """Transformer for converting JSON to XML."""
    
    @property
    def transformation_type(self) -> TransformationType:
        return TransformationType.FORMAT_CONVERSION
    
    def transform(self, data: Any, direction: TransformationDirection = TransformationDirection.FORWARD) -> TransformationResult:
        """Transform JSON data to XML or XML to JSON."""
        import time
        start_time = time.time()
        
        try:
            if direction == TransformationDirection.FORWARD:
                # JSON to XML
                if isinstance(data, str):
                    json_data = json.loads(data)
                else:
                    json_data = data
                
                transformed_data = self._json_to_xml(json_data)
            else:
                # XML to JSON
                if isinstance(data, str):
                    xml_data = data
                else:
                    xml_data = str(data)
                
                transformed_data = self._xml_to_json(xml_data)
            
            execution_time = time.time() - start_time
            self._update_metrics(True, execution_time)
            
            return TransformationResult(
                success=True,
                source_data=data,
                transformed_data=transformed_data,
                transformation_id=self.rule.id,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)
            
            return TransformationResult(
                success=False,
                source_data=data,
                transformed_data=None,
                transformation_id=self.rule.id,
                execution_time=execution_time,
                errors=[str(e)]
            )
    
    def validate_rule(self) -> List[str]:
        """Validate the transformation rule."""
        errors = []
        
        if self.rule.transformation_type != TransformationType.FORMAT_CONVERSION:
            errors.append("Invalid transformation type for JSONToXMLTransformer")
        
        if self.rule.source_format != DataFormat.JSON:
            errors.append("Source format must be JSON")
        
        if self.rule.target_format != DataFormat.XML:
            errors.append("Target format must be XML")
        
        return errors
    
    def _json_to_xml(self, json_data: Dict[str, Any]) -> str:
        """Convert JSON data to XML."""
        root = ET.Element("root")
        
        def _build_xml(element: ET.Element, data: Any) -> None:
            if isinstance(data, dict):
                for key, value in data.items():
                    child = ET.SubElement(element, key)
                    _build_xml(child, value)
            elif isinstance(data, list):
                for item in data:
                    child = ET.SubElement(element, "item")
                    _build_xml(child, item)
            else:
                element.text = str(data)
        
        _build_xml(root, json_data)
        return ET.tostring(root, encoding='unicode')
    
    def _xml_to_json(self, xml_data: str) -> Dict[str, Any]:
        """Convert XML data to JSON."""
        root = ET.fromstring(xml_data)
        
        def _build_dict(element: ET.Element) -> Dict[str, Any]:
            result = {}
            
            for child in element:
                if len(child) == 0:
                    # Leaf node
                    if child.text:
                        result[child.tag] = child.text
                    else:
                        result[child.tag] = None
                else:
                    # Has children
                    if child.tag in result:
                        # Multiple children with same tag
                        if not isinstance(result[child.tag], list):
                            result[child.tag] = [result[child.tag]]
                        result[child.tag].append(_build_dict(child))
                    else:
                        result[child.tag] = _build_dict(child)
            
            return result
        
        return _build_dict(root)


class JSONToYAMLTransformer(BaseTransformer):
    """Transformer for converting JSON to YAML."""
    
    @property
    def transformation_type(self) -> TransformationType:
        return TransformationType.FORMAT_CONVERSION
    
    def transform(self, data: Any, direction: TransformationDirection = TransformationDirection.FORWARD) -> TransformationResult:
        """Transform JSON data to YAML or YAML to JSON."""
        import time
        start_time = time.time()
        
        try:
            if direction == TransformationDirection.FORWARD:
                # JSON to YAML
                if isinstance(data, str):
                    json_data = json.loads(data)
                else:
                    json_data = data
                
                transformed_data = yaml.dump(json_data, default_flow_style=False)
            else:
                # YAML to JSON
                if isinstance(data, str):
                    yaml_data = data
                else:
                    yaml_data = str(data)
                
                transformed_data = yaml.safe_load(yaml_data)
            
            execution_time = time.time() - start_time
            self._update_metrics(True, execution_time)
            
            return TransformationResult(
                success=True,
                source_data=data,
                transformed_data=transformed_data,
                transformation_id=self.rule.id,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)
            
            return TransformationResult(
                success=False,
                source_data=data,
                transformed_data=None,
                transformation_id=self.rule.id,
                execution_time=execution_time,
                errors=[str(e)]
            )
    
    def validate_rule(self) -> List[str]:
        """Validate the transformation rule."""
        errors = []
        
        if self.rule.transformation_type != TransformationType.FORMAT_CONVERSION:
            errors.append("Invalid transformation type for JSONToYAMLTransformer")
        
        if self.rule.source_format != DataFormat.JSON:
            errors.append("Source format must be JSON")
        
        if self.rule.target_format != DataFormat.YAML:
            errors.append("Target format must be YAML")
        
        return errors


# ---------------------------------------------------------------------------
# Field Mapping Transformer
# ---------------------------------------------------------------------------

class FieldMappingTransformer(BaseTransformer):
    """Transformer for mapping fields between different schemas."""
    
    @property
    def transformation_type(self) -> TransformationType:
        return TransformationType.FIELD_MAPPING
    
    def transform(self, data: Any, direction: TransformationDirection = TransformationDirection.FORWARD) -> TransformationResult:
        """Transform data by mapping fields."""
        import time
        start_time = time.time()
        
        try:
            if not isinstance(data, dict):
                raise DataFormatError("Data must be a dictionary for field mapping")
            
            transformed_data = {}
            
            # Apply field mappings
            for source_field, target_field in self.rule.field_mappings.items():
                if source_field in data:
                    transformed_data[target_field] = data[source_field]
            
            # Apply value mappings
            for field, mapping in self.rule.value_mappings.items():
                if field in transformed_data and transformed_data[field] in mapping:
                    transformed_data[field] = mapping[transformed_data[field]]
            
            # Apply filters
            filtered_data = self._apply_filters(transformed_data)
            
            # Apply validations
            validation_errors = self._apply_validations(filtered_data)
            
            execution_time = time.time() - start_time
            self._update_metrics(len(validation_errors) == 0, execution_time)
            
            return TransformationResult(
                success=len(validation_errors) == 0,
                source_data=data,
                transformed_data=filtered_data,
                transformation_id=self.rule.id,
                execution_time=execution_time,
                errors=validation_errors
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)
            
            return TransformationResult(
                success=False,
                source_data=data,
                transformed_data=None,
                transformation_id=self.rule.id,
                execution_time=execution_time,
                errors=[str(e)]
            )
    
    def validate_rule(self) -> List[str]:
        """Validate the transformation rule."""
        errors = []
        
        if self.rule.transformation_type != TransformationType.FIELD_MAPPING:
            errors.append("Invalid transformation type for FieldMappingTransformer")
        
        if not self.rule.field_mappings:
            errors.append("Field mappings are required")
        
        return errors
    
    def _apply_filters(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply filters to data."""
        filtered_data = data.copy()
        
        for filter_rule in self.rule.filters:
            filter_type = filter_rule.get("type")
            
            if filter_type == "exclude_fields":
                exclude_fields = filter_rule.get("fields", [])
                for field in exclude_fields:
                    filtered_data.pop(field, None)
            
            elif filter_type == "include_fields":
                include_fields = filter_rule.get("fields", [])
                filtered_data = {k: v for k, v in filtered_data.items() if k in include_fields}
            
            elif filter_type == "remove_null":
                filtered_data = {k: v for k, v in filtered_data.items() if v is not None}
            
            elif filter_type == "remove_empty":
                filtered_data = {k: v for k, v in filtered_data.items() if v != ""}
        
        return filtered_data
    
    def _apply_validations(self, data: Dict[str, Any]) -> List[str]:
        """Apply validations to data."""
        errors = []
        
        for validation in self.rule.validations:
            validation_type = validation.get("type")
            field = validation.get("field")
            
            if validation_type == "required":
                if field not in data or data[field] is None:
                    errors.append(f"Required field '{field}' is missing or null")
            
            elif validation_type == "type":
                expected_type = validation.get("expected_type")
                if field in data and not isinstance(data[field], eval(expected_type)):
                    errors.append(f"Field '{field}' must be of type {expected_type}")
            
            elif validation_type == "min_length":
                min_length = validation.get("min_length")
                if field in data and len(str(data[field])) < min_length:
                    errors.append(f"Field '{field}' must be at least {min_length} characters")
            
            elif validation_type == "max_length":
                max_length = validation.get("max_length")
                if field in data and len(str(data[field])) > max_length:
                    errors.append(f"Field '{field}' must be at most {max_length} characters")
        
        return errors


# ---------------------------------------------------------------------------
# Custom Transformer
# ---------------------------------------------------------------------------

class CustomTransformer(BaseTransformer):
    """Transformer that uses a custom function."""
    
    @property
    def transformation_type(self) -> TransformationType:
        return TransformationType.CUSTOM
    
    def transform(self, data: Any, direction: TransformationDirection = TransformationDirection.FORWARD) -> TransformationResult:
        """Transform data using custom function."""
        import time
        start_time = time.time()
        
        try:
            if not self.rule.custom_function:
                raise IntegrationError("Custom function is not defined")
            
            transformed_data = self.rule.custom_function(data, direction)
            
            execution_time = time.time() - start_time
            self._update_metrics(True, execution_time)
            
            return TransformationResult(
                success=True,
                source_data=data,
                transformed_data=transformed_data,
                transformation_id=self.rule.id,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)
            
            return TransformationResult(
                success=False,
                source_data=data,
                transformed_data=None,
                transformation_id=self.rule.id,
                execution_time=execution_time,
                errors=[str(e)]
            )
    
    def validate_rule(self) -> List[str]:
        """Validate the transformation rule."""
        errors = []
        
        if self.rule.transformation_type != TransformationType.CUSTOM:
            errors.append("Invalid transformation type for CustomTransformer")
        
        if not self.rule.custom_function:
            errors.append("Custom function is required")
        
        return errors


# ---------------------------------------------------------------------------
# Transformation Engine
# ---------------------------------------------------------------------------

class TransformationEngine:
    """Engine for managing and executing transformations."""
    
    def __init__(self):
        self.transformers: Dict[str, BaseTransformer] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()  # Need to import threading
    
    def register_transformer(self, transformer: BaseTransformer) -> None:
        """Register a transformer."""
        with self._lock:
            if transformer.rule.id in self.transformers:
                raise IntegrationError(f"Transformer with ID '{transformer.rule.id}' already exists")
            
            # Validate rule
            errors = transformer.validate_rule()
            if errors:
                raise ValidationError(f"Invalid transformation rule: {', '.join(errors)}")
            
            self.transformers[transformer.rule.id] = transformer
            self.logger.info(f"Registered transformer: {transformer.rule.id}")
    
    def unregister_transformer(self, transformer_id: str) -> bool:
        """Unregister a transformer."""
        with self._lock:
            if transformer_id in self.transformers:
                del self.transformers[transformer_id]
                self.logger.info(f"Unregistered transformer: {transformer_id}")
                return True
            return False
    
    def get_transformer(self, transformer_id: str) -> Optional[BaseTransformer]:
        """Get a transformer by ID."""
        with self._lock:
            return self.transformers.get(transformer_id)
    
    def list_transformers(self, transformation_type: Optional[TransformationType] = None) -> List[BaseTransformer]:
        """List transformers with optional filtering."""
        with self._lock:
            transformers = list(self.transformers.values())
            
            if transformation_type:
                transformers = [t for t in transformers if t.transformation_type == transformation_type]
            
            return transformers
    
    def transform_data(
        self,
        transformer_id: str,
        data: Any,
        direction: TransformationDirection = TransformationDirection.FORWARD
    ) -> TransformationResult:
        """Transform data using a specific transformer."""
        transformer = self.get_transformer(transformer_id)
        if not transformer:
            raise IntegrationNotFoundError(f"Transformer '{transformer_id}' not found")
        
        return transformer.transform(data, direction)
    
    def transform_chain(
        self,
        transformer_ids: List[str],
        data: Any,
        direction: TransformationDirection = TransformationDirection.FORWARD
    ) -> List[TransformationResult]:
        """Transform data through a chain of transformers."""
        results = []
        current_data = data
        
        for transformer_id in transformer_ids:
            result = self.transform_data(transformer_id, current_data, direction)
            results.append(result)
            
            if result.success:
                current_data = result.transformed_data
            else:
                # Stop chain on failure
                break
        
        return results
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all transformers."""
        metrics = {}
        
        for transformer_id, transformer in self.transformers.items():
            metrics[transformer_id] = transformer.get_metrics().to_dict()
        
        return {
            "transformers": metrics,
            "total_transformers": len(self.transformers),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def create_transformer_from_rule(self, rule: TransformationRule) -> BaseTransformer:
        """Create a transformer from a rule."""
        if rule.transformation_type == TransformationType.FORMAT_CONVERSION:
            if rule.source_format == DataFormat.JSON and rule.target_format == DataFormat.XML:
                return JSONToXMLTransformer(rule)
            elif rule.source_format == DataFormat.JSON and rule.target_format == DataFormat.YAML:
                return JSONToYAMLTransformer(rule)
            else:
                raise IntegrationError(f"Unsupported format conversion: {rule.source_format} to {rule.target_format}")
        
        elif rule.transformation_type == TransformationType.FIELD_MAPPING:
            return FieldMappingTransformer(rule)
        
        elif rule.transformation_type == TransformationType.CUSTOM:
            return CustomTransformer(rule)
        
        else:
            raise IntegrationError(f"Unsupported transformation type: {rule.transformation_type}")


# Global transformation engine instance
transformation_engine = TransformationEngine()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_field_mapping_transformer(
    transformer_id: str,
    name: str,
    field_mappings: Dict[str, str],
    **kwargs: Any
) -> BaseTransformer:
    """Create a field mapping transformer."""
    rule = TransformationRule(
        id=transformer_id,
        name=name,
        transformation_type=TransformationType.FIELD_MAPPING,
        field_mappings=field_mappings,
        **kwargs
    )
    
    transformer = transformation_engine.create_transformer_from_rule(rule)
    transformation_engine.register_transformer(transformer)
    
    return transformer


def transform_fields(
    data: Dict[str, Any],
    field_mappings: Dict[str, str],
    transformer_id: Optional[str] = None
) -> TransformationResult:
    """Transform data fields."""
    if not transformer_id:
        transformer_id = f"field_mapping_{hash(str(field_mappings))}"
        
        # Create temporary transformer
        transformer = create_field_mapping_transformer(
            transformer_id=transformer_id,
            name="Temporary Field Mapping",
            field_mappings=field_mappings
        )
    
    return transformation_engine.transform_data(transformer_id, data)


# Initialize logging
logger.info("Data transformer module initialized")
