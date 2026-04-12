"""
Scripts Serializers

This module provides comprehensive serializers for script management with
enterprise-grade validation, security, and performance optimization following
industry standards from Jenkins, GitHub Actions, and Ansible.
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
from ..database_models.script_model import (
    Script, AutomationScript, DataProcessingScript, MaintenanceScript,
    DeploymentScript, ScriptExecution, ScriptLog, ScriptSecurity
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class ScriptSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Script model.
    
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
        model = Script
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'type', 'content',
            'parameters', 'environment', 'timeout', 'retry_policy', 'status',
            'created_at', 'created_at_formatted', 'updated_at', 'updated_at_formatted',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_at_formatted', 'updated_at',
            'updated_at_formatted', 'created_by', 'updated_by'
        ]
    
    def get_created_at_formatted(self, obj: Script) -> str:
        """Get formatted creation time."""
        try:
            if obj.created_at:
                return obj.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def get_updated_at_formatted(self, obj: Script) -> str:
        """Get formatted update time."""
        try:
            if obj.updated_at:
                return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def validate_name(self, value: str) -> str:
        """Validate script name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Script name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Script name contains prohibited characters")
        
        return value
    
    def validate_type(self, value: str) -> str:
        """Validate script type with security checks."""
        valid_types = ['automation', 'data_processing', 'maintenance', 'deployment']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid script type. Must be one of: {valid_types}")
        return value
    
    def validate_content(self, value: str) -> str:
        """Validate script content with security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Script content is too short")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'eval\s*\(',             # Code execution
            r'exec\s*\(',             # Code execution
            r'system\s*\(',           # System calls
            r'os\.system',            # System calls
            r'subprocess\.call',       # Subprocess calls
            r'import\s+os',           # OS imports
            r'import\s+sys',          # System imports
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Script content contains prohibited code")
        
        return value
    
    def validate_parameters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate script parameters with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a dictionary")
        
        # Security: Check for prohibited content
        parameters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, parameters_str, re.IGNORECASE):
                raise serializers.ValidationError("Parameters contain prohibited content")
        
        # Validate parameter structure
        for key, val in value.items():
            if not isinstance(key, str):
                raise serializers.ValidationError("Parameter keys must be strings")
            
            # Check for prohibited content in values
            if isinstance(val, str):
                prohibited_patterns = [
                    r'<script', r'javascript:', r'on\w+\s*='
                ]
                
                for pattern in prohibited_patterns:
                    if re.search(pattern, val, re.IGNORECASE):
                        raise serializers.ValidationError(f"Parameter {key} contains prohibited content")
        
        return value
    
    def validate_environment(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate environment variables with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Environment must be a dictionary")
        
        # Security: Check for prohibited content
        env_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, env_str, re.IGNORECASE):
                raise serializers.ValidationError("Environment contains prohibited content")
        
        # Validate environment structure
        for key, val in value.items():
            if not isinstance(key, str):
                raise serializers.ValidationError("Environment keys must be strings")
            
            # Check for prohibited environment variables
            prohibited_env_vars = [
                'PATH', 'HOME', 'USER', 'SHELL', 'ENV',
                'PYTHONPATH', 'DJANGO_SETTINGS_MODULE'
            ]
            
            if key in prohibited_env_vars:
                raise serializers.ValidationError(f"Prohibited environment variable: {key}")
        
        return value
    
    def validate_timeout(self, value: int) -> int:
        """Validate timeout with security checks."""
        if not isinstance(value, int) or value < 1 or value > 3600:
            raise serializers.ValidationError("Timeout must be between 1 and 3600 seconds")
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
    
    def validate_status(self, value: str) -> str:
        """Validate script status with security checks."""
        valid_statuses = ['active', 'inactive', 'deprecated', 'maintenance']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate advertiser access
        advertiser = attrs.get('advertiser')
        if advertiser and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
        
        # Business logic: Validate script type vs content
        script_type = attrs.get('type')
        content = attrs.get('content', '')
        
        if script_type == 'automation':
            ScriptSerializer._validate_automation_content(content)
        elif script_type == 'data_processing':
            ScriptSerializer._validate_data_processing_content(content)
        elif script_type == 'maintenance':
            ScriptSerializer._validate_maintenance_content(content)
        elif script_type == 'deployment':
            ScriptSerializer._validate_deployment_content(content)
        
        return attrs
    
    @staticmethod
    def _validate_automation_content(content: str) -> None:
        """Validate automation script content."""
        # Check for automation-specific patterns
        automation_patterns = [
            r'while\s+True',           # Infinite loops
            r'for\s+.*\s+range\s*\(', # Large ranges
            r'time\.sleep',            # Sleep calls
            r'open\s*\(',              # File operations
            r'file\s*\(',              # File operations
        ]
        
        import re
        for pattern in automation_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Automation script contains potentially unsafe code")
    
    @staticmethod
    def _validate_data_processing_content(content: str) -> None:
        """Validate data processing script content."""
        # Check for data processing-specific patterns
        data_patterns = [
            r'drop\s+table',           # Database operations
            r'delete\s+from',          # Database operations
            r'truncate\s+table',        # Database operations
            r'rm\s+-rf',               # File operations
            r'del\s+.*\/s',            # File operations
        ]
        
        import re
        for pattern in data_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Data processing script contains potentially unsafe operations")
    
    @staticmethod
    def _validate_maintenance_content(content: str) -> None:
        """Validate maintenance script content."""
        # Check for maintenance-specific patterns
        maintenance_patterns = [
            r'shutdown',                # System shutdown
            r'reboot',                  # System reboot
            r'format',                  # Disk formatting
            r'fdisk',                   # Disk operations
            r'mkfs',                    # Filesystem operations
        ]
        
        import re
        for pattern in maintenance_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Maintenance script contains potentially dangerous operations")
    
    @staticmethod
    def _validate_deployment_content(content: str) -> None:
        """Validate deployment script content."""
        # Check for deployment-specific patterns
        deployment_patterns = [
            r'sudo\s+',                # Sudo operations
            r'chmod\s+777',            # File permissions
            r'chown\s+',                # File ownership
            r'su\s+',                   # User switching
        ]
        
        import re
        for pattern in deployment_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Deployment script contains potentially dangerous operations")


class ScriptCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating scripts.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    type = serializers.ChoiceField(
        choices=['automation', 'data_processing', 'maintenance', 'deployment'],
        required=True
    )
    content = serializers.CharField(required=True)
    parameters = serializers.JSONField(required=False, default=dict)
    environment = serializers.JSONField(required=False, default=dict)
    timeout = serializers.IntegerField(required=False, default=300, min_value=1, max_value=3600)
    retry_policy = serializers.JSONField(required=False, default=dict)
    status = serializers.ChoiceField(
        choices=['active', 'inactive', 'deprecated', 'maintenance'],
        required=False,
        default='active'
    )
    
    def validate_name(self, value: str) -> str:
        """Validate script name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Script name must be at least 3 characters long")
        
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
                raise serializers.ValidationError("Script name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Script name contains prohibited characters")
        
        # Validate name length
        if len(value) > 255:
            raise serializers.ValidationError("Script name is too long")
        
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
    
    def validate_content(self, value: str) -> str:
        """Validate script content with comprehensive security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Script content is too short")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'eval\s*\(',             # Code execution
            r'exec\s*\(',             # Code execution
            r'system\s*\(',           # System calls
            r'os\.system',            # System calls
            r'subprocess\.call',       # Subprocess calls
            r'import\s+os',           # OS imports
            r'import\s+sys',          # System imports
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Script content contains prohibited code")
        
        # Validate content length
        if len(value) > 1048576:  # 1MB limit
            raise serializers.ValidationError("Script content is too large")
        
        return value
    
    def validate_parameters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate script parameters with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a dictionary")
        
        # Security: Check for prohibited content
        parameters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, parameters_str, re.IGNORECASE):
                raise serializers.ValidationError("Parameters contain prohibited content")
        
        # Validate parameter structure
        for key, val in value.items():
            if not isinstance(key, str):
                raise serializers.ValidationError("Parameter keys must be strings")
            
            # Check for prohibited content in values
            if isinstance(val, str):
                prohibited_patterns = [
                    r'<script', r'javascript:', r'on\w+\s*='
                ]
                
                for pattern in prohibited_patterns:
                    if re.search(pattern, val, re.IGNORECASE):
                        raise serializers.ValidationError(f"Parameter {key} contains prohibited content")
        
        return value
    
    def validate_environment(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate environment variables with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Environment must be a dictionary")
        
        # Security: Check for prohibited content
        env_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, env_str, re.IGNORECASE):
                raise serializers.ValidationError("Environment contains prohibited content")
        
        # Validate environment structure
        for key, val in value.items():
            if not isinstance(key, str):
                raise serializers.ValidationError("Environment keys must be strings")
            
            # Check for prohibited environment variables
            prohibited_env_vars = [
                'PATH', 'HOME', 'USER', 'SHELL', 'ENV',
                'PYTHONPATH', 'DJANGO_SETTINGS_MODULE'
            ]
            
            if key in prohibited_env_vars:
                raise serializers.ValidationError(f"Prohibited environment variable: {key}")
        
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
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate script type vs content
        script_type = attrs.get('type')
        content = attrs.get('content', '')
        
        if script_type == 'automation':
            ScriptCreateSerializer._validate_automation_content(content)
        elif script_type == 'data_processing':
            ScriptCreateSerializer._validate_data_processing_content(content)
        elif script_type == 'maintenance':
            ScriptCreateSerializer._validate_maintenance_content(content)
        elif script_type == 'deployment':
            ScriptCreateSerializer._validate_deployment_content(content)
        
        # Business logic: Validate retry policy defaults
        retry_policy = attrs.get('retry_policy', {})
        if not retry_policy:
            attrs['retry_policy'] = {
                'max_retries': 3,
                'base_delay': 60,
                'max_delay': 3600,
                'backoff_factor': 2
            }
        
        # Business logic: Validate environment defaults
        if 'environment' not in attrs:
            attrs['environment'] = {}
        
        return attrs
    
    @staticmethod
    def _validate_automation_content(content: str) -> None:
        """Validate automation script content."""
        # Check for automation-specific patterns
        automation_patterns = [
            r'while\s+True',           # Infinite loops
            r'for\s+.*\s+range\s*\(', # Large ranges
            r'time\.sleep',            # Sleep calls
            r'open\s*\(',              # File operations
            r'file\s*\(',              # File operations
        ]
        
        import re
        for pattern in automation_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Automation script contains potentially unsafe code")
    
    @staticmethod
    def _validate_data_processing_content(content: str) -> None:
        """Validate data processing script content."""
        # Check for data processing-specific patterns
        data_patterns = [
            r'drop\s+table',           # Database operations
            r'delete\s+from',          # Database operations
            r'truncate\s+table',        # Database operations
            r'rm\s+-rf',               # File operations
            r'del\s+.*\/s',            # File operations
        ]
        
        import re
        for pattern in data_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Data processing script contains potentially unsafe operations")
    
    @staticmethod
    def _validate_maintenance_content(content: str) -> None:
        """Validate maintenance script content."""
        # Check for maintenance-specific patterns
        maintenance_patterns = [
            r'shutdown',                # System shutdown
            r'reboot',                  # System reboot
            r'format',                  # Disk formatting
            r'fdisk',                   # Disk operations
            r'mkfs',                    # Filesystem operations
        ]
        
        import re
        for pattern in maintenance_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Maintenance script contains potentially dangerous operations")
    
    @staticmethod
    def _validate_deployment_content(content: str) -> None:
        """Validate deployment script content."""
        # Check for deployment-specific patterns
        deployment_patterns = [
            r'sudo\s+',                # Sudo operations
            r'chmod\s+777',            # File permissions
            r'chown\s+',                # File ownership
            r'su\s+',                   # User switching
        ]
        
        import re
        for pattern in deployment_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise serializers.ValidationError("Deployment script contains potentially dangerous operations")


class AutomationScriptSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for AutomationScript model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = AutomationScript
        fields = [
            'id', 'script', 'trigger_type', 'trigger_config',
            'actions', 'conditions'
        ]
        read_only_fields = ['id', 'script']
    
    def validate_trigger_type(self, value: str) -> str:
        """Validate trigger type with security checks."""
        valid_triggers = ['manual', 'schedule', 'event', 'webhook']
        if value not in valid_triggers:
            raise serializers.ValidationError(f"Invalid trigger type. Must be one of: {valid_triggers}")
        return value
    
    def validate_trigger_config(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trigger configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Trigger configuration must be a dictionary")
        
        # Security: Check for prohibited content
        trigger_config_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, trigger_config_str, re.IGNORECASE):
                raise serializers.ValidationError("Trigger configuration contains prohibited content")
        
        return value
    
    def validate_actions(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate actions with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Actions must be a list")
        
        # Validate each action
        for action in value:
            if not isinstance(action, dict):
                raise serializers.ValidationError("Each action must be a dictionary")
            
            if 'type' not in action:
                raise serializers.ValidationError("Each action must have a type")
        
        return value
    
    def validate_conditions(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate conditions with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Conditions must be a list")
        
        # Validate each condition
        for condition in value:
            if not isinstance(condition, dict):
                raise serializers.ValidationError("Each condition must be a dictionary")
            
            if 'type' not in condition:
                raise serializers.ValidationError("Each condition must have a type")
        
        return value


class DataProcessingScriptSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for DataProcessingScript model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = DataProcessingScript
        fields = [
            'id', 'script', 'data_source', 'data_target',
            'processing_type', 'batch_size', 'retry_count'
        ]
        read_only_fields = ['id', 'script']
    
    def validate_data_source(self, value: str) -> str:
        """Validate data source with security checks."""
        if not value:
            raise serializers.ValidationError("Data source is required")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Data source contains suspicious content")
        
        return value
    
    def validate_data_target(self, value: str) -> str:
        """Validate data target with security checks."""
        if not value:
            raise serializers.ValidationError("Data target is required")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Data target contains suspicious content")
        
        return value
    
    def validate_processing_type(self, value: str) -> str:
        """Validate processing type with security checks."""
        valid_types = ['etl', 'elt', 'validation', 'transformation', 'aggregation']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid processing type. Must be one of: {valid_types}")
        return value
    
    def validate_batch_size(self, value: int) -> int:
        """Validate batch size with security checks."""
        if not isinstance(value, int) or value < 1 or value > 100000:
            raise serializers.ValidationError("Batch size must be between 1 and 100000")
        return value
    
    def validate_retry_count(self, value: int) -> int:
        """Validate retry count with security checks."""
        if not isinstance(value, int) or value < 0 or value > 10:
            raise serializers.ValidationError("Retry count must be between 0 and 10")
        return value


class MaintenanceScriptSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for MaintenanceScript model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = MaintenanceScript
        fields = [
            'id', 'script', 'maintenance_type', 'target_systems',
            'impact_level', 'approval_required'
        ]
        read_only_fields = ['id', 'script']
    
    def validate_maintenance_type(self, value: str) -> str:
        """Validate maintenance type with security checks."""
        valid_types = ['cleanup', 'backup', 'restore', 'update', 'optimization']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid maintenance type. Must be one of: {valid_types}")
        return value
    
    def validate_target_systems(self, value: List[str]) -> List[str]:
        """Validate target systems with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Target systems must be a list")
        
        # Validate each system
        for system in value:
            if not isinstance(system, str):
                raise serializers.ValidationError("Each target system must be a string")
        
        return value
    
    def validate_impact_level(self, value: str) -> str:
        """Validate impact level with security checks."""
        valid_impacts = ['low', 'medium', 'high', 'critical']
        if value not in valid_impacts:
            raise serializers.ValidationError(f"Invalid impact level. Must be one of: {valid_impacts}")
        return value
    
    def validate_approval_required(self, value: bool) -> bool:
        """Validate approval requirement with security checks."""
        if not isinstance(value, bool):
            raise serializers.ValidationError("Approval required must be a boolean")
        return value


class DeploymentScriptSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for DeploymentScript model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = DeploymentScript
        fields = [
            'id', 'script', 'deployment_type', 'target_environment',
            'rollback_script', 'approval_required'
        ]
        read_only_fields = ['id', 'script']
    
    def validate_deployment_type(self, value: str) -> str:
        """Validate deployment type with security checks."""
        valid_types = ['manual', 'automatic', 'rollback', 'blue_green', 'canary']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid deployment type. Must be one of: {valid_types}")
        return value
    
    def validate_target_environment(self, value: str) -> str:
        """Validate target environment with security checks."""
        valid_environments = ['development', 'staging', 'production', 'testing']
        if value not in valid_environments:
            raise serializers.ValidationError(f"Invalid target environment. Must be one of: {valid_environments}")
        return value
    
    def validate_rollback_script(self, value: str) -> str:
        """Validate rollback script with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',  # Script tags
                r'javascript:',              # JavaScript protocol
                r'eval\s*\(',             # Code execution
                r'exec\s*\(',             # Code execution
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Rollback script contains prohibited code")
        
        return value
    
    def validate_approval_required(self, value: bool) -> bool:
        """Validate approval requirement with security checks."""
        if not isinstance(value, bool):
            raise serializers.ValidationError("Approval required must be a boolean")
        return value


class ScriptExecutionSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for ScriptExecution model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = ScriptExecution
        fields = [
            'id', 'script', 'parameters', 'environment', 'status',
            'start_time', 'end_time', 'output', 'error_message',
            'exit_code', 'duration', 'executed_by'
        ]
        read_only_fields = ['id', 'script', 'start_time', 'executed_by']
    
    def validate_status(self, value: str) -> str:
        """Validate execution status with security checks."""
        valid_statuses = ['pending', 'running', 'success', 'failed', 'timeout', 'cancelled']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_parameters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate execution parameters with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a dictionary")
        
        # Security: Check for prohibited content
        parameters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, parameters_str, re.IGNORECASE):
                raise serializers.ValidationError("Parameters contain prohibited content")
        
        return value
    
    def validate_environment(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate execution environment with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Environment must be a dictionary")
        
        # Security: Check for prohibited content
        env_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, env_str, re.IGNORECASE):
                raise serializers.ValidationError("Environment contains prohibited content")
        
        return value
    
    def validate_output(self, value: Optional[str]) -> Optional[str]:
        """Validate execution output with security checks."""
        if value is not None:
            if not isinstance(value, str):
                raise serializers.ValidationError("Output must be a string")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Output contains prohibited content")
            
            # Validate output length
            if len(value) > 1048576:  # 1MB limit
                raise serializers.ValidationError("Output is too long")
        
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
    
    def validate_exit_code(self, value: Optional[int]) -> Optional[int]:
        """Validate exit code with security checks."""
        if value is not None:
            if not isinstance(value, int) or value < -1 or value > 255:
                raise serializers.ValidationError("Exit code must be between -1 and 255")
        return value
    
    def validate_duration(self, value: float) -> float:
        """Validate duration with security checks."""
        if not isinstance(value, (int, float)) or value < 0 or value > 3600:
            raise serializers.ValidationError("Duration must be between 0 and 3600 seconds")
        return float(value)


# Request/Response Serializers for Script Endpoints

class ScriptCreateRequestSerializer(serializers.Serializer):
    """Serializer for script creation requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    type = serializers.ChoiceField(
        choices=['automation', 'data_processing', 'maintenance', 'deployment'],
        required=True
    )
    content = serializers.CharField(required=True)
    parameters = serializers.JSONField(default=dict)
    environment = serializers.JSONField(default=dict)
    timeout = serializers.IntegerField(default=300, min_value=1, max_value=3600)
    retry_policy = serializers.JSONField(default=dict)
    status = serializers.ChoiceField(
        choices=['active', 'inactive', 'deprecated', 'maintenance'],
        default='active'
    )


