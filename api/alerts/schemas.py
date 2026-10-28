"""
JSON Schema definitions for alerts app
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional


class AlertSchemas:
    """JSON schemas for alert-related data structures"""
    
    ALERT_RULE_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "description": "Unique identifier for the alert rule"
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100,
                "description": "Name of the alert rule"
            },
            "alert_type": {
                "type": "string",
                "enum": [
                    "high_earning", "mass_signup", "payment_spike", "fraud_spike",
                    "server_error", "low_balance", "server_down", "offer_fraud",
                    "referral_abuse", "revenue_drop", "payout_delay",
                    "gateway_failure", "high_churn", "abuse_detected"
                ],
                "description": "Type of alert"
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Severity level of the alert"
            },
            "description": {
                "type": "string",
                "maxLength": 1000,
                "description": "Detailed description of the alert rule"
            },
            "threshold_value": {
                "type": "number",
                "minimum": 0,
                "description": "Threshold value that triggers the alert"
            },
            "time_window_minutes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1440,
                "description": "Time window in minutes for threshold evaluation"
            },
            "cooldown_minutes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1440,
                "description": "Cooldown period between alerts in minutes"
            },
            "is_active": {
                "type": "boolean",
                "description": "Whether the alert rule is currently active"
            },
            "send_email": {
                "type": "boolean",
                "description": "Whether to send email notifications"
            },
            "send_telegram": {
                "type": "boolean",
                "description": "Whether to send Telegram notifications"
            },
            "send_sms": {
                "type": "boolean",
                "description": "Whether to send SMS notifications"
            },
            "email_recipients": {
                "type": "string",
                "description": "Comma-separated list of email recipients"
            },
            "telegram_chat_id": {
                "type": "string",
                "description": "Telegram chat ID for notifications"
            },
            "sms_recipients": {
                "type": "string",
                "description": "Comma-separated list of SMS recipients"
            },
            "webhook_url": {
                "type": "string",
                "format": "uri",
                "description": "Webhook URL for notifications"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when the rule was created"
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when the rule was last updated"
            },
            "last_triggered": {
                "type": ["string", "null"],
                "format": "date-time",
                "description": "Timestamp when the rule was last triggered"
            }
        },
        "required": ["name", "alert_type", "severity", "threshold_value", "time_window_minutes"],
        "additionalProperties": False
    }
    
    ALERT_LOG_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "description": "Unique identifier for the alert log"
            },
            "rule": {
                "type": "integer",
                "description": "ID of the associated alert rule"
            },
            "triggered_at": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when the alert was triggered"
            },
            "trigger_value": {
                "type": "number",
                "description": "Actual value that triggered the alert"
            },
            "threshold_value": {
                "type": "number",
                "description": "Threshold value that was exceeded"
            },
            "message": {
                "type": "string",
                "maxLength": 1000,
                "description": "Alert message"
            },
            "details": {
                "type": "object",
                "description": "Additional details about the alert"
            },
            "is_resolved": {
                "type": "boolean",
                "description": "Whether the alert has been resolved"
            },
            "resolved_at": {
                "type": ["string", "null"],
                "format": "date-time",
                "description": "Timestamp when the alert was resolved"
            },
            "resolved_by": {
                "type": ["integer", "null"],
                "description": "ID of the user who resolved the alert"
            },
            "resolution_note": {
                "type": "string",
                "description": "Note about the resolution"
            },
            "escalation_level": {
                "type": "integer",
                "minimum": 0,
                "description": "Current escalation level"
            }
        },
        "required": ["rule", "triggered_at", "message"],
        "additionalProperties": False
    }
    
    NOTIFICATION_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "description": "Unique identifier for the notification"
            },
            "alert_log": {
                "type": "integer",
                "description": "ID of the associated alert log"
            },
            "notification_type": {
                "type": "string",
                "enum": ["email", "telegram", "sms", "push", "webhook", "slack", "discord", "pagerduty", "opsgenie"],
                "description": "Type of notification"
            },
            "recipient": {
                "type": "string",
                "description": "Recipient of the notification"
            },
            "subject": {
                "type": "string",
                "maxLength": 200,
                "description": "Subject of the notification"
            },
            "message": {
                "type": "string",
                "maxLength": 1000,
                "description": "Message content"
            },
            "status": {
                "type": "string",
                "enum": ["pending", "sent", "failed", "delivered", "read"],
                "description": "Status of the notification"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when the notification was created"
            },
            "sent_at": {
                "type": ["string", "null"],
                "format": "date-time",
                "description": "Timestamp when the notification was sent"
            },
            "delivered_at": {
                "type": ["string", "null"],
                "format": "date-time",
                "description": "Timestamp when the notification was delivered"
            },
            "error_message": {
                "type": "string",
                "description": "Error message if notification failed"
            },
            "retry_count": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of retry attempts"
            }
        },
        "required": ["alert_log", "notification_type", "recipient", "message"],
        "additionalProperties": False
    }
    
    INCIDENT_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "description": "Unique identifier for the incident"
            },
            "title": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "description": "Title of the incident"
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the incident"
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Severity level of the incident"
            },
            "status": {
                "type": "string",
                "enum": ["investigating", "identified", "monitoring", "resolved", "post_mortem"],
                "description": "Current status of the incident"
            },
            "detected_at": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when the incident was detected"
            },
            "resolved_at": {
                "type": ["string", "null"],
                "format": "date-time",
                "description": "Timestamp when the incident was resolved"
            },
            "assigned_to": {
                "type": ["integer", "null"],
                "description": "ID of the user assigned to the incident"
            },
            "affected_services": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of affected services"
            },
            "impact": {
                "type": "string",
                "enum": ["none", "minor", "major", "critical"],
                "description": "Impact level of the incident"
            },
            "timeline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string", "format": "date-time"},
                        "event": {"type": "string"},
                        "description": {"type": "string"},
                        "author": {"type": "string"}
                    },
                    "required": ["timestamp", "event", "description"]
                },
                "description": "Timeline of incident events"
            }
        },
        "required": ["title", "severity", "status", "detected_at"],
        "additionalProperties": False
    }


class WebhookSchemas:
    """JSON schemas for webhook payloads"""
    
    WEBHOOK_PAYLOAD_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "description": "Type of webhook event"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp of the event"
            },
            "data": {
                "type": "object",
                "description": "Event data payload"
            },
            "signature": {
                "type": "string",
                "description": "HMAC signature for verification"
            }
        },
        "required": ["event_type", "timestamp", "data"],
        "additionalProperties": False
    }
    
    ALERT_WEBHOOK_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "const": "alert.triggered"
            },
            "alert_id": {
                "type": "integer",
                "description": "ID of the triggered alert"
            },
            "rule_name": {
                "type": "string",
                "description": "Name of the alert rule"
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Severity level"
            },
            "message": {
                "type": "string",
                "description": "Alert message"
            },
            "trigger_value": {
                "type": "number",
                "description": "Value that triggered the alert"
            },
            "threshold_value": {
                "type": "number",
                "description": "Threshold that was exceeded"
            },
            "triggered_at": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when alert was triggered"
            },
            "details": {
                "type": "object",
                "description": "Additional alert details"
            }
        },
        "required": ["event_type", "alert_id", "rule_name", "severity", "message"],
        "additionalProperties": False
    }


class SystemSchemas:
    """JSON schemas for system-related data"""
    
    HEALTH_CHECK_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "check_name": {
                "type": "string",
                "description": "Name of the health check"
            },
            "check_type": {
                "type": "string",
                "enum": ["database", "cache", "external_api", "service", "resource"],
                "description": "Type of health check"
            },
            "status": {
                "type": "string",
                "enum": ["healthy", "degraded", "unhealthy", "unknown"],
                "description": "Health status"
            },
            "response_time_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Response time in milliseconds"
            },
            "status_message": {
                "type": "string",
                "description": "Detailed status message"
            },
            "checked_at": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when check was performed"
            }
        },
        "required": ["check_name", "check_type", "status", "checked_at"],
        "additionalProperties": False
    }
    
    METRICS_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp of metrics collection"
            },
            "cpu_usage_percent": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "CPU usage percentage"
            },
            "memory_usage_percent": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Memory usage percentage"
            },
            "disk_usage_percent": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Disk usage percentage"
            },
            "total_users": {
                "type": "integer",
                "minimum": 0,
                "description": "Total number of users"
            },
            "active_users_1h": {
                "type": "integer",
                "minimum": 0,
                "description": "Active users in last hour"
            },
            "total_earnings_1h": {
                "type": "number",
                "minimum": 0,
                "description": "Total earnings in last hour"
            },
            "fraud_indicators_1h": {
                "type": "integer",
                "minimum": 0,
                "description": "Fraud indicators in last hour"
            }
        },
        "required": ["timestamp"],
        "additionalProperties": False
    }


class SchemaValidator:
    """Utility class for JSON schema validation"""
    
    @staticmethod
    def validate_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data against JSON schema
        
        Args:
            data: Data to validate
            schema: JSON schema to validate against
            
        Returns:
            Dictionary with validation result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            import jsonschema
            
            validator = jsonschema.Draft7Validator(schema)
            errors = list(validator.iter_errors(data))
            
            if errors:
                error_messages = []
                for error in errors:
                    path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                    error_messages.append(f"{path}: {error.message}")
                
                return {
                    "valid": False,
                    "errors": error_messages
                }
            
            return {"valid": True, "errors": []}
        
        except ImportError:
            # Fallback validation if jsonschema is not available
            return SchemaValidator._basic_validation(data, schema)
    
    @staticmethod
    def _basic_validation(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Basic validation without jsonschema library"""
        errors = []
        
        # Check required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Check field types
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in data:
                expected_type = field_schema.get("type")
                actual_value = data[field]
                
                if expected_type == "string" and not isinstance(actual_value, str):
                    errors.append(f"Field {field} must be a string")
                elif expected_type == "number" and not isinstance(actual_value, (int, float)):
                    errors.append(f"Field {field} must be a number")
                elif expected_type == "integer" and not isinstance(actual_value, int):
                    errors.append(f"Field {field} must be an integer")
                elif expected_type == "boolean" and not isinstance(actual_value, bool):
                    errors.append(f"Field {field} must be a boolean")
                elif expected_type == "array" and not isinstance(actual_value, list):
                    errors.append(f"Field {field} must be an array")
                elif expected_type == "object" and not isinstance(actual_value, dict):
                    errors.append(f"Field {field} must be an object")
        
        return {"valid": len(errors) == 0, "errors": errors}
    
    @staticmethod
    def get_schema_for_type(schema_type: str) -> Dict[str, Any]:
        """Get schema by type name"""
        schemas = {
            "alert_rule": AlertSchemas.ALERT_RULE_SCHEMA,
            "alert_log": AlertSchemas.ALERT_LOG_SCHEMA,
            "notification": AlertSchemas.NOTIFICATION_SCHEMA,
            "incident": AlertSchemas.INCIDENT_SCHEMA,
            "webhook_payload": WebhookSchemas.WEBHOOK_PAYLOAD_SCHEMA,
            "alert_webhook": WebhookSchemas.ALERT_WEBHOOK_SCHEMA,
            "health_check": SystemSchemas.HEALTH_CHECK_SCHEMA,
            "metrics": SystemSchemas.METRICS_SCHEMA,
        }
        
        return schemas.get(schema_type, {})


# Export schemas for easy access
ALL_SCHEMAS = {
    "alert_rule": AlertSchemas.ALERT_RULE_SCHEMA,
    "alert_log": AlertSchemas.ALERT_LOG_SCHEMA,
    "notification": AlertSchemas.NOTIFICATION_SCHEMA,
    "incident": AlertSchemas.INCIDENT_SCHEMA,
    "webhook_payload": WebhookSchemas.WEBHOOK_PAYLOAD_SCHEMA,
    "alert_webhook": WebhookSchemas.ALERT_WEBHOOK_SCHEMA,
    "health_check": SystemSchemas.HEALTH_CHECK_SCHEMA,
    "metrics": SystemSchemas.METRICS_SCHEMA,
}
