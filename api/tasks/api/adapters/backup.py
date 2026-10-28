"""
api/adapters/backup.py
Backup adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta
import json
import os
import subprocess

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_backup_status(request):
    """Get current backup status."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get backup status from cache
        backup_status = cache.get(f'backup_status_{tenant_id}', {
            'last_backup': None,
            'status': 'idle',
            'progress': 0,
            'total_files': 0,
            'completed_files': 0,
            'error_count': 0,
            'start_time': None,
            'estimated_completion': None
        })
        
        # Get recent backup history
        from backup.models import BackupHistory
        recent_backups = BackupHistory.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')[:10]
        
        backup_data = {
            'tenant_id': tenant_id,
            'current_status': backup_status,
            'recent_backups': [
                {
                    'id': backup.id,
                    'backup_type': backup.backup_type,
                    'status': backup.status,
                    'file_count': backup.file_count,
                    'total_size': str(backup.total_size),
                    'created_at': backup.created_at.isoformat(),
                    'completed_at': backup.completed_at.isoformat() if backup.completed_at else None,
                    'duration_seconds': backup.duration_seconds,
                    'error_message': backup.error_message,
                    'retention_days': backup.retention_days
                }
                for backup in recent_backups
            ],
            'backup_schedule': _get_backup_schedule(tenant_id),
            'storage_info': _get_backup_storage_info(tenant_id),
            'system_health': _get_backup_system_health()
        }
        
        return Response({
            'success': True,
            'data': backup_data,
            'message': 'Backup status retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error getting backup status: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve backup status',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_backup(request):
    """Create a new backup."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate backup parameters
        backup_type = data.get('backup_type', 'full')  # 'full', 'incremental', 'database', 'files'
        include_sensitive = data.get('include_sensitive', False)
        compression = data.get('compression', 'gzip')
        encryption = data.get('encryption', True)
        
        # Check if backup is already running
        current_status = cache.get(f'backup_status_{tenant_id}', {})
        if current_status.get('status') == 'running':
            return Response({
                'success': False,
                'error': 'Backup already in progress',
                'details': 'Please wait for current backup to complete'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Initialize backup
        backup_id = _initialize_backup(backup_type, user.id, tenant_id)
        
        # Start backup process
        backup_result = _start_backup_process(backup_id, backup_type, {
            'include_sensitive': include_sensitive,
            'compression': compression,
            'encryption': encryption,
            'tenant_id': tenant_id
        })
        
        if backup_result['success']:
            return Response({
                'success': True,
                'data': {
                    'backup_id': backup_id,
                    'backup_type': backup_type,
                    'status': 'started',
                    'estimated_duration': backup_result['estimated_duration'],
                    'file_count_estimate': backup_result['file_count_estimate']
                },
                'message': 'Backup started successfully'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Failed to start backup',
                'details': backup_result.get('error', 'Unknown error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error creating backup: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create backup',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_backup_history(request):
    """Get backup history."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        backup_type = request.GET.get('type')  # 'all', 'full', 'incremental', 'database', 'files'
        status = request.GET.get('status')  # 'all', 'completed', 'failed', 'running'
        
        # Get backup history
        from backup.models import BackupHistory
        queryset = BackupHistory.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if backup_type and backup_type != 'all':
            queryset = queryset.filter(backup_type=backup_type)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        # Paginate
        backups = queryset[offset:offset+limit]
        
        # Serialize backups
        backup_data = []
        for backup in backups:
            backup_data.append({
                'id': backup.id,
                'backup_type': backup.backup_type,
                'status': backup.status,
                'file_count': backup.file_count,
                'total_size': str(backup.total_size),
                'created_at': backup.created_at.isoformat(),
                'completed_at': backup.completed_at.isoformat() if backup.completed_at else None,
                'duration_seconds': backup.duration_seconds,
                'error_message': backup.error_message,
                'created_by': {
                    'id': backup.created_by.id,
                    'username': backup.created_by.username,
                },
                'retention_days': backup.retention_days,
                'encryption_enabled': backup.encryption_enabled,
                'compression_type': backup.compression_type,
                'backup_location': backup.backup_location,
                'checksum': backup.checksum,
                'metadata': backup.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'backups': backup_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(backup_data) == limit
                },
                'filters': {
                    'type': backup_type,
                    'status': status
                },
                'summary': _get_backup_summary(queryset)
            },
            'message': 'Backup history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error getting backup history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve backup history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def restore_backup(request, backup_id):
    """Restore from backup."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get backup
        from backup.models import BackupHistory
        try:
            backup = BackupHistory.objects.get(
                id=backup_id,
                tenant_id=tenant_id,
                status='completed'
            )
        except BackupHistory.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Backup not found',
                'details': f'Backup with ID {backup_id} not found or not completed'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate backup file exists
        if not _backup_file_exists(backup):
            return Response({
                'success': False,
                'error': 'Backup file not found',
                'details': 'Backup file is missing or corrupted'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get restore options
        restore_options = {
            'restore_type': data.get('restore_type', 'full'),  # 'full', 'database', 'files', 'selective'
            'confirm_restore': data.get('confirm_restore', False),
            'create_backup_before': data.get('create_backup_before', True),
            'restore_sensitive': data.get('restore_sensitive', False)
        }
        
        if not restore_options['confirm_restore']:
            return Response({
                'success': False,
                'error': 'Restore confirmation required',
                'details': 'Please confirm restore operation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create backup before restore if requested
        if restore_options['create_backup_before']:
            pre_restore_backup = _initialize_backup('pre_restore', user.id, tenant_id)
            _start_backup_process(pre_restore_backup, 'pre_restore', {
                'tenant_id': tenant_id,
                'reason': 'pre_restore_backup'
            })
        
        # Start restore process
        restore_id = _start_restore_process(backup, restore_options, user.id, tenant_id)
        
        return Response({
            'success': True,
            'data': {
                'restore_id': restore_id,
                'backup_id': backup_id,
                'restore_type': restore_options['restore_type'],
                'status': 'started',
                'estimated_duration': _estimate_restore_duration(backup, restore_options),
                'pre_restore_backup': pre_restore_backup if restore_options['create_backup_before'] else None
            },
            'message': 'Restore started successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error restoring backup: {e}")
        return Response({
            'success': False,
            'error': 'Failed to restore backup',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def delete_backup(request, backup_id):
    """Delete a backup."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get backup
        from backup.models import BackupHistory
        try:
            backup = BackupHistory.objects.get(
                id=backup_id,
                tenant_id=tenant_id
            )
        except BackupHistory.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Backup not found',
                'details': f'Backup with ID {backup_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Delete backup file
        if _backup_file_exists(backup):
            _delete_backup_file(backup)
        
        # Delete backup record
        backup.delete()
        
        # Log backup deletion
        _log_backup_action('delete', backup_id, user.id, tenant_id)
        
        return Response({
            'success': True,
            'data': {
                'backup_id': backup_id,
                'deleted_at': timezone.now().isoformat(),
                'deleted_by': {
                    'id': user.id,
                    'username': user.username
                }
            },
            'message': 'Backup deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error deleting backup: {e}")
        return Response({
            'success': False,
            'error': 'Failed to delete backup',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_backup_settings(request):
    """Get backup configuration settings."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get backup settings from cache
        settings = cache.get(f'backup_settings_{tenant_id}', {
            'backup_schedule': {
                'enabled': True,
                'frequency': 'daily',  # 'daily', 'weekly', 'monthly'
                'time': '02:00',
                'timezone': 'UTC'
            },
            'retention_policy': {
                'daily_backups': 7,
                'weekly_backups': 4,
                'monthly_backups': 12,
                'auto_cleanup': True
            },
            'storage_settings': {
                'primary_location': '/backups',
                'secondary_location': '/backups/secondary',
                'compression': 'gzip',
                'encryption': True,
                'encryption_key_rotation_days': 90
            },
            'backup_types': {
                'full_backup': {
                    'enabled': True,
                    'includes': ['database', 'files', 'media'],
                    'exclude_sensitive': False
                },
                'incremental_backup': {
                    'enabled': True,
                    'frequency': 'every_6_hours',
                    'max_incremental_size': '1GB'
                },
                'database_backup': {
                    'enabled': True,
                    'frequency': 'daily',
                    'include_tables': ['all'],
                    'exclude_tables': ['sessions', 'cache']
                },
                'files_backup': {
                    'enabled': True,
                    'directories': ['/media', '/static', '/uploads'],
                    'exclude_patterns': ['*.tmp', '*.log', '*.cache']
                }
            },
            'notification_settings': {
                'success_notifications': True,
                'failure_notifications': True,
                'recipients': ['admin@example.com'],
                'notification_channels': ['email', 'slack']
            }
        })
        
        return Response({
            'success': True,
            'data': {
                'tenant_id': tenant_id,
                'settings': settings,
                'storage_usage': _get_storage_usage(tenant_id),
                'next_scheduled_backup': _get_next_scheduled_backup(settings['backup_schedule'])
            },
            'message': 'Backup settings retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error getting backup settings: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve backup settings',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_backup_schedule(tenant_id) -> Dict:
    """Get backup schedule for tenant."""
    return cache.get(f'backup_schedule_{tenant_id}', {
        'enabled': True,
        'frequency': 'daily',
        'time': '02:00',
        'timezone': 'UTC',
        'last_run': cache.get(f'last_backup_run_{tenant_id}'),
        'next_run': _calculate_next_backup_time(tenant_id)
    })


def _get_backup_storage_info(tenant_id) -> Dict:
    """Get backup storage information."""
    return {
        'primary_location': f'/backups/tenant_{tenant_id}',
        'secondary_location': f'/backups/secondary/tenant_{tenant_id}',
        'total_space': '100GB',
        'used_space': str(_calculate_used_space(tenant_id)),
        'available_space': str(_calculate_available_space(tenant_id)),
        'compression_ratio': 0.65,
        'encryption_enabled': True
    }


def _get_backup_system_health() -> Dict:
    """Get backup system health status."""
    return {
        'backup_service_status': 'healthy',
        'storage_status': 'healthy',
        'network_status': 'healthy',
        'database_status': 'healthy',
        'last_health_check': timezone.now().isoformat(),
        'service_uptime': '99.9%',
        'error_rate': '0.1%'
    }


def _initialize_backup(backup_type, user_id, tenant_id) -> str:
    """Initialize backup process."""
    import uuid
    backup_id = str(uuid.uuid4())
    
    # Create backup record
    from backup.models import BackupHistory
    backup = BackupHistory.objects.create(
        backup_type=backup_type,
        status='initializing',
        created_by_id=user_id,
        tenant_id=tenant_id,
        created_at=timezone.now()
    )
    
    # Update cache with backup status
    cache.set(f'backup_status_{tenant_id}', {
        'backup_id': backup_id,
        'status': 'initializing',
        'progress': 0,
        'total_files': 0,
        'completed_files': 0,
        'error_count': 0,
        'start_time': timezone.now().isoformat()
    }, timeout=86400)
    
    return backup_id


def _start_backup_process(backup_id, backup_type, options) -> Dict:
    """Start backup process."""
    try:
        # Update backup status
        tenant_id = options.get('tenant_id')
        cache.set(f'backup_status_{tenant_id}', {
            'backup_id': backup_id,
            'status': 'running',
            'progress': 0,
            'total_files': 0,
            'completed_files': 0,
            'error_count': 0,
            'start_time': timezone.now().isoformat()
        }, timeout=86400)
        
        # Start backup based on type
        if backup_type == 'full':
            return _perform_full_backup(backup_id, options)
        elif backup_type == 'incremental':
            return _perform_incremental_backup(backup_id, options)
        elif backup_type == 'database':
            return _perform_database_backup(backup_id, options)
        elif backup_type == 'files':
            return _perform_files_backup(backup_id, options)
        else:
            return {
                'success': False,
                'error': f'Unsupported backup type: {backup_type}'
            }
            
    except Exception as e:
        logger.error(f"[BackupAdapter] Error starting backup process: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def _perform_full_backup(backup_id, options) -> Dict:
    """Perform full backup."""
    try:
        # Simulate full backup process
        tenant_id = options.get('tenant_id')
        
        # Update backup record
        from backup.models import BackupHistory
        backup = BackupHistory.objects.get(id=backup_id)
        backup.status = 'running'
        backup.started_at = timezone.now()
        backup.save()
        
        # Simulate backup process
        file_count = 0
        total_size = 0
        
        # Backup database
        db_result = _backup_database(tenant_id)
        if db_result['success']:
            file_count += db_result['file_count']
            total_size += db_result['size']
        
        # Backup files
        files_result = _backup_files(tenant_id, options)
        if files_result['success']:
            file_count += files_result['file_count']
            total_size += files_result['size']
        
        # Complete backup
        backup.status = 'completed'
        backup.completed_at = timezone.now()
        backup.file_count = file_count
        backup.total_size = total_size
        backup.duration_seconds = (timezone.now() - backup.started_at).total_seconds()
        backup.checksum = _generate_backup_checksum(backup_id)
        backup.save()
        
        # Update cache
        cache.set(f'backup_status_{tenant_id}', {
            'backup_id': backup_id,
            'status': 'completed',
            'progress': 100,
            'total_files': file_count,
            'completed_files': file_count,
            'error_count': 0,
            'start_time': backup.started_at.isoformat()
        }, timeout=86400)
        
        return {
            'success': True,
            'estimated_duration': backup.duration_seconds
        }
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error performing full backup: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def _backup_database(tenant_id) -> Dict:
    """Backup database."""
    try:
        # Simulate database backup
        # In production, this would use pg_dump, mysqldump, etc.
        
        return {
            'success': True,
            'file_count': 1,
            'size': 1024 * 1024 * 100  # 100MB
        }
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error backing up database: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def _backup_files(tenant_id, options) -> Dict:
    """Backup files."""
    try:
        # Simulate files backup
        # In production, this would backup media, static files, etc.
        
        return {
            'success': True,
            'file_count': 50,
            'size': 1024 * 1024 * 500  # 500MB
        }
        
    except Exception as e:
        logger.error(f"[BackupAdapter] Error backing up files: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def _generate_backup_checksum(backup_id) -> str:
    """Generate backup checksum."""
    import hashlib
    return hashlib.sha256(f"backup_{backup_id}_{timezone.now().isoformat()}".encode()).hexdigest()


def _backup_file_exists(backup) -> bool:
    """Check if backup file exists."""
    # Simulate file existence check
    return True


def _delete_backup_file(backup):
    """Delete backup file."""
    # Simulate file deletion
    pass


def _log_backup_action(action, backup_id, user_id, tenant_id):
    """Log backup action."""
    try:
        from backup.models import BackupActionLog
        BackupActionLog.objects.create(
            action=action,
            backup_id=backup_id,
            user_id=user_id,
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
    except Exception:
        pass


def _get_backup_summary(queryset) -> Dict:
    """Get backup summary statistics."""
    try:
        total_backups = queryset.count()
        completed_backups = queryset.filter(status='completed').count()
        failed_backups = queryset.filter(status='failed').count()
        
        # Calculate total size
        total_size = queryset.aggregate(
            total_size=Sum(F('total_size'))
        )['total_size'] or Decimal('0')
        
        # Calculate average duration
        avg_duration = queryset.filter(
            status='completed',
            duration_seconds__isnull=False
        ).aggregate(
            avg_duration=Avg(F('duration_seconds'))
        )['avg_duration'] or 0
        
        return {
            'total_backups': total_backups,
            'completed_backups': completed_backups,
            'failed_backups': failed_backups,
            'success_rate': round((completed_backups / max(total_backups, 1)) * 100, 2),
            'total_size': str(total_size),
            'average_duration_seconds': round(avg_duration, 2),
            'last_backup': queryset.order_by('-created_at').first().created_at.isoformat() if queryset.exists() else None
        }
        
    except Exception:
        return {}


def _calculate_used_space(tenant_id) -> str:
    """Calculate used storage space."""
    # Simulate space calculation
    return str(Decimal('50') * Decimal('1024') * Decimal('1024') * Decimal('1024'))  # 50GB


def _calculate_available_space(tenant_id) -> str:
    """Calculate available storage space."""
    # Simulate space calculation
    return str(Decimal('50') * Decimal('1024') * Decimal('1024') * Decimal('1024'))  # 50GB


def _calculate_next_backup_time(tenant_id) -> str:
    """Calculate next backup time."""
    schedule = cache.get(f'backup_schedule_{tenant_id}', {})
    if schedule.get('enabled'):
        # Calculate next backup time based on schedule
        return timezone.now().isoformat()
    return None


def _get_next_scheduled_backup(schedule) -> str:
    """Get next scheduled backup time."""
    if schedule.get('enabled'):
        # Calculate next backup time
        return timezone.now().isoformat()
    return None


def _estimate_restore_duration(backup, options) -> int:
    """Estimate restore duration."""
    # Simulate duration estimation
    base_duration = backup.duration_seconds or 3600  # 1 hour default
    
    if options.get('restore_type') == 'full':
        return base_duration * 1.5
    elif options.get('restore_type') == 'database':
        return base_duration * 0.8
    elif options.get('restore_type') == 'files':
        return base_duration * 1.2
    
    return base_duration


def _start_restore_process(backup, options, user_id, tenant_id) -> str:
    """Start restore process."""
    import uuid
    restore_id = str(uuid.uuid4())
    
    # Create restore record
    from backup.models import RestoreHistory
    restore = RestoreHistory.objects.create(
        backup_id=backup.id,
        restore_type=options.get('restore_type'),
        status='running',
        created_by_id=user_id,
        tenant_id=tenant_id,
        created_at=timezone.now()
    )
    
    # Simulate restore process
    # In production, this would actually restore the backup
    
    return restore_id


def _get_storage_usage(tenant_id) -> Dict:
    """Get storage usage information."""
    return {
        'used_space': str(_calculate_used_space(tenant_id)),
        'available_space': str(_calculate_available_space(tenant_id)),
        'total_space': str(Decimal('100') * Decimal('1024') * Decimal('1024') * Decimal('1024')),  # 100GB
        'usage_percentage': 50.0
    }