class ScriptExecuteRequestSerializer(serializers.Serializer):
    """Serializer for script execution requests."""
    
    parameters = serializers.JSONField(default=dict)
    environment = serializers.JSONField(default=dict)


class ScriptScheduleRequestSerializer(serializers.Serializer):
    """Serializer for script scheduling requests."""
    
    schedule_type = serializers.ChoiceField(
        choices=['cron', 'interval', 'event', 'manual'],
        required=True
    )
    cron_expression = serializers.CharField(required=False, allow_blank=True)
    interval = serializers.IntegerField(required=False, allow_null=True)
    next_run = serializers.DateTimeField(required=False, allow_null=True)
    active = serializers.BooleanField(default=True)


class ScriptTestRequestSerializer(serializers.Serializer):
    """Serializer for script testing requests."""
    
    parameters = serializers.JSONField(default=dict)
    environment = serializers.JSONField(default=dict)


class ScriptTestResponseSerializer(serializers.Serializer):
    """Serializer for script test responses."""
    
    success = serializers.BooleanField()
    execution_id = serializers.UUIDField()
    status_code = serializers.IntegerField()
    output = serializers.CharField()
    error_message = serializers.CharField()
    duration = serializers.FloatField()


class ScriptStatsResponseSerializer(serializers.Serializer):
    """Serializer for script stats responses."""
    
    script_id = serializers.UUIDField()
    script_name = serializers.CharField()
    total_executions = serializers.IntegerField()
    successful_executions = serializers.IntegerField()
    failed_executions = serializers.IntegerField()
    timeout_executions = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_duration = serializers.FloatField()
    error_breakdown = serializers.ListField()
    last_30_days = serializers.DateTimeField()


