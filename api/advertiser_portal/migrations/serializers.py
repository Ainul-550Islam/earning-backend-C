"""
Migrations Serializers

This module provides comprehensive serializers for migration management with
enterprise-grade validation, security, and performance optimization following
industry standards from Django Migrations, Alembic, and Flyway.
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
from ..database_models.migration_model import (
    Migration, SchemaMigration, DataMigration, Rollback,
    MigrationTracking, MigrationValidation, MigrationBackup, MigrationExecution
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class MigrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Migration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    created_at_formatted = serializers.SerializerMethodField()
    updated_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Migration
        fields = [
            'id', 'name', 'type', 'description', 'dependencies',
            'rollback_script', 'validation_script', 'backup_required',
            'status', 'created_at', 'created_at_formatted',
            'updated_at', 'updated_at_formatted',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_at_formatted',
            'updated_at', 'updated_at_formatted',
            'created_by', 'updated_by'
        ]
    
    def get_created_at_formatted(self, obj: Migration) -> str:
        """Get formatted creation time."""
        try:
            if obj.created_at:
                return obj.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def get_updated_at_formatted(self, obj: Migration) -> str:
        """Get formatted update time."""
        try:
            if obj.updated_at:
                return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def validate_name(self, value: str) -> str:
        """Validate migration name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Migration name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Migration name contains prohibited characters")
        
        return value
    
    def validate_type(self, value: str) -> str:
        """Validate migration type with security checks."""
        valid_types = ['schema', 'data', 'mixed', 'rollback']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid migration type. Must be one of: {valid_types}")
        return value
    
    def validate_description(self, value: str) -> str:
        """Validate migration description with security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Migration description must be at least 10 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Migration description contains prohibited content")
        
        return value
    
    def validate_dependencies(self, value: List[str]) -> List[str]:
        """Validate migration dependencies with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Dependencies must be a list")
        
        # Validate each dependency
        for dep_id in value:
            try:
                UUID(dep_id)
            except ValueError:
                raise serializers.ValidationError(f"Invalid dependency ID format: {dep_id}")
        
        return value
    
    def validate_rollback_script(self, value: str) -> str:
        """Validate rollback script with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'eval\s*\(',
                r'exec\s*\(',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Rollback script contains prohibited code")
        
        return value
    
    def validate_validation_script(self, value: str) -> str:
        """Validate validation script with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'eval\s*\(',
                r'exec\s*\(',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Validation script contains prohibited code")
        
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate migration status with security checks."""
        valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate migration type vs content
        migration_type = attrs.get('type')
        
        # Type-specific validation
        if migration_type == 'schema':
            MigrationSerializer._validate_schema_migration_config(attrs)
        elif migration_type == 'data':
            MigrationSerializer._validate_data_migration_config(attrs)
        elif migration_type == 'mixed':
            MigrationSerializer._validate_mixed_migration_config(attrs)
        elif migration_type == 'rollback':
            MigrationSerializer._validate_rollback_migration_config(attrs)
        
        return attrs
    
    @staticmethod
    def _validate_schema_migration_config(attrs: Dict[str, Any]) -> None:
        """Validate schema migration configuration."""
        # Schema migrations should have rollback script
        if not attrs.get('rollback_script'):
            raise serializers.ValidationError("Schema migrations require a rollback script")
    
    @staticmethod
    def _validate_data_migration_config(attrs: Dict[str, Any]) -> None:
        """Validate data migration configuration."""
        # Data migrations should have validation script
        if not attrs.get('validation_script'):
            raise serializers.ValidationError("Data migrations require a validation script")
    
    @staticmethod
    def _validate_mixed_migration_config(attrs: Dict[str, Any]) -> None:
        """Validate mixed migration configuration."""
        # Mixed migrations should have both rollback and validation scripts
        if not attrs.get('rollback_script'):
            raise serializers.ValidationError("Mixed migrations require a rollback script")
        
        if not attrs.get('validation_script'):
            raise serializers.ValidationError("Mixed migrations require a validation script")
    
    @staticmethod
    def _validate_rollback_migration_config(attrs: Dict[str, Any]) -> None:
        """Validate rollback migration configuration."""
        # Rollback migrations should have target migration
        if not attrs.get('target_migration'):
            raise serializers.ValidationError("Rollback migrations require a target migration")


class MigrationCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating migrations.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    type = serializers.ChoiceField(
        choices=['schema', 'data', 'mixed', 'rollback'],
        required=True
    )
    description = serializers.CharField(required=True)
    dependencies = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    content = serializers.CharField(required=False, allow_blank=True)
    rollback_script = serializers.CharField(required=False, allow_blank=True)
    validation_script = serializers.CharField(required=False, allow_blank=True)
    backup_required = serializers.BooleanField(default=True)
    status = serializers.ChoiceField(
        choices=['pending', 'running', 'completed', 'failed', 'cancelled'],
        required=False,
        default='pending'
    )
    
    def validate_name(self, value: str) -> str:
        """Validate migration name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Migration name must be at least 3 characters long")
        
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
                raise serializers.ValidationError("Migration name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Migration name contains prohibited characters")
        
        # Validate name length
        if len(value) > 255:
            raise serializers.ValidationError("Migration name is too long")
        
        return value
    
    def validate_type(self, value: str) -> str:
        """Validate migration type with comprehensive security checks."""
        valid_types = ['schema', 'data', 'mixed', 'rollback']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid migration type. Must be one of: {valid_types}")
        return value
    
    def validate_description(self, value: str) -> str:
        """Validate migration description with comprehensive security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Migration description must be at least 10 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Migration description contains prohibited content")
        
        # Validate description length
        if len(value) > 1000:
            raise serializers.ValidationError("Migration description is too long")
        
        return value
    
    def validate_dependencies(self, value: List[str]) -> List[str]:
        """Validate migration dependencies with comprehensive security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Dependencies must be a list")
        
        # Validate each dependency
        for dep_id in value:
            try:
                UUID(dep_id)
            except ValueError:
                raise serializers.ValidationError(f"Invalid dependency ID format: {dep_id}")
        
        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Dependencies must be unique")
        
        return value
    
    def validate_content(self, value: str) -> str:
        """Validate migration content with comprehensive security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',  # Script tags
                r'javascript:',              # JavaScript protocol
                r'eval\s*\(',             # Code execution
                r'exec\s*\(',             # Code execution
                r'system\s*\(',           # System calls
                r'os\.system',            # System calls
                r'subprocess\.call',       # Subprocess calls
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Migration content contains prohibited code")
            
            # Validate content length
            if len(value) > 1048576:  # 1MB limit
                raise serializers.ValidationError("Migration content is too large")
        
        return value
    
    def validate_rollback_script(self, value: str) -> str:
        """Validate rollback script with comprehensive security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',  # Script tags
                r'javascript:',              # JavaScript protocol
                r'eval\s*\(',             # Code execution
                r'exec\s*\(',             # Code execution
                r'system\s*\(',           # System calls
                r'os\.system',            # System calls
                r'subprocess\.call',       # Subprocess calls
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Rollback script contains prohibited code")
            
            # Validate script length
            if len(value) > 1048576:  # 1MB limit
                raise serializers.ValidationError("Rollback script is too large")
        
        return value
    
    def validate_validation_script(self, value: str) -> str:
        """Validate validation script with comprehensive security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',  # Script tags
                r'javascript:',              # JavaScript protocol
                r'eval\s*\(',             # Code execution
                r'exec\s*\(',             # Code execution
                r'system\s*\(',           # System calls
                r'os\.system',            # System calls
                r'subprocess\.call',       # Subprocess calls
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Validation script contains prohibited code")
            
            # Validate script length
            if len(value) > 1048576:  # 1MB limit
                raise serializers.ValidationError("Validation script is too large")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate migration type vs content
        migration_type = attrs.get('type')
        content = attrs.get('content', '')
        
        if migration_type == 'schema':
            MigrationCreateSerializer._validate_schema_migration_config(content)
        elif migration_type == 'data':
            MigrationCreateSerializer._validate_data_migration_config(content)
        elif migration_type == 'mixed':
            MigrationCreateSerializer._validate_mixed_migration_config(content)
        elif migration_type == 'rollback':
            MigrationCreateSerializer._validate_rollback_migration_config(attrs)
        
        # Business logic: Validate dependencies
        dependencies = attrs.get('dependencies', [])
        if dependencies and migration_type == 'rollback':
            # Rollback migrations should not have dependencies
            raise serializers.ValidationError("Rollback migrations cannot have dependencies")
        
        return attrs
    
    @staticmethod
    def _validate_schema_migration_config(content: str) -> None:
        """Validate schema migration configuration."""
        # Schema migrations should have rollback script
        if not content:
            raise serializers.ValidationError("Schema migrations require content or rollback script")
    
    @staticmethod
    def _validate_data_migration_config(content: str) -> None:
        """Validate data migration configuration."""
        # Data migrations should have validation script
        if not content:
            raise serializers.ValidationError("Data migrations require content or validation script")
    
    @staticmethod
    def _validate_mixed_migration_config(content: str) -> None:
        """Validate mixed migration configuration."""
        # Mixed migrations should have both content and rollback script
        if not content:
            raise serializers.ValidationError("Mixed migrations require content and rollback script")
    
    @staticmethod
    def _validate_rollback_migration_config(attrs: Dict[str, Any]) -> None:
        """Validate rollback migration configuration."""
        # Rollback migrations should have target migration
        if not attrs.get('content'):
            raise serializers.ValidationError("Rollback migrations require rollback script or target migration")


class SchemaMigrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for SchemaMigration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = SchemaMigration
        fields = [
            'id', 'migration', 'sql_script', 'django_migration',
            'target_models', 'table_operations'
        ]
        read_only_fields = ['id', 'migration']
    
    def validate_sql_script(self, value: str) -> str:
        """Validate SQL script with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'eval\s*\(',
                r'exec\s*\(',
                r'drop\s+database',       # Dangerous SQL
                r'delete\s+from',          # Dangerous SQL
                r'truncate\s+table',       # Dangerous SQL
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    # Some of these are allowed in schema migrations but need special handling
                    if pattern in [r'drop\s+database', r'delete\s+from', r'truncate\s+table']:
                        raise serializers.ValidationError(f"SQL script contains dangerous operation: {pattern}")
        
        return value
    
    def validate_django_migration(self, value: str) -> str:
        """Validate Django migration with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'eval\s*\(',
                r'exec\s*\(',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Django migration contains prohibited content")
        
        return value
    
    def validate_target_models(self, value: List[str]) -> List[str]:
        """Validate target models with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Target models must be a list")
        
        # Validate each model name
        for model_name in value:
            if not isinstance(model_name, str):
                raise serializers.ValidationError("Target models must be strings")
            
            # Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, model_name, re.IGNORECASE):
                    raise serializers.ValidationError(f"Target model contains prohibited content: {model_name}")
        
        return value
    
    def validate_table_operations(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate table operations with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Table operations must be a list")
        
        # Validate each operation
        for operation in value:
            if not isinstance(operation, dict):
                raise serializers.ValidationError("Each table operation must be a dictionary")
            
            # Validate operation structure
            required_fields = ['type', 'table_name']
            for field in required_fields:
                if field not in operation:
                    raise serializers.ValidationError(f"Table operation missing required field: {field}")
            
            # Validate operation type
            valid_types = ['create', 'alter', 'drop']
            if operation['type'] not in valid_types:
                raise serializers.ValidationError(f"Invalid operation type: {operation['type']}")
            
            # Validate table name
            table_name = operation['table_name']
            if not isinstance(table_name, str):
                raise serializers.ValidationError("Table name must be a string")
            
            if not table_name.isidentifier():
                raise serializers.ValidationError(f"Invalid table name: {table_name}")
        
        return value


class DataMigrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for DataMigration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = DataMigration
        fields = [
            'id', 'migration', 'source_models', 'target_models',
            'transformation_script', 'batch_size', 'validation_rules'
        ]
        read_only_fields = ['id', 'migration']
    
    def validate_source_models(self, value: List[str]) -> List[str]:
        """Validate source models with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Source models must be a list")
        
        # Validate each model name
        for model_name in value:
            if not isinstance(model_name, str):
                raise serializers.ValidationError("Source models must be strings")
            
            # Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, model_name, re.IGNORECASE):
                    raise serializers.ValidationError(f"Source model contains prohibited content: {model_name}")
        
        return value
    
    def validate_target_models(self, value: List[str]) -> List[str]:
        """Validate target models with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Target models must be a list")
        
        # Validate each model name
        for model_name in value:
            if not isinstance(model_name, str):
                raise serializers.ValidationError("Target models must be strings")
            
            # Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, model_name, re.IGNORECASE):
                    raise serializers.ValidationError(f"Target model contains prohibited content: {model_name}")
        
        return value
    
    def validate_transformation_script(self, value: str) -> str:
        """Validate transformation script with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'eval\s*\(',
                r'exec\s*\(',
                r'system\s*\(',
                r'os\.system',
                r'subprocess\.call',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Transformation script contains prohibited code")
        
        return value
    
    def validate_batch_size(self, value: int) -> int:
        """Validate batch size with security checks."""
        if not isinstance(value, int) or value < 1 or value > 100000:
            raise serializers.ValidationError("Batch size must be between 1 and 100000")
        return value
    
    def validate_validation_rules(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate validation rules with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Validation rules must be a list")
        
        # Validate each rule
        for rule in value:
            if not isinstance(rule, dict):
                raise serializers.ValidationError("Each validation rule must be a dictionary")
            
            # Validate rule structure
            required_fields = ['field', 'type']
            for field in required_fields:
                if field not in rule:
                    raise serializers.ValidationError(f"Validation rule missing required field: {field}")
            
            # Validate rule type
            valid_types = ['required', 'format', 'default', 'custom']
            if rule['type'] not in valid_types:
                raise serializers.ValidationError(f"Invalid rule type: {rule['type']}")
        
        return value


class RollbackSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Rollback model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = Rollback
        fields = [
            'id', 'migration', 'target_migration', 'rollback_script',
            'backup_location', 'rollback_type'
        ]
        read_only_fields = ['id', 'migration']
    
    def validate_target_migration(self, value: str) -> str:
        """Validate target migration with security checks."""
        if not value:
            raise serializers.ValidationError("Target migration is required")
        
        try:
            UUID(value)
        except ValueError:
            raise serializers.ValidationError("Invalid target migration ID format")
        
        return value
    
    def validate_rollback_script(self, value: str) -> str:
        """Validate rollback script with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'eval\s*\(',
                r'exec\s*\(',
                r'system\s*\(',
                r'os\.system',
                r'subprocess\.call',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Rollback script contains prohibited code")
        
        return value
    
    def validate_backup_location(self, value: str) -> str:
        """Validate backup location with security checks."""
        if value:
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
                    raise serializers.ValidationError("Backup location contains suspicious content")
        
        return value
    
    def validate_rollback_type(self, value: str) -> str:
        """Validate rollback type with security checks."""
        valid_types = ['full', 'partial', 'data', 'schema']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid rollback type. Must be one of: {valid_types}")
        return value


class MigrationExecutionSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for MigrationExecution model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = MigrationExecution
        fields = [
            'id', 'migration', 'parameters', 'environment', 'status',
            'start_time', 'end_time', 'output', 'error_message',
            'affected_rows', 'duration', 'executed_by'
        ]
        read_only_fields = ['id', 'migration', 'start_time', 'executed_by']
    
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
    
    def validate_affected_rows(self, value: Optional[int]) -> Optional[int]:
        """Validate affected rows with security checks."""
        if value is not None:
            if not isinstance(value, int) or value < 0:
                raise serializers.ValidationError("Affected rows must be a non-negative integer")
        return value
    
    def validate_duration(self, value: float) -> float:
        """Validate duration with security checks."""
        if not isinstance(value, (int, float)) or value < 0 or value > 3600:
            raise serializers.ValidationError("Duration must be between 0 and 3600 seconds")
        return float(value)


# Request/Response Serializers for Migration Endpoints

class MigrationCreateRequestSerializer(serializers.Serializer):
    """Serializer for migration creation requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    type = serializers.ChoiceField(
        choices=['schema', 'data', 'mixed', 'rollback'],
        required=True
    )
    description = serializers.CharField(required=True)
    dependencies = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    content = serializers.CharField(required=False, allow_blank=True)
    rollback_script = serializers.CharField(required=False, allow_blank=True)
    validation_script = serializers.CharField(required=False, allow_blank=True)
    backup_required = serializers.BooleanField(default=True)
    status = serializers.ChoiceField(
        choices=['pending', 'running', 'completed', 'failed', 'cancelled'],
        required=False,
        default='pending'
    )


class MigrationExecuteRequestSerializer(serializers.Serializer):
    """Serializer for migration execution requests."""
    
    parameters = serializers.JSONField(default=dict)
    environment = serializers.JSONField(default=dict)


class MigrationRollbackRequestSerializer(serializers.Serializer):
    """Serializer for migration rollback requests."""
    
    parameters = serializers.JSONField(default=dict)
    environment = serializers.JSONField(default=dict)


class MigrationValidationRequestSerializer(serializers.Serializer):
    """Serializer for migration validation requests."""
    
    parameters = serializers.JSONField(default=dict)
    validation_type = serializers.ChoiceField(
        choices=['syntax', 'dependencies', 'order', 'security'],
        default='syntax'
    )


class MigrationTestRequestSerializer(serializers.Serializer):
    """Serializer for migration testing requests."""
    
    dry_run = serializers.BooleanField(default=True)
    parameters = serializers.JSONField(default=dict)
    environment = serializers.JSONField(default=dict)


class MigrationStatsResponseSerializer(serializers.Serializer):
    """Serializer for migration stats responses."""
    
    migration_id = serializers.UUIDField()
    migration_name = serializers.CharField()
    migration_type = serializers.CharField()
    total_executions = serializers.IntegerField()
    successful_executions = serializers.IntegerField()
    failed_executions = serializers.IntegerField()
    timeout_executions = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_duration = serializers.FloatField()
    last_execution = serializers.DateTimeField()
    last_execution_status = serializers.CharField()


class MigrationHistoryResponseSerializer(serializers.Serializer):
    """Serializer for migration history responses."""
    
    execution_id = serializers.UUIDField()
    status = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    duration = serializers.FloatField()
    affected_rows = serializers.IntegerField()
    error_message = serializers.CharField()
    executed_by = serializers.CharField()


class MigrationValidationResponseSerializer(serializers.Serializer):
    """Serializer for migration validation responses."""
    
    validation_type = serializers.CharField()
    status = serializers.CharField()
    issues = serializers.ListField()
    message = serializers.CharField()
    validated_at = serializers.DateTimeField()


class MigrationSystemStatusResponseSerializer(serializers.Serializer):
    """Serializer for system status responses."""
    
    total_migrations = serializers.IntegerField()
    pending_migrations = serializers.IntegerField()
    running_migrations = serializers.IntegerField()
    total_executions_24h = serializers.IntegerField()
    successful_executions_24h = serializers.IntegerField()
    success_rate_24h = serializers.FloatField()
    system_status = serializers.CharField()
    checked_at = serializers.DateTimeField()


class BackupCreateRequestSerializer(serializers.Serializer):
    """Serializer for backup creation requests."""
    
    backup_type = serializers.ChoiceField(
        choices=['pre_migration', 'post_migration', 'manual'],
        default='pre_migration'
    )
    compression = serializers.BooleanField(default=True)
    storage_location = serializers.CharField(required=False, allow_blank=True)


class BackupRestoreRequestSerializer(serializers.Serializer):
    """Serializer for backup restore requests."""
    
    restore_type = serializers.ChoiceField(
        choices=['full', 'partial', 'data', 'schema'],
        default='full'
    )
    force_restore = serializers.BooleanField(default=False)
    validation_required = serializers.BooleanField(default=True)
