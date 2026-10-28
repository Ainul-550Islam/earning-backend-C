"""
Security Schemas Module
JSON schemas and validation schemas for security data
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.schemas')


class SecuritySchema:
    """Base security schema class"""
    
    def __init__(self, schema_type: str, version: str = "1.0"):
        self.schema_type = schema_type
        self.version = version
        self.created_at = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to dictionary"""
        return {
            'schema_type': self.schema_type,
            'version': self.version,
            'created_at': self.created_at.isoformat()
        }


class SecurityLogSchema(SecuritySchema):
    """Schema for security log validation"""
    
    def __init__(self):
        super().__init__("security_log", "1.0")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get security log JSON schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Security Log",
            "description": "Schema for security log entries",
            "properties": {
                "id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the log entry"
                },
                "user": {
                    "type": ["string", "null"],
                    "description": "User identifier"
                },
                "security_type": {
                    "type": "string",
                    "enum": [
                        "login", "logout", "failed_login", "password_change",
                        "account_locked", "account_unlocked", "permission_denied",
                        "data_access", "data_modified", "data_deleted",
                        "api_access", "file_upload", "file_download",
                        "security_policy_violation", "threat_detected",
                        "incident_created", "incident_resolved"
                    ],
                    "description": "Type of security event"
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Severity level of the event"
                },
                "ip_address": {
                    "type": "string",
                    "format": "ipv4",
                    "description": "IP address of the source"
                },
                "user_agent": {
                    "type": "string",
                    "description": "User agent string"
                },
                "description": {
                    "type": "string",
                    "maxLength": 1000,
                    "description": "Description of the security event"
                },
                "risk_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Risk score (0-100)"
                },
                "response_time_ms": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "description": "Response time in milliseconds"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the log was created"
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the log was last updated"
                }
            },
            "required": ["security_type", "severity", "description"],
            "additionalProperties": False
        }


class SecurityIncidentSchema(SecuritySchema):
    """Schema for security incident validation"""
    
    def __init__(self):
        super().__init__("security_incident", "1.0")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get security incident JSON schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Security Incident",
            "description": "Schema for security incidents",
            "properties": {
                "id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the incident"
                },
                "title": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Title of the incident"
                },
                "incident_type": {
                    "type": "string",
                    "enum": [
                        "data_breach", "malware_detected", "unauthorized_access",
                        "ddos_attack", "phishing", "social_engineering",
                        "insider_threat", "physical_security", "system_vulnerability",
                        "policy_violation", "compliance_violation"
                    ],
                    "description": "Type of incident"
                },
                "description": {
                    "type": "string",
                    "maxLength": 2000,
                    "description": "Detailed description of the incident"
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Severity level of the incident"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Priority level for handling"
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "investigating", "resolved", "closed"],
                    "description": "Current status of the incident"
                },
                "user": {
                    "type": ["string", "null"],
                    "description": "User associated with the incident"
                },
                "assigned_to": {
                    "type": ["string", "null"],
                    "description": "User assigned to handle the incident"
                },
                "affected_systems": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of affected systems"
                },
                "resolution_notes": {
                    "type": ["string", "null"],
                    "maxLength": 2000,
                    "description": "Notes about incident resolution"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                },
                "opened_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the incident was opened"
                },
                "resolved_at": {
                    "type": ["string", "null"],
                    "format": "date-time",
                    "description": "Timestamp when the incident was resolved"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the incident was created"
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the incident was last updated"
                }
            },
            "required": ["title", "incident_type", "description", "severity", "priority"],
            "additionalProperties": False
        }


