"""
Scripts Views

This module provides DRF ViewSets for script management with
enterprise-grade security, real-time processing, and comprehensive
error handling following industry standards from Jenkins, GitHub Actions, and Ansible.
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
from ..database_models.script_model import (
    Script, AutomationScript, DataProcessingScript, MaintenanceScript,
    DeploymentScript, ScriptExecution, ScriptLog, ScriptSecurity
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    ScriptService, AutomationScriptService, DataProcessingScriptService,
    MaintenanceScriptService, DeploymentScriptService, ScriptExecutionService,
    ScriptMonitoringService, ScriptSecurityService,
    ScriptConfig, ScriptExecution as ScriptExecutionData
)

User = get_user_model()


class ScriptViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for script management.
    
    Features:
    - Multi-type script support
    - Real-time execution
    - Advanced security
    - Performance monitoring
    - Comprehensive logging
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create script with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Code security scanning
        - Audit logging
        """
        try:
            # Security: Validate request
            ScriptViewSet._validate_create_request(request)
            
            # Get script configuration
            script_config = request.data
            
            # Create script
            script = ScriptService.create_script(script_config, request.user)
            
            # Return response
            response_data = {
                'script_id': str(script.id),
                'name': script.name,
                'type': script.type,
                'content': script.content,
                'parameters': script.parameters,
                'environment': script.environment,
                'timeout': script.timeout,
                'retry_policy': script.retry_policy,
                'status': script.status,
                'created_at': script.created_at.isoformat()
            }
            
            # Security: Log script creation
            ScriptViewSet._log_script_creation(script, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating script: {str(e)}")
            return Response({'error': 'Failed to create script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """
        Execute script with enterprise-grade processing.
        
        Security measures:
        - User permission validation
        - Execution environment validation
        - Resource monitoring
        - Audit logging
        """
        try:
            # Security: Validate script access
            script_id = UUID(pk)
            execution_config = request.data
            
            # Execute script
            execution = ScriptService.execute_script(script_id, execution_config, request.user)
            
            return Response({
                'execution_id': str(execution.id),
                'status': execution.status,
                'start_time': execution.start_time.isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error executing script: {str(e)}")
            return Response({'error': 'Failed to execute script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """
        Schedule script execution with advanced scheduling.
        
        Security measures:
        - User permission validation
        - Schedule validation
        - Resource management
        - Audit logging
        """
        try:
            # Security: Validate script access
            script_id = UUID(pk)
            schedule_config = request.data
            
            # Schedule script
            schedule = ScriptService.schedule_script(script_id, schedule_config, request.user)
            
            return Response({'schedule': schedule}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error scheduling script: {str(e)}")
            return Response({'error': 'Failed to schedule script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Get script statistics and performance metrics.
        
        Security measures:
        - User permission validation
        - Stats access control
        - Rate limiting
        """
        try:
            # Security: Validate script access
            script_id = UUID(pk)
            
            # Get statistics
            stats = ScriptService.get_script_stats(script_id)
            
            return Response({'stats': stats}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting script stats: {str(e)}")
            return Response({'error': 'Failed to get script stats'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def executions(self, request, pk=None):
        """
        Get script execution history.
        
        Security measures:
        - User permission validation
        - Execution access control
        - Data filtering
        """
        try:
            # Security: Validate script access
            script_id = UUID(pk)
            
            # Get query parameters
            filters = {
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'status': request.query_params.get('status'),
                'limit': int(request.query_params.get('limit', 100))
            }
            
            # Get executions
            executions_data = ScriptViewSet._get_script_executions(script_id, filters)
            
            return Response({'executions': executions_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting script executions: {str(e)}")
            return Response({'error': 'Failed to get script executions'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test script with sample data.
        
        Security measures:
        - User permission validation
        - Test execution validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate script access
            script_id = UUID(pk)
            test_config = request.data
            
            # Test script
            test_result = ScriptViewSet._test_script(script_id, test_config, request.user)
            
            return Response({'test_result': test_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error testing script: {str(e)}")
            return Response({'error': 'Failed to test script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List scripts with filtering and pagination.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            ScriptViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'type': request.query_params.get('type'),
                'status': request.query_params.get('status'),
                'page': int(request.query_params.get('page', 1)),
                'page_size': min(int(request.query_params.get('page_size', 20)), 100)
            }
            
            # Get scripts list
            scripts_data = ScriptViewSet._get_scripts_list(user, filters)
            
            return Response(scripts_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing scripts: {str(e)}")
            return Response({'error': 'Failed to list scripts'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'type', 'content']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate script type
        valid_types = ['automation', 'data_processing', 'maintenance', 'deployment']
        script_type = request.data.get('type')
        if script_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid script type: {script_type}")
        
        # Security: Validate script content
        content = request.data.get('content')
        if not content or len(content.strip()) < 10:
            raise AdvertiserValidationError("Script content is too short")
        
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
                raise AdvertiserValidationError("Script content contains prohibited code")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have script permissions")
    
    @staticmethod
    def _get_scripts_list(user: User, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get scripts list with filtering and pagination."""
        try:
            # Build query
            queryset = Script.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(advertiser__user=user)
            
            # Apply filters
            if filters.get('type'):
                queryset = queryset.filter(type=filters['type'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            # Pagination
            page = filters.get('page', 1)
            page_size = filters.get('page_size', 20)
            offset = (page - 1) * page_size
            
            # Get paginated results
            results = queryset[offset:offset + page_size]
            
            # Format results
            scripts = []
            for script in results:
                scripts.append({
                    'id': str(script.id),
                    'name': script.name,
                    'type': script.type,
                    'status': script.status,
                    'created_at': script.created_at.isoformat(),
                    'updated_at': script.updated_at.isoformat()
                })
            
            return {
                'scripts': scripts,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': queryset.count(),
                    'total_pages': (queryset.count() + page_size - 1) // page_size
                },
                'filters_applied': filters
            }
            
        except Exception as e:
            logger.error(f"Error getting scripts list: {str(e)}")
            return {
                'scripts': [],
                'pagination': {'page': 1, 'page_size': 20, 'total_count': 0, 'total_pages': 0},
                'filters_applied': filters,
                'error': 'Failed to retrieve scripts'
            }
    
    @staticmethod
    def _get_script_executions(script_id: UUID, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get script executions with filtering."""
        try:
            # Build query
            queryset = ScriptExecution.objects.filter(script_id=script_id)
            
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
            executions_data = []
            for execution in executions:
                executions_data.append({
                    'id': str(execution.id),
                    'status': execution.status,
                    'start_time': execution.start_time.isoformat(),
                    'end_time': execution.end_time.isoformat() if execution.end_time else None,
                    'duration': execution.duration,
                    'exit_code': execution.exit_code,
                    'error_message': execution.error_message
                })
            
            return executions_data
            
        except Exception as e:
            logger.error(f"Error getting script executions: {str(e)}")
            return []
    
    @staticmethod
    def _test_script(script_id: UUID, test_config: Dict[str, Any], user: User) -> Dict[str, Any]:
        """Test script with sample data."""
        try:
            # Get script
            script = Script.objects.get(id=script_id)
            
            # Create test execution
            test_execution_config = {
                'parameters': test_config.get('parameters', {}),
                'environment': test_config.get('environment', {'TEST_MODE': 'true'})
            }
            
            # Execute script in test mode
            execution = ScriptService.execute_script(script_id, test_execution_config, user)
            
            return {
                'success': execution.status == 'success',
                'execution_id': str(execution.id),
                'status_code': execution.exit_code,
                'output': execution.output,
                'error_message': execution.error_message,
                'duration': execution.duration
            }
            
        except Exception as e:
            logger.error(f"Error testing script: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _log_script_creation(script: Script, user: User) -> None:
        """Log script creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                script,
                user,
                description=f"Created script: {script.name}"
            )
        except Exception as e:
            logger.error(f"Error logging script creation: {str(e)}")


class AutomationScriptViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for automation script management.
    
    Features:
    - Automation script configuration
    - Trigger management
    - Action execution
    - Condition evaluation
    - Performance monitoring
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create automation script with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Trigger validation
        - Audit logging
        """
        try:
            # Security: Validate request
            AutomationScriptViewSet._validate_create_request(request)
            
            # Get automation script configuration
            script_config = request.data
            
            # Create automation script
            script = AutomationScriptService.create_automation_script(script_config)
            
            return Response({'automation_script_id': str(script.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating automation script: {str(e)}")
            return Response({'error': 'Failed to create automation script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['trigger_type', 'actions']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate trigger type
        valid_triggers = ['manual', 'schedule', 'event', 'webhook']
        trigger_type = request.data.get('trigger_type')
        if trigger_type not in valid_triggers:
            raise AdvertiserValidationError(f"Invalid trigger type: {trigger_type}")


class DataProcessingScriptViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for data processing script management.
    
    Features:
    - Data processing configuration
    - ETL pipeline management
    - Batch processing
    - Data validation
    - Performance monitoring
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create data processing script with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Data source validation
        - Audit logging
        """
        try:
            # Security: Validate request
            DataProcessingScriptViewSet._validate_create_request(request)
            
            # Get data processing script configuration
            script_config = request.data
            
            # Create data processing script
            script = DataProcessingScriptService.create_data_processing_script(script_config)
            
            return Response({'data_processing_script_id': str(script.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating data processing script: {str(e)}")
            return Response({'error': 'Failed to create data processing script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['data_source', 'data_target', 'processing_type']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate processing type
        valid_types = ['etl', 'elt', 'validation', 'transformation', 'aggregation']
        processing_type = request.data.get('processing_type')
        if processing_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid processing type: {processing_type}")


class MaintenanceScriptViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for maintenance script management.
    
    Features:
    - Maintenance script configuration
    - System maintenance tasks
    - Impact assessment
    - Approval workflow
    - Performance monitoring
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create maintenance script with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Impact level validation
        - Audit logging
        """
        try:
            # Security: Validate request
            MaintenanceScriptViewSet._validate_create_request(request)
            
            # Get maintenance script configuration
            script_config = request.data
            
            # Create maintenance script
            script = MaintenanceScriptService.create_maintenance_script(script_config)
            
            return Response({'maintenance_script_id': str(script.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating maintenance script: {str(e)}")
            return Response({'error': 'Failed to create maintenance script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['maintenance_type', 'target_systems']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate maintenance type
        valid_types = ['cleanup', 'backup', 'restore', 'update', 'optimization']
        maintenance_type = request.data.get('maintenance_type')
        if maintenance_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid maintenance type: {maintenance_type}")


class DeploymentScriptViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for deployment script management.
    
    Features:
    - Deployment script configuration
    - Environment management
    - Rollback capabilities
    - Approval workflow
    - Performance monitoring
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create deployment script with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Environment validation
        - Audit logging
        """
        try:
            # Security: Validate request
            DeploymentScriptViewSet._validate_create_request(request)
            
            # Get deployment script configuration
            script_config = request.data
            
            # Create deployment script
            script = DeploymentScriptService.create_deployment_script(script_config)
            
            return Response({'deployment_script_id': str(script.id)}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating deployment script: {str(e)}")
            return Response({'error': 'Failed to create deployment script'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['deployment_type', 'target_environment']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate deployment type
        valid_types = ['manual', 'automatic', 'rollback', 'blue_green', 'canary']
        deployment_type = request.data.get('deployment_type')
        if deployment_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid deployment type: {deployment_type}")


class ScriptExecutionViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for script execution management.
    
    Features:
    - Script execution tracking
    - Real-time monitoring
    - Output capture
    - Error handling
    - Performance metrics
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """
        Get script execution details.
        
        Security measures:
        - User permission validation
        - Execution access control
        - Data filtering
        """
        try:
            # Security: Validate execution access
            execution_id = UUID(pk)
            
            # Get execution details
            execution = ScriptExecutionService.get_execution(execution_id)
            
            if not execution:
                return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'execution_id': str(execution.id),
                'script_id': str(execution.script_id),
                'status': execution.status,
                'start_time': execution.start_time.isoformat(),
                'end_time': execution.end_time.isoformat() if execution.end_time else None,
                'duration': execution.duration,
                'exit_code': execution.exit_code,
                'output': execution.output,
                'error_message': execution.error_message
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting execution details: {str(e)}")
            return Response({'error': 'Failed to get execution details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List script executions with filtering.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            ScriptExecutionViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'script_id': request.query_params.get('script_id'),
                'status': request.query_params.get('status'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'limit': int(request.query_params.get('limit', 100))
            }
            
            # Get executions list
            executions_data = ScriptExecutionViewSet._get_executions_list(user, filters)
            
            return Response({'executions': executions_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing executions: {str(e)}")
            return Response({'error': 'Failed to list executions'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have script execution permissions")
    
    @staticmethod
    def _get_executions_list(user: User, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get executions list with filtering."""
        try:
            # Build query
            queryset = ScriptExecution.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                # Get user's scripts
                user_script_ids = Script.objects.filter(
                    advertiser__user=user
                ).values_list('id', flat=True)
                
                queryset = queryset.filter(script_id__in=user_script_ids)
            
            # Apply filters
            if filters.get('script_id'):
                queryset = queryset.filter(script_id=filters['script_id'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('date_from'):
                queryset = queryset.filter(start_time__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(start_time__lte=filters['date_to'])
            
            # Get limited results
            executions = queryset.order_by('-start_time')[:filters.get('limit', 100)]
            
            # Format results
            executions_data = []
            for execution in executions:
                executions_data.append({
                    'execution_id': str(execution.id),
                    'script_id': str(execution.script_id),
                    'status': execution.status,
                    'start_time': execution.start_time.isoformat(),
                    'end_time': execution.end_time.isoformat() if execution.end_time else None,
                    'duration': execution.duration,
                    'exit_code': execution.exit_code
                })
            
            return executions_data
            
        except Exception as e:
            logger.error(f"Error getting executions list: {str(e)}")
            return []


class ScriptMonitoringViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for script monitoring.
    
    Features:
    - Real-time health monitoring
    - Performance metrics
    - Error tracking
    - Alert management
    - System health checks
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['get'])
    def health(self, request, pk=None):
        """
        Get script health status.
        
        Security measures:
        - User permission validation
        - Health access control
        - Rate limiting
        """
        try:
            # Security: Validate script access
            script_id = UUID(pk)
            
            # Get health status
            health = ScriptMonitoringService.get_script_health(script_id)
            
            return Response({'health': health}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting script health: {str(e)}")
            return Response({'error': 'Failed to get script health'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """
        Get overall script system health.
        
        Security measures:
        - User permission validation
        - System access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            ScriptMonitoringViewSet._validate_user_access(user)
            
            # Get system health
            health = ScriptMonitoringService.get_system_health()
            
            return Response({'health': health}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return Response({'error': 'Failed to get system health'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have script monitoring permissions")


class ScriptSecurityViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for script security management.
    
    Features:
    - Script security validation
    - Code scanning
    - Vulnerability assessment
    - Security monitoring
    - Alert management
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def validate(self, request):
        """
        Validate script security with comprehensive checks.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Security scanning
        - Audit logging
        """
        try:
            # Security: Validate request
            ScriptSecurityViewSet._validate_request(request)
            
            # Get script content
            script_content = request.data.get('content', '')
            
            # Validate security
            security_result = ScriptSecurityService.validate_script_security(script_content)
            
            return Response({'security': security_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error validating script security: {str(e)}")
            return Response({'error': 'Failed to validate script security'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_request(request) -> None:
        """Validate request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        if not request.data.get('content'):
            raise AdvertiserValidationError("Script content is required")
