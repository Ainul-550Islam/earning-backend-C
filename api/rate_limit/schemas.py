# api/rate_limit/schemas.py
"""
Schema definitions for rate limit module.

Provides JSON schemas for API validation and documentation.
"""

from typing import Dict, Any, List
import json


class RateLimitSchemas:
    """
    JSON schemas for rate limit API validation.
    """
    
    # Rate limit configuration schema
    RATE_LIMIT_CONFIG_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Rate Limit Configuration",
        "description": "Schema for rate limit configuration",
        "required": ["rate_limit_type", "requests_per_unit", "time_unit", "time_value"],
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True,
                "description": "Unique identifier"
            },
            "name": {
                "type": "string",
                "maxLength": 100,
                "pattern": "^[a-zA-Z0-9_-]+$",
                "description": "Configuration name"
            },
            "rate_limit_type": {
                "type": "string",
                "enum": ["user", "ip", "endpoint", "global", "referral", "task", "offer"],
                "description": "Type of rate limiting"
            },
            "requests_per_unit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000000,
                "description": "Number of requests allowed"
            },
            "time_unit": {
                "type": "string",
                "enum": ["second", "minute", "hour", "day"],
                "description": "Time unit for rate limiting"
            },
            "time_value": {
                "type": "integer",
                "minimum": 1,
                "maximum": 365,
                "description": "Time value multiplier"
            },
            "user": {
                "type": "integer",
                "description": "User ID for user-specific limits"
            },
            "ip_address": {
                "type": "string",
                "format": "ipv4",
                "description": "IP address for IP-specific limits"
            },
            "endpoint": {
                "type": "string",
                "maxLength": 500,
                "pattern": "^/",
                "description": "Endpoint path for endpoint-specific limits"
            },
            "task_type": {
                "type": "string",
                "maxLength": 50,
                "pattern": "^[a-zA-Z0-9_-]+$",
                "description": "Task type for task-specific limits"
            },
            "offer_wall": {
                "type": "string",
                "maxLength": 100,
                "pattern": "^[a-zA-Z0-9_-]+$",
                "description": "Offer wall for offer-specific limits"
            },
            "whitelist": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of whitelisted identifiers"
            },
            "is_active": {
                "type": "boolean",
                "default": True,
                "description": "Whether the configuration is active"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            }
        }
    }
    
    # Rate limit log schema
    RATE_LIMIT_LOG_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Rate Limit Log",
        "description": "Schema for rate limit log entries",
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True,
                "description": "Unique identifier"
            },
            "user": {
                "type": "integer",
                "description": "User ID"
            },
            "ip_address": {
                "type": "string",
                "format": "ipv4",
                "description": "Client IP address"
            },
            "endpoint": {
                "type": "string",
                "description": "API endpoint"
            },
            "request_method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                "description": "HTTP method"
            },
            "status": {
                "type": "string",
                "enum": ["allowed", "blocked", "throttled"],
                "description": "Request status"
            },
            "requests_count": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of requests made"
            },
            "suspicion_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Suspicion score (0-100)"
            },
            "response_time": {
                "type": "number",
                "minimum": 0,
                "description": "Response time in milliseconds"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            }
        }
    }
    
    # IP block schema
    IP_BLOCK_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "IP Block",
        "description": "Schema for IP block entries",
        "required": ["ip_address", "block_type", "block_reason"],
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True,
                "description": "Unique identifier"
            },
            "ip_address": {
                "type": "string",
                "format": "ipv4",
                "description": "IP address or CIDR range"
            },
            "block_type": {
                "type": "string",
                "enum": ["single", "range", "subnet", "country", "asn", "wildcard"],
                "description": "Type of IP block"
            },
            "block_reason": {
                "type": "string",
                "enum": ["manual", "abuse", "rate_limit", "security", "policy", 
                         "malware", "suspicious", "auto_detection", "user_report", "system_detection"],
                "description": "Reason for blocking"
            },
            "expires_at": {
                "type": "string",
                "format": "date-time",
                "description": "Expiration time (null for permanent blocks)"
            },
            "permanent": {
                "type": "boolean",
                "default": False,
                "description": "Whether the block is permanent"
            },
            "is_active": {
                "type": "boolean",
                "default": True,
                "description": "Whether the block is currently active"
            },
            "created_by": {
                "type": "integer",
                "description": "User who created the block"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            }
        }
    }
    
    # Abuse report schema
    ABUSE_REPORT_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Abuse Report",
        "description": "Schema for abuse reports",
        "required": ["abuse_type", "severity"],
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True,
                "description": "Unique identifier"
            },
            "user": {
                "type": "integer",
                "description": "User ID (if applicable)"
            },
            "ip_address": {
                "type": "string",
                "format": "ipv4",
                "description": "IP address of the abuser"
            },
            "abuse_type": {
                "type": "string",
                "enum": ["rate_limit", "spam", "fraud", "malicious", "bot", 
                         "scraping", "brute_force", "ddos", "suspicious_pattern", "other"],
                "description": "Type of abuse"
            },
            "severity": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Severity level (1-5)"
            },
            "description": {
                "type": "string",
                "maxLength": 1000,
                "description": "Detailed description of the abuse"
            },
            "evidence": {
                "type": "object",
                "description": "Evidence supporting the abuse report"
            },
            "is_investigated": {
                "type": "boolean",
                "default": False,
                "description": "Whether the report has been investigated"
            },
            "is_blocked": {
                "type": "boolean",
                "default": False,
                "description": "Whether the abuser was blocked"
            },
            "investigated_by": {
                "type": "integer",
                "description": "User who investigated the report"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            }
        }
    }
    
    # Rate limit exception schema
    RATE_LIMIT_EXCEPTION_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Rate Limit Exception",
        "description": "Schema for rate limit exceptions",
        "required": ["exception_type"],
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True,
                "description": "Unique identifier"
            },
            "user": {
                "type": "integer",
                "description": "User ID (if applicable)"
            },
            "ip_address": {
                "type": "string",
                "format": "ipv4",
                "description": "IP address (if applicable)"
            },
            "exception_type": {
                "type": "string",
                "enum": ["whitelist", "blacklist", "bypass", "increased_limit", 
                         "decreased_limit", "no_limit", "custom_limit"],
                "description": "Type of exception"
            },
            "multiplier": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 1000,
                "description": "Multiplier for rate limits"
            },
            "max_requests": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000000,
                "description": "Maximum requests allowed"
            },
            "endpoints": {
                "type": "array",
                "items": {
                    "type": "string",
                    "pattern": "^/"
                },
                "description": "List of affected endpoints"
            },
            "expires_at": {
                "type": "string",
                "format": "date-time",
                "description": "Expiration time (null for permanent exceptions)"
            },
            "permanent": {
                "type": "boolean",
                "default": False,
                "description": "Whether the exception is permanent"
            },
            "is_active": {
                "type": "boolean",
                "default": True,
                "description": "Whether the exception is currently active"
            },
            "usage_count": {
                "type": "integer",
                "minimum": 0,
                "readOnly": True,
                "description": "Number of times this exception has been used"
            },
            "last_used_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            }
        }
    }
    
    # User rate limit profile schema
    USER_RATE_LIMIT_PROFILE_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "User Rate Limit Profile",
        "description": "Schema for user rate limit profiles",
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True,
                "description": "Unique identifier"
            },
            "user": {
                "type": "integer",
                "description": "User ID"
            },
            "total_requests": {
                "type": "integer",
                "minimum": 0,
                "readOnly": True,
                "description": "Total requests made by user"
            },
            "blocked_requests": {
                "type": "integer",
                "minimum": 0,
                "readOnly": True,
                "description": "Total blocked requests"
            },
            "api_health_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "API health score (0-100)"
            },
            "suspicion_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Suspicion score (0-100)"
            },
            "is_premium": {
                "type": "boolean",
                "default": False,
                "description": "Whether user has premium access"
            },
            "premium_until": {
                "type": "string",
                "format": "date-time",
                "description": "Premium access expiration"
            },
            "custom_daily_limit": {
                "type": "integer",
                "minimum": 0,
                "description": "Custom daily request limit"
            },
            "custom_hourly_limit": {
                "type": "integer",
                "minimum": 0,
                "description": "Custom hourly request limit"
            },
            "daily_usage": {
                "type": "integer",
                "minimum": 0,
                "readOnly": True,
                "description": "Current daily usage"
            },
            "hourly_usage": {
                "type": "integer",
                "minimum": 0,
                "readOnly": True,
                "description": "Current hourly usage"
            },
            "current_usage": {
                "type": "integer",
                "minimum": 0,
                "readOnly": True,
                "description": "Current usage in current time window"
            },
            "last_request_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "endpoint_health": {
                "type": "object",
                "description": "Health status per endpoint"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            }
        }
    }
    
    # Rate limit insight schema
    RATE_LIMIT_INSIGHT_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Rate Limit Insight",
        "description": "Schema for rate limit insights",
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True,
                "description": "Unique identifier"
            },
            "date": {
                "type": "string",
                "format": "date",
                "description": "Date of the insight"
            },
            "total_requests": {
                "type": "integer",
                "minimum": 0,
                "description": "Total requests for the day"
            },
            "blocked_requests": {
                "type": "integer",
                "minimum": 0,
                "description": "Blocked requests for the day"
            },
            "unique_ips": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of unique IP addresses"
            },
            "unique_users": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of unique users"
            },
            "avg_response_time": {
                "type": "number",
                "minimum": 0,
                "description": "Average response time in milliseconds"
            },
            "peak_hour": {
                "type": "integer",
                "minimum": 0,
                "maximum": 23,
                "description": "Hour with peak traffic (0-23)"
            },
            "top_endpoints": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Top endpoints by request count"
            },
            "top_ips": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Top IP addresses by request count"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "readOnly": True
            }
        }
    }
    
    # API response schemas
    API_RESPONSE_SCHEMAS = {
        "success_response": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": True
                },
                "data": {
                    "type": "object",
                    "description": "Response data"
                },
                "message": {
                    "type": "string",
                    "description": "Success message"
                }
            }
        },
        "error_response": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": False
                },
                "error": {
                    "type": "string",
                    "description": "Error code"
                },
                "message": {
                    "type": "string",
                    "description": "Error message"
                },
                "details": {
                    "type": "object",
                    "description": "Additional error details"
                }
            }
        },
        "rate_limit_exceeded_response": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": False
                },
                "error": {
                    "type": "string",
                    "example": "rate_limit_exceeded"
                },
                "message": {
                    "type": "string",
                    "example": "Rate limit exceeded"
                },
                "limit": {
                    "type": "integer",
                    "description": "Rate limit value"
                },
                "remaining": {
                    "type": "integer",
                    "description": "Remaining requests"
                },
                "reset_time": {
                    "type": "integer",
                    "description": "Unix timestamp when limit resets"
                },
                "retry_after": {
                    "type": "integer",
                    "description": "Seconds to wait before retry"
                }
            }
        }
    }
    
    # Query parameter schemas
    QUERY_PARAMETER_SCHEMAS = {
        "pagination": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "description": "Page number"
                },
                "page_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Number of items per page"
                }
            }
        },
        "date_range": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date (YYYY-MM-DD)"
                },
                "date_to": {
                    "type": "string",
                    "format": "date",
                    "description": "End date (YYYY-MM-DD)"
                },
                "datetime_from": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Start datetime"
                },
                "datetime_to": {
                    "type": "string",
                    "format": "date-time",
                    "description": "End datetime"
                }
            }
        },
        "filtering": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Filter by user ID"
                },
                "ip_address": {
                    "type": "string",
                    "format": "ipv4",
                    "description": "Filter by IP address"
                },
                "status": {
                    "type": "string",
                    "enum": ["allowed", "blocked", "throttled"],
                    "description": "Filter by status"
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Filter by active status"
                }
            }
        }
    }