class ThreatIntelligenceSchema(SecuritySchema):
    """Schema for threat intelligence validation"""
    
    def __init__(self):
        super().__init__("threat_intelligence", "1.0")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get threat intelligence JSON schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Threat Intelligence",
            "description": "Schema for threat intelligence data",
            "properties": {
                "id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the threat intelligence"
                },
                "threat_type": {
                    "type": "string",
                    "enum": [
                        "malware", "phishing", "botnet", "apt", "ransomware",
                        "trojan", "spyware", "adware", "rootkit", "worm",
                        "ddos", "sql_injection", "xss", "csrf", "social_engineering"
                    ],
                    "description": "Type of threat"
                },
                "indicator_type": {
                    "type": "string",
                    "enum": ["ip_address", "domain", "url", "hash", "email", "file"],
                    "description": "Type of indicator"
                },
                "indicator": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Threat indicator value"
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Severity level of the threat"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence level (0-1)"
                },
                "source": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Source of the intelligence"
                },
                "description": {
                    "type": "string",
                    "maxLength": 2000,
                    "description": "Description of the threat"
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Whether the threat is currently active"
                },
                "ip_range": {
                    "type": ["string", "null"],
                    "description": "IP range if applicable"
                },
                "expires_at": {
                    "type": ["string", "null"],
                    "format": "date-time",
                    "description": "Expiration date of the threat"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the intelligence was created"
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the intelligence was last updated"
                }
            },
            "required": ["threat_type", "indicator_type", "indicator", "severity", "confidence", "source"],
            "additionalProperties": False
        }


class DeviceInfoSchema(SecuritySchema):
    """Schema for device information validation"""
    
    def __init__(self):
        super().__init__("device_info", "1.0")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get device info JSON schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Device Information",
            "description": "Schema for device information",
            "properties": {
                "id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the device"
                },
                "user": {
                    "type": "string",
                    "description": "User identifier"
                },
                "device_id": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Device identifier"
                },
                "device_type": {
                    "type": "string",
                    "enum": ["mobile", "tablet", "desktop", "server", "iot"],
                    "description": "Type of device"
                },
                "device_brand": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Device brand"
                },
                "device_model": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Device model"
                },
                "android_version": {
                    "type": ["string", "null"],
                    "description": "Android version"
                },
                "app_version": {
                    "type": ["string", "null"],
                    "description": "App version"
                },
                "ip_address": {
                    "type": ["string", "null"],
                    "format": "ipv4",
                    "description": "IP address of the device"
                },
                "user_agent": {
                    "type": ["string", "null"],
                    "description": "User agent string"
                },
                "is_trusted": {
                    "type": "boolean",
                    "description": "Whether the device is trusted"
                },
                "is_rooted": {
                    "type": "boolean",
                    "description": "Whether the device is rooted"
                },
                "is_emulator": {
                    "type": "boolean",
                    "description": "Whether the device is an emulator"
                },
                "is_vpn": {
                    "type": "boolean",
                    "description": "Whether the device is using VPN"
                },
                "is_proxy": {
                    "type": "boolean",
                    "description": "Whether the device is using proxy"
                },
                "risk_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Risk score (0-100)"
                },
                "last_activity": {
                    "type": ["string", "null"],
                    "format": "date-time",
                    "description": "Last activity timestamp"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the device info was created"
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the device info was last updated"
                }
            },
            "required": ["user", "device_id", "device_type"],
            "additionalProperties": False
        }


class SecurityPolicySchema(SecuritySchema):
    """Schema for security policy validation"""
    
    def __init__(self):
        super().__init__("security_policy", "1.0")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get security policy JSON schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Security Policy",
            "description": "Schema for security policies",
            "properties": {
                "id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the policy"
                },
                "name": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Name of the policy"
                },
                "policy_type": {
                    "type": "string",
                    "enum": [
                        "password_policy", "access_policy", "data_policy",
                        "network_policy", "device_policy", "api_policy",
                        "audit_policy", "compliance_policy"
                    ],
                    "description": "Type of policy"
                },
                "description": {
                    "type": "string",
                    "maxLength": 2000,
                    "description": "Description of the policy"
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Whether the policy is active"
                },
                "rules": {
                    "type": "object",
                    "description": "Policy rules and configuration"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the policy was created"
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the policy was last updated"
                }
            },
            "required": ["name", "policy_type", "description"],
            "additionalProperties": False
        }


