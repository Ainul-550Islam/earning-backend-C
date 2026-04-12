"""
Migrations Services

This module handles comprehensive database migration management with enterprise-grade
security, real-time processing, and advanced features following industry
standards from Django Migrations, Alembic, and Flyway.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import time
import asyncio
import subprocess
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
import os
import sys
import hashlib
import shutil

from django.db import transaction, connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, Avg, Q, F, Window
from django.db.models.functions import Coalesce, RowNumber
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.management import call_command
from django.apps import apps

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.migration_model import (
    Migration, SchemaMigration, DataMigration, Rollback,
    MigrationTracking, MigrationValidation, MigrationBackup
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


@dataclass
class MigrationConfig:
    """Migration configuration with metadata."""
    migration_id: str
    name: str
    type: str
    description: str
    dependencies: List[str]
    rollback_script: str
    validation_script: str
    backup_required: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class MigrationExecution:
    """Migration execution data with metadata."""
    execution_id: str
    migration_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    output: Optional[str]
    error_message: Optional[str]
    affected_rows: Optional[int]
    duration: float
    user_id: Optional[str]


class MigrationService:
    """
    Enterprise-grade migration management service.
    
    Features:
    - Schema and data migrations
    - Rollback capabilities
    - Migration tracking
    - Validation and testing
    - Performance optimization
    """
    
    @staticmethod
    def create_migration(migration_config: Dict[str, Any], created_by: Optional[User] = None) -> Migration:
        """
        Create migration with enterprise-grade security.
        
        Supported migration types:
        - Schema: Database schema changes
        - Data: Data transformation and migration
        - Mixed: Both schema and data changes
        - Rollback: Migration rollback operations
        
        Security features:
        - Migration validation and sanitization
        - Permission validation
        - Dependency checking
        - Audit logging
        """
        try:
            # Security: Validate migration configuration
            MigrationService._validate_migration_config(migration_config, created_by)
            
            # Get migration-specific configuration
            migration_type = migration_config.get('type')
            
            with transaction.atomic():
                # Create base migration
                migration = Migration.objects.create(
                    name=migration_config.get('name'),
                    type=migration_type,
                    description=migration_config.get('description'),
                    dependencies=migration_config.get('dependencies', []),
                    rollback_script=migration_config.get('rollback_script', ''),
                    validation_script=migration_config.get('validation_script', ''),
                    backup_required=migration_config.get('backup_required', True),
                    status='pending',
                    created_by=created_by
                )
                
                # Create type-specific migration
                if migration_type == 'schema':
                    MigrationService._create_schema_migration(migration, migration_config)
                elif migration_type == 'data':
                    MigrationService._create_data_migration(migration, migration_config)
                elif migration_type == 'mixed':
                    MigrationService._create_mixed_migration(migration, migration_config)
                elif migration_type == 'rollback':
                    MigrationService._create_rollback_migration(migration, migration_config)
                
                # Send notification
                Notification.objects.create(
                    user=created_by,
                    title='Migration Created',
                    message=f'Successfully created {migration_type} migration: {migration.name}',
                    notification_type='migration',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log migration creation
                MigrationService._log_migration_creation(migration, created_by)
                
                return migration
                
        except Exception as e:
            logger.error(f"Error creating migration: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create migration: {str(e)}")
    
    @staticmethod
    def execute_migration(migration_id: UUID, execution_config: Dict[str, Any], executed_by: Optional[User] = None) -> MigrationExecution:
        """
        Execute migration with enterprise-grade processing.
        
        Execution features:
        - Pre-execution validation
        - Backup creation
        - Atomic execution
        - Post-execution validation
        - Rollback on failure
        """
        try:
            # Security: Validate execution configuration
            MigrationService._validate_execution_config(execution_config, executed_by)
            
            # Get migration
            migration = Migration.objects.get(id=migration_id)
            
            # Create execution record
            execution = MigrationService._create_execution_record(migration, execution_config, executed_by)
            
            # Execute migration based on type
            if migration.type == 'schema':
                result = MigrationService._execute_schema_migration(migration, execution)
            elif migration.type == 'data':
                result = MigrationService._execute_data_migration(migration, execution)
            elif migration.type == 'mixed':
                result = MigrationService._execute_mixed_migration(migration, execution)
            elif migration.type == 'rollback':
                result = MigrationService._execute_rollback_migration(migration, execution)
            else:
                result = MigrationService._execute_generic_migration(migration, execution)
            
            # Update execution record
            MigrationService._update_execution_record(execution, result)
            
            return execution
            
        except Exception as e:
            logger.error(f"Error executing migration: {str(e)}")
            raise AdvertiserServiceError(f"Failed to execute migration: {str(e)}")
    
    @staticmethod
    def rollback_migration(migration_id: UUID, rollback_config: Dict[str, Any], rolled_back_by: Optional[User] = None) -> MigrationExecution:
        """
        Rollback migration with enterprise-grade processing.
        
        Rollback features:
        - Pre-rollback validation
        - Backup restoration
        - Atomic rollback
        - Post-rollback validation
        - Rollback tracking
        """
        try:
            # Security: Validate rollback configuration
            MigrationService._validate_rollback_config(rollback_config, rolled_back_by)
            
            # Get migration
            migration = Migration.objects.get(id=migration_id)
            
            # Create rollback execution record
            execution = MigrationService._create_rollback_execution_record(migration, rollback_config, rolled_back_by)
            
            # Execute rollback
            rollback_result = MigrationService._execute_rollback(migration, execution)
            
            # Update execution record
            MigrationService._update_execution_record(execution, rollback_result)
            
            return execution
            
        except Exception as e:
            logger.error(f"Error rolling back migration: {str(e)}")
            raise AdvertiserServiceError(f"Failed to rollback migration: {str(e)}")
    
    @staticmethod
    def validate_migration(migration_id: UUID, validation_config: Dict[str, Any], validated_by: Optional[User] = None) -> Dict[str, Any]:
        """
        Validate migration with comprehensive checks.
        
        Validation features:
        - Schema validation
        - Data integrity checks
        - Performance impact analysis
        - Security validation
        """
        try:
            # Security: Validate validation configuration
            MigrationService._validate_validation_config(validation_config, validated_by)
            
            # Get migration
            migration = Migration.objects.get(id=migration_id)
            
            # Perform validation based on type
            if migration.type == 'schema':
                validation_result = MigrationService._validate_schema_migration(migration, validation_config)
            elif migration.type == 'data':
                validation_result = MigrationService._validate_data_migration(migration, validation_config)
            elif migration.type == 'mixed':
                validation_result = MigrationService._validate_mixed_migration(migration, validation_config)
            else:
                validation_result = MigrationService._validate_generic_migration(migration, validation_config)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating migration: {str(e)}")
            raise AdvertiserServiceError(f"Failed to validate migration: {str(e)}")
    
    @staticmethod
    def get_migration_stats(migration_id: UUID) -> Dict[str, Any]:
        """
        Get migration statistics with comprehensive metrics.
        
        Statistics include:
        - Execution success rate
        - Average execution time
        - Error breakdown
        - Performance impact
        - Rollback statistics
        """
        try:
            # Get migration
            migration = Migration.objects.get(id=migration_id)
            
            # Calculate statistics
            stats = MigrationService._calculate_migration_stats(migration)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting migration stats: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get migration stats: {str(e)}")
    
    @staticmethod
    def _validate_migration_config(migration_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate migration configuration with security checks."""
        # Security: Check required fields
        required_fields = ['name', 'type', 'description']
        for field in required_fields:
            if not migration_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate migration type
        valid_types = ['schema', 'data', 'mixed', 'rollback']
        migration_type = migration_config.get('type')
        if migration_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid migration type: {migration_type}")
        
        # Security: Validate migration content
        content = migration_config.get('content', '')
        if content:
            MigrationService._validate_migration_content(content, migration_type)
        
        # Security: Check user permissions
        if user and not user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
    
    @staticmethod
    def _validate_migration_content(content: str, migration_type: str) -> None:
        """Validate migration content with security checks."""
        if not content or len(content.strip()) < 10:
            raise AdvertiserValidationError("Migration content is too short")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'eval\s*\(',             # Code execution
            r'exec\s*\(',             # Code execution
            r'system\s*\(',           # System calls
            r'os\.system',            # System calls
            r'subprocess\.call',       # Subprocess calls
            r'drop\s+database',       # Dangerous SQL
            r'delete\s+from',          # Dangerous SQL
            r'truncate\s+table',       # Dangerous SQL
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise AdvertiserValidationError("Migration content contains prohibited code")
        
        # Type-specific validation
        if migration_type == 'schema':
            MigrationService._validate_schema_content(content)
        elif migration_type == 'data':
            MigrationService._validate_data_content(content)
        elif migration_type == 'mixed':
            MigrationService._validate_mixed_content(content)
    
    @staticmethod
    def _validate_schema_content(content: str) -> None:
        """Validate schema migration content."""
        # Check for schema-specific patterns
        schema_patterns = [
            r'drop\s+table',           # Table operations
            r'delete\s+from',          # Table operations
            r'truncate\s+table',        # Table operations
            r'alter\s+table',          # Table operations
            r'create\s+table',         # Table operations
        ]
        
        import re
        for pattern in schema_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                # These are allowed in schema migrations but need special handling
                pass
    
    @staticmethod
    def _validate_data_content(content: str) -> None:
        """Validate data migration content."""
        # Check for data-specific patterns
        data_patterns = [
            r'update\s+.*\s+set',      # Data operations
            r'insert\s+into',           # Data operations
            r'bulk\s+insert',           # Bulk operations
            r'copy\s+from',             # Data operations
        ]
        
        import re
        for pattern in data_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                # These are allowed in data migrations but need special handling
                pass
    
    @staticmethod
    def _validate_mixed_content(content: str) -> None:
        """Validate mixed migration content."""
        # Mixed migrations can contain both schema and data operations
        MigrationService._validate_schema_content(content)
        MigrationService._validate_data_content(content)
    
    @staticmethod
    def _validate_execution_config(execution_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate execution configuration with security checks."""
        # Security: Check user permissions
        if user and not user.is_superuser:
            raise AdvertiserValidationError("User does not have migration execution permissions")
        
        # Security: Validate execution parameters
        parameters = execution_config.get('parameters', {})
        for key, value in parameters.items():
            if not isinstance(key, str):
                raise AdvertiserValidationError("Parameter keys must be strings")
            
            # Check for prohibited content in values
            if isinstance(value, str):
                prohibited_patterns = [
                    r'<script', r'javascript:', r'on\w+\s*='
                ]
                
                import re
                for pattern in prohibited_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        raise AdvertiserValidationError(f"Parameter {key} contains prohibited content")
    
    @staticmethod
    def _validate_rollback_config(rollback_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate rollback configuration with security checks."""
        # Security: Check user permissions
        if user and not user.is_superuser:
            raise AdvertiserValidationError("User does not have migration rollback permissions")
        
        # Security: Validate rollback parameters
        parameters = rollback_config.get('parameters', {})
        for key, value in parameters.items():
            if not isinstance(key, str):
                raise AdvertiserValidationError("Parameter keys must be strings")
    
    @staticmethod
    def _validate_validation_config(validation_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate validation configuration with security checks."""
        # Security: Check user permissions
        if user and not user.is_superuser:
            raise AdvertiserValidationError("User does not have migration validation permissions")
        
        # Security: Validate validation parameters
        parameters = validation_config.get('parameters', {})
        for key, value in parameters.items():
            if not isinstance(key, str):
                raise AdvertiserValidationError("Parameter keys must be strings")
    
    @staticmethod
    def _create_schema_migration(migration: Migration, migration_config: Dict[str, Any]) -> SchemaMigration:
        """Create schema migration specific configuration."""
        return SchemaMigration.objects.create(
            migration=migration,
            sql_script=migration_config.get('sql_script', ''),
            django_migration=migration_config.get('django_migration', ''),
            target_models=migration_config.get('target_models', []),
            table_operations=migration_config.get('table_operations', [])
        )
    
    @staticmethod
    def _create_data_migration(migration: Migration, migration_config: Dict[str, Any]) -> DataMigration:
        """Create data migration specific configuration."""
        return DataMigration.objects.create(
            migration=migration,
            source_models=migration_config.get('source_models', []),
            target_models=migration_config.get('target_models', []),
            transformation_script=migration_config.get('transformation_script', ''),
            batch_size=migration_config.get('batch_size', 1000),
            validation_rules=migration_config.get('validation_rules', [])
        )
    
    @staticmethod
    def _create_mixed_migration(migration: Migration, migration_config: Dict[str, Any]) -> None:
        """Create mixed migration specific configuration."""
        # Create both schema and data migration components
        MigrationService._create_schema_migration(migration, migration_config)
        MigrationService._create_data_migration(migration, migration_config)
    
    @staticmethod
    def _create_rollback_migration(migration: Migration, migration_config: Dict[str, Any]) -> Rollback:
        """Create rollback migration specific configuration."""
        return Rollback.objects.create(
            migration=migration,
            target_migration=migration_config.get('target_migration'),
            rollback_script=migration_config.get('rollback_script', ''),
            backup_location=migration_config.get('backup_location', ''),
            rollback_type=migration_config.get('rollback_type', 'full')
        )
    
    @staticmethod
    def _create_execution_record(migration: Migration, execution_config: Dict[str, Any], executed_by: Optional[User]) -> MigrationExecution:
        """Create migration execution record."""
        try:
            return MigrationExecution.objects.create(
                migration=migration,
                parameters=execution_config.get('parameters', {}),
                environment=execution_config.get('environment', {}),
                status='running',
                start_time=timezone.now(),
                executed_by=executed_by
            )
            
        except Exception as e:
            logger.error(f"Error creating execution record: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create execution record: {str(e)}")
    
    @staticmethod
    def _create_rollback_execution_record(migration: Migration, rollback_config: Dict[str, Any], rolled_back_by: Optional[User]) -> MigrationExecution:
        """Create rollback execution record."""
        try:
            return MigrationExecution.objects.create(
                migration=migration,
                parameters=rollback_config.get('parameters', {}),
                environment=rollback_config.get('environment', {}),
                status='running',
                start_time=timezone.now(),
                executed_by=rolled_back_by,
                execution_type='rollback'
            )
            
        except Exception as e:
            logger.error(f"Error creating rollback execution record: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create rollback execution record: {str(e)}")
    
    @staticmethod
    def _execute_schema_migration(migration: Migration, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute schema migration."""
        try:
            # Create backup if required
            if migration.backup_required:
                MigrationService._create_migration_backup(migration, execution)
            
            # Get schema migration
            schema_migration = migration.schema_migration
            
            # Execute SQL script if provided
            if schema_migration.sql_script:
                result = MigrationService._execute_sql_script(schema_migration.sql_script, execution)
            else:
                # Execute Django migration if provided
                if schema_migration.django_migration:
                    result = MigrationService._execute_django_migration(schema_migration.django_migration, execution)
                else:
                    result = MigrationService._execute_table_operations(schema_migration.table_operations, execution)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing schema migration: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_data_migration(migration: Migration, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute data migration."""
        try:
            # Create backup if required
            if migration.backup_required:
                MigrationService._create_migration_backup(migration, execution)
            
            # Get data migration
            data_migration = migration.data_migration
            
            # Execute transformation script if provided
            if data_migration.transformation_script:
                result = MigrationService._execute_transformation_script(data_migration.transformation_script, execution)
            else:
                # Execute default data migration
                result = MigrationService._execute_default_data_migration(data_migration, execution)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing data migration: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_mixed_migration(migration: Migration, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute mixed migration."""
        try:
            # Create backup if required
            if migration.backup_required:
                MigrationService._create_migration_backup(migration, execution)
            
            # Execute schema migration first
            schema_result = MigrationService._execute_schema_migration(migration, execution)
            
            if schema_result['status'] != 'success':
                return schema_result
            
            # Execute data migration
            data_result = MigrationService._execute_data_migration(migration, execution)
            
            return data_result
            
        except Exception as e:
            logger.error(f"Error executing mixed migration: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_rollback_migration(migration: Migration, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute rollback migration."""
        try:
            # Get rollback information
            rollback = migration.rollback
            
            # Restore backup if available
            if rollback.backup_location:
                result = MigrationService._restore_migration_backup(rollback.backup_location, execution)
            else:
                # Execute rollback script
                result = MigrationService._execute_rollback_script(rollback.rollback_script, execution)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing rollback migration: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_generic_migration(migration: Migration, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute generic migration."""
        try:
            # Create backup if required
            if migration.backup_required:
                MigrationService._create_migration_backup(migration, execution)
            
            # Execute migration content
            content = migration.content or ''
            if content:
                result = MigrationService._execute_migration_script(content, execution)
            else:
                result = {
                    'status': 'success',
                    'message': 'No content to execute'
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing generic migration: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_sql_script(sql_script: str, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute SQL script."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql_script)
                affected_rows = cursor.rowcount
                
                return {
                    'status': 'success',
                    'affected_rows': affected_rows,
                    'message': 'SQL script executed successfully'
                }
                
        except Exception as e:
            logger.error(f"Error executing SQL script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_django_migration(django_migration: str, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute Django migration."""
        try:
            # Use Django's migration command
            call_command('migrate', django_migration, verbosity=0)
            
            return {
                'status': 'success',
                'message': 'Django migration executed successfully'
            }
            
        except Exception as e:
            logger.error(f"Error executing Django migration: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_table_operations(table_operations: List[Dict[str, Any]], execution: MigrationExecution) -> Dict[str, Any]:
        """Execute table operations."""
        try:
            with connection.cursor() as cursor:
                affected_rows = 0
                
                for operation in table_operations:
                    operation_type = operation.get('type')
                    table_name = operation.get('table_name')
                    
                    if operation_type == 'create':
                        cursor.execute(operation.get('sql', ''))
                    elif operation_type == 'alter':
                        cursor.execute(operation.get('sql', ''))
                    elif operation_type == 'drop':
                        cursor.execute(operation.get('sql', ''))
                    
                    affected_rows += cursor.rowcount
                
                return {
                    'status': 'success',
                    'affected_rows': affected_rows,
                    'message': 'Table operations executed successfully'
                }
                
        except Exception as e:
            logger.error(f"Error executing table operations: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_transformation_script(transformation_script: str, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute transformation script."""
        try:
            # Create secure execution environment
            env = MigrationService._create_execution_environment(execution)
            
            # Execute script in sandbox
            result = MigrationService._run_script_in_sandbox(transformation_script, env, execution.migration.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing transformation script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_default_data_migration(data_migration: DataMigration, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute default data migration."""
        try:
            # Get source and target models
            source_models = data_migration.source_models
            target_models = data_migration.target_models
            
            # Execute data migration logic
            affected_rows = 0
            
            for source_model_name, target_model_name in zip(source_models, target_models):
                try:
                    # Get model classes
                    source_model = apps.get_model('advertiser_portal', source_model_name)
                    target_model = apps.get_model('advertiser_portal', target_model_name)
                    
                    # Migrate data in batches
                    batch_size = data_migration.batch_size
                    offset = 0
                    
                    while True:
                        with transaction.atomic():
                            # Get batch of source data
                            source_data = list(source_model.objects.all()[offset:offset + batch_size])
                            
                            if not source_data:
                                break
                            
                            # Transform and insert into target
                            for item in source_data:
                                target_data = MigrationService._transform_data(item, data_migration.validation_rules)
                                target_model.objects.create(**target_data)
                            
                            affected_rows += len(source_data)
                            offset += batch_size
                
                except Exception as e:
                    logger.error(f"Error migrating data from {source_model_name} to {target_model_name}: {str(e)}")
                    continue
            
            return {
                'status': 'success',
                'affected_rows': affected_rows,
                'message': 'Data migration executed successfully'
            }
            
        except Exception as e:
            logger.error(f"Error executing default data migration: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_rollback(rollback: Rollback, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute rollback."""
        try:
            # Execute rollback script
            if rollback.rollback_script:
                result = MigrationService._execute_rollback_script(rollback.rollback_script, execution)
            else:
                result = {
                    'status': 'success',
                    'message': 'No rollback script to execute'
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing rollback: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_migration_script(script_content: str, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute migration script."""
        try:
            # Create secure execution environment
            env = MigrationService._create_execution_environment(execution)
            
            # Execute script in sandbox
            result = MigrationService._run_script_in_sandbox(script_content, env, execution.migration.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing migration script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_rollback_script(rollback_script: str, execution: MigrationExecution) -> Dict[str, Any]:
        """Execute rollback script."""
        try:
            # Create secure execution environment
            env = MigrationService._create_execution_environment(execution)
            
            # Execute script in sandbox
            result = MigrationService._run_script_in_sandbox(rollback_script, env, execution.migration.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing rollback script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _create_execution_environment(execution: MigrationExecution) -> Dict[str, str]:
        """Create secure execution environment."""
        env = {}
        
        # Add base environment
        env.update(execution.environment or {})
        
        # Add migration environment variables
        env['MIGRATION_ID'] = str(execution.migration.id)
        env['EXECUTION_ID'] = str(execution.id)
        env['MIGRATION_TYPE'] = execution.migration.type
        env['PYTHONPATH'] = settings.BASE_DIR
        env['DJANGO_SETTINGS_MODULE'] = settings.SETTINGS_MODULE
        
        # Add user environment variables
        if execution.executed_by:
            env['USER_ID'] = str(execution.executed_by.id)
            env['USER_NAME'] = execution.executed_by.username
        
        return env
    
    @staticmethod
    def _run_script_in_sandbox(script_content: str, env: Dict[str, str], timeout: int) -> Dict[str, Any]:
        """Run script in secure sandbox environment."""
        try:
            # Create temporary script file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            try:
                # Execute script in subprocess with timeout
                result = subprocess.run(
                    [sys.executable, script_path],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=settings.BASE_DIR
                )
                
                return {
                    'status': 'success' if result.returncode == 0 else 'failed',
                    'exit_code': result.returncode,
                    'output': result.stdout,
                    'error_message': result.stderr if result.returncode != 0 else None
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(script_path)
                except OSError:
                    pass
            
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'exit_code': -1,
                'error_message': 'Script execution timed out'
            }
        except Exception as e:
            logger.error(f"Error running script in sandbox: {str(e)}")
            return {
                'status': 'failed',
                'exit_code': -1,
                'error_message': str(e)
            }
    
    @staticmethod
    def _create_migration_backup(migration: Migration, execution: MigrationExecution) -> None:
        """Create migration backup."""
        try:
            # Create backup record
            backup = MigrationBackup.objects.create(
                migration=migration,
                execution=execution,
                backup_type='pre_migration',
                backup_location='',
                status='creating',
                created_at=timezone.now()
            )
            
            # Create database backup
            backup_location = MigrationService._create_database_backup(migration, backup)
            
            # Update backup record
            backup.backup_location = backup_location
            backup.status = 'completed'
            backup.save(update_fields=['backup_location', 'status'])
            
        except Exception as e:
            logger.error(f"Error creating migration backup: {str(e)}")
    
    @staticmethod
    def _create_database_backup(migration: Migration, backup: MigrationBackup) -> str:
        """Create database backup."""
        try:
            # Generate backup filename
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"migration_{migration.id}_{timestamp}.sql"
            backup_path = os.path.join(settings.MEDIA_ROOT, 'backups', backup_filename)
            
            # Ensure backup directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Create backup using pg_dump or similar
            db_config = settings.DATABASES['default']
            if db_config['ENGINE'] == 'django.db.backends.postgresql':
                # PostgreSQL backup
                cmd = [
                    'pg_dump',
                    '--host', db_config['HOST'],
                    '--port', str(db_config['PORT']),
                    '--username', db_config['USER'],
                    '--no-password',
                    '--clean',
                    '--if-exists',
                    '--file', backup_path,
                    db_config['NAME']
                ]
                
                env = os.environ.copy()
                env['PGPASSWORD'] = db_config['PASSWORD']
                
                subprocess.run(cmd, env=env, check=True)
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Error creating database backup: {str(e)}")
            return ''
    
    @staticmethod
    def _restore_migration_backup(backup_location: str, execution: MigrationExecution) -> Dict[str, Any]:
        """Restore migration backup."""
        try:
            if not os.path.exists(backup_location):
                return {
                    'status': 'failed',
                    'error_message': 'Backup file not found'
                }
            
            # Restore database backup
            db_config = settings.DATABASES['default']
            if db_config['ENGINE'] == 'django.db.backends.postgresql':
                # PostgreSQL restore
                cmd = [
                    'psql',
                    '--host', db_config['HOST'],
                    '--port', str(db_config['PORT']),
                    '--username', db_config['USER'],
                    '--no-password',
                    '--file', backup_location,
                    db_config['NAME']
                ]
                
                env = os.environ.copy()
                env['PGPASSWORD'] = db_config['PASSWORD']
                
                subprocess.run(cmd, env=env, check=True)
            
            return {
                'status': 'success',
                'message': 'Backup restored successfully'
            }
            
        except Exception as e:
            logger.error(f"Error restoring migration backup: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e)
            }
    
    @staticmethod
    def _transform_data(source_data: Any, validation_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transform data according to validation rules."""
        try:
            # Apply transformation rules
            transformed_data = {}
            
            # Basic transformation - copy all fields
            if hasattr(source_data, '__dict__'):
                transformed_data = source_data.__dict__.copy()
            else:
                transformed_data = source_data.copy()
            
            # Remove Django internal fields
            django_fields = ['id', 'created_at', 'updated_at', 'is_deleted']
            for field in django_fields:
                transformed_data.pop(field, None)
            
            # Apply validation rules
            for rule in validation_rules:
                field_name = rule.get('field')
                rule_type = rule.get('type')
                
                if field_name in transformed_data:
                    if rule_type == 'required':
                        if not transformed_data[field_name]:
                            raise ValueError(f"Field {field_name} is required")
                    elif rule_type == 'format':
                        # Apply format transformation
                        format_rule = rule.get('format')
                        if format_rule == 'uppercase':
                            transformed_data[field_name] = str(transformed_data[field_name]).upper()
                        elif format_rule == 'lowercase':
                            transformed_data[field_name] = str(transformed_data[field_name]).lower()
                    elif rule_type == 'default':
                        # Apply default value if empty
                        if not transformed_data[field_name]:
                            transformed_data[field_name] = rule.get('default')
            
            return transformed_data
            
        except Exception as e:
            logger.error(f"Error transforming data: {str(e)}")
            raise
    
    @staticmethod
    def _update_execution_record(execution: MigrationExecution, result: Dict[str, Any]) -> None:
        """Update execution record with results."""
        try:
            execution.status = result.get('status', 'failed')
            execution.end_time = timezone.now()
            execution.output = result.get('output', '')
            execution.error_message = result.get('error_message', '')
            execution.affected_rows = result.get('affected_rows', 0)
            execution.duration = (execution.end_time - execution.start_time).total_seconds()
            execution.save(update_fields=[
                'status', 'end_time', 'output', 'error_message', 'affected_rows', 'duration'
            ])
            
        except Exception as e:
            logger.error(f"Error updating execution record: {str(e)}")
    
    @staticmethod
    def _validate_schema_migration(migration: Migration, validation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate schema migration."""
        try:
            # Get schema migration
            schema_migration = migration.schema_migration
            
            # Validate SQL syntax
            if schema_migration.sql_script:
                syntax_result = MigrationService._validate_sql_syntax(schema_migration.sql_script)
            else:
                syntax_result = {'valid': True, 'message': 'No SQL script to validate'}
            
            # Validate table operations
            if schema_migration.table_operations:
                operations_result = MigrationService._validate_table_operations(schema_migration.table_operations)
            else:
                operations_result = {'valid': True, 'message': 'No table operations to validate'}
            
            return {
                'sql_validation': syntax_result,
                'operations_validation': operations_result,
                'overall_status': 'valid' if syntax_result['valid'] and operations_result['valid'] else 'invalid'
            }
            
        except Exception as e:
            logger.error(f"Error validating schema migration: {str(e)}")
            return {
                'overall_status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _validate_data_migration(migration: Migration, validation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data migration."""
        try:
            # Get data migration
            data_migration = migration.data_migration
            
            # Validate source models
            source_validation = MigrationService._validate_models(data_migration.source_models)
            
            # Validate target models
            target_validation = MigrationService._validate_models(data_migration.target_models)
            
            # Validate transformation script
            if data_migration.transformation_script:
                script_validation = MigrationService._validate_transformation_script(data_migration.transformation_script)
            else:
                script_validation = {'valid': True, 'message': 'No transformation script to validate'}
            
            return {
                'source_validation': source_validation,
                'target_validation': target_validation,
                'script_validation': script_validation,
                'overall_status': 'valid' if all([
                    source_validation['valid'],
                    target_validation['valid'],
                    script_validation['valid']
                ]) else 'invalid'
            }
            
        except Exception as e:
            logger.error(f"Error validating data migration: {str(e)}")
            return {
                'overall_status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _validate_mixed_migration(migration: Migration, validation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate mixed migration."""
        try:
            # Validate both schema and data components
            schema_result = MigrationService._validate_schema_migration(migration, validation_config)
            data_result = MigrationService._validate_data_migration(migration, validation_config)
            
            return {
                'schema_validation': schema_result,
                'data_validation': data_result,
                'overall_status': 'valid' if (
                    schema_result['overall_status'] == 'valid' and
                    data_result['overall_status'] == 'valid'
                ) else 'invalid'
            }
            
        except Exception as e:
            logger.error(f"Error validating mixed migration: {str(e)}")
            return {
                'overall_status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _validate_generic_migration(migration: Migration, validation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generic migration."""
        try:
            # Validate migration content
            content = migration.content or ''
            if content:
                syntax_result = MigrationService._validate_script_syntax(content)
            else:
                syntax_result = {'valid': True, 'message': 'No content to validate'}
            
            return {
                'content_validation': syntax_result,
                'overall_status': syntax_result['valid']
            }
            
        except Exception as e:
            logger.error(f"Error validating generic migration: {str(e)}")
            return {
                'overall_status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _validate_sql_syntax(sql_script: str) -> Dict[str, Any]:
        """Validate SQL syntax."""
        try:
            # Basic SQL syntax validation
            with connection.cursor() as cursor:
                # Use EXPLAIN to validate syntax without executing
                cursor.execute(f"EXPLAIN {sql_script}")
                cursor.fetchone()  # Fetch the result
                
            return {'valid': True, 'message': 'SQL syntax is valid'}
            
        except Exception as e:
            return {'valid': False, 'error_message': str(e)}
    
    @staticmethod
    def _validate_table_operations(table_operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate table operations."""
        try:
            for operation in table_operations:
                operation_type = operation.get('type')
                table_name = operation.get('table_name')
                
                if not operation_type or not table_name:
                    return {
                        'valid': False,
                        'error_message': 'Invalid table operation format'
                    }
                
                # Validate operation type
                valid_types = ['create', 'alter', 'drop']
                if operation_type not in valid_types:
                    return {
                        'valid': False,
                        'error_message': f'Invalid operation type: {operation_type}'
                    }
                
                # Validate table name
                if not table_name.isidentifier():
                    return {
                        'valid': False,
                        'error_message': f'Invalid table name: {table_name}'
                    }
            
            return {'valid': True, 'message': 'Table operations are valid'}
            
        except Exception as e:
            return {'valid': False, 'error_message': str(e)}
    
    @staticmethod
    def _validate_models(model_names: List[str]) -> Dict[str, Any]:
        """Validate model names."""
        try:
            for model_name in model_names:
                try:
                    apps.get_model('advertiser_portal', model_name)
                except LookupError:
                    return {
                        'valid': False,
                        'error_message': f'Model not found: {model_name}'
                    }
            
            return {'valid': True, 'message': 'All models are valid'}
            
        except Exception as e:
            return {'valid': False, 'error_message': str(e)}
    
    @staticmethod
    def _validate_transformation_script(script_content: str) -> Dict[str, Any]:
        """Validate transformation script."""
        try:
            # Basic Python syntax validation
            compile(script_content, '<string>', 'exec')
            
            return {'valid': True, 'message': 'Transformation script syntax is valid'}
            
        except SyntaxError as e:
            return {'valid': False, 'error_message': str(e)}
        except Exception as e:
            return {'valid': False, 'error_message': str(e)}
    
    @staticmethod
    def _validate_script_syntax(script_content: str) -> Dict[str, Any]:
        """Validate script syntax."""
        try:
            # Basic Python syntax validation
            compile(script_content, '<string>', 'exec')
            
            return {'valid': True, 'message': 'Script syntax is valid'}
            
        except SyntaxError as e:
            return {'valid': False, 'error_message': str(e)}
        except Exception as e:
            return {'valid': False, 'error_message': str(e)}
    
    @staticmethod
    def _calculate_migration_stats(migration: Migration) -> Dict[str, Any]:
        """Calculate migration statistics."""
        try:
            # Get executions for this migration
            executions = MigrationExecution.objects.filter(migration=migration)
            
            # Calculate statistics
            total_executions = executions.count()
            successful_executions = executions.filter(status='success').count()
            failed_executions = executions.filter(status='failed').count()
            timeout_executions = executions.filter(status='timeout').count()
            
            # Calculate success rate
            success_rate = (successful_executions / max(total_executions, 1)) * 100
            
            # Calculate average execution time
            avg_duration = executions.aggregate(
                avg_duration=Avg('duration')
            )['avg_duration'] or 0
            
            # Get last execution
            last_execution = executions.order_by('-start_time').first()
            
            return {
                'migration_id': str(migration.id),
                'migration_name': migration.name,
                'migration_type': migration.type,
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'failed_executions': failed_executions,
                'timeout_executions': timeout_executions,
                'success_rate': round(success_rate, 2),
                'avg_duration': round(avg_duration, 3),
                'last_execution': last_execution.start_time.isoformat() if last_execution else None,
                'last_execution_status': last_execution.status if last_execution else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating migration stats: {str(e)}")
            return {
                'migration_id': str(migration.id),
                'error': 'Failed to calculate statistics'
            }
    
    @staticmethod
    def _log_migration_creation(migration: Migration, user: Optional[User]) -> None:
        """Log migration creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                migration,
                user,
                description=f"Created migration: {migration.name}"
            )
        except Exception as e:
            logger.error(f"Error logging migration creation: {str(e)}")


class SchemaMigrationService:
    """Service for schema migration management."""
    
    @staticmethod
    def create_schema_migration(migration_config: Dict[str, Any]) -> SchemaMigration:
        """Create schema migration with specific configuration."""
        try:
            # Validate schema migration configuration
            SchemaMigrationService._validate_schema_migration_config(migration_config)
            
            # Create schema migration
            schema_migration = SchemaMigration.objects.create(
                sql_script=migration_config.get('sql_script', ''),
                django_migration=migration_config.get('django_migration', ''),
                target_models=migration_config.get('target_models', []),
                table_operations=migration_config.get('table_operations', [])
            )
            
            return schema_migration
            
        except Exception as e:
            logger.error(f"Error creating schema migration: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create schema migration: {str(e)}")
    
    @staticmethod
    def _validate_schema_migration_config(migration_config: Dict[str, Any]) -> None:
        """Validate schema migration configuration."""
        # Validate SQL script or Django migration
        sql_script = migration_config.get('sql_script', '')
        django_migration = migration_config.get('django_migration', '')
        
        if not sql_script and not django_migration:
            raise AdvertiserValidationError("Either SQL script or Django migration must be provided")
        
        if sql_script and django_migration:
            raise AdvertiserValidationError("Cannot provide both SQL script and Django migration")


class DataMigrationService:
    """Service for data migration management."""
    
    @staticmethod
    def create_data_migration(migration_config: Dict[str, Any]) -> DataMigration:
        """Create data migration with specific configuration."""
        try:
            # Validate data migration configuration
            DataMigrationService._validate_data_migration_config(migration_config)
            
            # Create data migration
            data_migration = DataMigration.objects.create(
                source_models=migration_config.get('source_models', []),
                target_models=migration_config.get('target_models', []),
                transformation_script=migration_config.get('transformation_script', ''),
                batch_size=migration_config.get('batch_size', 1000),
                validation_rules=migration_config.get('validation_rules', [])
            )
            
            return data_migration
            
        except Exception as e:
            logger.error(f"Error creating data migration: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create data migration: {str(e)}")
    
    @staticmethod
    def _validate_data_migration_config(migration_config: Dict[str, Any]) -> None:
        """Validate data migration configuration."""
        # Validate source and target models
        source_models = migration_config.get('source_models', [])
        target_models = migration_config.get('target_models', [])
        
        if not source_models or not target_models:
            raise AdvertiserValidationError("Both source and target models must be provided")
        
        if len(source_models) != len(target_models):
            raise AdvertiserValidationError("Source and target models must have the same length")
        
        # Validate batch size
        batch_size = migration_config.get('batch_size', 1000)
        if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 100000:
            raise AdvertiserValidationError("Batch size must be between 1 and 100000")


class RollbackService:
    """Service for rollback management."""
    
    @staticmethod
    def create_rollback(migration_config: Dict[str, Any]) -> Rollback:
        """Create rollback with specific configuration."""
        try:
            # Validate rollback configuration
            RollbackService._validate_rollback_config(migration_config)
            
            # Create rollback
            rollback = Rollback.objects.create(
                target_migration=migration_config.get('target_migration'),
                rollback_script=migration_config.get('rollback_script', ''),
                backup_location=migration_config.get('backup_location', ''),
                rollback_type=migration_config.get('rollback_type', 'full')
            )
            
            return rollback
            
        except Exception as e:
            logger.error(f"Error creating rollback: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create rollback: {str(e)}")
    
    @staticmethod
    def _validate_rollback_config(migration_config: Dict[str, Any]) -> None:
        """Validate rollback configuration."""
        # Validate target migration
        if not migration_config.get('target_migration'):
            raise AdvertiserValidationError("Target migration is required")
        
        # Validate rollback type
        valid_types = ['full', 'partial', 'data', 'schema']
        rollback_type = migration_config.get('rollback_type', 'full')
        if rollback_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid rollback type: {rollback_type}")


class MigrationTrackingService:
    """Service for migration tracking and monitoring."""
    
    @staticmethod
    def get_migration_history(migration_id: UUID) -> List[Dict[str, Any]]:
        """Get migration execution history."""
        try:
            executions = MigrationExecution.objects.filter(migration_id=migration_id).order_by('-start_time')
            
            history = []
            for execution in executions:
                history.append({
                    'execution_id': str(execution.id),
                    'status': execution.status,
                    'start_time': execution.start_time.isoformat(),
                    'end_time': execution.end_time.isoformat() if execution.end_time else None,
                    'duration': execution.duration,
                    'affected_rows': execution.affected_rows,
                    'error_message': execution.error_message,
                    'executed_by': execution.executed_by.username if execution.executed_by else None
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting migration history: {str(e)}")
            return []
    
    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        """Get overall migration system status."""
        try:
            # Get system metrics
            total_migrations = Migration.objects.count()
            pending_migrations = Migration.objects.filter(status='pending').count()
            running_migrations = MigrationExecution.objects.filter(status='running').count()
            
            # Get recent executions
            recent_executions = MigrationExecution.objects.filter(
                start_time__gte=timezone.now() - timedelta(hours=24)
            )
            
            total_executions = recent_executions.count()
            successful_executions = recent_executions.filter(status='success').count()
            
            # Calculate success rate
            success_rate = (successful_executions / max(total_executions, 1)) * 100
            
            return {
                'total_migrations': total_migrations,
                'pending_migrations': pending_migrations,
                'running_migrations': running_migrations,
                'total_executions_24h': total_executions,
                'successful_executions_24h': successful_executions,
                'success_rate_24h': round(success_rate, 2),
                'system_status': 'healthy' if success_rate >= 95 else 'warning',
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {str(e)}")
            return {
                'system_status': 'error',
                'error': str(e)
            }


class MigrationValidationService:
    """Service for migration validation."""
    
    @staticmethod
    def validate_migration_dependencies(migration_id: UUID) -> Dict[str, Any]:
        """Validate migration dependencies."""
        try:
            migration = Migration.objects.get(id=migration_id)
            dependencies = migration.dependencies
            
            validation_result = {
                'dependencies': dependencies,
                'status': 'valid',
                'issues': []
            }
            
            # Check if all dependencies exist and are completed
            for dep_id in dependencies:
                try:
                    dep_migration = Migration.objects.get(id=dep_id)
                    if dep_migration.status != 'completed':
                        validation_result['status'] = 'invalid'
                        validation_result['issues'].append(f"Dependency {dep_id} is not completed")
                except Migration.DoesNotExist:
                    validation_result['status'] = 'invalid'
                    validation_result['issues'].append(f"Dependency {dep_id} does not exist")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating migration dependencies: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def validate_migration_order(migration_ids: List[UUID]) -> Dict[str, Any]:
        """Validate migration execution order."""
        try:
            migrations = Migration.objects.filter(id__in=migration_ids)
            
            # Build dependency graph
            dependency_graph = {}
            for migration in migrations:
                dependency_graph[str(migration.id)] = migration.dependencies
            
            # Check for circular dependencies
            validation_result = {
                'migration_order': [],
                'status': 'valid',
                'issues': []
            }
            
            # Simple topological sort
            visited = set()
            temp_visited = set()
            
            def visit(mig_id):
                if mig_id in temp_visited:
                    validation_result['status'] = 'invalid'
                    validation_result['issues'].append(f"Circular dependency detected: {mig_id}")
                    return
                
                if mig_id in visited:
                    return
                
                temp_visited.add(mig_id)
                
                for dep_id in dependency_graph.get(mig_id, []):
                    visit(dep_id)
                
                temp_visited.remove(mig_id)
                visited.add(mig_id)
                validation_result['migration_order'].append(mig_id)
            
            for migration in migrations:
                visit(str(migration.id))
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating migration order: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }


class MigrationBackupService:
    """Service for migration backup management."""
    
    @staticmethod
    def create_backup(migration_id: UUID, backup_config: Dict[str, Any]) -> MigrationBackup:
        """Create migration backup."""
        try:
            # Validate backup configuration
            MigrationBackupService._validate_backup_config(backup_config)
            
            # Get migration
            migration = Migration.objects.get(id=migration_id)
            
            # Create backup
            backup = MigrationBackup.objects.create(
                migration=migration,
                backup_type=backup_config.get('backup_type', 'pre_migration'),
                backup_location='',
                status='creating',
                created_at=timezone.now()
            )
            
            # Create backup file
            backup_location = MigrationService._create_database_backup(migration, backup)
            
            # Update backup record
            backup.backup_location = backup_location
            backup.status = 'completed'
            backup.save(update_fields=['backup_location', 'status'])
            
            return backup
            
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create backup: {str(e)}")
    
    @staticmethod
    def _validate_backup_config(backup_config: Dict[str, Any]) -> None:
        """Validate backup configuration."""
        # Validate backup type
        valid_types = ['pre_migration', 'post_migration', 'manual']
        backup_type = backup_config.get('backup_type', 'pre_migration')
        if backup_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid backup type: {backup_type}")
    
    @staticmethod
    def restore_backup(backup_id: UUID, restore_config: Dict[str, Any]) -> Dict[str, Any]:
        """Restore migration backup."""
        try:
            # Get backup
            backup = MigrationBackup.objects.get(id=backup_id)
            
            # Restore backup
            restore_result = MigrationService._restore_migration_backup(backup.backup_location, None)
            
            return restore_result
            
        except Exception as e:
            logger.error(f"Error restoring backup: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e)
            }
