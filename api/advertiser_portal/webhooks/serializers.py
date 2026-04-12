"""
Webhooks Serializers

This module provides comprehensive serializers for webhook management with
enterprise-grade validation, security, and performance optimization following
industry standards from Stripe Webhooks, GitHub Webhooks, and Zapier Webhooks.
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
from ..database_models.webhook_model import (
    Webhook, WebhookEvent, WebhookDelivery, WebhookRetry,
    WebhookLog, WebhookQueue, WebhookSecurity
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class WebhookSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Webhook model.
    
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
        model = Webhook
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'url', 'events',
            'secret', 'active', 'retry_policy', 'timeout', 'headers',
            'created_at', 'created_at_formatted', 'updated_at', 'updated_at_formatted',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'secret', 'created_at', 'created_at_formatted',
            'updated_at', 'updated_at_formatted', 'created_by', 'updated_by'
        ]
    
    def get_created_at_formatted(self, obj: Webhook) -> str:
        """Get formatted creation time."""
        try:
            if obj.created_at:
                return obj.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def get_updated_at_formatted(self, obj: Webhook) -> str:
        """Get formatted update time."""
        try:
            if obj.updated_at:
                return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def validate_name(self, value: str) -> str:
        """Validate webhook name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Webhook name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Webhook name contains prohibited characters")
        
        return value
    
    def validate_url(self, value: str) -> str:
        """Validate webhook URL with security checks."""
        if not value:
            raise serializers.ValidationError("Webhook URL is required")
        
        # Security: Validate URL format
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("URL must be a valid HTTP/HTTPS URL")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("URL contains suspicious content")
        
        # Validate URL length
        if len(value) > 2048:
            raise serializers.ValidationError("URL is too long")
        
        return value
    
    def validate_events(self, value: List[str]) -> List[str]:
        """Validate webhook events with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Events must be a list")
        
        # Validate event types
        valid_events = [
            'campaign.created', 'campaign.updated', 'campaign.deleted',
            'ad.created', 'ad.updated', 'ad.deleted',
            'payment.completed', 'payment.failed', 'payment.refunded',
            'user.created', 'user.updated', 'user.deleted',
            'integration.connected', 'integration.disconnected',
            'system.maintenance', 'system.error'
        ]
        
        for event in value:
            if event not in valid_events:
                raise serializers.ValidationError(f"Invalid event type: {event}")
        
        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Events must be unique")
        
        return value
    
    def validate_retry_policy(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate retry policy with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Retry policy must be a dictionary")
        
        # Security: Check for prohibited content
        retry_policy_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, retry_policy_str, re.IGNORECASE):
                raise serializers.ValidationError("Retry policy contains prohibited content")
        
        # Validate retry policy structure
        valid_keys = ['max_retries', 'base_delay', 'max_delay', 'backoff_factor']
        for key in value.keys():
            if key not in valid_keys:
                raise serializers.ValidationError(f"Invalid retry policy key: {key}")
        
        # Validate specific values
        if 'max_retries' in value:
            max_retries = value['max_retries']
            if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 10:
                raise serializers.ValidationError("max_retries must be between 0 and 10")
        
        if 'base_delay' in value:
            base_delay = value['base_delay']
            if not isinstance(base_delay, int) or base_delay < 1 or base_delay > 3600:
                raise serializers.ValidationError("base_delay must be between 1 and 3600 seconds")
        
        if 'max_delay' in value:
            max_delay = value['max_delay']
            if not isinstance(max_delay, int) or max_delay < 1 or max_delay > 86400:
                raise serializers.ValidationError("max_delay must be between 1 and 86400 seconds")
        
        if 'backoff_factor' in value:
            backoff_factor = value['backoff_factor']
            if not isinstance(backoff_factor, (int, float)) or backoff_factor < 1 or backoff_factor > 10:
                raise serializers.ValidationError("backoff_factor must be between 1 and 10")
        
        return value
    
    def validate_timeout(self, value: int) -> int:
        """Validate timeout with security checks."""
        if not isinstance(value, int) or value < 1 or value > 300:
            raise serializers.ValidationError("Timeout must be between 1 and 300 seconds")
        return value
    
    def validate_headers(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate headers with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Headers must be a dictionary")
        
        # Security: Check for prohibited content
        headers_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, headers_str, re.IGNORECASE):
                raise serializers.ValidationError("Headers contain prohibited content")
        
        # Validate header structure
        for key, val in value.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise serializers.ValidationError("Header keys and values must be strings")
            
            # Check for prohibited header names
            prohibited_headers = ['Host', 'Connection', 'Upgrade']
            if key in prohibited_headers:
                raise serializers.ValidationError(f"Prohibited header name: {key}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate advertiser access
        advertiser = attrs.get('advertiser')
        if advertiser and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
        
        # Business logic: Validate URL uniqueness per advertiser
        url = attrs.get('url')
        advertiser = attrs.get('advertiser')
        
        if url and advertiser:
            existing_webhook = Webhook.objects.filter(
                url=url,
                advertiser=advertiser
            ).exclude(id=self.instance.id if self.instance else None).first()
            
            if existing_webhook:
                raise serializers.ValidationError(f"Webhook with URL '{url}' already exists for this advertiser")
        
        # Business logic: Validate retry policy defaults
        retry_policy = attrs.get('retry_policy', {})
        if not retry_policy:
            attrs['retry_policy'] = {
                'max_retries': 3,
                'base_delay': 60,
                'max_delay': 3600,
                'backoff_factor': 2
            }
        
        # Business logic: Validate timeout defaults
        if 'timeout' not in attrs:
            attrs['timeout'] = 30
        
        return attrs


class WebhookCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating webhooks.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    url = serializers.URLField(max_length=2048, required=True)
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'campaign.created', 'campaign.updated', 'campaign.deleted',
            'ad.created', 'ad.updated', 'ad.deleted',
            'payment.completed', 'payment.failed', 'payment.refunded',
            'user.created', 'user.updated', 'user.deleted',
            'integration.connected', 'integration.disconnected',
            'system.maintenance', 'system.error'
        ]),
        required=True,
        min_length=1
    )
    active = serializers.BooleanField(required=False, default=True)
    retry_policy = serializers.JSONField(required=False, default=dict)
    timeout = serializers.IntegerField(required=False, default=30, min_value=1, max_value=300)
    headers = serializers.JSONField(required=False, default=dict)
    
    def validate_name(self, value: str) -> str:
        """Validate webhook name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Webhook name must be at least 3 characters long")
        
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
                raise serializers.ValidationError("Webhook name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Webhook name contains prohibited characters")
        
        # Validate name length
        if len(value) > 255:
            raise serializers.ValidationError("Webhook name is too long")
        
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
    
    def validate_url(self, value: str) -> str:
        """Validate webhook URL with comprehensive security checks."""
        if not value:
            raise serializers.ValidationError("Webhook URL is required")
        
        # Security: Validate URL format
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("URL must be a valid HTTP/HTTPS URL")
        
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
                raise serializers.ValidationError("URL contains suspicious content")
        
        # Validate URL structure
        if '..' in value:
            raise serializers.ValidationError("URL cannot contain directory traversal")
        
        # Validate URL length
        if len(value) > 2048:
            raise serializers.ValidationError("URL is too long")
        
        return value
    
    def validate_events(self, value: List[str]) -> List[str]:
        """Validate webhook events with comprehensive security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Events must be a list")
        
        if len(value) == 0:
            raise serializers.ValidationError("At least one event must be specified")
        
        # Validate event types
        valid_events = [
            'campaign.created', 'campaign.updated', 'campaign.deleted',
            'ad.created', 'ad.updated', 'ad.deleted',
            'payment.completed', 'payment.failed', 'payment.refunded',
            'user.created', 'user.updated', 'user.deleted',
            'integration.connected', 'integration.disconnected',
            'system.maintenance', 'system.error'
        ]
        
        for event in value:
            if event not in valid_events:
                raise serializers.ValidationError(f"Invalid event type: {event}")
        
        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Events must be unique")
        
        return value
    
    def validate_retry_policy(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate retry policy with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Retry policy must be a dictionary")
        
        # Security: Check for prohibited content
        retry_policy_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, retry_policy_str, re.IGNORECASE):
                raise serializers.ValidationError("Retry policy contains prohibited content")
        
        # Validate retry policy structure
        valid_keys = ['max_retries', 'base_delay', 'max_delay', 'backoff_factor']
        for key in value.keys():
            if key not in valid_keys:
                raise serializers.ValidationError(f"Invalid retry policy key: {key}")
        
        # Validate specific values
        if 'max_retries' in value:
            max_retries = value['max_retries']
            if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 10:
                raise serializers.ValidationError("max_retries must be between 0 and 10")
        
        if 'base_delay' in value:
            base_delay = value['base_delay']
            if not isinstance(base_delay, int) or base_delay < 1 or base_delay > 3600:
                raise serializers.ValidationError("base_delay must be between 1 and 3600 seconds")
        
        if 'max_delay' in value:
            max_delay = value['max_delay']
            if not isinstance(max_delay, int) or max_delay < 1 or max_delay > 86400:
                raise serializers.ValidationError("max_delay must be between 1 and 86400 seconds")
        
        if 'backoff_factor' in value:
            backoff_factor = value['backoff_factor']
            if not isinstance(backoff_factor, (int, float)) or backoff_factor < 1 or backoff_factor > 10:
                raise serializers.ValidationError("backoff_factor must be between 1 and 10")
        
        return value
    
    def validate_timeout(self, value: int) -> int:
        """Validate timeout with comprehensive security checks."""
        if not isinstance(value, int) or value < 1 or value > 300:
            raise serializers.ValidationError("Timeout must be between 1 and 300 seconds")
        return value
    
    def validate_headers(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate headers with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Headers must be a dictionary")
        
        # Security: Check for prohibited content
        headers_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, headers_str, re.IGNORECASE):
                raise serializers.ValidationError("Headers contain prohibited content")
        
        # Validate header structure
        for key, val in value.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise serializers.ValidationError("Header keys and values must be strings")
            
            # Check for prohibited header names
            prohibited_headers = ['Host', 'Connection', 'Upgrade', 'Content-Length']
            if key in prohibited_headers:
                raise serializers.ValidationError(f"Prohibited header name: {key}")
            
            # Validate header length
            if len(key) > 100 or len(val) > 1000:
                raise serializers.ValidationError("Header name or value is too long")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate URL uniqueness per advertiser
        url = attrs.get('url')
        advertiser_id = attrs.get('advertiser_id')
        
        if url and advertiser_id:
            try:
                advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
                
                existing_webhook = Webhook.objects.filter(
                    url=url,
                    advertiser=advertiser
                ).first()
                
                if existing_webhook:
                    raise serializers.ValidationError(f"Webhook with URL '{url}' already exists for this advertiser")
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
        
        # Business logic: Validate retry policy defaults
        retry_policy = attrs.get('retry_policy', {})
        if not retry_policy:
            attrs['retry_policy'] = {
                'max_retries': 3,
                'base_delay': 60,
                'max_delay': 3600,
                'backoff_factor': 2
            }
        
        # Business logic: Validate timeout defaults
        if 'timeout' not in attrs:
            attrs['timeout'] = 30
        
        # Business logic: Validate headers defaults
        if 'headers' not in attrs:
            attrs['headers'] = {}
        
        return attrs


class WebhookEventSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebhookEvent model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'event_id', 'event_type', 'data', 'source',
            'user_id', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'event_id', 'created_at']
    
    def validate_event_type(self, value: str) -> str:
        """Validate event type with security checks."""
        valid_types = [
            'campaign.created', 'campaign.updated', 'campaign.deleted',
            'ad.created', 'ad.updated', 'ad.deleted',
            'payment.completed', 'payment.failed', 'payment.refunded',
            'user.created', 'user.updated', 'user.deleted',
            'integration.connected', 'integration.disconnected',
            'system.maintenance', 'system.error'
        ]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid event type. Must be one of: {valid_types}")
        return value
    
    def validate_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate event data with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Event data must be a dictionary")
        
        # Security: Check for prohibited content
        data_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, data_str, re.IGNORECASE):
                raise serializers.ValidationError("Event data contains prohibited content")
        
        # Validate data size
        data_size = len(data_str)
        if data_size > 1048576:  # 1MB limit
            raise serializers.ValidationError("Event data is too large")
        
        return value
    
    def validate_source(self, value: str) -> str:
        """Validate event source with security checks."""
        valid_sources = ['system', 'user', 'integration', 'external']
        if value not in valid_sources:
            raise serializers.ValidationError(f"Invalid source. Must be one of: {valid_sources}")
        return value
    
    def validate_user_id(self, value: Optional[str]) -> Optional[str]:
        """Validate user ID with security checks."""
        if value is not None:
            try:
                UUID(value)
            except ValueError:
                raise serializers.ValidationError("Invalid user ID format")
        return value
    
    def validate_metadata(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        
        # Security: Check for prohibited content
        metadata_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, metadata_str, re.IGNORECASE):
                raise serializers.ValidationError("Metadata contains prohibited content")
        
        return value


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebhookDelivery model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = WebhookDelivery
        fields = [
            'id', 'webhook_id', 'event_id', 'attempt', 'status',
            'response_code', 'response_body', 'error_message',
            'delivered_at', 'duration', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_status(self, value: str) -> str:
        """Validate delivery status with security checks."""
        valid_statuses = ['pending', 'processing', 'delivered', 'failed', 'timeout', 'retry']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_response_code(self, value: Optional[int]) -> Optional[int]:
        """Validate response code with security checks."""
        if value is not None:
            if not isinstance(value, int) or value < 100 or value > 599:
                raise serializers.ValidationError("Response code must be between 100 and 599")
        return value
    
    def validate_response_body(self, value: Optional[str]) -> Optional[str]:
        """Validate response body with security checks."""
        if value is not None:
            if not isinstance(value, str):
                raise serializers.ValidationError("Response body must be a string")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Response body contains prohibited content")
            
            # Validate response body length
            if len(value) > 10000:  # 10KB limit
                raise serializers.ValidationError("Response body is too long")
        
        return value
    
    def validate_error_message(self, value: Optional[str]) -> Optional[str]:
        """Validate error message with security checks."""
        if value is not None:
            if not isinstance(value, str):
                raise serializers.ValidationError("Error message must be a string")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Error message contains prohibited content")
            
            # Validate error message length
            if len(value) > 1000:
                raise serializers.ValidationError("Error message is too long")
        
        return value
    
    def validate_duration(self, value: float) -> float:
        """Validate duration with security checks."""
        if not isinstance(value, (int, float)) or value < 0 or value > 300:
            raise serializers.ValidationError("Duration must be between 0 and 300 seconds")
        return float(value)


class WebhookRetrySerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebhookRetry model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = WebhookRetry
        fields = [
            'id', 'delivery_id', 'attempt', 'status', 'scheduled_at',
            'delay', 'executed_at', 'result', 'error_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_status(self, value: str) -> str:
        """Validate retry status with security checks."""
        valid_statuses = ['pending', 'processing', 'completed', 'failed']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_delay(self, value: int) -> int:
        """Validate delay with security checks."""
        if not isinstance(value, int) or value < 0 or value > 86400:
            raise serializers.ValidationError("Delay must be between 0 and 86400 seconds")
        return value
    
    def validate_result(self, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate result with security checks."""
        if value is not None:
            if not isinstance(value, dict):
                raise serializers.ValidationError("Result must be a dictionary")
            
            # Security: Check for prohibited content
            result_str = json.dumps(value)
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, result_str, re.IGNORECASE):
                    raise serializers.ValidationError("Result contains prohibited content")
        
        return value
    
    def validate_error_message(self, value: Optional[str]) -> Optional[str]:
        """Validate error message with security checks."""
        if value is not None:
            if not isinstance(value, str):
                raise serializers.ValidationError("Error message must be a string")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Error message contains prohibited content")
            
            # Validate error message length
            if len(value) > 1000:
                raise serializers.ValidationError("Error message is too long")
        
        return value


class WebhookLogSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebhookLog model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = WebhookLog
        fields = [
            'id', 'webhook_id', 'event_id', 'action', 'status',
            'message', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_action(self, value: str) -> str:
        """Validate action with security checks."""
        valid_actions = [
            'created', 'updated', 'deleted', 'triggered', 'delivered',
            'failed', 'retry', 'timeout', 'error'
        ]
        if value not in valid_actions:
            raise serializers.ValidationError(f"Invalid action. Must be one of: {valid_actions}")
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate log status with security checks."""
        valid_statuses = ['success', 'warning', 'error', 'info']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_message(self, value: str) -> str:
        """Validate message with security checks."""
        if not isinstance(value, str):
            raise serializers.ValidationError("Message must be a string")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Message contains prohibited content")
        
        # Validate message length
        if len(value) > 1000:
            raise serializers.ValidationError("Message is too long")
        
        return value
    
    def validate_metadata(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        
        # Security: Check for prohibited content
        metadata_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, metadata_str, re.IGNORECASE):
                raise serializers.ValidationError("Metadata contains prohibited content")
        
        return value


class WebhookQueueSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebhookQueue model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = WebhookQueue
        fields = [
            'id', 'webhook_id', 'event_id', 'priority', 'status',
            'processed_at', 'result', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_priority(self, value: int) -> int:
        """Validate priority with security checks."""
        if not isinstance(value, int) or value < 0 or value > 100:
            raise serializers.ValidationError("Priority must be between 0 and 100")
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate queue status with security checks."""
        valid_statuses = ['pending', 'processing', 'completed', 'failed']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_result(self, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate result with security checks."""
        if value is not None:
            if not isinstance(value, dict):
                raise serializers.ValidationError("Result must be a dictionary")
            
            # Security: Check for prohibited content
            result_str = json.dumps(value)
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, result_str, re.IGNORECASE):
                    raise serializers.ValidationError("Result contains prohibited content")
        
        return value


class WebhookSecuritySerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebhookSecurity model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = WebhookSecurity
        fields = [
            'id', 'webhook_id', 'ip_address', 'action', 'reason',
            'blocked_until', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_ip_address(self, value: str) -> str:
        """Validate IP address with security checks."""
        import ipaddress
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise serializers.ValidationError("Invalid IP address format")
        return value
    
    def validate_action(self, value: str) -> str:
        """Validate security action with security checks."""
        valid_actions = ['blocked', 'unblocked', 'monitored', 'flagged']
        if value not in valid_actions:
            raise serializers.ValidationError(f"Invalid action. Must be one of: {valid_actions}")
        return value
    
    def validate_reason(self, value: str) -> str:
        """Validate reason with security checks."""
        if not isinstance(value, str):
            raise serializers.ValidationError("Reason must be a string")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Reason contains prohibited content")
        
        # Validate reason length
        if len(value) > 500:
            raise serializers.ValidationError("Reason is too long")
        
        return value


# Request/Response Serializers for Webhook Endpoints

class WebhookCreateRequestSerializer(serializers.Serializer):
    """Serializer for webhook creation requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    url = serializers.URLField(max_length=2048, required=True)
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'campaign.created', 'campaign.updated', 'campaign.deleted',
            'ad.created', 'ad.updated', 'ad.deleted',
            'payment.completed', 'payment.failed', 'payment.refunded',
            'user.created', 'user.updated', 'user.deleted',
            'integration.connected', 'integration.disconnected',
            'system.maintenance', 'system.error'
        ]),
        required=True,
        min_length=1
    )
    active = serializers.BooleanField(default=True)
    retry_policy = serializers.JSONField(default=dict)
    timeout = serializers.IntegerField(default=30, min_value=1, max_value=300)
    headers = serializers.JSONField(default=dict)


