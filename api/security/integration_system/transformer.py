"""
Integration Transformer Module
Data transformation system for integration
"""

import logging
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import *

User = get_user_model()
logger = logging.getLogger('security.integration.transformer')


class DataTransformer:
    """Base data transformer"""
    
    def __init__(self, name: str, source_format: str, target_format: str):
        self.name = name
        self.source_format = source_format
        self.target_format = target_format
        self.field_mappings = {}
        self.transformations = {}
        self.validations = {}
        self.enabled = True
        self.statistics = {
            'transformations': 0,
            'successes': 0,
            'failures': 0,
            'last_activity': None
        }
    
    def add_field_mapping(self, source_field: str, target_field: str):
        """Add field mapping"""
        self.field_mappings[source_field] = target_field
    
    def add_transformation(self, field: str, transformation: Callable):
        """Add field transformation"""
        self.transformations[field] = transformation
    
    def add_validation(self, field: str, validation: Callable):
        """Add field validation"""
        self.validations[field] = validation
    
    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data from source to target format"""
        if not self.enabled:
            return data
        
        try:
            self.statistics['transformations'] += 1
            self.statistics['last_activity'] = timezone.now()
            
            # Create transformed data
            transformed = {}
            
            # Apply field mappings and transformations
            for source_field, target_field in self.field_mappings.items():
                if source_field in data:
                    value = data[source_field]
                    
                    # Apply transformation if exists
                    if source_field in self.transformations:
                        try:
                            value = self.transformations[source_field](value)
                        except Exception as e:
                            logger.error(f"Error in transformation for field {source_field}: {e}")
                            continue
                    
                    # Apply validation if exists
                    if target_field in self.validations:
                        try:
                            if not self.validations[target_field](value):
                                logger.warning(f"Validation failed for field {target_field}")
                                continue
                        except Exception as e:
                            logger.error(f"Error in validation for field {target_field}: {e}")
                            continue
                    
                    transformed[target_field] = value
            
            # Add unmapped fields
            for field, value in data.items():
                if field not in self.field_mappings:
                    transformed[field] = value
            
            self.statistics['successes'] += 1
            return transformed
            
        except Exception as e:
            self.statistics['failures'] += 1
            logger.error(f"Error in transformer {self.name}: {e}")
            return data
    
    def enable(self):
        """Enable transformer"""
        self.enabled = True
    
    def disable(self):
        """Disable transformer"""
        self.enabled = False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get transformer statistics"""
        total = self.statistics['transformations']
        success_rate = (self.statistics['successes'] / total) if total > 0 else 0
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'source_format': self.source_format,
            'target_format': self.target_format,
            'field_mappings_count': len(self.field_mappings),
            'transformations_count': len(self.transformations),
            'validations_count': len(self.validations),
            'statistics': {
                **self.statistics,
                'success_rate': success_rate
            }
        }