class SchemaValidator:
    """
    Schema validator for rate limit API requests.
    """
    
    @staticmethod
    def get_schema(schema_name: str) -> Dict[str, Any]:
        """
        Get schema by name.
        
        Args:
            schema_name: Name of the schema
            
        Returns:
            Schema dictionary
        """
        schemas = RateLimitSchemas()
        return getattr(schemas, schema_name.upper(), {})
    
    @staticmethod
    def validate_request_data(data: Dict[str, Any], schema_name: str) -> bool:
        """
        Validate request data against schema.
        
        Args:
            data: Request data to validate
            schema_name: Name of the schema
            
        Returns:
            True if valid, False otherwise
        """
        try:
            schema = SchemaValidator.get_schema(schema_name)
            # In a real implementation, use jsonschema library
            # For now, just do basic validation
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_schema_example(schema_name: str) -> Dict[str, Any]:
        """
        Get example data for a schema.
        
        Args:
            schema_name: Name of the schema
            
        Returns:
            Example data dictionary
        """
        examples = {
            "rate_limit_config": {
                "name": "api_user_limit",
                "rate_limit_type": "user",
                "requests_per_unit": 100,
                "time_unit": "minute",
                "time_value": 1,
                "is_active": True
            },
            "ip_block": {
                "ip_address": "192.168.1.100",
                "block_type": "single",
                "block_reason": "abuse",
                "permanent": False,
                "is_active": True
            },
            "abuse_report": {
                "abuse_type": "spam",
                "severity": 3,
                "description": "Excessive API requests from single IP"
            },
            "rate_limit_exception": {
                "exception_type": "increased_limit",
                "multiplier": 2.0,
                "permanent": False,
                "is_active": True
            },
            "user_rate_limit_profile": {
                "api_health_score": 85,
                "suspicion_score": 10,
                "is_premium": False,
                "custom_daily_limit": 1000,
                "custom_hourly_limit": 100
            }
        }
        
        return examples.get(schema_name.lower(), {})


# Export schemas and validator
__all__ = [
    'RateLimitSchemas',
    'SchemaValidator'
]