class WebhookTriggerRequestSerializer(serializers.Serializer):
    """Serializer for webhook trigger requests."""
    
    event_type = serializers.ChoiceField(choices=[
        'campaign.created', 'campaign.updated', 'campaign.deleted',
        'ad.created', 'ad.updated', 'ad.deleted',
        'payment.completed', 'payment.failed', 'payment.refunded',
        'user.created', 'user.updated', 'user.deleted',
        'integration.connected', 'integration.disconnected',
        'system.maintenance', 'system.error'
    ], required=True)
    data = serializers.JSONField(required=True)
    source = serializers.CharField(default='system')
    user_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(default=dict)


class WebhookTestRequestSerializer(serializers.Serializer):
    """Serializer for webhook test requests."""
    
    event_type = serializers.ChoiceField(choices=[
        'campaign.created', 'campaign.updated', 'campaign.deleted',
        'ad.created', 'ad.updated', 'ad.deleted',
        'payment.completed', 'payment.failed', 'payment.refunded',
        'user.created', 'user.updated', 'user.deleted',
        'integration.connected', 'integration.disconnected',
        'system.maintenance', 'system.error'
    ], required=True)
    data = serializers.JSONField(required=True)
    source = serializers.CharField(default='test')


class WebhookTestResponseSerializer(serializers.Serializer):
    """Serializer for webhook test responses."""
    
    success = serializers.BooleanField()
    delivery_id = serializers.UUIDField()
    status_code = serializers.IntegerField()
    response_body = serializers.CharField()
    error_message = serializers.CharField()
    duration = serializers.FloatField()


