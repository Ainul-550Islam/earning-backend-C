"""
schemas.py – Schema definitions and validation for postback module.

Provides comprehensive schema definitions including:
- JSON schema definitions
- Data validation schemas
- API response schemas
- Configuration schemas
"""
import logging
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus, RejectionReason

logger = logging.getLogger(__name__)


class SchemaType(Enum):
    """Schema type enumeration."""
    POSTBACK_REQUEST = "postback_request"
    POSTBACK_RESPONSE = "postback_response"
    NETWORK_CONFIG = "network_config"
    INSIGHT_DATA = "insight_data"
    ANALYTICS_REPORT = "analytics_report"


class SchemaValidator:
    """
    JSON schema validator for postback data.
    
    Provides validation against defined schemas with detailed
    error reporting and performance monitoring.
    """
    
    def __init__(self):
        self.schemas = {}
        self.validation_history = []
        self._load_builtin_schemas()
    
    def _load_builtin_schemas(self):
        """Load built-in schemas."""
        self.schemas[SchemaType.POSTBACK_REQUEST.value] = self._get_postback_request_schema()
        self.schemas[SchemaType.POSTBACK_RESPONSE.value] = self._get_postback_response_schema()
        self.schemas[SchemaType.NETWORK_CONFIG.value] = self._get_network_config_schema()
        self.schemas[SchemaType.INSIGHT_DATA.value] = self._get_insight_data_schema()
        self.schemas[SchemaType.ANALYTICS_REPORT.value] = self._get_analytics_report_schema()
    
    def validate(self, data: Dict[str, Any], schema_type: Union[str, SchemaType]) -> Dict[str, Any]:
        """
        Validate data against a schema.
        
        Args:
            data: Data to validate
            schema_type: Schema type to validate against
            
        Returns:
            Validation result
        """
        schema_key = schema_type.value if isinstance(schema_type, SchemaType) else schema_type
        
        if schema_key not in self.schemas:
            raise ValueError(f"Schema type '{schema_key}' not found")
        
        schema = self.schemas[schema_key]
        start_time = timezone.now()
        
        try:
            # Perform validation
            errors = self._validate_against_schema(data, schema)
            
            is_valid = len(errors) == 0
            validation_time = (timezone.now() - start_time).total_seconds()
            
            result = {
                'is_valid': is_valid,
                'errors': errors,
                'schema_type': schema_key,
                'validation_time': validation_time,
                'validated_at': timezone.now().isoformat(),
            }
            
            # Record validation
            self._record_validation(data, schema_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating data against schema {schema_key}: {str(e)}")
            
            return {
                'is_valid': False,
                'errors': [{'message': f"Validation error: {str(e)}", 'severity': 'critical'}],
                'schema_type': schema_key,
                'validation_time': (timezone.now() - start_time).total_seconds(),
                'validated_at': timezone.now().isoformat(),
            }
    
    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate data against a JSON schema."""
        errors = []
        
        # Check required fields
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in data:
                errors.append({
                    'field': field,
                    'message': f"Required field '{field}' is missing",
                    'severity': 'error',
                    'code': 'required'
                })
        
        # Check field types and constraints
        properties = schema.get('properties', {})
        for field_name, field_schema in properties.items():
            if field_name in data:
                field_value = data[field_name]
                field_errors = self._validate_field(field_name, field_value, field_schema)
                errors.extend(field_errors)
        
        return errors
    
    def _validate_field(self, field_name: str, field_value: Any, field_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate a single field against its schema."""
        errors = []
        
        # Check type
        expected_type = field_schema.get('type')
        if expected_type:
            if not self._check_type(field_value, expected_type):
                errors.append({
                    'field': field_name,
                    'message': f"Field '{field_name}' must be of type {expected_type}",
                    'severity': 'error',
                    'code': 'type_mismatch'
                })
                return errors  # Skip other validations if type is wrong
        
        # Check constraints
        if isinstance(field_value, str):
            # String constraints
            min_length = field_schema.get('minLength')
            if min_length and len(field_value) < min_length:
                errors.append({
                    'field': field_name,
                    'message': f"Field '{field_name}' must be at least {min_length} characters long",
                    'severity': 'error',
                    'code': 'min_length'
                })
            
            max_length = field_schema.get('maxLength')
            if max_length and len(field_value) > max_length:
                errors.append({
                    'field': field_name,
                    'message': f"Field '{field_name}' must be at most {max_length} characters long",
                    'severity': 'error',
                    'code': 'max_length'
                })
            
            # Pattern validation
            pattern = field_schema.get('pattern')
            if pattern:
                import re
                if not re.match(pattern, field_value):
                    errors.append({
                        'field': field_name,
                        'message': f"Field '{field_name}' does not match required pattern",
                        'severity': 'error',
                        'code': 'pattern_mismatch'
                    })
        
        elif isinstance(field_value, (int, float)):
            # Numeric constraints
            minimum = field_schema.get('minimum')
            if minimum is not None and field_value < minimum:
                errors.append({
                    'field': field_name,
                    'message': f"Field '{field_name}' must be at least {minimum}",
                    'severity': 'error',
                    'code': 'minimum'
                })
            
            maximum = field_schema.get('maximum')
            if maximum is not None and field_value > maximum:
                errors.append({
                    'field': field_name,
                    'message': f"Field '{field_name}' must be at most {maximum}",
                    'severity': 'error',
                    'code': 'maximum'
                })
        
        elif isinstance(field_value, list):
            # Array constraints
            min_items = field_schema.get('minItems')
            if min_items is not None and len(field_value) < min_items:
                errors.append({
                    'field': field_name,
                    'message': f"Field '{field_name}' must have at least {min_items} items",
                    'severity': 'error',
                    'code': 'min_items'
                })
            
            max_items = field_schema.get('maxItems')
            if max_items is not None and len(field_value) > max_items:
                errors.append({
                    'field': field_name,
                    'message': f"Field '{field_name}' must have at most {max_items} items",
                    'severity': 'error',
                    'code': 'max_items'
                })
            
            # Validate array items
            items_schema = field_schema.get('items')
            if items_schema:
                for i, item in enumerate(field_value):
                    item_errors = self._validate_field(f"{field_name}[{i}]", item, items_schema)
                    errors.extend(item_errors)
        
        return errors
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_mapping = {
            'string': str,
            'integer': int,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict,
            'null': type(None),
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True  # Unknown type, assume valid
    
    def _record_validation(self, data: Dict[str, Any], schema_type: str, result: Dict[str, Any]):
        """Record validation details."""
        validation_record = {
            'schema_type': schema_type,
            'data_hash': self._hash_data(data),
            'result': result,
            'timestamp': timezone.now().isoformat(),
        }
        
        self.validation_history.append(validation_record)
        
        # Keep only last 100 validations
        if len(self.validation_history) > 100:
            self.validation_history = self.validation_history[-100:]
    
    def _hash_data(self, data: Dict[str, Any]) -> str:
        """Generate hash of data for identification."""
        import hashlib
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def add_schema(self, schema_type: str, schema: Dict[str, Any]):
        """Add a custom schema."""
        self.schemas[schema_type] = schema
        logger.info(f"Added custom schema: {schema_type}")
    
    def get_schema(self, schema_type: str) -> Optional[Dict[str, Any]]:
        """Get a schema by type."""
        return self.schemas.get(schema_type)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validator statistics."""
        return {
            'total_schemas': len(self.schemas),
            'schema_types': list(self.schemas.keys()),
            'validation_history_count': len(self.validation_history),
        }
    
    def _get_postback_request_schema(self) -> Dict[str, Any]:
        """Get postback request schema."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Postback Request",
            "description": "Schema for validating postback request data",
            "required": ["network_key", "lead_id"],
            "properties": {
                "network_key": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100,
                    "description": "Unique identifier for the network"
                },
                "lead_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 255,
                    "description": "Unique identifier for the lead"
                },
                "offer_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 255,
                    "description": "Identifier for the offer"
                },
                "payout": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 10000,
                    "description": "Payout amount for the lead"
                },
                "source_ip": {
                    "type": "string",
                    "pattern": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$",
                    "description": "IP address of the request source"
                },
                "user_agent": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "User agent string"
                },
                "custom_fields": {
                    "type": "object",
                    "description": "Custom fields for the postback"
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp of the postback"
                }
            }
        }
    
    def _get_postback_response_schema(self) -> Dict[str, Any]:
        """Get postback response schema."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Postback Response",
            "description": "Schema for validating postback response data",
            "required": ["status", "postback_id"],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["received", "validated", "rewarded", "rejected", "duplicate", "failed"],
                    "description": "Status of the postback processing"
                },
                "postback_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the postback"
                },
                "message": {
                    "type": "string",
                    "maxLength": 1000,
                    "description": "Response message"
                },
                "payout": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Payout amount awarded"
                },
                "rejection_reason": {
                    "type": "string",
                    "enum": [status.value for status in RejectionReason],
                    "description": "Reason for rejection if applicable"
                },
                "processed_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when postback was processed"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            }
        }
    
    def _get_network_config_schema(self) -> Dict[str, Any]:
        """Get network configuration schema."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Network Configuration",
            "description": "Schema for validating network configuration data",
            "required": ["network_key", "name", "is_active"],
            "properties": {
                "network_key": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100,
                    "pattern": r"^[a-zA-Z0-9_-]+$",
                    "description": "Unique key for the network"
                },
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 255,
                    "description": "Human-readable name of the network"
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Whether the network is active"
                },
                "secret_key": {
                    "type": "string",
                    "minLength": 16,
                    "maxLength": 255,
                    "description": "Secret key for signature verification"
                },
                "signature_algorithm": {
                    "type": "string",
                    "enum": ["none", "hmac_sha1", "hmac_sha256"],
                    "description": "Signature algorithm to use"
                },
                "ip_whitelist": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?:/[0-9]+)?$"
                    },
                    "description": "List of allowed IP addresses"
                },
                "required_fields": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Required fields for postbacks"
                },
                "max_payout": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Maximum payout amount"
                },
                "default_reward_points": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Default reward points"
                }
            }
        }
    
    def _get_insight_data_schema(self) -> Dict[str, Any]:
        """Get insight data schema."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Insight Data",
            "description": "Schema for validating insight data",
            "required": ["network_key", "date", "received_count"],
            "properties": {
                "network_key": {
                    "type": "string",
                    "description": "Network identifier"
                },
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Date of the insight"
                },
                "received_count": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Number of postbacks received"
                },
                "rewarded_count": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Number of postbacks rewarded"
                },
                "rejected_count": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Number of postbacks rejected"
                },
                "health_score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Health score (0-100)"
                },
                "total_payout": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Total payout amount"
                },
                "anomaly_detected": {
                    "type": "boolean",
                    "description": "Whether anomalies were detected"
                },
                "anomaly_details": {
                    "type": "object",
                    "description": "Details about detected anomalies"
                }
            }
        }
    
    def _get_analytics_report_schema(self) -> Dict[str, Any]:
        """Get analytics report schema."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Analytics Report",
            "description": "Schema for validating analytics report data",
            "required": ["report_type", "period_start", "period_end", "data"],
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly", "custom"],
                    "description": "Type of report"
                },
                "period_start": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Start of reporting period"
                },
                "period_end": {
                    "type": "string",
                    "format": "date-time",
                    "description": "End of reporting period"
                },
                "data": {
                    "type": "object",
                    "description": "Report data"
                },
                "summary": {
                    "type": "object",
                    "properties": {
                        "total_postbacks": {
                            "type": "integer",
                            "minimum": 0
                        },
                        "total_payout": {
                            "type": "number",
                            "minimum": 0
                        },
                        "success_rate": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        }
                    }
                },
                "generated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When the report was generated"
                }
            }
        }