class ScriptExecutionResponseSerializer(serializers.Serializer):
    """Serializer for script execution responses."""
    
    execution_id = serializers.UUIDField()
    script_id = serializers.UUIDField()
    status = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    duration = serializers.FloatField()
    exit_code = serializers.IntegerField()
    output = serializers.CharField()
    error_message = serializers.CharField()


class ScriptHealthResponseSerializer(serializers.Serializer):
    """Serializer for script health responses."""
    
    script_id = serializers.UUIDField()
    script_name = serializers.CharField()
    health_status = serializers.CharField()
    success_rate = serializers.FloatField()
    total_executions_24h = serializers.IntegerField()
    successful_executions_24h = serializers.IntegerField()
    last_execution = serializers.DateTimeField()
    checked_at = serializers.DateTimeField()


class ScriptSystemHealthResponseSerializer(serializers.Serializer):
    """Serializer for system health responses."""
    
    total_active_scripts = serializers.IntegerField()
    total_executions_24h = serializers.IntegerField()
    successful_executions_24h = serializers.IntegerField()
    success_rate_24h = serializers.FloatField()
    pending_executions = serializers.IntegerField()
    system_status = serializers.CharField()
    checked_at = serializers.DateTimeField()


class ScriptSecurityValidationRequestSerializer(serializers.Serializer):
    """Serializer for script security validation requests."""
    
    content = serializers.CharField(required=True)


class ScriptSecurityValidationResponseSerializer(serializers.Serializer):
    """Serializer for script security validation responses."""
    
    security_status = serializers.CharField()
    issues = serializers.ListField()
    issue_count = serializers.IntegerField()
    validated_at = serializers.DateTimeField()