class WebhookStatsResponseSerializer(serializers.Serializer):
    """Serializer for webhook stats responses."""
    
    webhook_id = serializers.UUIDField()
    webhook_name = serializers.CharField()
    total_deliveries = serializers.IntegerField()
    successful_deliveries = serializers.IntegerField()
    failed_deliveries = serializers.IntegerField()
    timeout_deliveries = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_response_time = serializers.FloatField()
    error_breakdown = serializers.ListField()
    last_30_days = serializers.DateTimeField()


class WebhookDeliveryResponseSerializer(serializers.Serializer):
    """Serializer for webhook delivery responses."""
    
    delivery_id = serializers.UUIDField()
    event_id = serializers.CharField()
    attempt = serializers.IntegerField()
    status = serializers.CharField()
    response_code = serializers.IntegerField()
    response_body = serializers.CharField()
    error_message = serializers.CharField()
    delivered_at = serializers.DateTimeField()
    duration = serializers.FloatField()
    created_at = serializers.DateTimeField()


class WebhookEventResponseSerializer(serializers.Serializer):
    """Serializer for webhook event responses."""
    
    event_id = serializers.CharField()
    event_type = serializers.CharField()
    data = serializers.JSONField()
    source = serializers.CharField()
    user_id = serializers.CharField()
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()