# Global schema validator instance
schema_validator = SchemaValidator()


# Convenience functions
def validate_postback_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate postback request data."""
    return schema_validator.validate(data, SchemaType.POSTBACK_REQUEST)


def validate_postback_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate postback response data."""
    return schema_validator.validate(data, SchemaType.POSTBACK_RESPONSE)


def validate_network_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate network configuration data."""
    return schema_validator.validate(data, SchemaType.NETWORK_CONFIG)


def validate_insight_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate insight data."""
    return schema_validator.validate(data, SchemaType.INSIGHT_DATA)


def validate_analytics_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate analytics report data."""
    return schema_validator.validate(data, SchemaType.ANALYTICS_REPORT)


# Schema management functions
def add_custom_schema(schema_type: str, schema: Dict[str, Any]):
    """Add a custom schema."""
    schema_validator.add_schema(schema_type, schema)


def get_schema(schema_type: str) -> Optional[Dict[str, Any]]:
    """Get a schema by type."""
    return schema_validator.get_schema(schema_type)


def get_schema_statistics() -> Dict[str, Any]:
    """Get schema validator statistics."""
    return schema_validator.get_statistics()


# Schema initialization
def initialize_schemas():
    """Initialize schema system."""
    try:
        logger.info("Schema system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing schema system: {str(e)}")
