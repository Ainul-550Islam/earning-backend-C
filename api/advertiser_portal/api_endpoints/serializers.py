"""
API Endpoints Serializers

This module provides comprehensive serializers for API endpoint management with
enterprise-grade validation, security, and performance optimization following
industry standards from Postman, Swagger, and API Gateway.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import Coalesce

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.api_endpoint_model import (
    APIEndpoint, RESTEndpoint, GraphQLEndpoint, WebSocketEndpoint,
    APIDocumentation, APIVersion, APIAuthentication, APIRateLimit
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class APIEndpointSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for APIEndpoint model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    created_at_formatted = serializers.SerializerMethodField()
    updated_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = APIEndpoint
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'endpoint_type',
            'method', 'path', 'handler', 'authentication', 'rate_limit',
            'version', 'status', 'settings', 'created_at', 'created_at_formatted',
            'updated_at', 'updated_at_formatted', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_at_formatted', 'updated_at',
            'updated_at_formatted', 'created_by', 'updated_by'
        ]
    
    def get_created_at_formatted(self, obj: APIEndpoint) -> str:
        """Get formatted creation time."""
        try:
            if obj.created_at:
                return obj.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def get_updated_at_formatted(self, obj: APIEndpoint) -> str:
        """Get formatted update time."""
        try:
            if obj.updated_at:
                return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def validate_name(self, value: str) -> str:
        """Validate endpoint name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Endpoint name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Endpoint name contains prohibited characters")
        
        return value
    
    def validate_endpoint_type(self, value: str) -> str:
        """Validate endpoint type with security checks."""
        valid_types = ['rest', 'graphql', 'websocket', 'webhook']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid endpoint type. Must be one of: {valid_types}")
        return value
    
    def validate_method(self, value: str) -> str:
        """Validate HTTP method with security checks."""
        valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
        if value not in valid_methods:
            raise serializers.ValidationError(f"Invalid HTTP method. Must be one of: {valid_methods}")
        return value
    
    def validate_path(self, value: str) -> str:
        """Validate endpoint path with security checks."""
        if not value:
            raise serializers.ValidationError("Endpoint path is required")
        
        # Security: Validate path format
        if not value.startswith('/'):
            raise serializers.ValidationError("Path must start with '/'")
        
        # Security: Check for prohibited patterns
        prohibited_patterns = [
            r'\.\./',  # Directory traversal
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Path contains prohibited content")
        
        # Validate path length
        if len(value) > 255:
            raise serializers.ValidationError("Path is too long")
        
        return value
    
    def validate_handler(self, value: str) -> str:
        """Validate handler with security checks."""
        if not value:
            raise serializers.ValidationError("Handler is required")
        
        # Security: Validate handler format
        if '.' not in value:
            raise serializers.ValidationError("Handler must be in format 'module.function'")
        
        # Security: Check for prohibited patterns
        prohibited_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'eval(',  # Code execution
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Handler contains prohibited content")
        
        return value
    
    def validate_authentication(self, value: List[str]) -> List[str]:
        """Validate authentication methods with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Authentication must be a list")
        
        valid_auth_methods = ['none', 'bearer', 'basic', 'api_key', 'oauth2', 'jwt']
        for auth_method in value:
            if auth_method not in valid_auth_methods:
                raise serializers.ValidationError(f"Invalid authentication method: {auth_method}")
        
        return value
    
    def validate_rate_limit(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rate limit configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Rate limit must be a dictionary")
        
        # Security: Check for prohibited content
        rate_limit_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, rate_limit_str, re.IGNORECASE):
                raise serializers.ValidationError("Rate limit contains prohibited content")
        
        # Validate rate limit structure
        valid_keys = ['requests_per_minute', 'requests_per_hour', 'requests_per_day', 'burst_limit']
        for key in value.keys():
            if key not in valid_keys:
                raise serializers.ValidationError(f"Invalid rate limit key: {key}")
        
        # Validate rate limit values
        for key, val in value.items():
            if not isinstance(val, int) or val < 1:
                raise serializers.ValidationError(f"{key} must be a positive integer")
        
        return value
    
    def validate_version(self, value: str) -> str:
        """Validate API version with security checks."""
        if not value:
            raise serializers.ValidationError("Version is required")
        
        # Security: Validate version format
        import re
        if not re.match(r'^v\d+(\.\d+)*$', value):
            raise serializers.ValidationError("Version must be in format 'v1', 'v1.2', etc.")
        
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate endpoint status with security checks."""
        valid_statuses = ['active', 'inactive', 'deprecated', 'maintenance']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate advertiser access
        advertiser = attrs.get('advertiser')
        if advertiser and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
        
        # Business logic: Validate endpoint type vs method
        endpoint_type = attrs.get('endpoint_type')
        method = attrs.get('method')
        
        if endpoint_type == 'rest':
            valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            if method not in valid_methods:
                raise serializers.ValidationError(f"Invalid method for REST endpoint: {method}")
        
        elif endpoint_type == 'graphql':
            if method != 'POST':
                raise serializers.ValidationError("GraphQL endpoints must use POST method")
        
        elif endpoint_type == 'websocket':
            if method != 'GET':
                raise serializers.ValidationError("WebSocket endpoints must use GET method")
        
        # Business logic: Validate path uniqueness
        path = attrs.get('path')
        method = attrs.get('method')
        version = attrs.get('version')
        
        if path and method and version:
            existing_endpoint = APIEndpoint.objects.filter(
                path=path,
                method=method,
                version=version
            ).exclude(id=self.instance.id if self.instance else None).first()
            
            if existing_endpoint:
                raise serializers.ValidationError(f"Endpoint with path '{path}' and method '{method}' already exists for version '{version}'")
        
        return attrs


class APIEndpointCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating API endpoints.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    endpoint_type = serializers.ChoiceField(
        choices=['rest', 'graphql', 'websocket', 'webhook'],
        required=True
    )
    method = serializers.ChoiceField(
        choices=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'],
        required=True
    )
    path = serializers.CharField(max_length=255, required=True)
    handler = serializers.CharField(max_length=500, required=True)
    authentication = serializers.ListField(
        child=serializers.ChoiceField(choices=['none', 'bearer', 'basic', 'api_key', 'oauth2', 'jwt']),
        required=False,
        default=[]
    )
    rate_limit = serializers.JSONField(required=False, default=dict)
    version = serializers.CharField(max_length=20, required=False, default='v1')
    status = serializers.ChoiceField(
        choices=['active', 'inactive', 'deprecated', 'maintenance'],
        required=False,
        default='active'
    )
    settings = serializers.JSONField(required=False, default=dict)
    
    def validate_name(self, value: str) -> str:
        """Validate endpoint name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Endpoint name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Endpoint name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Endpoint name contains prohibited characters")
        
        # Validate name length
        if len(value) > 255:
            raise serializers.ValidationError("Endpoint name is too long")
        
        return value
    
    def validate_advertiser_id(self, value: Optional[UUID]) -> Optional[UUID]:
        """Validate advertiser ID with security checks."""
        if value is not None:
            try:
                advertiser = Advertiser.objects.get(id=value, is_deleted=False)
                
                # Security: Check user permissions
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
                return value
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
            except ValueError:
                raise serializers.ValidationError("Invalid advertiser ID format")
        
        return value
    
    def validate_endpoint_type(self, value: str) -> str:
        """Validate endpoint type with comprehensive security checks."""
        valid_types = ['rest', 'graphql', 'websocket', 'webhook']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid endpoint type. Must be one of: {valid_types}")
        return value
    
    def validate_method(self, value: str) -> str:
        """Validate HTTP method with comprehensive security checks."""
        valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
        if value not in valid_methods:
            raise serializers.ValidationError(f"Invalid HTTP method. Must be one of: {valid_methods}")
        return value
    
    def validate_path(self, value: str) -> str:
        """Validate endpoint path with comprehensive security checks."""
        if not value:
            raise serializers.ValidationError("Endpoint path is required")
        
        # Security: Validate path format
        if not value.startswith('/'):
            raise serializers.ValidationError("Path must start with '/'")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
            r'ftp://',  # FTP protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Path contains suspicious content")
        
        # Validate path structure
        if '..' in value:
            raise serializers.ValidationError("Path cannot contain directory traversal")
        
        # Validate path length
        if len(value) > 255:
            raise serializers.ValidationError("Path is too long")
        
        return value
    
    def validate_handler(self, value: str) -> str:
        """Validate handler with comprehensive security checks."""
        if not value:
            raise serializers.ValidationError("Handler is required")
        
        # Security: Validate handler format
        if '.' not in value:
            raise serializers.ValidationError("Handler must be in format 'module.function'")
        
        # Security: Check for prohibited patterns
        prohibited_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'eval(',  # Code execution
            r'exec(',  # Code execution
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Handler contains prohibited content")
        
        # Validate handler length
        if len(value) > 500:
            raise serializers.ValidationError("Handler is too long")
        
        return value
    
    def validate_authentication(self, value: List[str]) -> List[str]:
        """Validate authentication methods with comprehensive security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Authentication must be a list")
        
        valid_auth_methods = ['none', 'bearer', 'basic', 'api_key', 'oauth2', 'jwt']
        for auth_method in value:
            if auth_method not in valid_auth_methods:
                raise serializers.ValidationError(f"Invalid authentication method: {auth_method}")
        
        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Authentication methods must be unique")
        
        return value
    
    def validate_rate_limit(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rate limit configuration with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Rate limit must be a dictionary")
        
        # Security: Check for prohibited content
        rate_limit_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, rate_limit_str, re.IGNORECASE):
                raise serializers.ValidationError("Rate limit contains prohibited content")
        
        # Validate rate limit structure
        valid_keys = ['requests_per_minute', 'requests_per_hour', 'requests_per_day', 'burst_limit']
        for key in value.keys():
            if key not in valid_keys:
                raise serializers.ValidationError(f"Invalid rate limit key: {key}")
        
        # Validate rate limit values
        for key, val in value.items():
            if not isinstance(val, int) or val < 1:
                raise serializers.ValidationError(f"{key} must be a positive integer")
            
            # Validate reasonable limits
            if key == 'requests_per_minute' and val > 1000:
                raise serializers.ValidationError("requests_per_minute cannot exceed 1000")
            elif key == 'requests_per_hour' and val > 10000:
                raise serializers.ValidationError("requests_per_hour cannot exceed 10000")
            elif key == 'requests_per_day' and val > 100000:
                raise serializers.ValidationError("requests_per_day cannot exceed 100000")
        
        return value
    
    def validate_version(self, value: str) -> str:
        """Validate API version with comprehensive security checks."""
        if not value:
            raise serializers.ValidationError("Version is required")
        
        # Security: Validate version format
        import re
        if not re.match(r'^v\d+(\.\d+)*$', value):
            raise serializers.ValidationError("Version must be in format 'v1', 'v1.2', etc.")
        
        # Validate version length
        if len(value) > 20:
            raise serializers.ValidationError("Version is too long")
        
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate endpoint status with comprehensive security checks."""
        valid_statuses = ['active', 'inactive', 'deprecated', 'maintenance']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        # Validate settings structure
        valid_setting_keys = [
            'timeout', 'retry_attempts', 'cors_enabled', 'compression_enabled',
            'logging_enabled', 'monitoring_enabled', 'custom_headers'
        ]
        
        for key in value.keys():
            if key not in valid_setting_keys:
                raise serializers.ValidationError(f"Invalid setting key: {key}")
        
        # Validate specific settings
        if 'timeout' in value:
            timeout = value['timeout']
            if not isinstance(timeout, int) or timeout < 1 or timeout > 300:
                raise serializers.ValidationError("timeout must be between 1 and 300 seconds")
        
        if 'retry_attempts' in value:
            retry_attempts = value['retry_attempts']
            if not isinstance(retry_attempts, int) or retry_attempts < 0 or retry_attempts > 10:
                raise serializers.ValidationError("retry_attempts must be between 0 and 10")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate endpoint type vs method
        endpoint_type = attrs.get('endpoint_type')
        method = attrs.get('method')
        
        if endpoint_type == 'rest':
            valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            if method not in valid_methods:
                raise serializers.ValidationError(f"Invalid method for REST endpoint: {method}")
        
        elif endpoint_type == 'graphql':
            if method != 'POST':
                raise serializers.ValidationError("GraphQL endpoints must use POST method")
        
        elif endpoint_type == 'websocket':
            if method != 'GET':
                raise serializers.ValidationError("WebSocket endpoints must use GET method")
        
        # Business logic: Validate path uniqueness
        path = attrs.get('path')
        method = attrs.get('method')
        version = attrs.get('version', 'v1')
        
        if path and method and version:
            existing_endpoint = APIEndpoint.objects.filter(
                path=path,
                method=method,
                version=version
            ).first()
            
            if existing_endpoint:
                raise serializers.ValidationError(f"Endpoint with path '{path}' and method '{method}' already exists for version '{version}'")
        
        # Business logic: Validate advertiser access
        advertiser_id = attrs.get('advertiser_id')
        if advertiser_id:
            try:
                advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
                
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
        
        # Business logic: Validate endpoint type vs settings
        endpoint_type = attrs.get('endpoint_type')
        settings = attrs.get('settings', {})
        
        if endpoint_type == 'websocket':
            if 'heartbeat_interval' not in settings:
                settings['heartbeat_interval'] = 30
            if 'max_connections' not in settings:
                settings['max_connections'] = 1000
        
        elif endpoint_type == 'graphql':
            if 'playground_enabled' not in settings:
                settings['playground_enabled'] = True
            if 'introspection_enabled' not in settings:
                settings['introspection_enabled'] = True
        
        elif endpoint_type == 'rest':
            if 'pagination_enabled' not in settings:
                settings['pagination_enabled'] = True
            if 'filtering_enabled' not in settings:
                settings['filtering_enabled'] = True
        
        return attrs


class RESTEndpointSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for RESTEndpoint model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = RESTEndpoint
        fields = [
            'id', 'api_endpoint', 'response_format', 'request_validation',
            'response_serialization', 'pagination', 'filtering', 'sorting'
        ]
        read_only_fields = ['id', 'api_endpoint']
    
    def validate_response_format(self, value: str) -> str:
        """Validate response format with security checks."""
        valid_formats = ['json', 'xml', 'yaml', 'csv', 'text']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Invalid response format. Must be one of: {valid_formats}")
        return value
    
    def validate_request_validation(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate request validation configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Request validation must be a dictionary")
        
        # Security: Check for prohibited content
        validation_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, validation_str, re.IGNORECASE):
                raise serializers.ValidationError("Request validation contains prohibited content")
        
        return value
    
    def validate_response_serialization(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate response serialization configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Response serialization must be a dictionary")
        
        # Security: Check for prohibited content
        serialization_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, serialization_str, re.IGNORECASE):
                raise serializers.ValidationError("Response serialization contains prohibited content")
        
        return value
    
    def validate_pagination(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate pagination configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Pagination must be a dictionary")
        
        # Security: Check for prohibited content
        pagination_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, pagination_str, re.IGNORECASE):
                raise serializers.ValidationError("Pagination contains prohibited content")
        
        return value
    
    def validate_filtering(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filtering configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filtering must be a dictionary")
        
        # Security: Check for prohibited content
        filtering_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, filtering_str, re.IGNORECASE):
                raise serializers.ValidationError("Filtering contains prohibited content")
        
        return value
    
    def validate_sorting(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate sorting configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Sorting must be a dictionary")
        
        # Security: Check for prohibited content
        sorting_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, sorting_str, re.IGNORECASE):
                raise serializers.ValidationError("Sorting contains prohibited content")
        
        return value


class GraphQLEndpointSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for GraphQLEndpoint model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = GraphQLEndpoint
        fields = [
            'id', 'api_endpoint', 'schema', 'resolvers', 'subscriptions',
            'playground_enabled', 'introspection_enabled'
        ]
        read_only_fields = ['id', 'api_endpoint']
    
    def validate_schema(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GraphQL schema with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Schema must be a dictionary")
        
        # Security: Check for prohibited content
        schema_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, schema_str, re.IGNORECASE):
                raise serializers.ValidationError("Schema contains prohibited content")
        
        return value
    
    def validate_resolvers(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GraphQL resolvers with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Resolvers must be a dictionary")
        
        # Security: Check for prohibited content
        resolvers_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, resolvers_str, re.IGNORECASE):
                raise serializers.ValidationError("Resolvers contain prohibited content")
        
        return value
    
    def validate_subscriptions(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GraphQL subscriptions with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Subscriptions must be a dictionary")
        
        # Security: Check for prohibited content
        subscriptions_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, subscriptions_str, re.IGNORECASE):
                raise serializers.ValidationError("Subscriptions contain prohibited content")
        
        return value


class WebSocketEndpointSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebSocketEndpoint model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = WebSocketEndpoint
        fields = [
            'id', 'api_endpoint', 'protocol', 'subprotocols', 'heartbeat_interval',
            'max_connections', 'message_format'
        ]
        read_only_fields = ['id', 'api_endpoint']
    
    def validate_protocol(self, value: str) -> str:
        """Validate WebSocket protocol with security checks."""
        valid_protocols = ['ws', 'wss']
        if value not in valid_protocols:
            raise serializers.ValidationError(f"Invalid protocol. Must be one of: {valid_protocols}")
        return value
    
    def validate_subprotocols(self, value: List[str]) -> List[str]:
        """Validate WebSocket subprotocols with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Subprotocols must be a list")
        
        # Security: Check for prohibited content
        for subprotocol in value:
            if not isinstance(subprotocol, str):
                raise serializers.ValidationError("Subprotocols must be strings")
            
            prohibited_patterns = [
                r'<script',  # Script injection
                r'javascript:',  # JavaScript protocol
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, subprotocol, re.IGNORECASE):
                    raise serializers.ValidationError(f"Subprotocol contains prohibited content: {subprotocol}")
        
        return value
    
    def validate_heartbeat_interval(self, value: int) -> int:
        """Validate heartbeat interval with security checks."""
        if not isinstance(value, int) or value < 1 or value > 300:
            raise serializers.ValidationError("Heartbeat interval must be between 1 and 300 seconds")
        return value
    
    def validate_max_connections(self, value: int) -> int:
        """Validate max connections with security checks."""
        if not isinstance(value, int) or value < 1 or value > 10000:
            raise serializers.ValidationError("Max connections must be between 1 and 10000")
        return value
    
    def validate_message_format(self, value: str) -> str:
        """Validate message format with security checks."""
        valid_formats = ['json', 'xml', 'text', 'binary']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Invalid message format. Must be one of: {valid_formats}")
        return value


class APIDocumentationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for APIDocumentation model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = APIDocumentation
        fields = [
            'id', 'api_endpoint', 'title', 'description', 'content',
            'format', 'version', 'is_public', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_title(self, value: str) -> str:
        """Validate documentation title with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Title contains prohibited characters")
        
        return value
    
    def validate_description(self, value: str) -> str:
        """Validate documentation description with security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Description contains prohibited content")
        
        return value
    
    def validate_content(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate documentation content with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Content must be a dictionary")
        
        # Security: Check for prohibited content
        content_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, content_str, re.IGNORECASE):
                raise serializers.ValidationError("Content contains prohibited content")
        
        return value
    
    def validate_format(self, value: str) -> str:
        """Validate documentation format with security checks."""
        valid_formats = ['openapi', 'swagger', 'raml', 'api_blueprint']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Invalid format. Must be one of: {valid_formats}")
        return value
    
    def validate_version(self, value: str) -> str:
        """Validate documentation version with security checks."""
        if not value:
            raise serializers.ValidationError("Version is required")
        
        # Security: Validate version format
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', value):
            raise serializers.ValidationError("Version must be in format '1.0.0'")
        
        return value
    
    def validate_is_public(self, value: bool) -> bool:
        """Validate public visibility with security checks."""
        if not isinstance(value, bool):
            raise serializers.ValidationError("is_public must be a boolean")
        return value


class APIVersionSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for APIVersion model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = APIVersion
        fields = [
            'id', 'version', 'description', 'endpoints', 'is_active',
            'deprecation_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_version(self, value: str) -> str:
        """Validate API version with security checks."""
        if not value:
            raise serializers.ValidationError("Version is required")
        
        # Security: Validate version format
        import re
        if not re.match(r'^v\d+(\.\d+)*$', value):
            raise serializers.ValidationError("Version must be in format 'v1', 'v1.2', etc.")
        
        return value
    
    def validate_description(self, value: str) -> str:
        """Validate version description with security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Description contains prohibited content")
        
        return value
    
    def validate_endpoints(self, value: List[str]) -> List[str]:
        """Validate version endpoints with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Endpoints must be a list")
        
        # Security: Check endpoint IDs
        for endpoint_id in value:
            try:
                UUID(endpoint_id)
            except ValueError:
                raise serializers.ValidationError(f"Invalid endpoint ID: {endpoint_id}")
        
        return value
    
    def validate_is_active(self, value: bool) -> bool:
        """Validate active status with security checks."""
        if not isinstance(value, bool):
            raise serializers.ValidationError("is_active must be a boolean")
        return value
    
    def validate_deprecation_date(self, value: Optional[datetime]) -> Optional[datetime]:
        """Validate deprecation date with security checks."""
        if value is not None:
            if value < timezone.now():
                raise serializers.ValidationError("Deprecation date cannot be in the past")
        
        return value


class APIAuthenticationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for APIAuthentication model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = APIAuthentication
        fields = [
            'id', 'user', 'name', 'api_key', 'permissions', 'expires_at',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_name(self, value: str) -> str:
        """Validate API key name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Name contains prohibited characters")
        
        return value
    
    def validate_api_key(self, value: str) -> str:
        """Validate API key with security checks."""
        if not value or len(value) < 32:
            raise serializers.ValidationError("API key must be at least 32 characters long")
        
        # Security: Check API key format
        import re
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', value):
            raise serializers.ValidationError("API key contains invalid characters")
        
        return value
    
    def validate_permissions(self, value: List[str]) -> List[str]:
        """Validate API key permissions with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Permissions must be a list")
        
        valid_permissions = [
            'read', 'write', 'delete', 'admin', 'campaigns', 'analytics',
            'billing', 'users', 'integrations', 'webhooks'
        ]
        
        for permission in value:
            if permission not in valid_permissions:
                raise serializers.ValidationError(f"Invalid permission: {permission}")
        
        return value
    
    def validate_expires_at(self, value: Optional[datetime]) -> Optional[datetime]:
        """Validate expiration date with security checks."""
        if value is not None:
            if value < timezone.now():
                raise serializers.ValidationError("Expiration date cannot be in the past")
        
        return value
    
    def validate_is_active(self, value: bool) -> bool:
        """Validate active status with security checks."""
        if not isinstance(value, bool):
            raise serializers.ValidationError("is_active must be a boolean")
        return value


class APIRateLimitSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for APIRateLimit model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = APIRateLimit
        fields = [
            'id', 'api_endpoint', 'requests_per_minute', 'requests_per_hour',
            'requests_per_day', 'burst_limit', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_requests_per_minute(self, value: int) -> int:
        """Validate requests per minute with security checks."""
        if not isinstance(value, int) or value < 1 or value > 1000:
            raise serializers.ValidationError("Requests per minute must be between 1 and 1000")
        return value
    
    def validate_requests_per_hour(self, value: int) -> int:
        """Validate requests per hour with security checks."""
        if not isinstance(value, int) or value < 1 or value > 10000:
            raise serializers.ValidationError("Requests per hour must be between 1 and 10000")
        return value
    
    def validate_requests_per_day(self, value: int) -> int:
        """Validate requests per day with security checks."""
        if not isinstance(value, int) or value < 1 or value > 100000:
            raise serializers.ValidationError("Requests per day must be between 1 and 100000")
        return value
    
    def validate_burst_limit(self, value: int) -> int:
        """Validate burst limit with security checks."""
        if not isinstance(value, int) or value < 1 or value > 1000:
            raise serializers.ValidationError("Burst limit must be between 1 and 1000")
        return value
    
    def validate_is_active(self, value: bool) -> bool:
        """Validate active status with security checks."""
        if not isinstance(value, bool):
            raise serializers.ValidationError("is_active must be a boolean")
        return value


# Request/Response Serializers for API Endpoints

class APIEndpointTestRequestSerializer(serializers.Serializer):
    """Serializer for API endpoint test requests."""
    
    endpoint_id = serializers.UUIDField(required=True)
    method = serializers.ChoiceField(
        choices=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        required=True
    )
    headers = serializers.JSONField(required=False, default=dict)
    query_params = serializers.JSONField(required=False, default=dict)
    body = serializers.JSONField(required=False, default=dict)


class APIEndpointTestResponseSerializer(serializers.Serializer):
    """Serializer for API endpoint test responses."""
    
    success = serializers.BooleanField()
    status_code = serializers.IntegerField()
    response_body = serializers.JSONField()
    processing_time = serializers.FloatField()
    cached = serializers.BooleanField()


class APIEndpointMetricsResponseSerializer(serializers.Serializer):
    """Serializer for API endpoint metrics responses."""
    
    endpoint_id = serializers.UUIDField()
    endpoint_name = serializers.CharField()
    total_requests = serializers.IntegerField()
    successful_requests = serializers.IntegerField()
    failed_requests = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_processing_time = serializers.FloatField()
    last_updated = serializers.DateTimeField()


class APIEndpointLogsResponseSerializer(serializers.Serializer):
    """Serializer for API endpoint logs responses."""
    
    request_id = serializers.CharField()
    method = serializers.CharField()
    path = serializers.CharField()
    status_code = serializers.IntegerField()
    processing_time = serializers.FloatField()
    ip_address = serializers.CharField()
    user_agent = serializers.CharField()
    timestamp = serializers.DateTimeField()


class RESTEndpointCreateRequestSerializer(serializers.Serializer):
    """Serializer for REST endpoint creation requests."""
    
    endpoint_id = serializers.UUIDField(required=True)
    response_format = serializers.ChoiceField(
        choices=['json', 'xml', 'yaml', 'csv', 'text'],
        default='json'
    )
    request_validation = serializers.JSONField(required=False, default=dict)
    response_serialization = serializers.JSONField(required=False, default=dict)
    pagination = serializers.JSONField(required=False, default=dict)
    filtering = serializers.JSONField(required=False, default=dict)
    sorting = serializers.JSONField(required=False, default=dict)


class GraphQLEndpointCreateRequestSerializer(serializers.Serializer):
    """Serializer for GraphQL endpoint creation requests."""
    
    endpoint_id = serializers.UUIDField(required=True)
    schema = serializers.JSONField(required=True)
    resolvers = serializers.JSONField(required=True)
    subscriptions = serializers.JSONField(required=False, default=dict)
    playground_enabled = serializers.BooleanField(default=True)
    introspection_enabled = serializers.BooleanField(default=True)


class WebSocketEndpointCreateRequestSerializer(serializers.Serializer):
    """Serializer for WebSocket endpoint creation requests."""
    
    endpoint_id = serializers.UUIDField(required=True)
    protocol = serializers.ChoiceField(
        choices=['ws', 'wss'],
        default='wss'
    )
    subprotocols = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    heartbeat_interval = serializers.IntegerField(default=30, min_value=1, max_value=300)
    max_connections = serializers.IntegerField(default=1000, min_value=1, max_value=10000)
    message_format = serializers.ChoiceField(
        choices=['json', 'xml', 'text', 'binary'],
        default='json'
    )


class APIDocumentationGenerateRequestSerializer(serializers.Serializer):
    """Serializer for API documentation generation requests."""
    
    endpoint_id = serializers.UUIDField(required=True)
    format = serializers.ChoiceField(
        choices=['openapi', 'swagger', 'raml', 'api_blueprint'],
        default='openapi'
    )
    include_examples = serializers.BooleanField(default=True)
    include_schemas = serializers.BooleanField(default=True)


class APIVersionCreateRequestSerializer(serializers.Serializer):
    """Serializer for API version creation requests."""
    
    version = serializers.CharField(max_length=20, required=True)
    description = serializers.CharField(required=True)
    endpoints = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )
    is_active = serializers.BooleanField(default=True)
    deprecation_date = serializers.DateTimeField(required=False, allow_null=True)


class APIKeyCreateRequestSerializer(serializers.Serializer):
    """Serializer for API key creation requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'read', 'write', 'delete', 'admin', 'campaigns', 'analytics',
            'billing', 'users', 'integrations', 'webhooks'
        ]),
        required=True
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class RateLimitCreateRequestSerializer(serializers.Serializer):
    """Serializer for rate limit creation requests."""
    
    endpoint_id = serializers.UUIDField(required=True)
    requests_per_minute = serializers.IntegerField(min_value=1, max_value=1000, required=True)
    requests_per_hour = serializers.IntegerField(min_value=1, max_value=10000, required=True)
    requests_per_day = serializers.IntegerField(min_value=1, max_value=100000, required=True)
    burst_limit = serializers.IntegerField(min_value=1, max_value=1000, required=True)
    is_active = serializers.BooleanField(default=True)