class WebhookHealthResponseSerializer(serializers.Serializer):
    """Serializer for webhook health responses."""
    
    webhook_id = serializers.UUIDField()
    webhook_name = serializers.CharField()
    health_status = serializers.CharField()
    success_rate = serializers.FloatField()
    total_deliveries_24h = serializers.IntegerField()
    successful_deliveries_24h = serializers.IntegerField()
    last_delivery = serializers.DateTimeField()
    checked_at = serializers.DateTimeField()


class WebhookSystemHealthResponseSerializer(serializers.Serializer):
    """Serializer for system health responses."""
    
    total_active_webhooks = serializers.IntegerField()
    total_events_24h = serializers.IntegerField()
    total_deliveries_24h = serializers.IntegerField()
    successful_deliveries_24h = serializers.IntegerField()
    success_rate_24h = serializers.FloatField()
    pending_retries = serializers.IntegerField()
    system_status = serializers.CharField()
    checked_at = serializers.DateTimeField()


class WebhookMetricsResponseSerializer(serializers.Serializer):
    """Serializer for webhook metrics responses."""
    
    total_deliveries = serializers.IntegerField()
    successful_deliveries = serializers.IntegerField()
    failed_deliveries = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_response_time = serializers.FloatField()
    period = serializers.DictField()


