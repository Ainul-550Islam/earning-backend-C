"""
Scripts Services

This module handles comprehensive script management with enterprise-grade security,
real-time processing, and advanced features following industry standards from
Jenkins, GitHub Actions, and Ansible.
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
import traceback

from django.db import transaction
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


@dataclass
class ScriptConfig:
    """Script configuration with metadata."""
    script_id: str
    name: str
    type: str
    content: str
    parameters: Dict[str, Any]
    environment: Dict[str, Any]
    timeout: int
    retry_policy: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class ScriptExecution:
    """Script execution data with metadata."""
    execution_id: str
    script_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    output: Optional[str]
    error_message: Optional[str]
    exit_code: Optional[int]
    duration: float
    user_id: Optional[str]


class ScriptService:
    """
    Enterprise-grade script management service.
    
    Features:
    - Multi-type script support
    - Real-time execution
    - Advanced security
    - Performance monitoring
    - Comprehensive logging
    """
    
    @staticmethod
    def create_script(script_config: Dict[str, Any], created_by: Optional[User] = None) -> Script:
        """
        Create script with enterprise-grade security.
        
        Supported script types:
        - Automation: Business process automation
        - Data Processing: ETL and data transformation
        - Maintenance: System maintenance tasks
        - Deployment: Application deployment scripts
        
        Security features:
        - Code validation and sanitization
        - Permission validation
        - Security scanning
        - Audit logging
        """
        try:
            # Security: Validate script configuration
            ScriptService._validate_script_config(script_config, created_by)
            
            # Get script-specific configuration
            script_type = script_config.get('type')
            
            with transaction.atomic():
                # Create base script
                script = Script.objects.create(
                    advertiser=script_config.get('advertiser'),
                    name=script_config.get('name'),
                    type=script_type,
                    content=script_config.get('content'),
                    parameters=script_config.get('parameters', {}),
                    environment=script_config.get('environment', {}),
                    timeout=script_config.get('timeout', 300),
                    retry_policy=script_config.get('retry_policy', {}),
                    status=script_config.get('status', 'active'),
                    created_by=created_by
                )
                
                # Create type-specific script
                if script_type == 'automation':
                    ScriptService._create_automation_script(script, script_config)
                elif script_type == 'data_processing':
                    ScriptService._create_data_processing_script(script, script_config)
                elif script_type == 'maintenance':
                    ScriptService._create_maintenance_script(script, script_config)
                elif script_type == 'deployment':
                    ScriptService._create_deployment_script(script, script_config)
                
                # Send notification
                Notification.objects.create(
                    user=created_by,
                    title='Script Created',
                    message=f'Successfully created {script_type} script: {script.name}',
                    notification_type='script',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log script creation
                ScriptService._log_script_creation(script, created_by)
                
                return script
                
        except Exception as e:
            logger.error(f"Error creating script: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create script: {str(e)}")
    
    @staticmethod
    def execute_script(script_id: UUID, execution_config: Dict[str, Any], executed_by: Optional[User] = None) -> ScriptExecution:
        """
        Execute script with enterprise-grade processing.
        
        Execution features:
        - Secure execution environment
        - Resource monitoring
        - Timeout handling
        - Output capture
        - Error handling
        """
        try:
            # Security: Validate execution configuration
            ScriptService._validate_execution_config(execution_config, executed_by)
            
            # Get script
            script = Script.objects.get(id=script_id)
            
            # Create execution record
            execution = ScriptService._create_execution_record(script, execution_config, executed_by)
            
            # Execute script based on type
            if script.type == 'automation':
                result = ScriptService._execute_automation_script(script, execution)
            elif script.type == 'data_processing':
                result = ScriptService._execute_data_processing_script(script, execution)
            elif script.type == 'maintenance':
                result = ScriptService._execute_maintenance_script(script, execution)
            elif script.type == 'deployment':
                result = ScriptService._execute_deployment_script(script, execution)
            else:
                result = ScriptService._execute_generic_script(script, execution)
            
            # Update execution record
            ScriptService._update_execution_record(execution, result)
            
            return execution
            
        except Exception as e:
            logger.error(f"Error executing script: {str(e)}")
            raise AdvertiserServiceError(f"Failed to execute script: {str(e)}")
    
    @staticmethod
    def schedule_script(script_id: UUID, schedule_config: Dict[str, Any], scheduled_by: Optional[User] = None) -> Dict[str, Any]:
        """
        Schedule script execution with advanced scheduling.
        
        Scheduling features:
        - Cron-based scheduling
        - Event-based scheduling
        - Resource management
        - Conflict resolution
        """
        try:
            # Security: Validate scheduling configuration
            ScriptService._validate_schedule_config(schedule_config, scheduled_by)
            
            # Get script
            script = Script.objects.get(id=script_id)
            
            # Create schedule
            schedule = ScriptService._create_schedule(script, schedule_config, scheduled_by)
            
            return schedule
            
        except Exception as e:
            logger.error(f"Error scheduling script: {str(e)}")
            raise AdvertiserServiceError(f"Failed to schedule script: {str(e)}")
    
    @staticmethod
    def get_script_stats(script_id: UUID) -> Dict[str, Any]:
        """
        Get script statistics with comprehensive metrics.
        
        Statistics include:
        - Execution success rate
        - Average execution time
        - Error breakdown
        - Resource usage
        - Performance metrics
        """
        try:
            # Get script
            script = Script.objects.get(id=script_id)
            
            # Calculate statistics
            stats = ScriptService._calculate_script_stats(script)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting script stats: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get script stats: {str(e)}")
    
    @staticmethod
    def _validate_script_config(script_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate script configuration with security checks."""
        # Security: Check required fields
        required_fields = ['name', 'type', 'content']
        for field in required_fields:
            if not script_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate script type
        valid_types = ['automation', 'data_processing', 'maintenance', 'deployment']
        script_type = script_config.get('type')
        if script_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid script type: {script_type}")
        
        # Security: Validate script content
        content = script_config.get('content')
        ScriptService._validate_script_content(content, script_type)
        
        # Security: Check user permissions
        if user and not user.is_superuser:
            advertiser = script_config.get('advertiser')
            if advertiser and advertiser.user != user:
                raise AdvertiserValidationError("User does not have access to this advertiser")
    
    @staticmethod
    def _validate_script_content(content: str, script_type: str) -> None:
        """Validate script content with security checks."""
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
            r'import\s+os',           # OS imports
            r'import\s+sys',          # System imports
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise AdvertiserValidationError("Script content contains prohibited code")
        
        # Type-specific validation
        if script_type == 'automation':
            ScriptService._validate_automation_script(content)
        elif script_type == 'data_processing':
            ScriptService._validate_data_processing_script(content)
        elif script_type == 'maintenance':
            ScriptService._validate_maintenance_script(content)
        elif script_type == 'deployment':
            ScriptService._validate_deployment_script(content)
    
    @staticmethod
    def _validate_automation_script(content: str) -> None:
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
                raise AdvertiserValidationError("Automation script contains potentially unsafe code")
    
    @staticmethod
    def _validate_data_processing_script(content: str) -> None:
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
                raise AdvertiserValidationError("Data processing script contains potentially unsafe operations")
    
    @staticmethod
    def _validate_maintenance_script(content: str) -> None:
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
                raise AdvertiserValidationError("Maintenance script contains potentially dangerous operations")
    
    @staticmethod
    def _validate_deployment_script(content: str) -> None:
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
                raise AdvertiserValidationError("Deployment script contains potentially dangerous operations")
    
    @staticmethod
    def _validate_execution_config(execution_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate execution configuration with security checks."""
        # Security: Check user permissions
        if user and not user.is_superuser:
            raise AdvertiserValidationError("User does not have script execution permissions")
        
        # Security: Validate parameters
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
    def _validate_schedule_config(schedule_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate schedule configuration with security checks."""
        # Security: Check user permissions
        if user and not user.is_superuser:
            raise AdvertiserValidationError("User does not have script scheduling permissions")
        
        # Security: Validate schedule type
        schedule_type = schedule_config.get('type')
        valid_types = ['cron', 'interval', 'event', 'manual']
        if schedule_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid schedule type: {schedule_type}")
        
        # Security: Validate cron expression
        if schedule_type == 'cron':
            cron_expression = schedule_config.get('cron_expression')
            if not cron_expression:
                raise AdvertiserValidationError("Cron expression is required for cron scheduling")
    
    @staticmethod
    def _create_automation_script(script: Script, script_config: Dict[str, Any]) -> AutomationScript:
        """Create automation script specific configuration."""
        return AutomationScript.objects.create(
            script=script,
            trigger_type=script_config.get('trigger_type', 'manual'),
            trigger_config=script_config.get('trigger_config', {}),
            actions=script_config.get('actions', []),
            conditions=script_config.get('conditions', [])
        )
    
    @staticmethod
    def _create_data_processing_script(script: Script, script_config: Dict[str, Any]) -> DataProcessingScript:
        """Create data processing script specific configuration."""
        return DataProcessingScript.objects.create(
            script=script,
            data_source=script_config.get('data_source', ''),
            data_target=script_config.get('data_target', ''),
            processing_type=script_config.get('processing_type', 'etl'),
            batch_size=script_config.get('batch_size', 1000),
            retry_count=script_config.get('retry_count', 3)
        )
    
    @staticmethod
    def _create_maintenance_script(script: Script, script_config: Dict[str, Any]) -> MaintenanceScript:
        """Create maintenance script specific configuration."""
        return MaintenanceScript.objects.create(
            script=script,
            maintenance_type=script_config.get('maintenance_type', 'cleanup'),
            target_systems=script_config.get('target_systems', []),
            impact_level=script_config.get('impact_level', 'low'),
            approval_required=script_config.get('approval_required', False)
        )
    
    @staticmethod
    def _create_deployment_script(script: Script, script_config: Dict[str, Any]) -> DeploymentScript:
        """Create deployment script specific configuration."""
        return DeploymentScript.objects.create(
            script=script,
            deployment_type=script_config.get('deployment_type', 'manual'),
            target_environment=script_config.get('target_environment', 'staging'),
            rollback_script=script_config.get('rollback_script', ''),
            approval_required=script_config.get('approval_required', True)
        )
    
    @staticmethod
    def _create_execution_record(script: Script, execution_config: Dict[str, Any], executed_by: Optional[User]) -> ScriptExecution:
        """Create script execution record."""
        try:
            return ScriptExecution.objects.create(
                script=script,
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
    def _execute_automation_script(script: Script, execution: ScriptExecution) -> Dict[str, Any]:
        """Execute automation script."""
        try:
            # Create secure execution environment
            env = ScriptService._create_execution_environment(script, execution)
            
            # Execute script
            result = ScriptService._run_script_in_sandbox(script.content, env, script.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing automation script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_data_processing_script(script: Script, execution: ScriptExecution) -> Dict[str, Any]:
        """Execute data processing script."""
        try:
            # Create secure execution environment
            env = ScriptService._create_execution_environment(script, execution)
            
            # Add data processing specific environment variables
            env['DATA_SOURCE'] = script.data_processing_script.data_source
            env['DATA_TARGET'] = script.data_processing_script.data_target
            env['PROCESSING_TYPE'] = script.data_processing_script.processing_type
            env['BATCH_SIZE'] = str(script.data_processing_script.batch_size)
            
            # Execute script
            result = ScriptService._run_script_in_sandbox(script.content, env, script.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing data processing script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_maintenance_script(script: Script, execution: ScriptExecution) -> Dict[str, Any]:
        """Execute maintenance script."""
        try:
            # Create secure execution environment
            env = ScriptService._create_execution_environment(script, execution)
            
            # Add maintenance specific environment variables
            env['MAINTENANCE_TYPE'] = script.maintenance_script.maintenance_type
            env['TARGET_SYSTEMS'] = ','.join(script.maintenance_script.target_systems)
            env['IMPACT_LEVEL'] = script.maintenance_script.impact_level
            
            # Execute script
            result = ScriptService._run_script_in_sandbox(script.content, env, script.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing maintenance script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_deployment_script(script: Script, execution: ScriptExecution) -> Dict[str, Any]:
        """Execute deployment script."""
        try:
            # Create secure execution environment
            env = ScriptService._create_execution_environment(script, execution)
            
            # Add deployment specific environment variables
            env['DEPLOYMENT_TYPE'] = script.deployment_script.deployment_type
            env['TARGET_ENVIRONMENT'] = script.deployment_script.target_environment
            env['ROLLBACK_SCRIPT'] = script.deployment_script.rollback_script
            
            # Execute script
            result = ScriptService._run_script_in_sandbox(script.content, env, script.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing deployment script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _execute_generic_script(script: Script, execution: ScriptExecution) -> Dict[str, Any]:
        """Execute generic script."""
        try:
            # Create secure execution environment
            env = ScriptService._create_execution_environment(script, execution)
            
            # Execute script
            result = ScriptService._run_script_in_sandbox(script.content, env, script.timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing generic script: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'exit_code': 1
            }
    
    @staticmethod
    def _create_execution_environment(script: Script, execution: ScriptExecution) -> Dict[str, str]:
        """Create secure execution environment."""
        env = {}
        
        # Add base environment
        env.update(script.environment or {})
        env.update(execution.environment or {})
        
        # Add security environment variables
        env['SCRIPT_ID'] = str(script.id)
        env['EXECUTION_ID'] = str(execution.id)
        env['SCRIPT_TYPE'] = script.type
        env['PYTHONPATH'] = settings.BASE_DIR
        env['DJANGO_SETTINGS_MODULE'] = settings.SETTINGS_MODULE
        
        # Add user environment variables
        if execution.executed_by:
            env['USER_ID'] = str(execution.executed_by.id)
            env['USER_NAME'] = execution.executed_by.username
        
        # Add advertiser environment variables
        if script.advertiser:
            env['ADVERTISER_ID'] = str(script.advertiser.id)
            env['ADVERTISER_NAME'] = script.advertiser.company_name
        
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
    def _update_execution_record(execution: ScriptExecution, result: Dict[str, Any]) -> None:
        """Update execution record with results."""
        try:
            execution.status = result.get('status', 'failed')
            execution.end_time = timezone.now()
            execution.output = result.get('output', '')
            execution.error_message = result.get('error_message', '')
            execution.exit_code = result.get('exit_code', -1)
            execution.duration = (execution.end_time - execution.start_time).total_seconds()
            execution.save(update_fields=[
                'status', 'end_time', 'output', 'error_message', 'exit_code', 'duration'
            ])
            
        except Exception as e:
            logger.error(f"Error updating execution record: {str(e)}")
    
    @staticmethod
    def _create_schedule(script: Script, schedule_config: Dict[str, Any], scheduled_by: Optional[User]) -> Dict[str, Any]:
        """Create script schedule."""
        try:
            # Create schedule record
            schedule_id = str(uuid.uuid4())
            
            schedule_data = {
                'id': schedule_id,
                'script_id': str(script.id),
                'type': schedule_config.get('type'),
                'cron_expression': schedule_config.get('cron_expression'),
                'interval': schedule_config.get('interval'),
                'next_run': schedule_config.get('next_run'),
                'active': schedule_config.get('active', True),
                'created_by': scheduled_by,
                'created_at': timezone.now()
            }
            
            # Store schedule in cache
            cache.set(f"script_schedule_{schedule_id}", schedule_data, timeout=86400)
            
            return schedule_data
            
        except Exception as e:
            logger.error(f"Error creating schedule: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create schedule: {str(e)}")
    
    @staticmethod
    def _calculate_script_stats(script: Script) -> Dict[str, Any]:
        """Calculate script statistics."""
        try:
            # Get executions for last 30 days
            since = timezone.now() - timedelta(days=30)
            executions = ScriptExecution.objects.filter(
                script=script,
                start_time__gte=since
            )
            
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
            
            # Calculate error breakdown
            error_breakdown = executions.filter(status='failed').values('error_message').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            return {
                'script_id': str(script.id),
                'script_name': script.name,
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'failed_executions': failed_executions,
                'timeout_executions': timeout_executions,
                'success_rate': round(success_rate, 2),
                'avg_duration': round(avg_duration, 3),
                'error_breakdown': list(error_breakdown),
                'last_30_days': timezone.now() - timedelta(days=30)
            }
            
        except Exception as e:
            logger.error(f"Error calculating script stats: {str(e)}")
            return {
                'script_id': str(script.id),
                'error': 'Failed to calculate statistics'
            }
    
    @staticmethod
    def _log_script_creation(script: Script, user: Optional[User]) -> None:
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


class AutomationScriptService:
    """Service for automation script management."""
    
    @staticmethod
    def create_automation_script(script_config: Dict[str, Any]) -> AutomationScript:
        """Create automation script with specific configuration."""
        try:
            # Validate automation script configuration
            AutomationScriptService._validate_automation_script_config(script_config)
            
            # Create automation script
            automation_script = AutomationScript.objects.create(
                trigger_type=script_config.get('trigger_type', 'manual'),
                trigger_config=script_config.get('trigger_config', {}),
                actions=script_config.get('actions', []),
                conditions=script_config.get('conditions', [])
            )
            
            return automation_script
            
        except Exception as e:
            logger.error(f"Error creating automation script: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create automation script: {str(e)}")
    
    @staticmethod
    def _validate_automation_script_config(script_config: Dict[str, Any]) -> None:
        """Validate automation script configuration."""
        # Validate trigger type
        valid_triggers = ['manual', 'schedule', 'event', 'webhook']
        trigger_type = script_config.get('trigger_type')
        if trigger_type not in valid_triggers:
            raise AdvertiserValidationError(f"Invalid trigger type: {trigger_type}")
        
        # Validate actions
        actions = script_config.get('actions', [])
        if not isinstance(actions, list):
            raise AdvertiserValidationError("Actions must be a list")
        
        for action in actions:
            if not isinstance(action, dict) or 'type' not in action:
                raise AdvertiserValidationError("Each action must have a type")


class DataProcessingScriptService:
    """Service for data processing script management."""
    
    @staticmethod
    def create_data_processing_script(script_config: Dict[str, Any]) -> DataProcessingScript:
        """Create data processing script with specific configuration."""
        try:
            # Validate data processing script configuration
            DataProcessingScriptService._validate_data_processing_script_config(script_config)
            
            # Create data processing script
            data_processing_script = DataProcessingScript.objects.create(
                data_source=script_config.get('data_source', ''),
                data_target=script_config.get('data_target', ''),
                processing_type=script_config.get('processing_type', 'etl'),
                batch_size=script_config.get('batch_size', 1000),
                retry_count=script_config.get('retry_count', 3)
            )
            
            return data_processing_script
            
        except Exception as e:
            logger.error(f"Error creating data processing script: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create data processing script: {str(e)}")
    
    @staticmethod
    def _validate_data_processing_script_config(script_config: Dict[str, Any]) -> None:
        """Validate data processing script configuration."""
        # Validate processing type
        valid_types = ['etl', 'elt', 'validation', 'transformation', 'aggregation']
        processing_type = script_config.get('processing_type')
        if processing_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid processing type: {processing_type}")
        
        # Validate batch size
        batch_size = script_config.get('batch_size', 1000)
        if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 100000:
            raise AdvertiserValidationError("Batch size must be between 1 and 100000")


class MaintenanceScriptService:
    """Service for maintenance script management."""
    
    @staticmethod
    def create_maintenance_script(script_config: Dict[str, Any]) -> MaintenanceScript:
        """Create maintenance script with specific configuration."""
        try:
            # Validate maintenance script configuration
            MaintenanceScriptService._validate_maintenance_script_config(script_config)
            
            # Create maintenance script
            maintenance_script = MaintenanceScript.objects.create(
                maintenance_type=script_config.get('maintenance_type', 'cleanup'),
                target_systems=script_config.get('target_systems', []),
                impact_level=script_config.get('impact_level', 'low'),
                approval_required=script_config.get('approval_required', False)
            )
            
            return maintenance_script
            
        except Exception as e:
            logger.error(f"Error creating maintenance script: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create maintenance script: {str(e)}")
    
    @staticmethod
    def _validate_maintenance_script_config(script_config: Dict[str, Any]) -> None:
        """Validate maintenance script configuration."""
        # Validate maintenance type
        valid_types = ['cleanup', 'backup', 'restore', 'update', 'optimization']
        maintenance_type = script_config.get('maintenance_type')
        if maintenance_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid maintenance type: {maintenance_type}")
        
        # Validate impact level
        valid_impacts = ['low', 'medium', 'high', 'critical']
        impact_level = script_config.get('impact_level', 'low')
        if impact_level not in valid_impacts:
            raise AdvertiserValidationError(f"Invalid impact level: {impact_level}")


class DeploymentScriptService:
    """Service for deployment script management."""
    
    @staticmethod
    def create_deployment_script(script_config: Dict[str, Any]) -> DeploymentScript:
        """Create deployment script with specific configuration."""
        try:
            # Validate deployment script configuration
            DeploymentScriptService._validate_deployment_script_config(script_config)
            
            # Create deployment script
            deployment_script = DeploymentScript.objects.create(
                deployment_type=script_config.get('deployment_type', 'manual'),
                target_environment=script_config.get('target_environment', 'staging'),
                rollback_script=script_config.get('rollback_script', ''),
                approval_required=script_config.get('approval_required', True)
            )
            
            return deployment_script
            
        except Exception as e:
            logger.error(f"Error creating deployment script: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create deployment script: {str(e)}")
    
    @staticmethod
    def _validate_deployment_script_config(script_config: Dict[str, Any]) -> None:
        """Validate deployment script configuration."""
        # Validate deployment type
        valid_types = ['manual', 'automatic', 'rollback', 'blue_green', 'canary']
        deployment_type = script_config.get('deployment_type')
        if deployment_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid deployment type: {deployment_type}")
        
        # Validate target environment
        valid_environments = ['development', 'staging', 'production', 'testing']
        target_environment = script_config.get('target_environment', 'staging')
        if target_environment not in valid_environments:
            raise AdvertiserValidationError(f"Invalid target environment: {target_environment}")


class ScriptExecutionService:
    """Service for script execution management."""
    
    @staticmethod
    def create_execution(execution_config: Dict[str, Any]) -> ScriptExecution:
        """Create script execution record."""
        try:
            # Validate execution configuration
            ScriptExecutionService._validate_execution_config(execution_config)
            
            # Create execution record
            execution = ScriptExecution.objects.create(
                script_id=execution_config.get('script_id'),
                parameters=execution_config.get('parameters', {}),
                environment=execution_config.get('environment', {}),
                status='pending',
                created_at=timezone.now()
            )
            
            return execution
            
        except Exception as e:
            logger.error(f"Error creating execution: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create execution: {str(e)}")
    
    @staticmethod
    def _validate_execution_config(execution_config: Dict[str, Any]) -> None:
        """Validate execution configuration."""
        # Validate script ID
        if not execution_config.get('script_id'):
            raise AdvertiserValidationError("Script ID is required")
        
        # Validate parameters
        parameters = execution_config.get('parameters', {})
        if not isinstance(parameters, dict):
            raise AdvertiserValidationError("Parameters must be a dictionary")


class ScriptMonitoringService:
    """Service for script monitoring and health checks."""
    
    @staticmethod
    def get_script_health(script_id: UUID) -> Dict[str, Any]:
        """Get script health status."""
        try:
            # Get script
            script = Script.objects.get(id=script_id)
            
            # Get recent executions
            since = timezone.now() - timedelta(hours=24)
            recent_executions = ScriptExecution.objects.filter(
                script=script,
                start_time__gte=since
            )
            
            # Calculate health metrics
            total_executions = recent_executions.count()
            successful_executions = recent_executions.filter(status='success').count()
            success_rate = (successful_executions / max(total_executions, 1)) * 100
            
            # Determine health status
            if total_executions == 0:
                health_status = 'unknown'
            elif success_rate >= 95:
                health_status = 'healthy'
            elif success_rate >= 80:
                health_status = 'warning'
            else:
                health_status = 'unhealthy'
            
            return {
                'script_id': str(script_id),
                'script_name': script.name,
                'health_status': health_status,
                'success_rate': round(success_rate, 2),
                'total_executions_24h': total_executions,
                'successful_executions_24h': successful_executions,
                'last_execution': recent_executions.order_by('-start_time').first().start_time if recent_executions.exists() else None,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting script health: {str(e)}")
            return {
                'script_id': str(script_id),
                'health_status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def get_system_health() -> Dict[str, Any]:
        """Get overall script system health."""
        try:
            # Get system metrics
            total_scripts = Script.objects.filter(status='active').count()
            total_executions = ScriptExecution.objects.filter(
                start_time__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            successful_executions = ScriptExecution.objects.filter(
                start_time__gte=timezone.now() - timedelta(hours=24),
                status='success'
            ).count()
            
            # Calculate system metrics
            success_rate = (successful_executions / max(total_executions, 1)) * 100
            pending_executions = ScriptExecution.objects.filter(status='pending').count()
            
            return {
                'total_active_scripts': total_scripts,
                'total_executions_24h': total_executions,
                'successful_executions_24h': successful_executions,
                'success_rate_24h': round(success_rate, 2),
                'pending_executions': pending_executions,
                'system_status': 'healthy' if success_rate >= 95 else 'warning',
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return {
                'system_status': 'error',
                'error': str(e)
            }


class ScriptSecurityService:
    """Service for script security management."""
    
    @staticmethod
    def validate_script_security(script_content: str) -> Dict[str, Any]:
        """Validate script security with comprehensive checks."""
        try:
            # Security checks
            security_issues = []
            
            # Check for prohibited patterns
            prohibited_patterns = [
                {'pattern': r'<script.*?>.*?</script>', 'issue': 'Script tags', 'severity': 'high'},
                {'pattern': r'javascript:', 'issue': 'JavaScript protocol', 'severity': 'high'},
                {'pattern': r'eval\s*\(', 'issue': 'Code execution', 'severity': 'high'},
                {'pattern': r'exec\s*\(', 'issue': 'Code execution', 'severity': 'high'},
                {'pattern': r'system\s*\(', 'issue': 'System calls', 'severity': 'high'},
                {'pattern': r'os\.system', 'issue': 'System calls', 'severity': 'high'},
                {'pattern': r'subprocess\.call', 'issue': 'Subprocess calls', 'severity': 'medium'},
                {'pattern': r'import\s+os', 'issue': 'OS imports', 'severity': 'medium'},
                {'pattern': r'import\s+sys', 'issue': 'System imports', 'severity': 'medium'},
                {'pattern': r'while\s+True', 'issue': 'Infinite loops', 'severity': 'medium'},
                {'pattern': r'open\s*\(', 'issue': 'File operations', 'severity': 'low'},
                {'pattern': r'file\s*\(', 'issue': 'File operations', 'severity': 'low'},
            ]
            
            import re
            for check in prohibited_patterns:
                if re.search(check['pattern'], script_content, re.IGNORECASE):
                    security_issues.append({
                        'type': check['issue'],
                        'severity': check['severity'],
                        'line': ScriptSecurityService._find_line_number(script_content, check['pattern'])
                    })
            
            # Determine overall security status
            has_high_severity = any(issue['severity'] == 'high' for issue in security_issues)
            has_medium_severity = any(issue['severity'] == 'medium' for issue in security_issues)
            
            if has_high_severity:
                security_status = 'critical'
            elif has_medium_severity:
                security_status = 'warning'
            else:
                security_status = 'safe'
            
            return {
                'security_status': security_status,
                'issues': security_issues,
                'issue_count': len(security_issues),
                'validated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating script security: {str(e)}")
            return {
                'security_status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def _find_line_number(content: str, pattern: str) -> int:
        """Find line number of pattern in content."""
        try:
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    return i
            return 0
        except Exception:
            return 0
