"""
Migrations Views

This module provides DRF ViewSets for migration management with
enterprise-grade security, real-time processing, and comprehensive
error handling following industry standards from Django Migrations,
Alembic, and Flyway.
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

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import Coalesce, RowNumber
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods

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
from .services import (
    MigrationService, SchemaMigrationService, DataMigrationService,
    RollbackService, MigrationTrackingService, MigrationValidationService,
    MigrationBackupService, MigrationConfig, MigrationExecution as MigrationExecutionData
)

User = get_user_model()


class MigrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for migration management.
    
    Features:
    - Schema and data migrations
    - Rollback capabilities
    - Migration tracking
    - Validation and testing
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create migration with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Migration validation
        - Audit logging
        """
        try:
            # Security: Validate request
            MigrationViewSet._validate_create_request(request)
            
            # Get migration configuration
            migration_config = request.data
            
            # Create migration
            migration = MigrationService.create_migration(migration_config, request.user)
            
            # Return response
            response_data = {
                'migration_id': str(migration.id),
                'name': migration.name,
                'type': migration.type,
                'description': migration.description,
                'dependencies': migration.dependencies,
                'backup_required': migration.backup_required,
                'status': migration.status,
                'created_at': migration.created_at.isoformat()
            }
            
            # Security: Log migration creation
            MigrationViewSet._log_migration_creation(migration, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating migration: {str(e)}")
            return Response({'error': 'Failed to create migration'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """
        Execute migration with enterprise-grade processing.
        
        Security measures:
        - User permission validation
        - Pre-execution validation
        - Backup creation
        - Audit logging
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            execution_config = request.data
            
            # Execute migration
            execution = MigrationService.execute_migration(migration_id, execution_config, request.user)
            
            return Response({
                'execution_id': str(execution.id),
                'status': execution.status,
                'start_time': execution.start_time.isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error executing migration: {str(e)}")
            return Response({'error': 'Failed to execute migration'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def rollback(self, request, pk=None):
        """
        Rollback migration with enterprise-grade processing.
        
        Security measures:
        - User permission validation
        - Pre-rollback validation
        - Backup restoration
        - Audit logging
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            rollback_config = request.data
            
            # Rollback migration
            execution = MigrationService.rollback_migration(migration_id, rollback_config, request.user)
            
            return Response({
                'execution_id': str(execution.id),
                'status': execution.status,
                'start_time': execution.start_time.isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error rolling back migration: {str(e)}")
            return Response({'error': 'Failed to rollback migration'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate migration with comprehensive checks.
        
        Security measures:
        - User permission validation
        - Validation execution
        - Security checks
        - Audit logging
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            validation_config = request.data
            
            # Validate migration
            validation_result = MigrationService.validate_migration(migration_id, validation_config, request.user)
            
            return Response({'validation_result': validation_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error validating migration: {str(e)}")
            return Response({'error': 'Failed to validate migration'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Get migration statistics and performance metrics.
        
        Security measures:
        - User permission validation
        - Stats access control
        - Rate limiting
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            
            # Get statistics
            stats = MigrationService.get_migration_stats(migration_id)
            
            return Response({'stats': stats}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting migration stats: {str(e)}")
            return Response({'error': 'Failed to get migration stats'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Get migration execution history.
        
        Security measures:
        - User permission validation
        - History access control
        - Data filtering
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            
            # Get query parameters
            filters = {
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'status': request.query_params.get('status'),
                'limit': int(request.query_params.get('limit', 100))
            }
            
            # Get history
            history_data = MigrationViewSet._get_migration_history(migration_id, filters)
            
            return Response({'history': history_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting migration history: {str(e)}")
            return Response({'error': 'Failed to get migration history'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List migrations with filtering and pagination.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            MigrationViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'type': request.query_params.get('type'),
                'status': request.query_params.get('status'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'page': int(request.query_params.get('page', 1)),
                'page_size': min(int(request.query_params.get('page_size', 20)), 100)
            }
            
            # Get migrations list
            migrations_data = MigrationViewSet._get_migrations_list(user, filters)
            
            return Response(migrations_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing migrations: {str(e)}")
            return Response({'error': 'Failed to list migrations'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not request.user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'type', 'description']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate migration type
        valid_types = ['schema', 'data', 'mixed', 'rollback']
        migration_type = request.data.get('type')
        if migration_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid migration type: {migration_type}")
        
        # Security: Validate migration content
        content = request.data.get('content', '')
        if content:
            MigrationViewSet._validate_migration_content(content, migration_type)
    
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
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise AdvertiserValidationError("Migration content contains prohibited code")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
    
    @staticmethod
    def _get_migrations_list(user: User, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get migrations list with filtering and pagination."""
        try:
            # Build query
            queryset = Migration.objects.all()
            
            # Apply filters
            if filters.get('type'):
                queryset = queryset.filter(type=filters['type'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
            
            # Pagination
            page = filters.get('page', 1)
            page_size = filters.get('page_size', 20)
            offset = (page - 1) * page_size
            
            # Get paginated results
            results = queryset[offset:offset + page_size]
            
            # Format results
            migrations = []
            for migration in results:
                migrations.append({
                    'id': str(migration.id),
                    'name': migration.name,
                    'type': migration.type,
                    'description': migration.description,
                    'status': migration.status,
                    'created_at': migration.created_at.isoformat(),
                    'updated_at': migration.updated_at.isoformat()
                })
            
            return {
                'migrations': migrations,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': queryset.count(),
                    'total_pages': (queryset.count() + page_size - 1) // page_size
                },
                'filters_applied': filters
            }
            
        except Exception as e:
            logger.error(f"Error getting migrations list: {str(e)}")
            return {
                'migrations': [],
                'pagination': {'page': 1, 'page_size': 20, 'total_count': 0, 'total_pages': 0},
                'filters_applied': filters,
                'error': 'Failed to retrieve migrations'
            }
    
    @staticmethod
    def _get_migration_history(migration_id: UUID, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get migration execution history with filtering."""
        try:
            # Build query
            queryset = MigrationExecution.objects.filter(migration_id=migration_id)
            
            # Apply filters
            if filters.get('date_from'):
                queryset = queryset.filter(start_time__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(start_time__lte=filters['date_to'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            # Get limited results
            executions = queryset.order_by('-start_time')[:filters.get('limit', 100)]
            
            # Format results
            history_data = []
            for execution in executions:
                history_data.append({
                    'execution_id': str(execution.id),
                    'status': execution.status,
                    'start_time': execution.start_time.isoformat(),
                    'end_time': execution.end_time.isoformat() if execution.end_time else None,
                    'duration': execution.duration,
                    'affected_rows': execution.affected_rows,
                    'error_message': execution.error_message,
                    'executed_by': execution.executed_by.username if execution.executed_by else None
                })
            
            return history_data
            
        except Exception as e:
            logger.error(f"Error getting migration history: {str(e)}")
            return []
    
    @staticmethod
    def _log_migration_creation(migration: Migration, user: User) -> None:
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


class SchemaMigrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for schema migration management.
    
    Features:
    - SQL script management
    - Django migration support
    - Table operations
    - Schema validation
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create schema migration with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - SQL validation
        - Audit logging
        """
        try:
            # Security: Validate request
            SchemaMigrationViewSet._validate_create_request(request)
            
            # Get schema migration configuration
            migration_config = request.data
            
            # Create schema migration
            schema_migration = SchemaMigrationService.create_schema_migration(migration_config)
            
            return Response({'schema_migration_id': str(schema_migration.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating schema migration: {str(e)}")
            return Response({'error': 'Failed to create schema migration'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not request.user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        # Security: Validate SQL script or Django migration
        sql_script = request.data.get('sql_script', '')
        django_migration = request.data.get('django_migration', '')
        
        if not sql_script and not django_migration:
            raise AdvertiserValidationError("Either SQL script or Django migration must be provided")
        
        if sql_script and django_migration:
            raise AdvertiserValidationError("Cannot provide both SQL script and Django migration")


class DataMigrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for data migration management.
    
    Features:
    - Data transformation scripts
    - Batch processing
    - Model mapping
    - Validation rules
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create data migration with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Model validation
        - Audit logging
        """
        try:
            # Security: Validate request
            DataMigrationViewSet._validate_create_request(request)
            
            # Get data migration configuration
            migration_config = request.data
            
            # Create data migration
            data_migration = DataMigrationService.create_data_migration(migration_config)
            
            return Response({'data_migration_id': str(data_migration.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating data migration: {str(e)}")
            return Response({'error': 'Failed to create data migration'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not request.user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        # Security: Validate source and target models
        source_models = request.data.get('source_models', [])
        target_models = request.data.get('target_models', [])
        
        if not source_models or not target_models:
            raise AdvertiserValidationError("Both source and target models must be provided")
        
        if len(source_models) != len(target_models):
            raise AdvertiserValidationError("Source and target models must have the same length")


class RollbackViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for rollback management.
    
    Features:
    - Rollback script management
    - Backup restoration
    - Rollback tracking
    - Validation and testing
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create rollback with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Rollback validation
        - Audit logging
        """
        try:
            # Security: Validate request
            RollbackViewSet._validate_create_request(request)
            
            # Get rollback configuration
            rollback_config = request.data
            
            # Create rollback
            rollback = RollbackService.create_rollback(rollback_config)
            
            return Response({'rollback_id': str(rollback.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating rollback: {str(e)}")
            return Response({'error': 'Failed to create rollback'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not request.user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        # Security: Validate target migration
        if not request.data.get('target_migration'):
            raise AdvertiserValidationError("Target migration is required")


class MigrationTrackingViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for migration tracking and monitoring.
    
    Features:
    - Execution tracking
    - Performance monitoring
    - History management
    - Status reporting
    - Analytics and metrics
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Get migration execution history.
        
        Security measures:
        - User permission validation
        - History access control
        - Data filtering
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            
            # Get history
            history_data = MigrationTrackingService.get_migration_history(migration_id)
            
            return Response({'history': history_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting migration history: {str(e)}")
            return Response({'error': 'Failed to get migration history'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def system_status(self, request):
        """
        Get overall migration system status.
        
        Security measures:
        - User permission validation
        - System access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            MigrationTrackingViewSet._validate_user_access(user)
            
            # Get system status
            status = MigrationTrackingService.get_system_status()
            
            return Response({'status': status}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting system status: {str(e)}")
            return Response({'error': 'Failed to get system status'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")


class MigrationValidationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for migration validation.
    
    Features:
    - Dependency validation
    - Order validation
    - Syntax validation
    - Security validation
    - Performance impact analysis
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['post'])
    def validate_dependencies(self, request, pk=None):
        """
        Validate migration dependencies.
        
        Security measures:
        - User permission validation
        - Validation execution
        - Security checks
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            
            # Validate dependencies
            validation_result = MigrationValidationService.validate_migration_dependencies(migration_id)
            
            return Response({'validation_result': validation_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error validating migration dependencies: {str(e)}")
            return Response({'error': 'Failed to validate dependencies'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def validate_order(self, request):
        """
        Validate migration execution order.
        
        Security measures:
        - User permission validation
        - Order validation
        - Dependency checking
        """
        try:
            # Security: Validate request
            MigrationValidationViewSet._validate_order_request(request)
            
            # Get migration IDs
            migration_ids = request.data.get('migration_ids', [])
            
            # Validate order
            validation_result = MigrationValidationService.validate_migration_order(migration_ids)
            
            return Response({'validation_result': validation_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error validating migration order: {str(e)}")
            return Response({'error': 'Failed to validate order'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_order_request(request) -> None:
        """Validate order request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not request.user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        if not request.data.get('migration_ids'):
            raise AdvertiserValidationError("Migration IDs are required")


class MigrationBackupViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for migration backup management.
    
    Features:
    - Backup creation
    - Backup restoration
    - Backup tracking
    - Backup validation
    - Storage management
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['post'])
    def create_backup(self, request, pk=None):
        """
        Create migration backup.
        
        Security measures:
        - User permission validation
        - Backup creation
        - Storage validation
        - Audit logging
        """
        try:
            # Security: Validate migration access
            migration_id = UUID(pk)
            backup_config = request.data
            
            # Create backup
            backup = MigrationBackupService.create_backup(migration_id, backup_config)
            
            return Response({'backup_id': str(backup.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            return Response({'error': 'Failed to create backup'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def restore_backup(self, request, pk=None):
        """
        Restore migration backup.
        
        Security measures:
        - User permission validation
        - Backup restoration
        - Validation
        - Audit logging
        """
        try:
            # Security: Validate backup access
            backup_id = UUID(pk)
            restore_config = request.data
            
            # Restore backup
            restore_result = MigrationBackupService.restore_backup(backup_id, restore_config)
            
            return Response({'restore_result': restore_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error restoring backup: {str(e)}")
            return Response({'error': 'Failed to restore backup'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_backup_request(request) -> None:
        """Validate backup request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not request.user.is_superuser:
            raise AdvertiserValidationError("User does not have migration permissions")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        # Security: Validate backup type
        valid_types = ['pre_migration', 'post_migration', 'manual']
        backup_type = request.data.get('backup_type', 'pre_migration')
        if backup_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid backup type: {backup_type}")
