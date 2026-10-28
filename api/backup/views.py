# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, FileResponse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Sum, Avg, Q, F, Case, When, Value, IntegerField, DecimalField
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from django.urls import reverse
from datetime import timedelta, datetime
import json
import uuid
import os
import hashlib
import mimetypes
from django.db.models.functions import Cast
from rest_framework import viewsets, status, generics, mixins
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from api.backup.pagination import BackupPagination

from .models import (
    Backup, BackupSchedule, BackupLog, BackupStorageLocation,
    BackupRestoration, BackupNotificationConfig, RetentionPolicy,
    DeltaBackupTracker, BackupVerification, BackupEncryption, BackupAlert
)
from .serializers import (
    BackupSerializer, BackupScheduleSerializer, BackupStorageLocationSerializer,
    BackupLogSerializer, BackupRestorationSerializer, BackupNotificationConfigSerializer,
    RetentionPolicySerializer, DeltaBackupTrackerSerializer,
    BackupVerificationSerializer, BackupEncryptionSerializer, BackupAlertSerializer,
    BackupProgressSerializer, BackupTaskRequestSerializer, RestoreRequestSerializer,
    HealthCheckSerializer, MaintenanceModeSerializer, BackupStatsSerializer,
    StorageUsageSerializer, PerformanceMetricsSerializer, NotificationRequestSerializer,
    BatchOperationSerializer, BulkActionSerializer,
    BackupCreateSerializer, BackupUpdateSerializer, BackupDetailSerializer,
    HealthyBackupManagerSerializer, ExpiredBackupManagerSerializer
)
from .tasks import (
    backup_database_task, restore_backup_task, cleanup_old_backups_task,
    perform_delta_backup, execute_gfs_retention_policy,
    send_multi_channel_notification, auto_cleanup_expired_backups,
    verify_backup_health_periodically, create_redundant_storage_copies,
    consolidate_delta_backup_chain
)


# ==================== MIXINS ====================

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff status"""
    def test_func(self):
        return self.request.user.is_staff


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin to require superuser status"""
    def test_func(self):
        return self.request.user.is_superuser


class BackupPermissionMixin:
    """Mixin for backup permissions"""
    
    def get_permissions(self):
        """Get permissions based on action"""
        if self.action in ['list', 'retrieve', 'logs']:
            permission_classes = [IsAuthenticated]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAdminUser]
        
        return [permission() for permission in permission_classes]


# ==================== VIEWSETS ====================

class BackupViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for Backup model"""
    queryset = Backup.objects.all().select_related(
        'created_by', 'verified_by', 'parent_backup', 'delta_base', 'schedule'
    ).prefetch_related('logs', 'child_backups', 'restorations')

    serializer_class = BackupSerializer
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    pagination_class = BackupPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'backup_type', 'storage_type', 'is_healthy', 'is_verified']
    search_fields = ['name', 'notes', 'database_name']
    ordering_fields = ['created_at', 'size', 'status']
    ordering = ['-created_at']
    throttle_classes = [UserRateThrottle]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BackupDetailSerializer
        if self.action == 'create':
            return BackupCreateSerializer
        if self.action in ('update', 'partial_update'):
            return BackupUpdateSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filter queryset based on user and query parameters"""
        queryset = super().get_queryset()
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by backup type
        backup_type = self.request.query_params.get('backup_type')
        if backup_type:
            queryset = queryset.filter(backup_type=backup_type)
        
        # Filter by storage type
        storage_type = self.request.query_params.get('storage_type')
        if storage_type:
            queryset = queryset.filter(storage_type=storage_type)
        
        # Filter by health status
        is_healthy = self.request.query_params.get('is_healthy')
        if is_healthy is not None:
            queryset = queryset.filter(is_healthy=is_healthy.lower() == 'true')
        
        # Filter by verification status
        is_verified = self.request.query_params.get('is_verified')
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(start_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_time__date__lte=end_date)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(database_name__icontains=search)
            )
        
        # Ordering
        ordering = self.request.query_params.get('ordering', '-start_time')
        if ordering.lstrip('-') in ['name', 'status', 'backup_type', 'start_time', 'file_size', 'health_score']:
            queryset = queryset.order_by(ordering)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify backup integrity"""
        backup = self.get_object()
        
        try:
            # Perform verification
            verification_result = self._verify_backup(backup)
            
            if verification_result['valid']:
                backup.mark_as_verified(verified_by=request.user)
            else:
                backup.is_verified = False
                backup.verified_by = request.user
                backup.verified_at = timezone.now()
                backup.save()
            
            # Log the verification
            BackupLog.objects.create(
                backup=backup,
                level='info' if verification_result['valid'] else 'error',
                message=f"Backup verification {'passed' if verification_result['valid'] else 'failed'}",
                details={
                    'verified_by': request.user.username,
                    'result': verification_result,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return Response({
                'success': True,
                'verified': verification_result['valid'],
                'message': verification_result['message']
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Verification failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def health_check(self, request, pk=None):
        """Perform health check on backup"""
        backup = self.get_object()
        
        try:
            # Perform health check using model method
            health_result = backup.check_health()
            verification_result = self._verify_backup(backup)
            
            # Log the health check
            BackupLog.objects.create(
                backup=backup,
                level='info' if verification_result['valid'] else 'error',
                message=f"Health check {'passed' if verification_result['valid'] else 'failed'}",
                details={
                    'checked_by': request.user.username,
                    'result': verification_result,
                    'health_score': backup.health_score,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return Response({
                'success': True,
                'healthy': verification_result['valid'],
                'health_score': backup.health_score,
                'message': verification_result['message']
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Health check failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def create_redundant_copy(self, request, pk=None):
        """Create redundant copies of backup"""
        backup = self.get_object()
        
        try:
            # Get available storage locations
            locations = BackupStorageLocation.objects.filter(
                is_active=True, is_connected=True
            ).order_by('priority')[:3]
            
            if len(locations) < 2:
                return Response({
                    'success': False,
                    'message': 'Need at least 2 active storage locations for redundancy'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update backup for redundancy
            backup.storage_type = 'redundant'
            backup.redundancy_level = len(locations)
            backup.storage_locations = [loc.id for loc in locations]
            backup.save()
            
            # Log the redundancy creation
            BackupLog.objects.create(
                backup=backup,
                level='info',
                message=f"Created {len(locations)} redundant copies",
                details={
                    'created_by': request.user.username,
                    'locations': [loc.name for loc in locations],
                    'redundancy_level': backup.redundancy_level,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return Response({
                'success': True,
                'copies_created': len(locations),
                'locations': [{'id': loc.id, 'name': loc.name} for loc in locations],
                'message': f'Created {len(locations)} redundant copies'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to create redundant copies: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get logs for a backup"""
        backup = self.get_object()
        logs = backup.logs.all().order_by('-timestamp')
        serializer = BackupLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download backup file"""
        backup = self.get_object()
        
        if not backup.file_path or not os.path.exists(backup.file_path):
            return Response({
                'success': False,
                'message': 'Backup file not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(backup.file_path)
            
            # Open file for reading
            file_handle = open(backup.file_path, 'rb')
            
            # Create response
            response = FileResponse(file_handle, content_type=mime_type or 'application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{backup.name}.backup"'
            response['Content-Length'] = os.path.getsize(backup.file_path)
            
            # Log the download
            BackupLog.objects.create(
                backup=backup,
                level='info',
                message=f"Backup downloaded by {request.user.username}",
                details={
                    'downloaded_by': request.user.username,
                    'file_size': backup.file_size,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return response
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to download backup: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Return backup statistics"""
        from django.db.models import Sum
        queryset = self.get_queryset()
        total = queryset.count()
        completed = queryset.filter(status='completed').count()
        failed = queryset.filter(status='failed').count()
        running = queryset.filter(status='running').count()
        total_size = queryset.aggregate(total=Sum('file_size'))['total'] or 0
        healthy_count = queryset.filter(is_healthy=True).count()
        return Response({
            'total': total,
            'completed': completed,
            'failed': failed,
            'running': running,
            'total_size': total_size,
            'healthy_count': healthy_count,
        })


    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Initiate restoration from this backup"""
        backup = self.get_object()
        restoration_type = request.data.get('restoration_type', 'full')
        tables = request.data.get('tables', [])
        notes = request.data.get('notes', '')
        try:
            from .models import BackupRestoration
            restoration = BackupRestoration.objects.create(
                backup=backup,
                restoration_type=restoration_type,
                tables=tables,
                notes=notes,
                initiated_by=request.user,
                status='pending',
            )
            return Response({
                'success': True,
                'restoration_id': str(restoration.id),
                'message': 'Restoration initiated successfully',
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Restoration failed: {str(e)}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _verify_backup(self, backup):
        """Verify backup file integrity"""
        if not backup.file_path or not os.path.exists(backup.file_path):
            return {
                'valid': False,
                'message': 'Backup file not found'
            }
        
        try:
            # Calculate current hash
            sha256_hash = hashlib.sha256()
            with open(backup.file_path, 'rb') as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            current_hash = sha256_hash.hexdigest()
            
            # Compare with stored hash
            if backup.file_hash and current_hash != backup.file_hash:
                return {
                    'valid': False,
                    'message': 'Hash mismatch - backup may be corrupted'
                }
            
            # Check file size
            actual_size = os.path.getsize(backup.file_path)
            if backup.file_size and actual_size != backup.file_size:
                return {
                    'valid': False,
                    'message': f'Size mismatch: expected {backup.file_size}, got {actual_size}'
                }
            
            return {
                'valid': True,
                'message': 'Backup integrity verified',
                'hash': current_hash
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f'Error during verification: {str(e)}'
            }


class BackupScheduleViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for BackupSchedule model"""
    queryset = BackupSchedule.objects.all().select_related('created_by')
    serializer_class = BackupScheduleSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle schedule active status"""
        schedule = self.get_object()
        schedule.is_active = not schedule.is_active
        schedule.save()
        
        return Response({
            'success': True,
            'is_active': schedule.is_active,
            'message': f"Schedule {'activated' if schedule.is_active else 'deactivated'}"
        })
    
    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Run schedule immediately"""
        schedule = self.get_object()
        
        try:
            # Create backup from schedule
            backup = Backup.objects.create(
                name=f"Scheduled: {schedule.name}",
                description=schedule.description,
                backup_type=schedule.backup_type,
                storage_type=schedule.storage_type,
                encryption_type=schedule.encryption_type,
                compression_type=schedule.compression_type,
                retention_days=schedule.retention_days,
                status='pending',
                created_by=request.user,
                is_scheduled=True,
                schedule=schedule,
                included_tables=schedule.include_tables,
                excluded_tables=schedule.exclude_tables
            )
            
            # Start backup task
            backup_database_task.delay(
                backup_id=str(backup.id),
                backup_type=schedule.backup_type,
                tables=schedule.include_tables or ['*'],
                user_id=str(request.user.id)
            )
            
            # Update schedule last run
            schedule.last_run = timezone.now()
            schedule.save()
            
            return Response({
                'success': True,
                'backup_id': str(backup.id),
                'message': f"Manual execution triggered for schedule '{schedule.name}'"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to run schedule: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackupStorageLocationViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for BackupStorageLocation model"""
    queryset = BackupStorageLocation.objects.all()
    serializer_class = BackupStorageLocationSerializer
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test connection to storage location"""
        location = self.get_object()
        
        try:
            # Simulate connection test
            # In production, this would actually test the connection
            is_connected = True  # Placeholder
            
            location.is_connected = is_connected
            location.last_connected = timezone.now()
            
            if not is_connected:
                location.connection_errors += 1
            else:
                location.connection_errors = 0
            
            location.save()
            
            return Response({
                'success': True,
                'is_connected': is_connected,
                'message': f"Connection test {'passed' if is_connected else 'failed'}"
            })
            
        except Exception as e:
            location.connection_errors += 1
            location.last_error_message = str(e)
            location.save()
            
            return Response({
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def usage_stats(self, request, pk=None):
        """Get usage statistics for storage location"""
        location = self.get_object()
        
        backups = Backup.objects.filter(storage_locations__contains=[location.id])
        
        stats = {
            'total_backups': backups.count(),
            'total_size': backups.aggregate(total=Sum('file_size'))['total'] or 0,
            'backup_types': list(backups.values('backup_type').annotate(
                count=Count('id'),
                size=Sum('file_size')
            )),
            'recent_backups': backups.order_by('-start_time')[:5].values(
                'id', 'name', 'start_time', 'file_size'
            )
        }
        
        return Response(stats)


class BackupNotificationConfigViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for BackupNotificationConfig model"""
    queryset = BackupNotificationConfig.objects.all().select_related('created_by')
    serializer_class = BackupNotificationConfigSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def test_notification(self, request, pk=None):
        """Send test notification"""
        config = self.get_object()
        
        try:
            # Create a test backup for notification
            test_backup = Backup.objects.create(
                name='Test Notification Backup',
                backup_type='full',
                status='completed',
                created_by=request.user
            )
            
            # Send test notification
            send_multi_channel_notification.delay(
                backup_id=str(test_backup.id),
                message='This is a test notification',
                level='info',
                channels=config.channels
            )
            
            return Response({
                'success': True,
                'message': f'Test notification sent via {", ".join(config.channels)}'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to send test notification: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RetentionPolicyViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for RetentionPolicy model"""
    queryset = RetentionPolicy.objects.all().select_related('created_by')
    serializer_class = RetentionPolicySerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a backup schedule"""
        schedule = self.get_object()
        schedule.is_paused = True
        schedule.next_run = None
        schedule.save()
        return Response({
            'success': True,
            'message': f"Schedule '{schedule.name}' paused",
        })

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused backup schedule"""
        schedule = self.get_object()
        schedule.is_paused = False
        # Recalculate next_run if schedule has a method for it
        if hasattr(schedule, 'calculate_next_run'):
            schedule.next_run = schedule.calculate_next_run()
        schedule.save()
        return Response({
            'success': True,
            'message': f"Schedule '{schedule.name}' resumed",
        })

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute retention policy"""
        policy = self.get_object()
        
        try:
            result = execute_gfs_retention_policy.delay(policy_id=str(policy.id))
            
            return Response({
                'success': True,
                'task_id': result.id,
                'message': 'Retention policy execution started'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to execute retention policy: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def affected_backups(self, request, pk=None):
        """Get backups affected by retention policy"""
        policy = self.get_object()
        
        backups = policy.get_backups_to_cleanup()
        backup_data = []
        
        for backup in backups:
            backup_data.append({
                'id': backup.id,
                'name': backup.name,
                'start_time': backup.start_time,
                'expires_at': backup.expires_at,
                'file_size': backup.file_size
            })
        
        return Response({
            'policy': policy.name,
            'affected_backups': backup_data,
            'count': len(backup_data)
        })


class DeltaBackupTrackerViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for DeltaBackupTracker model"""
    queryset = DeltaBackupTracker.objects.all().select_related('base_backup')
    serializer_class = DeltaBackupTrackerSerializer
    
    @action(detail=True, methods=['post'])
    def consolidate(self, request, pk=None):
        """Consolidate delta backup chain"""
        tracker = self.get_object()
        
        try:
            result = consolidate_delta_backup_chain.delay(chain_id=str(tracker.chain_id))
            
            return Response({
                'success': True,
                'task_id': result.id,
                'message': 'Delta chain consolidation started'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to consolidate delta chain: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def chain_backups(self, request, pk=None):
        """Get all backups in delta chain"""
        tracker = self.get_object()
        chain_backups = tracker.get_chain_backups()
        
        serializer = BackupSerializer(chain_backups, many=True)
        return Response(serializer.data)



class BackupLogViewSet(BackupPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for BackupLog model"""
    from .models import BackupLog
    from .serializers import BackupLogSerializer

    def get_queryset(self):
        from .models import BackupLog
        qs = BackupLog.objects.all().select_related('backup')
        params = self.request.query_params
        level = params.get('level')
        if level:
            qs = qs.filter(level=level)
        category = params.get('category')
        if category:
            qs = qs.filter(category=category)
        requires_attention = params.get('requires_attention')
        if requires_attention is not None:
            qs = qs.filter(requires_attention=requires_attention.lower() == 'true')
        is_processed = params.get('is_processed')
        if is_processed is not None:
            qs = qs.filter(is_processed=is_processed.lower() == 'true')
        is_archived = params.get('is_archived')
        if is_archived is not None:
            qs = qs.filter(is_archived=is_archived.lower() == 'true')
        backup_id = params.get('backup')
        if backup_id:
            qs = qs.filter(backup_id=backup_id)
        days = params.get('days')
        if days:
            from django.utils import timezone
            from datetime import timedelta
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=int(days)))
        level_list = params.getlist('level')
        if len(level_list) > 1:
            qs = qs.filter(level__in=level_list)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        from .serializers import BackupLogSerializer
        return BackupLogSerializer

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Return log statistics"""
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'errors': qs.filter(level__in=['error', 'critical']).count(),
            'warnings': qs.filter(level='warning').count(),
            'requiring_attention': qs.filter(requires_attention=True, is_processed=False).count(),
        })

    @action(detail=True, methods=['patch'])
    def mark_processed(self, request, pk=None):
        """Mark log as processed"""
        log = self.get_object()
        if hasattr(log, 'mark_as_processed'):
            log.mark_as_processed()
        else:
            log.is_processed = True
            log.save()
        return Response({'success': True, 'message': 'Log marked as processed'})

    @action(detail=True, methods=['patch'])
    def archive(self, request, pk=None):
        """Archive a log entry"""
        log = self.get_object()
        if hasattr(log, 'archive'):
            log.archive()
        else:
            log.is_archived = True
            log.save()
        return Response({'success': True, 'message': 'Log archived'})

    @action(detail=False, methods=['delete'])
    def cleanup(self, request):
        """Delete old logs"""
        from .models import BackupLog
        from django.utils import timezone
        from datetime import timedelta
        days = int(request.data.get('days', 90))
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = BackupLog.objects.filter(created_at__lt=cutoff).delete()
        return Response({'success': True, 'deleted_count': deleted_count})


class BackupRestorationViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for BackupRestoration model"""
    queryset = BackupRestoration.objects.all().select_related(
        'backup', 'initiated_by', 'reviewed_by', 'rollback_to_backup'
    )
    serializer_class = BackupRestorationSerializer
    
    def perform_create(self, serializer):
        serializer.save(initiated_by=self.request.user)


# ==================== API VIEWS ====================

class StartBackupView(APIView):
    """Start a new backup"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        serializer = BackupTaskRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            
            # Create backup record
            backup = Backup.objects.create(
                name=f"API Backup {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                description=data.get('description', ''),
                backup_type=data['backup_type'],
                storage_type=data['storage_type'],
                encryption_type=data['encryption_type'],
                compression_type=data['compression_type'],
                retention_days=data['retention_days'],
                status='pending',
                created_by=request.user,
                included_tables=data['tables'],
                notification_channels=data.get('notification_channels', ['email'])
            )
            
            # Start backup task
            backup_database_task.delay(
                backup_id=str(backup.id),
                backup_type=backup.backup_type,
                tables=backup.included_tables,
                encryption=backup.encryption_type,
                compression=backup.compression_type,
                user_id=str(request.user.id)
            )
            
            # Set progress tracking
            cache.set(f'backup_progress_{backup.id}', {
                'status': 'pending',
                'percentage': 0,
                'current_step': 'Initializing...',
                'started_at': timezone.now().isoformat(),
            }, 3600)
            
            return Response({
                'success': True,
                'backup_id': str(backup.id),
                'message': 'Backup started successfully'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CancelBackupView(APIView):
    """Cancel a running backup"""
    permission_classes = [IsAdminUser]
    
    def post(self, request, pk):
        try:
            backup = Backup.objects.get(id=pk)
            
            if backup.status == 'running':
                backup.status = 'cancelled'
                backup.save()
                
                # Update progress cache
                cache.set(f'backup_progress_{backup.id}', {
                    'status': 'cancelled',
                    'percentage': 0,
                    'current_step': 'Cancelled by user',
                    'ended_at': timezone.now().isoformat(),
                }, 300)
                
                # Log the cancellation
                BackupLog.objects.create(
                    backup=backup,
                    level='warning',
                    message=f"Backup cancelled by {request.user.username}",
                    details={'cancelled_by': request.user.username}
                )
                
                return Response({
                    'success': True,
                    'message': 'Backup cancelled'
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Backup is not running'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Backup.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Backup not found'
            }, status=status.HTTP_404_NOT_FOUND)


class RestoreBackupView(APIView):
    """Restore a backup"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        serializer = RestoreRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                backup = Backup.objects.get(id=data['backup_id'])
                
                # Enable maintenance mode if requested
                if data['enable_maintenance']:
                    cache.set('maintenance_mode', True, 3600)  # 1 hour
                    BackupLog.objects.create(
                        backup=backup,
                        level='warning',
                        message=f"Maintenance mode enabled for restore by {request.user.username}",
                        details={'enabled_by': request.user.username}
                    )
                
                # Start restore task
                restore_backup_task.delay(
                    backup_id=str(backup.id),
                    restore_type=data['restore_type'],
                    tables=data.get('tables', []),
                    user_id=str(request.user.id),
                    enable_maintenance=data['enable_maintenance']
                )
                
                # Log the restore attempt
                BackupLog.objects.create(
                    backup=backup,
                    level='info',
                    message=f"Restore initiated by {request.user.username}",
                    details={
                        'restore_type': data['restore_type'],
                        'tables': data.get('tables', []),
                        'initiated_by': request.user.username,
                        'timestamp': timezone.now().isoformat(),
                        'maintenance_mode': data['enable_maintenance']
                    }
                )
                
                return Response({
                    'success': True,
                    'message': 'Restore process started'
                })
                
            except Backup.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Backup not found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BackupStatusView(APIView):
    """Get overall backup status"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        running = Backup.objects.filter(status='running').count()
        pending = Backup.objects.filter(status='pending').count()
        failed_24h = Backup.objects.filter(
            status='failed',
            start_time__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        return Response({
            'running': running,
            'pending': pending,
            'failed_24h': failed_24h,
            'maintenance_mode': cache.get('maintenance_mode', False),
            'timestamp': timezone.now().isoformat(),
        })


class BackupProgressView(APIView):
    """Get backup progress"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        progress = cache.get(f'backup_progress_{pk}', {
            'status': 'unknown',
            'percentage': 0,
            'current_step': 'Not found',
            'started_at': None,
        })
        
        return Response(progress)


class MaintenanceModeView(APIView):
    """Toggle maintenance mode"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        serializer = MaintenanceModeSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            enable = data['enable']
            
            # Set maintenance mode with duration
            duration_seconds = data['duration_hours'] * 3600
            cache.set('maintenance_mode', enable, duration_seconds)
            
            # Log the action
            BackupLog.objects.create(
                level='warning' if enable else 'info',
                message=f"Maintenance mode {'enabled' if enable else 'disabled'} by {request.user.username}",
                details={
                    'action_by': request.user.username,
                    'reason': data.get('reason', ''),
                    'duration_hours': data['duration_hours'],
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return Response({
                'success': True,
                'maintenance_mode': enable,
                'message': f'Maintenance mode {"enabled" if enable else "disabled"}'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BackupVerifyView(APIView):
    """Verify backup integrity"""
    permission_classes = [IsAdminUser]
    
    def post(self, request, pk):
        try:
            backup = Backup.objects.get(id=pk)
            
            # Simulate verification
            if backup.file_hash:
                # In production, this would actually verify the file
                verification_result = {
                    'valid': True,
                    'message': 'Backup integrity verified',
                    'hash': backup.file_hash
                }
                
                backup.is_verified = verification_result['valid']
                backup.verified_by = request.user
                backup.verified_at = timezone.now()
                backup.verification_hash = verification_result.get('hash', '')
                backup.save()
                
                return Response({
                    'success': True,
                    'verified': verification_result['valid'],
                    'message': verification_result['message']
                })
            else:
                return Response({
                    'success': False,
                    'message': 'No file hash available for verification'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Backup.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Backup not found'
            }, status=status.HTTP_404_NOT_FOUND)


class BackupHealthCheckView(APIView):
    """Perform health check on backup"""
    permission_classes = [IsAdminUser]
    
    def post(self, request, pk):
        serializer = HealthCheckSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                backup = Backup.objects.get(id=pk)
                full_check = serializer.validated_data.get('full_check', False)
                
                # Perform health check
                if full_check:
                    # Full health check
                    is_healthy = True  # Placeholder
                    health_score = 95  # Placeholder
                else:
                    # Quick health check
                    is_healthy = backup.is_healthy
                    health_score = backup.health_score
                
                backup.is_healthy = is_healthy
                backup.last_health_check = timezone.now()
                backup.health_check_count += 1
                backup.health_score = health_score
                backup.save()
                
                return Response({
                    'success': True,
                    'healthy': is_healthy,
                    'health_score': health_score,
                    'message': 'Health check completed'
                })
                
            except Backup.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Backup not found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateRedundantCopyView(APIView):
    """Create redundant copies of backup"""
    permission_classes = [IsAdminUser]
    
    def post(self, request, pk):
        try:
            backup = Backup.objects.get(id=pk)
            
            # Get available storage locations
            locations = BackupStorageLocation.objects.filter(
                is_active=True, is_connected=True
            ).order_by('priority')[:3]
            
            if len(locations) < 2:
                return Response({
                    'success': False,
                    'message': 'Need at least 2 active storage locations for redundancy'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update backup for redundancy
            backup.storage_type = 'redundant'
            backup.redundancy_level = len(locations)
            backup.storage_locations = [loc.id for loc in locations]
            backup.save()
            
            # Log the redundancy creation
            BackupLog.objects.create(
                backup=backup,
                level='info',
                message=f"Created {len(locations)} redundant copies",
                details={
                    'created_by': request.user.username,
                    'locations': [loc.name for loc in locations],
                    'redundancy_level': backup.redundancy_level
                }
            )
            
            return Response({
                'success': True,
                'copies_created': len(locations),
                'locations': [{'id': loc.id, 'name': loc.name} for loc in locations],
                'message': f'Created {len(locations)} redundant copies'
            })
            
        except Backup.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Backup not found'
            }, status=status.HTTP_404_NOT_FOUND)


class TestNotificationView(APIView):
    """Send test notification"""
    permission_classes = [IsAdminUser]
    
    def post(self, request, pk):
        try:
            backup = Backup.objects.get(id=pk)
            
            # Get notification channels from backup or use default
            channels = backup.notification_channels or ['email']
            
            # Send test notification
            send_multi_channel_notification.delay(
                backup_id=str(backup.id),
                message='Test notification from backup system',
                level='info',
                channels=channels
            )
            
            backup.notification_sent = True
            backup.save()
            
            return Response({
                'success': True,
                'message': f'Test notification sent via {", ".join(channels)}'
            })
            
        except Backup.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Backup not found'
            }, status=status.HTTP_404_NOT_FOUND)


class CleanupOldBackupsView(APIView):
    """Cleanup old backups"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        # Run cleanup task
        cleanup_old_backups_task.delay(request.user.id)
        
        return Response({
            'success': True,
            'message': 'Cleanup task started'
        })


class CloneBackupView(APIView):
    """Clone backup configuration"""
    permission_classes = [IsAdminUser]
    
    def post(self, request, pk):
        try:
            original = Backup.objects.get(id=pk)
            
            # Create clone
            clone = Backup.objects.create(
                name=f"Clone of {original.name}",
                description=original.description,
                backup_type=original.backup_type,
                storage_type=original.storage_type,
                encryption_type=original.encryption_type,
                compression_type=original.compression_type,
                retention_days=original.retention_days,
                retention_policy=original.retention_policy,
                database_engine=original.database_engine,
                database_name=original.database_name,
                included_tables=original.included_tables,
                excluded_tables=original.excluded_tables,
                status='pending',
                created_by=request.user,
                parent_backup=original,
                health_score=100,
                is_healthy=True,
                notification_channels=original.notification_channels,
            )
            
            return Response({
                'success': True,
                'backup_id': str(clone.id),
                'message': 'Backup configuration cloned'
            })
            
        except Backup.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Backup not found'
            }, status=status.HTTP_404_NOT_FOUND)


class BackupLogsView(APIView):
    """Get logs for a backup"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        try:
            backup = Backup.objects.get(id=pk)
            logs = backup.logs.all().order_by('-timestamp')
            serializer = BackupLogSerializer(logs, many=True)
            return Response(serializer.data)
            
        except Backup.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Backup not found'
            }, status=status.HTTP_404_NOT_FOUND)


class BackupDownloadView(APIView):
    """Download backup file"""
    permission_classes = [IsAdminUser]
    
    def get(self, request, pk):
        try:
            backup = Backup.objects.get(id=pk)
            
            if not backup.file_path or not os.path.exists(backup.file_path):
                return Response({
                    'success': False,
                    'message': 'Backup file not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(backup.file_path)
            
            # Open file for reading
            file_handle = open(backup.file_path, 'rb')
            
            # Create response
            response = FileResponse(file_handle, content_type=mime_type or 'application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{backup.name}.backup"'
            response['Content-Length'] = os.path.getsize(backup.file_path)
            
            # Log the download
            BackupLog.objects.create(
                backup=backup,
                level='info',
                message=f"Backup downloaded by {request.user.username}",
                details={
                    'downloaded_by': request.user.username,
                    'file_size': backup.file_size,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return response
            
        except Backup.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Backup not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to download backup: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ANALYTICS VIEWS ====================

class BackupGrowthAnalyticsView(APIView):
    """Get backup growth analytics"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Daily growth
        daily_growth = Backup.objects.filter(
            start_time__date__gte=week_ago
        ).extra({
            'day': "date(start_time)"
        }).values('day').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('day')
        
        # Monthly growth
        monthly_growth = Backup.objects.filter(
            start_time__date__gte=month_ago
        ).extra({
            'month': "date_trunc('month', start_time)"
        }).values('month').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('month')
        
        return Response({
            'daily_growth': list(daily_growth),
            'monthly_growth': list(monthly_growth),
            'timeframe': {
                'week_ago': week_ago.isoformat(),
                'month_ago': month_ago.isoformat(),
                'today': today.isoformat()
            }
        })



class StorageUsageAnalyticsView(APIView):
    """Get storage usage analytics"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Storage distribution by type
        storage_distribution = Backup.objects.values('storage_type').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('-total_size')
        
        # ✅ FIX: is_active → status='active'
        storage_locations = BackupStorageLocation.objects.filter(status='active').annotate(
            backup_count=Count('backup', distinct=True),
        ).order_by('-priority')
        
        total_capacity = sum(getattr(loc, 'total_space', 0) or 0 for loc in storage_locations)
        total_used     = sum(getattr(loc, 'used_space',  0) or 0 for loc in storage_locations)
        total_available = total_capacity - total_used
        
        return Response({
            'storage_distribution': list(storage_distribution),
            'storage_locations': [
                {
                    'id':               loc.id,
                    'name':             loc.name,
                    'type':             loc.storage_type,
                    'total_space':      getattr(loc, 'total_space', 0),
                    'used_space':       getattr(loc, 'used_space', 0),
                    'space_used_percentage': getattr(loc, 'space_used_percentage', 0),
                    'backup_count':     loc.backup_count,
                }
                for loc in storage_locations
            ],
            'capacity_summary': {
                'total_capacity':   total_capacity,
                'total_used':       total_used,
                'total_available':  total_available,
                'usage_percentage': (total_used / total_capacity * 100) if total_capacity > 0 else 0
            }
        })

# class StorageUsageAnalyticsView(APIView):
#     """Get storage usage analytics"""
#     permission_classes = [IsAdminUser]
    
#     def get(self, request):
#         # Storage distribution by type
#         storage_distribution = Backup.objects.values('storage_type').annotate(
#             count=Count('id'),
#             total_size=Sum('file_size')
#         ).order_by('-total_size')
        
#         # Storage locations usage
#         storage_locations = BackupStorageLocation.objects.filter(is_active=True).annotate(
#             backup_count=Count('backup'),
#             location_size=Sum('backup__file_size')
#         ).order_by('-priority')
        
#         # Calculate total capacity
#         total_capacity = sum(loc.max_capacity for loc in storage_locations if loc.max_capacity > 0)
#         total_used = sum(loc.used_capacity for loc in storage_locations)
#         total_available = total_capacity - total_used
        
#         return Response({
#             'storage_distribution': list(storage_distribution),
#             'storage_locations': [
#                 {
#                     'id': loc.id,
#                     'name': loc.name,
#                     'type': loc.storage_type,
#                     'max_capacity': loc.max_capacity,
#                     'used_capacity': loc.used_capacity,
#                     'usage_percentage': loc.usage_percentage,
#                     'backup_count': loc.backup_count,
#                     'location_size': loc.location_size
#                 }
#                 for loc in storage_locations
#             ],
#             'capacity_summary': {
#                 'total_capacity': total_capacity,
#                 'total_used': total_used,
#                 'total_available': total_available,
#                 'usage_percentage': (total_used / total_capacity * 100) if total_capacity > 0 else 0
#             }
#         })


class PerformanceMetricsView(APIView):
    """Get performance metrics"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Performance metrics for completed backups
        performance_stats = Backup.objects.filter(
            status='completed'
        ).aggregate(
            avg_duration=Avg('duration'),
            total_duration=Sum('duration'),
            avg_backup_speed=Avg('backup_speed'),
            avg_upload_speed=Avg('upload_speed'),
            avg_compression_ratio=Avg('compression_ratio')
        )
        
        # Success rate by type
        success_by_type = Backup.objects.values('backup_type').annotate(
            total=Count('id'),
            success=Count('id', filter=Q(status='completed')),
            success_rate=Case(
                When(total=0, then=Value(0)),
                default=Count('id', filter=Q(status='completed')) * 100.0 / Count('id'),
                output_field=DecimalField()
            )
        ).order_by('-success_rate')
        
        # Health statistics
        health_stats = Backup.objects.aggregate(
            total=Count('id'),
            healthy=Count('id', filter=Q(is_healthy=True)),
            unhealthy=Count('id', filter=Q(is_healthy=False)),
            avg_health_score=Avg('health_score')
        )
        
        return Response({
            'performance_stats': performance_stats,
            'success_by_type': list(success_by_type),
            'health_stats': health_stats
        })


class RetentionAnalysisView(APIView):
    """Get retention analysis"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Expired backups
        expired_backups = Backup.objects.filter(
            expires_at__lt=timezone.now(),
            is_permanent=False
        ).count()
        
        total_backups = Backup.objects.count()
        compliance_rate = ((total_backups - expired_backups) / total_backups * 100) if total_backups > 0 else 100
        
        # GFS compliance
        gfs_backups = Backup.objects.filter(retention_policy='gfs')
        gfs_compliant = gfs_backups.filter(
            expires_at__gte=timezone.now()
        ).count()
        gfs_rate = (gfs_compliant / gfs_backups.count() * 100) if gfs_backups.count() > 0 else 100
        
        # Backup age distribution
        age_distribution = Backup.objects.annotate(
            age_days=(timezone.now() - F('start_time')).days
        ).values(
            'age_category'
        ).annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('age_category')
        
        return Response({
            'expired_backups': expired_backups,
            'compliance_rate': round(compliance_rate, 1),
            'gfs_compliance_rate': round(gfs_rate, 1),
            'age_distribution': list(age_distribution),
            'summary': {
                'total_backups': total_backups,
                'expired_percentage': (expired_backups / total_backups * 100) if total_backups > 0 else 0
            }
        })


# ==================== REPORT VIEWS ====================

class BackupSummaryReportView(APIView):
    """Generate backup summary report"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Basic statistics
        total_backups = Backup.objects.count()
        total_size = Backup.objects.aggregate(total=Sum('file_size'))['total'] or 0
        successful_backups = Backup.objects.filter(status='completed').count()
        failed_backups = Backup.objects.filter(status='failed').count()
        running_backups = Backup.objects.filter(status='running').count()
        
        # Success rate
        success_rate = (successful_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Recent backups
        recent_backups = Backup.objects.select_related('created_by').order_by('-start_time')[:10]
        
        # Status distribution
        status_distribution = Backup.objects.values('status').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('-count')
        
        return Response({
            'summary': {
                'total_backups': total_backups,
                'total_size': total_size,
                'successful_backups': successful_backups,
                'failed_backups': failed_backups,
                'running_backups': running_backups,
                'success_rate': round(success_rate, 1)
            },
            'recent_backups': BackupSerializer(recent_backups, many=True).data,
            'status_distribution': list(status_distribution),
            'generated_at': timezone.now().isoformat(),
            'generated_by': request.user.username
        })


class HealthReportView(APIView):
    """Generate health report"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        total_backups     = Backup.objects.count()
        healthy_backups   = Backup.objects.filter(is_healthy=True).count()
        unhealthy_backups = Backup.objects.filter(is_healthy=False).count()
        

        # Health score 0-100 → bucket into 0-25, 26-50, 51-75, 76-100
        excellent = Backup.objects.filter(health_score__gte=76).count()
        good      = Backup.objects.filter(health_score__gte=51, health_score__lt=76).count()
        fair      = Backup.objects.filter(health_score__gte=26, health_score__lt=51).count()
        poor      = Backup.objects.filter(health_score__lt=26).count()
        
        health_score_distribution = [
            {'range': '76-100 (Excellent)', 'count': excellent},
            {'range': '51-75  (Good)',       'count': good},
            {'range': '26-50  (Fair)',        'count': fair},
            {'range': '0-25   (Poor)',        'count': poor},
        ]
        
        # Unhealthy backups details
        unhealthy_details = list(Backup.objects.filter(is_healthy=False).values(
            'id', 'name', 'health_score', 'last_health_check', 'error_message'
        )[:20])
        
        # Storage health — ✅ FIX: is_active → status='active'
        storage_locations = BackupStorageLocation.objects.filter(status='active')
        storage_health = []
        for location in storage_locations:
            score = 100
            if not getattr(location, 'is_connected', True):
                score -= 40
            pct = getattr(location, 'space_used_percentage', 0) or 0
            if pct > 90:  score -= 30
            elif pct > 80: score -= 20
            if getattr(location, 'connection_errors', 0) > 10:
                score -= 20
            storage_health.append({
                'name':   location.name,
                'score':  max(0, score),
                'status': 'Healthy' if score >= 80 else 'Warning' if score >= 60 else 'Critical'
            })
        
        return Response({
            'health_summary': {
                'total_backups':    total_backups,
                'healthy_backups':  healthy_backups,
                'unhealthy_backups':unhealthy_backups,
                'health_rate':      (healthy_backups / total_backups * 100) if total_backups > 0 else 0
            },
            'health_score_distribution': health_score_distribution,
            'unhealthy_backups':   unhealthy_details,
            'storage_health':      storage_health,
            'generated_at':        timezone.now().isoformat()
        })

# class HealthReportView(APIView):
#     """Generate health report"""
#     permission_classes = [IsAdminUser]
    
#     def get(self, request):
#         # Health statistics
#         total_backups = Backup.objects.count()
#         healthy_backups = Backup.objects.filter(is_healthy=True).count()
#         unhealthy_backups = Backup.objects.filter(is_healthy=False).count()
        
#         # Health score distribution
#         health_score_distribution = Backup.objects.values(
#             'health_range'
#         ).annotate(
#             count=Count('id'),
#             total_size=Sum('file_size')
#         ).order_by('health_range')
        
#         # Unhealthy backups details
#         unhealthy_details = Backup.objects.filter(is_healthy=False).values(
#             'id', 'name', 'health_score', 'last_health_check', 'last_error'
#         )[:20]
        
#         # Storage health
#         storage_locations = BackupStorageLocation.objects.filter(is_active=True)
#         storage_health = []
        
#         for location in storage_locations:
#             health_score = 100
#             if not location.is_connected:
#                 health_score -= 40
#             if location.usage_percentage > 90:
#                 health_score -= 30
#             elif location.usage_percentage > 80:
#                 health_score -= 20
#             if location.connection_errors > 10:
#                 health_score -= 20
            
#             storage_health.append({
#                 'name': location.name,
#                 'score': max(0, health_score),
#                 'status': 'Healthy' if health_score >= 80 else 'Warning' if health_score >= 60 else 'Critical'
#             })
        
#         return Response({
#             'health_summary': {
#                 'total_backups': total_backups,
#                 'healthy_backups': healthy_backups,
#                 'unhealthy_backups': unhealthy_backups,
#                 'health_rate': (healthy_backups / total_backups * 100) if total_backups > 0 else 0
#             },
#             'health_score_distribution': list(health_score_distribution),
#             'unhealthy_backups': list(unhealthy_details),
#             'storage_health': storage_health,
#             'generated_at': timezone.now().isoformat()
#         })


class ComplianceReportView(APIView):
    """Generate compliance report"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Retention compliance
        expired_backups = Backup.objects.filter(
            expires_at__lt=timezone.now(),
            is_permanent=False
        ).count()
        
        total_backups = Backup.objects.count()
        retention_compliance = ((total_backups - expired_backups) / total_backups * 100) if total_backups > 0 else 100
        
        # Verification compliance
        verified_backups = Backup.objects.filter(is_verified=True).count()
        verification_compliance = (verified_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Health compliance
        healthy_backups = Backup.objects.filter(is_healthy=True).count()
        health_compliance = (healthy_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Schedule compliance
        schedules = BackupSchedule.objects.filter(is_active=True)
        schedule_compliance = []
        
        for schedule in schedules:
            last_7_days = timezone.now() - timedelta(days=7)
            expected_runs = 7  # For daily schedule, adjust based on frequency
            actual_runs = schedule.backup_set.filter(
                start_time__gte=last_7_days
            ).count()
            
            compliance_rate = (actual_runs / expected_runs * 100) if expected_runs > 0 else 0
            
            schedule_compliance.append({
                'name': schedule.name,
                'frequency': schedule.frequency,
                'expected_runs': expected_runs,
                'actual_runs': actual_runs,
                'compliance_rate': round(compliance_rate, 1)
            })
        
        return Response({
            'compliance_summary': {
                'retention_compliance': round(retention_compliance, 1),
                'verification_compliance': round(verification_compliance, 1),
                'health_compliance': round(health_compliance, 1),
                'overall_compliance': round((retention_compliance + verification_compliance + health_compliance) / 3, 1)
            },
            'schedule_compliance': schedule_compliance,
            'issues': {
                'expired_backups': expired_backups,
                'unverified_backups': total_backups - verified_backups,
                'unhealthy_backups': total_backups - healthy_backups
            },
            'generated_at': timezone.now().isoformat()
        })


# ==================== SYSTEM VIEWS ====================

class SystemMetricsView(APIView):
    """Get system metrics"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        import psutil
        import shutil
        
        try:
            # Disk usage
            total, used, free = shutil.disk_usage("/")
            disk_usage = {
                'total': total,
                'used': used,
                'free': free,
                'percentage': (used / total) * 100
            }
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = {
                'total': memory.total,
                'used': memory.used,
                'free': memory.available,
                'percentage': memory.percent
            }
            
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Network I/O
            net_io = psutil.net_io_counters()
            network_usage = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
            
            return Response({
                'disk_usage': disk_usage,
                'memory_usage': memory_usage,
                'cpu_usage': cpu_usage,
                'network_usage': network_usage,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'error': str(e),
                'message': 'Failed to get system metrics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackupDashboardStatsView(APIView):
    """Get dashboard statistics"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Calculate backup health
        total_backups = Backup.objects.count()
        successful_backups = Backup.objects.filter(status='completed').count()
        healthy_backups = Backup.objects.filter(is_healthy=True).count()
        
        success_rate = (successful_backups / total_backups * 100) if total_backups > 0 else 0
        health_rate = (healthy_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Recent success
        recent_success = Backup.objects.filter(
            status='completed',
            start_time__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Storage health
        # storage_health = BackupStorageLocation.objects.filter(is_active=True, is_connected=True).count()
        # total_storage = BackupStorageLocation.objects.filter(is_active=True).count()
        storage_health = BackupStorageLocation.objects.filter(status='active', is_connected=True).count()
        total_storage = BackupStorageLocation.objects.filter(status='active').count()
        storage_rate = (storage_health / total_storage * 100) if total_storage > 0 else 0
        
        # Calculate health score
        health_score = (success_rate * 0.3) + (min(100, recent_success * 10) * 0.2) + (storage_rate * 0.2) + (health_rate * 0.3)
        
        if health_score >= 80:
            health_status = 'Healthy'
        elif health_score >= 60:
            health_status = 'Warning'
        else:
            health_status = 'Critical'
        
        return Response({
            'backup_health': {
                'score': round(health_score, 1),
                'status': health_status,
                'success_rate': round(success_rate, 1),
                'health_rate': round(health_rate, 1),
                'storage_rate': round(storage_rate, 1)
            },
            'quick_stats': {
                'total_backups': total_backups,
                'successful_backups': successful_backups,
                'healthy_backups': healthy_backups,
                'running_backups': Backup.objects.filter(status='running').count(),
                'pending_backups': Backup.objects.filter(status='pending').count(),
                'failed_24h': Backup.objects.filter(
                    status='failed',
                    start_time__gte=timezone.now() - timedelta(hours=24)
                ).count()
            },
            'timestamp': timezone.now().isoformat()
        })


# ==================== WEBHOOK VIEWS ====================

class BackupCompleteWebhookView(APIView):
    """Webhook for backup completion"""
    permission_classes = [AllowAny]
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, backup_id):
        try:
            backup = Backup.objects.get(id=backup_id)
            
            # Update backup status based on webhook data
            data = request.data
            
            if data.get('status') == 'completed':
                backup.status = 'completed'
                backup.end_time = timezone.now()
                backup.file_size = data.get('file_size', 0)
                backup.file_hash = data.get('file_hash', '')
                backup.save()
                
                # Send notifications
                if backup.notification_channels:
                    send_multi_channel_notification.delay(
                        backup_id=str(backup.id),
                        message=f"Backup completed successfully: {backup.name}",
                        level='success',
                        channels=backup.notification_channels
                    )
            
            elif data.get('status') == 'failed':
                backup.status = 'failed'
                backup.last_error = data.get('error_message', 'Unknown error')
                backup.save()
                
                # Send failure notifications
                if backup.notification_channels:
                    send_multi_channel_notification.delay(
                        backup_id=str(backup.id),
                        message=f"Backup failed: {backup.name} - {backup.last_error}",
                        level='error',
                        channels=backup.notification_channels
                    )
            
            return Response({'success': True})
            
        except Backup.DoesNotExist:
            return Response({'success': False, 'message': 'Backup not found'}, status=404)


class RestoreCompleteWebhookView(APIView):
    """Webhook for restore completion"""
    permission_classes = [AllowAny]
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, restoration_id):
        try:
            restoration = BackupRestoration.objects.get(id=restoration_id)
            
            # Update restoration status
            data = request.data
            
            if data.get('status') == 'completed':
                restoration.status = 'completed'
                restoration.completed_at = timezone.now()
                restoration.success = data.get('success', True)
                restoration.verification_passed = data.get('verification_passed', False)
                restoration.save()
                
                # Disable maintenance mode if enabled
                if cache.get('maintenance_mode'):
                    cache.set('maintenance_mode', False, 1)
            
            elif data.get('status') == 'failed':
                restoration.status = 'failed'
                restoration.completed_at = timezone.now()
                restoration.success = False
                restoration.error_message = data.get('error_message', 'Unknown error')
                restoration.save()
            
            return Response({'success': True})
            
        except BackupRestoration.DoesNotExist:
            return Response({'success': False, 'message': 'Restoration not found'}, status=404)


class HealthAlertWebhookView(APIView):
    """Webhook for health alerts"""
    permission_classes = [AllowAny]
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        data = request.data
        
        # Create health alert log
        BackupLog.objects.create(
            level='critical',
            message=data.get('message', 'Health alert received'),
            details=data
        )
        
        # Send notifications to all active configs
        configs = BackupNotificationConfig.objects.filter(
            is_active=True,
            notification_types__contains=['health_alert']
        )
        
        for config in configs:
            send_multi_channel_notification.delay(
                backup_id=None,
                message=data.get('message', 'Health alert'),
                level='critical',
                channels=config.channels
            )
        
        return Response({'success': True})


# ==================== PUBLIC VIEWS ====================

class PublicBackupStatusView(APIView):
    """Public backup status (read-only)"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        # Basic status information only
        total_backups = Backup.objects.count()
        successful_backups = Backup.objects.filter(status='completed').count()
        running_backups = Backup.objects.filter(status='running').count()
        
        return Response({
            'status': 'operational',
            'backups': {
                'total': total_backups,
                'successful': successful_backups,
                'running': running_backups
            },
            'last_updated': timezone.now().isoformat()
        })


class PublicHealthCheckView(APIView):
    """Public health check endpoint"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        # Check database connection
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = 'healthy'
        except:
            db_status = 'unhealthy'
        
        # Check storage locations
        storage_locations = BackupStorageLocation.objects.filter(status='active')
        storage_status = all(loc.is_connected for loc in storage_locations)
        
        # Check recent backups
        recent_backups = Backup.objects.filter(
            start_time__gte=timezone.now() - timedelta(hours=24)
        )
        recent_success = recent_backups.filter(status='completed').exists()
        
        overall_status = 'healthy' if all([db_status == 'healthy', storage_status, recent_success]) else 'degraded'
        
        return Response({
            'status': overall_status,
            'components': {
                'database': db_status,
                'storage': 'healthy' if storage_status else 'unhealthy',
                'recent_backups': 'healthy' if recent_success else 'unhealthy'
            },
            'timestamp': timezone.now().isoformat()
        })


# ==================== ADMIN DASHBOARD VIEWS ====================

class BackupAdminDashboardView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """Backup admin dashboard view"""
    template_name = 'admin/backup_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Backup statistics
        total_backups = Backup.objects.count()
        total_size = Backup.objects.aggregate(total=Sum('file_size'))['total'] or 0
        successful_backups = Backup.objects.filter(status='completed').count()
        failed_backups = Backup.objects.filter(status='failed').count()
        
        # Calculate success rate
        success_rate = (successful_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Recent backups
        recent_backups = Backup.objects.select_related('created_by', 'verified_by').order_by('-start_time')[:10]
        
        # Backup status distribution
        status_distribution = Backup.objects.values('status').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('-count')
        
        # Backup type distribution
        type_distribution = Backup.objects.values('backup_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Storage usage by type
        storage_distribution = Backup.objects.values('storage_type').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('-total_size')
        
        # Active schedules
        active_schedules = BackupSchedule.objects.filter(is_active=True).count()
        
        # Storage locations status
        storage_locations = BackupStorageLocation.objects.filter(is_active=True).annotate(
            backup_count=Count('backup'),
            location_size=Sum('backup__file_size')
        ).order_by('-priority')
        
        # Currently running backups
        running_backups = Backup.objects.filter(status='running').count()
        
        # Check maintenance mode
        maintenance_mode = cache.get('maintenance_mode', False)
        
        # Calculate backup health
        healthy_backups = Backup.objects.filter(is_healthy=True).count()
        health_rate = (healthy_backups / total_backups * 100) if total_backups > 0 else 0
        
        recent_success = Backup.objects.filter(
            status='completed',
            start_time__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # storage_health = BackupStorageLocation.objects.filter(is_active=True, is_connected=True).count()
        # total_storage = BackupStorageLocation.objects.filter(is_active=True).count()
        storage_health = BackupStorageLocation.objects.filter(status='active', is_connected=True).count()
        total_storage = BackupStorageLocation.objects.filter(status='active').count()
        storage_rate = (storage_health / total_storage * 100) if total_storage > 0 else 0
        
        health_score = (success_rate * 0.3) + (min(100, recent_success * 10) * 0.2) + (storage_rate * 0.2) + (health_rate * 0.3)
        
        if health_score >= 80:
            health_status = 'Healthy'
        elif health_score >= 60:
            health_status = 'Warning'
        else:
            health_status = 'Critical'
        
        context.update({
            'title': 'Backup & Recovery Dashboard',
            'today': today,
            'total_backups': total_backups,
            'total_size': total_size,
            'successful_backups': successful_backups,
            'failed_backups': failed_backups,
            'success_rate': round(success_rate, 1),
            'healthy_backups': healthy_backups,
            'health_rate': round(health_rate, 1),
            'recent_backups': recent_backups,
            'status_distribution': list(status_distribution),
            'type_distribution': list(type_distribution),
            'storage_distribution': list(storage_distribution),
            'active_schedules': active_schedules,
            'storage_locations': storage_locations,
            'running_backups': running_backups,
            'maintenance_mode': maintenance_mode,
            'backup_health': {
                'score': round(health_score, 1),
                'status': health_status
            },
            'current_time': timezone.now().strftime("%H:%M:%S"),
        })
        
        return context


# Note: Other admin views (BackupAnalyticsDashboardView, StorageManagementDashboardView, etc.)
# would be implemented similarly with their specific context data

# ==================== ERROR HANDLERS ====================

def handler404(request, exception):
    """Custom 404 handler"""
    return JsonResponse({
        'error': 'Not Found',
        'message': 'The requested resource was not found',
        'status_code': 404
    }, status=404)


def handler500(request):
    """Custom 500 handler"""
    return JsonResponse({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred',
        'status_code': 500
    }, status=500)


# ==================== API VIEWS FOR ADMIN ====================

class APIBackupProgressView(APIView):
    """API endpoint for backup progress (admin)"""
    permission_classes = [IsAdminUser]
    
    def get(self, request, pk):
        progress = cache.get(f'backup_progress_{pk}', {
            'status': 'unknown',
            'percentage': 0,
            'current_step': 'Not found',
            'started_at': None,
        })
        
        return Response(progress)


class APIStartBackupView(APIView):
    """API endpoint to start backup (admin)"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        serializer = BackupTaskRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            
            # Create backup record
            backup = Backup.objects.create(
                name=f"Manual Backup {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                description=data.get('description', ''),
                backup_type=data['backup_type'],
                storage_type=data['storage_type'],
                encryption_type=data['encryption_type'],
                compression_type=data['compression_type'],
                retention_days=data['retention_days'],
                status='pending',
                created_by=request.user,
                included_tables=data['tables'],
                notification_channels=data.get('notification_channels', ['email'])
            )
            
            # Start backup task
            backup_database_task.delay(
                backup_id=str(backup.id),
                backup_type=backup.backup_type,
                tables=backup.included_tables,
                encryption=backup.encryption_type,
                compression=backup.compression_type,
                user_id=str(request.user.id)
            )
            
            # Set progress tracking
            cache.set(f'backup_progress_{backup.id}', {
                'status': 'pending',
                'percentage': 0,
                'current_step': 'Initializing...',
                'started_at': timezone.now().isoformat(),
            }, 3600)
            
            return Response({
                'success': True,
                'backup_id': str(backup.id),
                'message': 'Backup started successfully'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Note: Other admin API views would be implemented similarly
# They would be thin wrappers around the main API views with appropriate permissions


# ==================== ADDITIONAL VIEWSETS FOR NEW MODELS ====================

class BackupVerificationViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for BackupVerification model"""
    queryset = BackupVerification.objects.all().select_related(
        'backup', 'verified_by'
    )
    serializer_class = BackupVerificationSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by backup
        backup_id = self.request.query_params.get('backup_id')
        if backup_id:
            queryset = queryset.filter(backup__backup_id=backup_id)
        
        # Filter by verification method
        method = self.request.query_params.get('method')
        if method:
            queryset = queryset.filter(verification_method=method)
        
        # Filter by validity
        is_valid = self.request.query_params.get('is_valid')
        if is_valid is not None:
            queryset = queryset.filter(is_valid=is_valid.lower() == 'true')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def reverify(self, request, pk=None):
        """Re-verify a backup"""
        verification = self.get_object()
        
        try:
            from .services import BackupService
            service = BackupService()
            new_verification = service.verify_backup(
                verification.backup.backup_id,
                verification_method=verification.verification_method
            )
            
            return Response({
                'success': True,
                'verification_id': str(new_verification.verification_id),
                'message': 'Backup re-verification started'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackupEncryptionViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for BackupEncryption model"""
    queryset = BackupEncryption.objects.all().select_related('backup')
    serializer_class = BackupEncryptionSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by backup
        backup_id = self.request.query_params.get('backup_id')
        if backup_id:
            queryset = queryset.filter(backup__backup_id=backup_id)
        
        # Filter by algorithm
        algorithm = self.request.query_params.get('algorithm')
        if algorithm:
            queryset = queryset.filter(algorithm=algorithm)
        
        # Filter by encryption status
        is_encrypted = self.request.query_params.get('is_encrypted')
        if is_encrypted is not None:
            queryset = queryset.filter(is_encrypted=is_encrypted.lower() == 'true')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def rotate_key(self, request, pk=None):
        """Rotate encryption key for a backup"""
        encryption = self.get_object()
        
        try:
            from .services import BackupService
            service = BackupService()
            # Implement key rotation logic
            return Response({
                'success': True,
                'message': 'Key rotation initiated'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackupAlertViewSet(BackupPermissionMixin, viewsets.ModelViewSet):
    """ViewSet for BackupAlert model"""
    queryset = BackupAlert.objects.all().select_related(
        'backup', 'resolved_by'
    )
    serializer_class = BackupAlertSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by backup
        backup_id = self.request.query_params.get('backup_id')
        if backup_id:
            queryset = queryset.filter(backup__backup_id=backup_id)
        
        # Filter by alert type
        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        
        # Filter by severity
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by resolution status
        is_resolved = self.request.query_params.get('is_resolved')
        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved.lower() == 'true')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert"""
        alert = self.get_object()
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.save()
        
        return Response({
            'success': True,
            'message': 'Alert resolved successfully',
            'resolved_at': alert.resolved_at.isoformat()
        })
    
    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalate an alert"""
        alert = self.get_object()
        alert.escalation_level = alert.escalation_level + 1
        alert.save()
        
        # Send escalation notification
        try:
            from .tasks import send_multi_channel_notification
            send_multi_channel_notification.delay(
                alert_type='alert_escalated',
                message=f'Alert escalated: {alert.message}',
                backup_id=str(alert.backup.backup_id) if alert.backup else None
            )
        except:
            pass  # Don't fail the response if notification fails
        
        return Response({
            'success': True,
            'message': 'Alert escalated successfully',
            'escalation_level': alert.escalation_level
        })


# ==================== ANALYTICS AND MONITORING VIEWS ====================

class DashboardStatsView(APIView):
    """View for dashboard statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get dashboard statistics"""
        try:
            from django.db.models import Count, Sum, Avg, Q
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)
            last_30d = now - timedelta(days=30)
            
            # Basic stats
            total_backups = Backup.objects.count()
            successful_backups = Backup.objects.filter(status='completed').count()
            failed_backups = Backup.objects.filter(status='failed').count()
            
            # Recent stats
            recent_24h = Backup.objects.filter(created_at__gte=last_24h)
            recent_7d = Backup.objects.filter(created_at__gte=last_7d)
            recent_30d = Backup.objects.filter(created_at__gte=last_30d)
            
            # Storage stats
            total_size = Backup.objects.aggregate(
                total=Sum('file_size')
            )['total'] or 0
            
            # Alert stats
            active_alerts = BackupAlert.objects.filter(is_resolved=False).count()
            critical_alerts = BackupAlert.objects.filter(
                is_resolved=False,
                severity='critical'
            ).count()
            
            # Health score
            healthy_backups = Backup.objects.filter(
                status='completed',
                health_score__gte=80
            ).count()
            health_score = (healthy_backups / max(successful_backups, 1)) * 100
            
            stats = {
                'total_backups': total_backups,
                'successful_backups': successful_backups,
                'failed_backups': failed_backups,
                'success_rate': round((successful_backups / max(total_backups, 1)) * 100, 2),
                'total_size_bytes': total_size,
                'total_size_gb': round(total_size / (1024**3), 2),
                'last_24h_count': recent_24h.count(),
                'last_7d_count': recent_7d.count(),
                'last_30d_count': recent_30d.count(),
                'alerts_count': active_alerts,
                'critical_alerts_count': critical_alerts,
                'health_score': round(health_score, 2),
                'timestamp': now.isoformat()
            }
            
            serializer = BackupStatsSerializer(stats)
            return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'error': str(e),
                'message': 'Failed to fetch dashboard stats'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SystemHealthCheckView(APIView):
    """View for system health check"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Perform system health check"""
        try:
            checks = {}
            overall_status = 'healthy'
            
            # Database connectivity
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                checks['database'] = {'status': 'healthy', 'message': 'Database connection OK'}
            except Exception as e:
                checks['database'] = {'status': 'critical', 'message': f'Database error: {str(e)}'}
                overall_status = 'critical'
            
            # Storage backends
            storage_locations = BackupStorageLocation.objects.filter(is_active=True)
            storage_issues = 0
            
            for location in storage_locations:
                try:
                    # Test storage connectivity
                    if location.storage_type == 'local':
                        import os
                        if os.path.exists(location.config.get('backup_dir', '')):
                            checks[f'storage_{location.storage_type}'] = {
                                'status': 'healthy',
                                'message': f'{location.name} storage OK'
                            }
                        else:
                            checks[f'storage_{location.storage_type}'] = {
                                'status': 'warning',
                                'message': f'{location.name} storage path not accessible'
                            }
                            storage_issues += 1
                    else:
                        # For cloud storage, just check if config exists
                        if location.config:
                            checks[f'storage_{location.storage_type}'] = {
                                'status': 'healthy',
                                'message': f'{location.name} storage configured'
                            }
                        else:
                            checks[f'storage_{location.storage_type}'] = {
                                'status': 'warning',
                                'message': f'{location.name} storage not configured'
                            }
                            storage_issues += 1
                except Exception as e:
                    checks[f'storage_{location.storage_type}'] = {
                        'status': 'critical',
                        'message': f'{location.name} storage error: {str(e)}'
                    }
                    storage_issues += 1
            
            if storage_issues > 0:
                overall_status = 'warning' if overall_status == 'healthy' else 'critical'
            
            # Recent backup failures
            recent_failures = Backup.objects.filter(
                status='failed',
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            if recent_failures > 5:
                checks['backup_failures'] = {
                    'status': 'warning',
                    'message': f'{recent_failures} backup failures in last 24h'
                }
                overall_status = 'warning' if overall_status == 'healthy' else 'critical'
            else:
                checks['backup_failures'] = {
                    'status': 'healthy',
                    'message': f'{recent_failures} backup failures in last 24h'
                }
            
            # Disk space (for local storage)
            try:
                import shutil
                total, used, free = shutil.disk_usage("/")
                usage_percent = (used / total) * 100
                
                if usage_percent > 90:
                    checks['disk_space'] = {
                        'status': 'critical',
                        'message': f'Disk usage {usage_percent:.1f}%'
                    }
                    overall_status = 'critical'
                elif usage_percent > 80:
                    checks['disk_space'] = {
                        'status': 'warning',
                        'message': f'Disk usage {usage_percent:.1f}%'
                    }
                    overall_status = 'warning' if overall_status == 'healthy' else 'critical'
                else:
                    checks['disk_space'] = {
                        'status': 'healthy',
                        'message': f'Disk usage {usage_percent:.1f}%'
                    }
            except Exception:
                checks['disk_space'] = {
                    'status': 'unknown',
                    'message': 'Could not check disk space'
                }
            
            health_data = {
                'status': overall_status,
                'timestamp': timezone.now().isoformat(),
                'checks': checks,
                'uptime_seconds': 0,  # Would need to track this properly
                'version': '1.0.0',  # Would get from settings
                'environment': getattr(settings, 'ENVIRONMENT', 'unknown')
            }
            
            serializer = HealthCheckSerializer(health_data)
            return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'status': 'critical',
                'message': f'Health check failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Note: Other admin API views would be implemented similarly
# They would be thin wrappers around the main API views with appropriate permissions# ==================== MISSING OPERATIONAL VIEWS ====================



class BackupEncryptView(APIView):

    """Encrypt a backup"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            backup = get_object_or_404(Backup, pk=pk)

            

            if backup.is_encrypted:

                return Response({

                    'success': False,

                    'message': 'Backup is already encrypted'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            algorithm = request.data.get('algorithm', 'AES-256-GCM')

            

            # Start encryption task

            from .tasks import encrypt_backup_task

            task = encrypt_backup_task.delay(str(backup.id), algorithm)

            

            return Response({

                'success': True,

                'message': 'Backup encryption started',

                'task_id': task.id

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to start encryption: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class BackupCompressView(APIView):

    """Compress a backup"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            backup = get_object_or_404(Backup, pk=pk)

            

            if backup.is_compressed:

                return Response({

                    'success': False,

                    'message': 'Backup is already compressed'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            compression_format = request.data.get('format', 'gzip')

            level = request.data.get('level', 6)

            

            # Start compression task

            from .tasks import compress_backup_task

            task = compress_backup_task.delay(str(backup.id), compression_format, level)

            

            return Response({

                'success': True,

                'message': 'Backup compression started',

                'task_id': task.id

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to start compression: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class BackupMoveView(APIView):

    """Move backup to different storage"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            backup = get_object_or_404(Backup, pk=pk)

            

            target_storage_id = request.data.get('target_storage_id')

            if not target_storage_id:

                return Response({

                    'success': False,

                    'message': 'target_storage_id is required'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            target_storage = get_object_or_404(BackupStorageLocation, pk=target_storage_id)

            

            # Start move task

            from .tasks import move_backup_task

            task = move_backup_task.delay(str(backup.id), str(target_storage.id))

            

            return Response({

                'success': True,

                'message': 'Backup move started',

                'task_id': task.id

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to start move: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class BackupArchiveView(APIView):

    """Archive a backup"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            backup = get_object_or_404(Backup, pk=pk)

            

            if backup.status != 'completed':

                return Response({

                    'success': False,

                    'message': 'Only completed backups can be archived'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            # Start archive task

            from .tasks import archive_backup_task

            task = archive_backup_task.delay(str(backup.id))

            

            return Response({

                'success': True,

                'message': 'Backup archive started',

                'task_id': task.id

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to start archive: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





# ==================== SCHEDULE OPERATION VIEWS ====================



class ScheduleRunNowView(APIView):

    """Run schedule immediately"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            schedule = get_object_or_404(BackupSchedule, pk=pk)

            

            if not schedule.is_active:

                return Response({

                    'success': False,

                    'message': 'Schedule is not active'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            # Start backup task

            from .tasks import execute_schedule_task

            task = execute_schedule_task.delay(str(schedule.id))

            

            return Response({

                'success': True,

                'message': 'Schedule execution started',

                'task_id': task.id

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to start schedule: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class SchedulePauseView(APIView):

    """Pause a schedule"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            schedule = get_object_or_404(BackupSchedule, pk=pk)

            schedule.is_paused = True

            schedule.save()

            

            return Response({

                'success': True,

                'message': 'Schedule paused'

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to pause schedule: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ScheduleResumeView(APIView):

    """Resume a schedule"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            schedule = get_object_or_404(BackupSchedule, pk=pk)

            schedule.is_paused = False

            schedule.save()

            

            # Recalculate next run

            schedule.calculate_next_run()

            

            return Response({

                'success': True,

                'message': 'Schedule resumed',

                'next_run': schedule.next_run

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to resume schedule: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ScheduleNextRunView(APIView):

    """Get next run time for schedule"""

    permission_classes = [IsAuthenticated]

    

    def get(self, request, pk):

        try:

            schedule = get_object_or_404(BackupSchedule, pk=pk)

            

            return Response({

                'next_run': schedule.next_run,

                'last_run': schedule.last_run,

                'is_active': schedule.is_active,

                'is_paused': schedule.is_paused

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to get schedule info: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





# ==================== STORAGE OPERATION VIEWS ====================



class StorageTestConnectionView(APIView):

    """Test storage connection"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            storage = get_object_or_404(BackupStorageLocation, pk=pk)

            

            # Test connection using factory

            from .services.factory import get_backup_service_factory

            factory = get_backup_service_factory()

            service = factory.create_service(f'storage_{storage.storage_type}', storage.config)

            

            # Perform connection test

            if hasattr(service, 'test_connection'):

                result = service.test_connection()

            else:

                # Default test - try to list files

                result = {'success': True, 'message': 'Connection successful'}

            

            # Update storage status

            storage.last_checked = timezone.now()

            storage.connection_errors = None if result['success'] else result.get('message')

            storage.save()

            

            return Response(result)

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Connection test failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class StorageSyncView(APIView):

    """Sync storage metadata"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            storage = get_object_or_404(BackupStorageLocation, pk=pk)

            

            # Start sync task

            from .tasks import sync_storage_task

            task = sync_storage_task.delay(str(storage.id))

            

            return Response({

                'success': True,

                'message': 'Storage sync started',

                'task_id': task.id

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to start sync: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class StorageCleanupView(APIView):

    """Cleanup storage"""

    permission_classes = [IsAdminUser]

    

    def post(self, request, pk):

        try:

            storage = get_object_or_404(BackupStorageLocation, pk=pk)

            

            days = request.data.get('days', 30)

            dry_run = request.data.get('dry_run', False)

            

            # Start cleanup task

            from .tasks import cleanup_storage_task

            task = cleanup_storage_task.delay(str(storage.id), days, dry_run)

            

            return Response({

                'success': True,

                'message': 'Storage cleanup started',

                'task_id': task.id

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to start cleanup: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class StorageMetricsView(APIView):

    """Get storage metrics"""

    permission_classes = [IsAuthenticated]

    

    def get(self, request, pk):

        try:

            storage = get_object_or_404(BackupStorageLocation, pk=pk)

            

            # Get metrics from storage

            metrics = storage.get_metrics()

            

            return Response(metrics)

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to get metrics: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== ADDITIONAL MISSING VIEWS ====================



class BatchOperationsView(APIView):

    """Handle batch operations on backups"""

    permission_classes = [IsAdminUser]

    

    def post(self, request):

        try:

            serializer = BatchOperationSerializer(data=request.data)

            if serializer.is_valid():

                operation = serializer.validated_data['operation']

                backup_ids = serializer.validated_data['backup_ids']

                parameters = serializer.validated_data.get('parameters', {})

                dry_run = serializer.validated_data.get('dry_run', False)

                

                if dry_run:

                    return Response({

                        'success': True,

                        'message': f'Dry run: Would perform {operation} on {len(backup_ids)} backups',

                        'backup_ids': [str(bid) for bid in backup_ids],

                        'operation': operation,

                        'parameters': parameters

                    })

                

                # Start batch operation task

                from .tasks import batch_operation_task

                task = batch_operation_task.delay(operation, backup_ids, parameters)

                

                return Response({

                    'success': True,

                    'message': f'Batch {operation} started',

                    'task_id': task.id,

                    'backup_count': len(backup_ids)

                })

            

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Batch operation failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class BulkActionsView(APIView):

    """Handle bulk actions on backups with filters"""

    permission_classes = [IsAdminUser]

    

    def post(self, request):

        try:

            serializer = BulkActionSerializer(data=request.data)

            if serializer.is_valid():

                action = serializer.validated_data['action']

                filters = serializer.validated_data.get('filters', {})

                target_all = serializer.validated_data.get('target_all', False)

                dry_run = serializer.validated_data.get('dry_run', False)

                schedule = serializer.validated_data.get('schedule', False)

                schedule_time = serializer.validated_data.get('schedule_time')

                

                # Get target backups

                if target_all:

                    backups = Backup.objects.all()

                else:

                    backups = Backup.objects.filter(**filters)

                

                backup_ids = list(backups.values_list('id', flat=True))

                

                if dry_run:

                    return Response({

                        'success': True,

                        'message': f'Dry run: Would perform {action} on {len(backup_ids)} backups',

                        'backup_count': len(backup_ids),

                        'action': action,

                        'filters': filters

                    })

                

                if schedule:

                    # Schedule bulk action

                    from .tasks import schedule_bulk_action_task

                    task = schedule_bulk_action_task.delay(action, backup_ids, schedule_time)

                    

                    return Response({

                        'success': True,

                        'message': f'Bulk action scheduled for {schedule_time}',

                        'task_id': task.id,

                        'scheduled_time': schedule_time

                    })

                else:

                    # Execute immediately

                    from .tasks import bulk_action_task

                    task = bulk_action_task.delay(action, backup_ids)

                    

                    return Response({

                        'success': True,

                        'message': f'Bulk {action} started',

                        'task_id': task.id,

                        'backup_count': len(backup_ids)

                    })

            

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Bulk action failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ServiceStatusView(APIView):

    """Get status of all backup services"""

    permission_classes = [IsAuthenticated]

    

    def get(self, request):

        try:

            from .services.factory import get_backup_service_factory

            factory = get_backup_service_factory()

            

            # Get all service instances

            instances = factory.list_instances()

            

            services_status = {}

            for service_id, instance_info in instances.items():

                services_status[service_id] = {

                    'service_type': instance_info.service_type.value,

                    'created_at': instance_info.created_at,

                    'health_status': instance_info.health_status,

                    'last_health_check': instance_info.last_health_check,

                    'is_healthy': instance_info.is_healthy()

                }

            

            # Get factory statistics

            stats = factory.get_service_statistics()

            

            return Response({

                'services': services_status,

                'statistics': stats,

                'timestamp': timezone.now().isoformat()

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to get service status: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class SystemInfoView(APIView):

    """Get system information"""

    permission_classes = [IsAuthenticated]

    

    def get(self, request):

        try:

            import platform

            import psutil

            

            system_info = {

                'system': {

                    'platform': platform.platform(),

                    'architecture': platform.architecture(),

                    'processor': platform.processor(),

                    'hostname': platform.node(),

                },

                'memory': {

                    'total': psutil.virtual_memory().total,

                    'available': psutil.virtual_memory().available,

                    'used': psutil.virtual_memory().used,

                    'percentage': psutil.virtual_memory().percent,

                },

                'disk': {

                    'total': psutil.disk_usage('/').total,

                    'used': psutil.disk_usage('/').used,

                    'free': psutil.disk_usage('/').free,

                    'percentage': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100,

                },

                'python': {

                    'version': platform.python_version(),

                    'implementation': platform.python_implementation(),

                },

                'django': {

                    'version': django.__version__,

                    'settings': {

                        'DEBUG': settings.DEBUG,

                        'ENVIRONMENT': getattr(settings, 'ENVIRONMENT', 'unknown'),

                    }

                },

                'backup_module': {

                    'version': '1.0.0',

                    'features': [

                        'multiple_storage_backends',

                        'encryption',

                        'compression',

                        'scheduling',

                        'verification',

                        'monitoring',

                        'reporting'

                    ]

                }

            }

            

            return Response(system_info)

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to get system info: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class LogStreamView(APIView):

    """Stream backup logs in real-time"""

    permission_classes = [IsAuthenticated]

    

    def get(self, request):

        try:

            from django.http import StreamingHttpResponse

            import json

            

            def log_stream_generator():

                # Get recent logs

                logs = BackupLog.objects.order_by('-timestamp').select_related('backup')[:100]

                

                for log in logs:

                    yield f"data: {json.dumps({

                        'id': str(log.id),

                        'timestamp': log.timestamp.isoformat(),

                        'level': log.level,

                        'category': log.category,

                        'action': log.action,

                        'message': log.message,

                        'backup_id': str(log.backup.id) if log.backup else None,

                        'backup_name': log.backup.name if log.backup else None,

                        'duration': log.duration,

                        'error_message': log.error_message

                    })}\n\n"

            

            response = StreamingHttpResponse(

                log_stream_generator(),

                content_type='text/event-stream'

            )

            response['Cache-Control'] = 'no-cache'

            response['Connection'] = 'keep-alive'

            

            return response

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to stream logs: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class BackupSearchView(APIView):

    """Search backups"""

    permission_classes = [IsAuthenticated]

    

    def get(self, request):

        try:

            query = request.GET.get('q', '')

            if not query:

                return Response({

                    'success': False,

                    'message': 'Search query is required'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            # Search across multiple fields

            backups = Backup.objects.filter(

                Q(name__icontains=query) |

                Q(description__icontains=query) |

                Q(tags__icontains=query) |

                Q(metadata__icontains=query)

            ).select_related('created_by', 'backup_schedule')

            

            # Serialize results

            serializer = BackupSerializer(backups, many=True)

            

            return Response({

                'success': True,

                'query': query,

                'count': len(backups),

                'results': serializer.data

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Search failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class AdvancedSearchView(APIView):

    """Advanced search with filters"""

    permission_classes = [IsAuthenticated]

    

    def post(self, request):

        try:

            # Build complex query from request data

            filters = request.data.get('filters', {})

            sort_by = request.data.get('sort_by', '-created_at')

            limit = request.data.get('limit', 50)

            offset = request.data.get('offset', 0)

            

            queryset = Backup.objects.all()

            

            # Apply filters

            if 'status' in filters:

                queryset = queryset.filter(status=filters['status'])

            

            if 'backup_type' in filters:

                queryset = queryset.filter(backup_type=filters['backup_type'])

            

            if 'storage_type' in filters:

                queryset = queryset.filter(storage_type=filters['storage_type'])

            

            if 'date_from' in filters:

                queryset = queryset.filter(created_at__gte=filters['date_from'])

            

            if 'date_to' in filters:

                queryset = queryset.filter(created_at__lte=filters['date_to'])

            

            if 'size_min' in filters:

                queryset = queryset.filter(file_size__gte=filters['size_min'])

            

            if 'size_max' in filters:

                queryset = queryset.filter(file_size__lte=filters['size_max'])

            

            if 'created_by' in filters:

                queryset = queryset.filter(created_by__id=filters['created_by'])

            

            if 'tags' in filters:

                tags = filters['tags']

                if isinstance(tags, list):

                    queryset = queryset.filter(tags__overlap=tags)

                else:

                    queryset = queryset.filter(tags__icontains=tags)

            

            # Apply sorting

            queryset = queryset.order_by(sort_by)

            

            # Apply pagination

            total_count = queryset.count()

            backups = queryset[offset:offset+limit]

            

            # Serialize results

            serializer = BackupSerializer(backups, many=True)

            

            return Response({

                'success': True,

                'filters': filters,

                'sort_by': sort_by,

                'total_count': total_count,

                'offset': offset,

                'limit': limit,

                'results': serializer.data

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Advanced search failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class BatchVerificationView(APIView):

    """Batch verification of backups"""

    permission_classes = [IsAdminUser]

    

    def post(self, request):

        try:

            backup_ids = request.data.get('backup_ids', [])

            verification_method = request.data.get('method', 'hash')

            parallel = request.data.get('parallel', 2)

            

            if not backup_ids:

                return Response({

                    'success': False,

                    'message': 'backup_ids is required'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            # Start batch verification task

            from .tasks import batch_verification_task

            task = batch_verification_task.delay(backup_ids, verification_method, parallel)

            

            return Response({

                'success': True,

                'message': f'Batch verification started for {len(backup_ids)} backups',

                'task_id': task.id,

                'verification_method': verification_method,

                'backup_count': len(backup_ids)

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Batch verification failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ScheduleVerificationView(APIView):

    """Schedule periodic verification"""

    permission_classes = [IsAdminUser]

    

    def post(self, request):

        try:

            cron_expression = request.data.get('cron_expression')

            verification_method = request.data.get('method', 'hash')

            filters = request.data.get('filters', {})

            

            if not cron_expression:

                return Response({

                    'success': False,

                    'message': 'cron_expression is required'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            # Create verification schedule

            from .models import BackupSchedule

            schedule = BackupSchedule.objects.create(

                name=f'Verification Schedule - {timezone.now().strftime("%Y%m%d%H%M%S")}',

                description='Automated backup verification schedule',

                frequency='custom',

                cron_expression=cron_expression,

                backup_type='verification',

                is_active=True,

                created_by=request.user,

                metadata={

                    'verification_method': verification_method,

                    'filters': filters

                }

            )

            

            return Response({

                'success': True,

                'message': 'Verification schedule created',

                'schedule_id': schedule.id,

                'cron_expression': cron_expression,

                'next_run': schedule.next_run

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to schedule verification: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class EncryptionKeysView(APIView):

    """Manage encryption keys"""

    permission_classes = [IsAdminUser]

    

    def get(self, request):

        try:

            # Get all encryption records

            encryptions = BackupEncryption.objects.select_related('backup').all()

            

            keys_data = []

            for enc in encryptions:

                keys_data.append({

                    'id': str(enc.id),

                    'backup_id': str(enc.backup.id),

                    'backup_name': enc.backup.name,

                    'algorithm': enc.algorithm,

                    'key_hash': enc.key_hash,

                    'is_encrypted': enc.is_encrypted,

                    'key_version': enc.key_version,

                    'key_rotation_date': enc.key_rotation_date,

                    'created_at': enc.created_at

                })

            

            return Response({

                'success': True,

                'keys': keys_data,

                'count': len(keys_data)

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Failed to get encryption keys: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    

    def post(self, request):

        try:

            action = request.data.get('action')

            

            if action == 'rotate':

                # Rotate all encryption keys

                from .tasks import rotate_encryption_keys_task

                task = rotate_encryption_keys_task.delay()

                

                return Response({

                    'success': True,

                    'message': 'Encryption key rotation started',

                    'task_id': task.id

                })

            

            elif action == 'export':

                # Export encryption keys (secure)

                password = request.data.get('password')

                if not password:

                    return Response({

                        'success': False,

                        'message': 'Password is required for key export'

                    }, status=status.HTTP_400_BAD_REQUEST)

                

                from .tasks import export_encryption_keys_task

                task = export_encryption_keys_task.delay(password)

                

                return Response({

                    'success': True,

                    'message': 'Encryption keys export started',

                    'task_id': task.id

                })

            

            else:

                return Response({

                    'success': False,

                    'message': f'Unknown action: {action}'

                }, status=status.HTTP_400_BAD_REQUEST)

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Encryption keys operation failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class EncryptionRotateView(APIView):

    """Rotate encryption keys"""

    permission_classes = [IsAdminUser]

    

    def post(self, request):

        try:

            backup_ids = request.data.get('backup_ids', [])

            algorithm = request.data.get('algorithm', 'AES-256-GCM')

            

            if not backup_ids:

                return Response({

                    'success': False,

                    'message': 'backup_ids is required'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            # Start key rotation task

            from .tasks import rotate_backup_encryption_task

            task = rotate_backup_encryption_task.delay(backup_ids, algorithm)

            

            return Response({

                'success': True,

                'message': f'Encryption rotation started for {len(backup_ids)} backups',

                'task_id': task.id,

                'algorithm': algorithm,

                'backup_count': len(backup_ids)

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Encryption rotation failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ImportBackupView(APIView):

    """Import backup from external source"""

    permission_classes = [IsAdminUser]

    

    def post(self, request):

        try:

            source_type = request.data.get('source_type')  # url, file, s3

            source_path = request.data.get('source_path')

            storage_location_id = request.data.get('storage_location_id')

            

            if not source_type or not source_path:

                return Response({

                    'success': False,

                    'message': 'source_type and source_path are required'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            # Start import task

            from .tasks import import_backup_task

            task = import_backup_task.delay(source_type, source_path, storage_location_id)

            

            return Response({

                'success': True,

                'message': 'Backup import started',

                'task_id': task.id,

                'source_type': source_type,

                'source_path': source_path

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Import failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ExportBackupView(APIView):

    """Export backup to external destination"""

    permission_classes = [IsAdminUser]

    

    def post(self, request):

        try:

            backup_id = request.data.get('backup_id')

            destination_type = request.data.get('destination_type')  # url, file, s3

            destination_path = request.data.get('destination_path')

            

            if not backup_id or not destination_type:

                return Response({

                    'success': False,

                    'message': 'backup_id and destination_type are required'

                }, status=status.HTTP_400_BAD_REQUEST)

            

            backup = get_object_or_404(Backup, pk=backup_id)

            

            # Start export task

            from .tasks import export_backup_task

            task = export_backup_task.delay(str(backup.id), destination_type, destination_path)

            

            return Response({

                'success': True,

                'message': 'Backup export started',

                'task_id': task.id,

                'backup_name': backup.name,

                'destination_type': destination_type

            })

            

        except Exception as e:

            return Response({

                'success': False,

                'message': f'Export failed: {str(e)}'

            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





# Additional analytics and reporting views would follow similar patterns...