class JSONTransformer(DataTransformer):
    """JSON data transformer"""
    
    def __init__(self, name: str):
        super().__init__(name, 'json', 'json')
    
    def transform_json(self, json_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Transform JSON data"""
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON data: {e}")
                return {}
        else:
            data = json_data
        
        return self.transform(data)
    
    def transform_to_json(self, data: Dict[str, Any]) -> str:
        """Transform data to JSON string"""
        transformed_data = self.transform(data)
        return json.dumps(transformed_data, default=str)


class XMLTransformer(DataTransformer):
    """XML data transformer"""
    
    def __init__(self, name: str):
        super().__init__(name, 'xml', 'json')
        self.root_element = 'root'
        self.namespace = None
    
    def set_root_element(self, root_element: str):
        """Set root element name"""
        self.root_element = root_element
    
    def set_namespace(self, namespace: str):
        """Set XML namespace"""
        self.namespace = namespace
    
    def xml_to_dict(self, xml_data: str) -> Dict[str, Any]:
        """Convert XML to dictionary"""
        try:
            root = ET.fromstring(xml_data)
            return self._element_to_dict(root)
        except ET.ParseError as e:
            logger.error(f"Invalid XML data: {e}")
            return {}
    
    def _element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary"""
        result = {}
        
        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Add text content
        if element.text and element.text.strip():
            if len(element) == 0:
                return element.text.strip()
            else:
                result['#text'] = element.text.strip()
        
        # Add children
        for child in element:
            child_data = self._element_to_dict(child)
            
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result
    
    def dict_to_xml(self, data: Dict[str, Any]) -> str:
        """Convert dictionary to XML"""
        transformed_data = self.transform(data)
        root = ET.Element(self.root_element)
        
        if self.namespace:
            root.set('xmlns', self.namespace)
        
        self._dict_to_element(transformed_data, root)
        
        return ET.tostring(root, encoding='unicode')
    
    def _dict_to_element(self, data: Any, parent: ET.Element):
        """Convert dictionary to XML element"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key == '@attributes':
                    parent.attrib.update(value)
                elif key == '#text':
                    parent.text = str(value)
                else:
                    child = ET.SubElement(parent, key)
                    self._dict_to_element(value, child)
        elif isinstance(data, list):
            for item in data:
                child = ET.SubElement(parent, 'item')
                self._dict_to_element(item, child)
        else:
            parent.text = str(data)


class CSVTransformer(DataTransformer):
    """CSV data transformer"""
    
    def __init__(self, name: str):
        super().__init__(name, 'csv', 'json')
        self.delimiter = ','
        self.quotechar = '"'
        self.headers = True
    
    def set_delimiter(self, delimiter: str):
        """Set CSV delimiter"""
        self.delimiter = delimiter
    
    def set_quotechar(self, quotechar: str):
        """Set CSV quote character"""
        self.quotechar = quotechar
    
    def set_headers(self, headers: bool):
        """Set whether CSV has headers"""
        self.headers = headers
    
    def csv_to_dict(self, csv_data: str) -> List[Dict[str, Any]]:
        """Convert CSV to list of dictionaries"""
        import csv
        import io
        
        try:
            reader = csv.DictReader(
                io.StringIO(csv_data),
                delimiter=self.delimiter,
                quotechar=self.quotechar
            )
            
            data = []
            for row in reader:
                transformed_row = self.transform(row)
                data.append(transformed_row)
            
            return data
            
        except Exception as e:
            logger.error(f"Error parsing CSV data: {e}")
            return []
    
    def dict_to_csv(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """Convert dictionary/list to CSV"""
        import csv
        import io
        
        if isinstance(data, dict):
            data = [data]
        
        if not data:
            return ''
        
        # Transform data
        transformed_data = [self.transform(row) for row in data]
        
        # Get all field names
        fieldnames = set()
        for row in transformed_data:
            fieldnames.update(row.keys())
        
        fieldnames = sorted(fieldnames)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            delimiter=self.delimiter,
            quotechar=self.quotechar
        )
        
        writer.writeheader()
        for row in transformed_data:
            writer.writerow(row)
        
        return output.getvalue()


class FlatFileTransformer(DataTransformer):
    """Flat file data transformer"""
    
    def __init__(self, name: str):
        super().__init__(name, 'flat', 'json')
        self.field_positions = {}
        self.field_lengths = {}
        self.line_terminator = '\n'
    
    def add_field_position(self, field: str, start: int, length: int):
        """Add field position and length"""
        self.field_positions[field] = start
        self.field_lengths[field] = length
    
    def flat_to_dict(self, flat_data: str) -> Dict[str, Any]:
        """Convert flat file data to dictionary"""
        try:
            data = {}
            
            for field, start in self.field_positions.items():
                length = self.field_lengths.get(field, 0)
                end = start + length
                value = flat_data[start:end].strip()
                
                if value:
                    data[field] = value
            
            return self.transform(data)
            
        except Exception as e:
            logger.error(f"Error parsing flat file data: {e}")
            return {}
    
    def dict_to_flat(self, data: Dict[str, Any]) -> str:
        """Convert dictionary to flat file format"""
        transformed_data = self.transform(data)
        
        # Create fixed-width record
        record = [' '] * max(self.field_positions.values()) + max(self.field_lengths.values())
        
        for field, start in self.field_positions.items():
            length = self.field_lengths.get(field, 0)
            value = str(transformed_data.get(field, ''))[:length]
            record[start:start + length] = value.ljust(length)
        
        return ''.join(record)


class TransformerRegistry:
    """Registry for data transformers"""
    
    def __init__(self):
        self.transformers = {}
        self.transformer_chains = {}
        self.global_transformations = {}
        self.enabled = True
    
    def register_transformer(self, transformer: DataTransformer):
        """Register transformer"""
        self.transformers[transformer.name] = transformer
        logger.info(f"Registered transformer: {transformer.name}")
    
    def unregister_transformer(self, transformer_name: str) -> bool:
        """Unregister transformer"""
        if transformer_name in self.transformers:
            del self.transformers[transformer_name]
            logger.info(f"Unregistered transformer: {transformer_name}")
            return True
        return False
    
    def get_transformer(self, transformer_name: str) -> Optional[DataTransformer]:
        """Get transformer by name"""
        return self.transformers.get(transformer_name)
    
    def create_transformer(self, transformer_type: str, name: str, **kwargs) -> Optional[DataTransformer]:
        """Create transformer of specific type"""
        if transformer_type == 'json':
            transformer = JSONTransformer(name)
        elif transformer_type == 'xml':
            transformer = XMLTransformer(name)
        elif transformer_type == 'csv':
            transformer = CSVTransformer(name)
        elif transformer_type == 'flat':
            transformer = FlatFileTransformer(name)
        else:
            logger.error(f"Unknown transformer type: {transformer_type}")
            return None
        
        self.register_transformer(transformer)
        return transformer
    
    def create_transformer_chain(self, chain_name: str, transformer_names: List[str]):
        """Create transformer chain"""
        self.transformer_chains[chain_name] = transformer_names
        logger.info(f"Created transformer chain: {chain_name}")
    
    def transform_with_chain(self, chain_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data using transformer chain"""
        if chain_name not in self.transformer_chains:
            logger.error(f"Transformer chain not found: {chain_name}")
            return data
        
        transformer_names = self.transformer_chains[chain_name]
        result = data
        
        for transformer_name in transformer_names:
            transformer = self.get_transformer(transformer_name)
            if transformer:
                result = transformer.transform(result)
            else:
                logger.error(f"Transformer not found in chain: {transformer_name}")
                break
        
        return result
    
    def add_global_transformation(self, transformation_name: str, transformation: Callable):
        """Add global transformation"""
        self.global_transformations[transformation_name] = transformation
        logger.info(f"Added global transformation: {transformation_name}")
    
    def apply_global_transformations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all global transformations to data"""
        result = data.copy()
        
        for transformation_name, transformation in self.global_transformations.items():
            try:
                result = transformation(result)
            except Exception as e:
                logger.error(f"Error in global transformation {transformation_name}: {e}")
        
        return result
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all transformers"""
        return {
            'enabled': self.enabled,
            'total_transformers': len(self.transformers),
            'total_chains': len(self.transformer_chains),
            'global_transformations': len(self.global_transformations),
            'transformers': {
                name: transformer.get_statistics()
                for name, transformer in self.transformers.items()
            },
            'chains': self.transformer_chains
        }
    
    def enable_all_transformers(self):
        """Enable all transformers"""
        for transformer in self.transformers.values():
            transformer.enable()
    
    def disable_all_transformers(self):
        """Disable all transformers"""
        for transformer in self.transformers.values():
            transformer.disable()
    
    def enable(self):
        """Enable transformer registry"""
        self.enabled = True
        logger.info("Transformer registry enabled")
    
    def disable(self):
        """Disable transformer registry"""
        self.enabled = False
        logger.info("Transformer registry disabled")


# Global transformer registry
transformer_registry = TransformerRegistry()


# Built-in transformations
def timestamp_to_iso(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert timestamp fields to ISO format"""
    result = data.copy()
    
    for field, value in result.items():
        if isinstance(value, datetime):
            result[field] = value.isoformat()
        elif 'timestamp' in field.lower() and isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                result[field] = dt.isoformat()
            except ValueError:
                pass
    
    return result


def normalize_severity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize severity field"""
    result = data.copy()
    
    if 'severity' in result:
        severity = str(result['severity']).lower()
        
        # Map various severity values to standard ones
        severity_mapping = {
            'info': 'low',
            'warning': 'medium',
            'error': 'high',
            'critical': 'critical',
            'debug': 'low',
            'notice': 'medium',
            'alert': 'high'
        }
        
        result['severity'] = severity_mapping.get(severity, 'medium')
    
    return result


def add_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add metadata fields"""
    result = data.copy()
    
    if 'metadata' not in result:
        result['metadata'] = {}
    
    # Add common metadata
    result['metadata']['transformed_at'] = timezone.now().isoformat()
    result['metadata']['transformer_version'] = '1.0'
    
    return result


def flatten_nested_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested dictionary"""
    result = {}
    
    def _flatten(obj, prefix=''):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                _flatten(value, new_prefix)
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                new_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
                _flatten(value, new_prefix)
        else:
            result[prefix] = obj
    
    _flatten(data)
    return result


# Register global transformations
transformer_registry.add_global_transformation('timestamp_to_iso', timestamp_to_iso)
transformer_registry.add_global_transformation('normalize_severity', normalize_severity)
transformer_registry.add_global_transformation('add_metadata', add_metadata)
transformer_registry.add_global_transformation('flatten_nested', flatten_nested_data)


# Export symbols
__all__ = [
    'DataTransformer',
    'JSONTransformer',
    'XMLTransformer',
    'CSVTransformer',
    'FlatFileTransformer',
    'TransformerRegistry',
    'transformer_registry',
    'timestamp_to_iso',
    'normalize_severity',
    'add_metadata',
    'flatten_nested_data'
]