class WebhookSecurityBlockIPRequestSerializer(serializers.Serializer):
    """Serializer for IP blocking requests."""
    
    ip_address = serializers.IPAddressField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class WebhookSecurityUnblockIPRequestSerializer(serializers.Serializer):
    """Serializer for IP unblocking requests."""
    
    ip_address = serializers.IPAddressField(required=True)


class WebhookSecurityVerifySignatureRequestSerializer(serializers.Serializer):
    """Serializer for signature verification requests."""
    
    payload = serializers.JSONField(required=True)
    signature = serializers.CharField(required=True)
    secret = serializers.CharField(required=True)


class WebhookSecurityVerifySignatureResponseSerializer(serializers.Serializer):
    """Serializer for signature verification responses."""
    
    valid = serializers.BooleanField()
    signature = serializers.CharField()
    timestamp = serializers.DateTimeField()


class WebhookQueueStatsResponseSerializer(serializers.Serializer):
    """Serializer for queue stats responses."""
    
    pending_count = serializers.IntegerField()
    processing_count = serializers.IntegerField()
    completed_count_1h = serializers.IntegerField()
    total_in_queue = serializers.IntegerField()
    checked_at = serializers.DateTimeField()


class WebhookQueueProcessResponseSerializer(serializers.Serializer):
    """Serializer for queue processing responses."""
    
    processed_count = serializers.IntegerField()
    processed_retries = serializers.ListField(child=serializers.UUIDField())