class SecurityEventSchema(SecuritySchema):
    """Schema for security event validation"""
    
    def __init__(self):
        super().__init__("security_event", "1.0")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get security event JSON schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Security Event",
            "description": "Schema for security events",
            "properties": {
                "event_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the event"
                },
                "event_type": {
                    "type": "string",
                    "enum": [
                        "authentication", "authorization", "data_access",
                        "data_modification", "system_access", "network_access",
                        "file_access", "api_access", "security_violation",
                        "threat_detected", "policy_violation", "compliance_violation"
                    ],
                    "description": "Type of security event"
                },
                "severity": {
                    "type": "string",
                    "enum": ["info", "warning", "error", "critical"],
                    "description": "Severity level of the event"
                },
                "source": {
                    "type": "object",
                    "properties": {
                        "ip_address": {"type": "string", "format": "ipv4"},
                        "user_agent": {"type": "string"},
                        "device_id": {"type": "string"},
                        "session_id": {"type": "string"}
                    },
                    "description": "Source of the event"
                },
                "target": {
                    "type": "object",
                    "properties": {
                        "resource": {"type": "string"},
                        "resource_type": {"type": "string"},
                        "resource_id": {"type": "string"}
                    },
                    "description": "Target of the event"
                },
                "action": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "result": {"type": "string", "enum": ["success", "failure", "blocked"]},
                        "details": {"type": "object"}
                    },
                    "description": "Action performed"
                },
                "context": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "tenant_id": {"type": "string"},
                        "correlation_id": {"type": "string"},
                        "request_id": {"type": "string"}
                    },
                    "description": "Event context"
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the event occurred"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["event_type", "severity", "timestamp"],
            "additionalProperties": False
        }


class SecurityReportSchema(SecuritySchema):
    """Schema for security report validation"""
    
    def __init__(self):
        super().__init__("security_report", "1.0")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get security report JSON schema"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": "Security Report",
            "description": "Schema for security reports",
            "properties": {
                "report_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Unique identifier for the report"
                },
                "report_type": {
                    "type": "string",
                    "enum": [
                        "security_overview", "incident_report", "threat_intelligence",
                        "compliance_report", "audit_report", "risk_assessment",
                        "vulnerability_report", "access_report", "performance_report"
                    ],
                    "description": "Type of security report"
                },
                "title": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Title of the report"
                },
                "description": {
                    "type": "string",
                    "maxLength": 2000,
                    "description": "Description of the report"
                },
                "period": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "format": "date"},
                        "end_date": {"type": "string", "format": "date"},
                        "type": {"type": "string", "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"]}
                    },
                    "description": "Report period"
                },
                "data": {
                    "type": "object",
                    "description": "Report data and metrics"
                },
                "summary": {
                    "type": "object",
                    "properties": {
                        "total_events": {"type": "number"},
                        "critical_events": {"type": "number"},
                        "high_risk_events": {"type": "number"},
                        "resolved_incidents": {"type": "number"},
                        "open_incidents": {"type": "number"}
                    },
                    "description": "Report summary"
                },
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                            "description": {"type": "string"},
                            "action_items": {"type": "array", "items": {"type": "string"}}
                        }
                    },
                    "description": "Security recommendations"
                },
                "generated_by": {
                    "type": "string",
                    "description": "User or system that generated the report"
                },
                "generated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the report was generated"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["report_type", "title", "period"],
            "additionalProperties": False
        }


class SchemaRegistry:
    """Registry for security schemas"""
    
    def __init__(self):
        self.schemas = {}
        self._initialize_schemas()
    
    def _initialize_schemas(self):
        """Initialize all schemas"""
        self.schemas['security_log'] = SecurityLogSchema()
        self.schemas['security_incident'] = SecurityIncidentSchema()
        self.schemas['threat_intelligence'] = ThreatIntelligenceSchema()
        self.schemas['device_info'] = DeviceInfoSchema()
        self.schemas['security_policy'] = SecurityPolicySchema()
        self.schemas['security_event'] = SecurityEventSchema()
        self.schemas['security_report'] = SecurityReportSchema()
    
    def get_schema(self, schema_type: str) -> Optional[SecuritySchema]:
        """Get schema by type"""
        return self.schemas.get(schema_type)
    
    def get_all_schemas(self) -> Dict[str, SecuritySchema]:
        """Get all schemas"""
        return self.schemas
    
    def validate_data(self, schema_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against schema"""
        schema = self.get_schema(schema_type)
        if not schema:
            return {
                'valid': False,
                'error': f'Schema not found: {schema_type}'
            }
        
        try:
            # This would use a JSON schema validator in production
            # For now, perform basic validation
            return self._basic_validation(schema, data)
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }
    
    def _basic_validation(self, schema: SecuritySchema, data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic validation implementation"""
        # This is a simplified validation
        # In production, use jsonschema library
        
        if isinstance(schema, SecurityLogSchema):
            return self._validate_security_log(data)
        elif isinstance(schema, SecurityIncidentSchema):
            return self._validate_security_incident(data)
        elif isinstance(schema, ThreatIntelligenceSchema):
            return self._validate_threat_intelligence(data)
        elif isinstance(schema, DeviceInfoSchema):
            return self._validate_device_info(data)
        elif isinstance(schema, SecurityPolicySchema):
            return self._validate_security_policy(data)
        elif isinstance(schema, SecurityEventSchema):
            return self._validate_security_event(data)
        elif isinstance(schema, SecurityReportSchema):
            return self._validate_security_report(data)
        
        return {'valid': True, 'error': None}
    
    def _validate_security_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security log data"""
        required_fields = ['security_type', 'severity', 'description']
        
        for field in required_fields:
            if field not in data:
                return {
                    'valid': False,
                    'error': f'Required field missing: {field}'
                }
        
        # Validate severity
        valid_severities = ['low', 'medium', 'high', 'critical']
        if data['severity'] not in valid_severities:
            return {
                'valid': False,
                'error': f'Invalid severity: {data["severity"]}'
            }
        
        return {'valid': True, 'error': None}
    
    def _validate_security_incident(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security incident data"""
        required_fields = ['title', 'incident_type', 'description', 'severity', 'priority']
        
        for field in required_fields:
            if field not in data:
                return {
                    'valid': False,
                    'error': f'Required field missing: {field}'
                }
        
        return {'valid': True, 'error': None}
    
    def _validate_threat_intelligence(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate threat intelligence data"""
        required_fields = ['threat_type', 'indicator_type', 'indicator', 'severity', 'confidence', 'source']
        
        for field in required_fields:
            if field not in data:
                return {
                    'valid': False,
                    'error': f'Required field missing: {field}'
                }
        
        # Validate confidence range
        if not (0 <= data['confidence'] <= 1):
            return {
                'valid': False,
                'error': 'Confidence must be between 0 and 1'
            }
        
        return {'valid': True, 'error': None}
    
    def _validate_device_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate device info data"""
        required_fields = ['user', 'device_id', 'device_type']
        
        for field in required_fields:
            if field not in data:
                return {
                    'valid': False,
                    'error': f'Required field missing: {field}'
                }
        
        return {'valid': True, 'error': None}
    
    def _validate_security_policy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security policy data"""
        required_fields = ['name', 'policy_type', 'description']
        
        for field in required_fields:
            if field not in data:
                return {
                    'valid': False,
                    'error': f'Required field missing: {field}'
                }
        
        return {'valid': True, 'error': None}
    
    def _validate_security_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security event data"""
        required_fields = ['event_type', 'severity', 'timestamp']
        
        for field in required_fields:
            if field not in data:
                return {
                    'valid': False,
                    'error': f'Required field missing: {field}'
                }
        
        return {'valid': True, 'error': None}
    
    def _validate_security_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security report data"""
        required_fields = ['report_type', 'title', 'period']
        
        for field in required_fields:
            if field not in data:
                return {
                    'valid': False,
                    'error': f'Required field missing: {field}'
                }
        
        return {'valid': True, 'error': None}


# Global schema registry
schema_registry = SchemaRegistry()


# Export symbols
__all__ = [
    'SecuritySchema',
    'SecurityLogSchema',
    'SecurityIncidentSchema',
    'ThreatIntelligenceSchema',
    'DeviceInfoSchema',
    'SecurityPolicySchema',
    'SecurityEventSchema',
    'SecurityReportSchema',
    'SchemaRegistry',
    'schema_registry'
]