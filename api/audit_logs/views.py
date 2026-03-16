"""
Views for Audit Log management and querying
"""

from rest_framework import viewsets, generics, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Avg, Q, F, Value
from django.db.models.functions import TruncDate, TruncHour
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
import json
import csv
import io
from datetime import datetime, timedelta
import pandas as pd
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from core.views import BaseViewSet
from .models import (
    AuditLog, AuditLogConfig, AuditLogArchive,
    AuditDashboard, AuditAlertRule
)
from .serializers import (
    AuditLogSerializer, AuditLogDetailSerializer,
    AuditLogConfigSerializer, AuditLogArchiveSerializer,
    AuditDashboardSerializer, AuditAlertRuleSerializer,
    AuditStatsSerializer, AuditLogExportSerializer
)

from .services import AuditQuery
from .services import LogExporter
from .services import LogService
from .filters import AuditLogFilter

class AuditLogViewSet(BaseViewSet):
    """
    ViewSet for managing and querying audit logs
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AuditLogFilter
    search_fields = ['message', 'user__email', 'user__username', 'user_ip', 'resource_id']
    ordering_fields = ['timestamp', 'created_at', 'response_time_ms']
    ordering = ['-timestamp']
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve', 'stats', 'export', 'search']:
            # Only staff/admin can view all logs
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions
        """
        queryset = super().get_queryset()
        
        # If user is not admin, only show their own logs
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        
        # Apply date filters
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__lte=end_date)
            except ValueError:
                pass
        
        # Filter by action
        actions = self.request.query_params.getlist('action[]')
        if actions:
            queryset = queryset.filter(action__in=actions)
        
        # Filter by level
        levels = self.request.query_params.getlist('level[]')
        if levels:
            queryset = queryset.filter(level__in=levels)
        
        # Filter by success status
        success = self.request.query_params.get('success')
        if success is not None:
            queryset = queryset.filter(success=success.lower() == 'true')
        
        return queryset.select_related('user')
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action == 'retrieve':
            return AuditLogDetailSerializer
        return super().get_serializer_class()
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get audit log statistics
        """
        # Calculate date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Get base queryset
        queryset = self.get_queryset()
        
        # Calculate statistics
        stats = {
            'total_logs': queryset.count(),
            'logs_today': queryset.filter(timestamp__date=today).count(),
            'logs_this_week': queryset.filter(timestamp__date__gte=week_ago).count(),
            'logs_this_month': queryset.filter(timestamp__date__gte=month_ago).count(),
            
            'error_logs': queryset.filter(level='ERROR').count(),
            'warning_logs': queryset.filter(level='WARNING').count(),
            'security_logs': queryset.filter(level='SECURITY').count(),
            
            'top_actions': list(queryset.values('action')
                              .annotate(count=Count('id'))
                              .order_by('-count')[:10]),
            
            'top_users': list(queryset.filter(user__isnull=False)
                            .values('user__email', 'user__username')
                            .annotate(count=Count('id'))
                            .order_by('-count')[:10]),
            
            'top_ips': list(queryset.exclude(user_ip__isnull=True)
                          .values('user_ip')
                          .annotate(count=Count('id'))
                          .order_by('-count')[:10]),
            
            'avg_response_time': queryset.exclude(response_time_ms__isnull=True)
                                 .aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
            
            'success_rate': (queryset.filter(success=True).count() / max(queryset.count(), 1)) * 100,
        }
        
        # Add storage usage
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT pg_size_pretty(pg_total_relation_size('audit_logs'::regclass))
            """)
            stats['storage_usage'] = cursor.fetchone()[0]
        
        try:
            from api.audit_logs.models import AuditLogArchive
            stats['archive_count'] = AuditLogArchive.objects.count()
        except: stats['archive_count'] = 0
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_total_relation_size('audit_logs'::regclass)")
                stats['storage_usage_mb'] = round(cursor.fetchone()[0] / 1024 / 1024, 2)
        except: stats['storage_usage_mb'] = 0.0
        serializer = AuditStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """
        Get audit logs grouped by time interval
        """
        interval = request.query_params.get('interval', 'hour')
        limit = int(request.query_params.get('limit', 24))
        
        queryset = self.get_queryset()
        
        if interval == 'hour':
            queryset = queryset.annotate(
                time_group=TruncHour('timestamp')
            )
        elif interval == 'day':
            queryset = queryset.annotate(
                time_group=TruncDate('timestamp')
            )
        else:
            queryset = queryset.annotate(
                time_group=TruncHour('timestamp')
            )
        
        timeline_data = list(
            queryset.values('time_group', 'level')
                   .annotate(count=Count('id'))
                   .order_by('time_group')[:limit]
        )
        
        return Response(timeline_data)
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """
        Advanced search for audit logs
        """
        search_query = AuditQuery(request.user)
        
        # Parse search parameters
        query = request.data.get('query', {})
        page = int(request.data.get('page', 1))
        page_size = int(request.data.get('page_size', 50))
        sort_by = request.data.get('sort_by', '-timestamp')
        
        # Perform search
        results, total = search_query.advanced_search(
            query=query,
            page=page,
            page_size=page_size,
            sort_by=sort_by
        )
        
        # Serialize results
        serializer = self.get_serializer(results, many=True)
        
        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        })
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """
        Export audit logs in various formats
        """
        export_serializer = AuditLogExportSerializer(data=request.data)
        if not export_serializer.is_valid():
            return Response(export_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = export_serializer.validated_data
        exporter = LogExporter()
        
        try:
            # Get logs based on filters
            queryset = self.get_queryset()
            
            # Apply additional filters from export request
            if data.get('filters'):
                queryset = exporter.apply_filters(queryset, data['filters'])
            
            # Export in requested format
            export_data = exporter.export(
                queryset=queryset,
                format=data['format'],
                fields=data.get('fields'),
                compression=data['compression']
            )
            
            if data['format'] == 'json':
                response = HttpResponse(
                    json.dumps(export_data, indent=2, default=str),
                    content_type='application/json'
                )
                response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().date()}.json"'
                
            elif data['format'] == 'csv':
                response = HttpResponse(
                    export_data.getvalue(),
                    content_type='text/csv'
                )
                response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().date()}.csv"'
                
            elif data['format'] == 'excel':
                response = HttpResponse(
                    export_data.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().date()}.xlsx"'
                
            elif data['format'] == 'pdf':
                response = HttpResponse(
                    export_data.getvalue(),
                    content_type='application/pdf'
                )
                response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().date()}.pdf"'
            
            else:
                return Response(
                    {'error': 'Unsupported format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return response
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def redact(self, request, pk=None):
        """
        Redact sensitive information from a specific log
        """
        audit_log = self.get_object()
        
        # Check if user has permission to redact
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can redact logs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        fields_to_redact = request.data.get('fields', [])
        
        # Redact specified fields
        for field in fields_to_redact:
            if field == 'request_body':
                if audit_log.request_body:
                    audit_log.request_body = {'redacted': True, 'original_field': 'request_body'}
            elif field == 'response_body':
                if audit_log.response_body:
                    audit_log.response_body = {'redacted': True, 'original_field': 'response_body'}
            elif field == 'error_message':
                audit_log.error_message = '[REDACTED]'
            elif field == 'stack_trace':
                audit_log.stack_trace = '[REDACTED]'
        
        audit_log.save()
        
        # Log the redaction
        log_service = LogService()
        log_service.create_log(
            user=request.user,
            action='LOG_REDACT',
            level='INFO',
            message=f"Redacted fields {fields_to_redact} from audit log {pk}",
            resource_type='AuditLog',
            resource_id=pk,
            metadata={
                'redacted_fields': fields_to_redact,
                'redacted_by': str(request.user.id),
                'redacted_at': timezone.now().isoformat()
            }
        )
        
        return Response({'message': 'Log redacted successfully'})
    
    @action(detail=False, methods=['delete'])
    def purge(self, request):
        """
        Purge old audit logs based on retention policy
        """
        # Only superusers can purge logs
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can purge logs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        days = int(request.query_params.get('days', 365))
        confirm = request.query_params.get('confirm', 'false')
        
        if confirm.lower() != 'true':
            return Response({
                'warning': 'This will permanently delete logs older than {days} days.',
                'instructions': 'Add ?confirm=true to confirm deletion',
                'estimated_count': AuditLog.objects.filter(
                    timestamp__lt=timezone.now() - timedelta(days=days)
                ).count()
            })
        
        # Delete logs older than specified days
        deleted_count, _ = AuditLog.objects.filter(
            timestamp__lt=timezone.now() - timedelta(days=days)
        ).delete()
        
        # Log the purge action
        log_service = LogService()
        log_service.create_log(
            user=request.user,
            action='LOG_PURGE',
            level='WARNING',
            message=f"Purged {deleted_count} audit logs older than {days} days",
            metadata={
                'days': days,
                'deleted_count': deleted_count,
                'purged_by': str(request.user.id),
                'purged_at': timezone.now().isoformat()
            }
        )
        
        return Response({
            'message': f'Successfully purged {deleted_count} audit logs',
            'deleted_count': deleted_count
        })


class AuditLogConfigViewSet(BaseViewSet):
    """
    ViewSet for managing audit log configurations
    """
    queryset = AuditLogConfig.objects.all()
    serializer_class = AuditLogConfigSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None
    
    @action(detail=False, methods=['get'])
    def defaults(self, request):
        """
        Get default audit log configurations
        """
        # Define default configurations
        default_configs = [
            {
                'action': 'API_CALL',
                'enabled': True,
                'log_level': 'INFO',
                'log_request_body': True,
                'log_response_body': True,
                'log_headers': False,
                'retention_days': 365,
                'notify_admins': False,
                'notify_users': False
            },
            {
                'action': 'LOGIN',
                'enabled': True,
                'log_level': 'INFO',
                'log_request_body': False,
                'log_response_body': False,
                'retention_days': 365,
                'notify_admins': True,
                'notify_users': False
            },
            {
                'action': 'WITHDRAWAL',
                'enabled': True,
                'log_level': 'INFO',
                'log_request_body': True,
                'log_response_body': True,
                'retention_days': 730,  # 2 years for financial logs
                'notify_admins': True,
                'notify_users': True
            },
            {
                'action': 'SECURITY',
                'enabled': True,
                'log_level': 'SECURITY',
                'log_request_body': True,
                'log_response_body': True,
                'retention_days': 3650,  # 10 years for security logs
                'notify_admins': True,
                'notify_users': False
            }
        ]
        
        return Response(default_configs)
    
    @action(detail=False, methods=['post'])
    def reset(self, request):
        """
        Reset all configurations to defaults
        """
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can reset configurations'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete all existing configurations
        AuditLogConfig.objects.all().delete()
        
        # Create default configurations
        default_configs = [
            ('API_CALL', True, 'INFO', True, True, False, 365, False, False),
            ('LOGIN', True, 'INFO', False, False, False, 365, True, False),
            ('LOGOUT', True, 'INFO', False, False, False, 365, False, False),
            ('REGISTER', True, 'INFO', True, False, False, 365, True, False),
            ('WITHDRAWAL', True, 'INFO', True, True, False, 730, True, True),
            ('DEPOSIT', True, 'INFO', True, True, False, 730, True, True),
            ('SECURITY', True, 'SECURITY', True, True, True, 3650, True, False),
            ('ERROR', True, 'ERROR', True, True, False, 365, True, False),
        ]
        
        for config in default_configs:
            AuditLogConfig.objects.create(
                action=config[0],
                enabled=config[1],
                log_level=config[2],
                log_request_body=config[3],
                log_response_body=config[4],
                log_headers=config[5],
                retention_days=config[6],
                notify_admins=config[7],
                notify_users=config[8]
            )
        
        return Response({'message': 'Configurations reset to defaults'})


class AuditDashboardViewSet(BaseViewSet):
    """
    ViewSet for managing audit dashboards
    """
    queryset = AuditDashboard.objects.all()
    serializer_class = AuditDashboardSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Users can only see their own dashboards and default ones
        """
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(created_by=self.request.user) | Q(is_default=True)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Set created_by to current user
        """
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """
        Set a dashboard as default
        """
        dashboard = self.get_object()
        
        # Remove default from all dashboards
        AuditDashboard.objects.filter(is_default=True).update(is_default=False)
        
        # Set this as default
        dashboard.is_default = True
        dashboard.save()
        
        return Response({'message': 'Dashboard set as default'})
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Preview dashboard data
        """
        dashboard = self.get_object()
        audit_query = AuditQuery(request.user)
        
        # Apply dashboard filters to get data
        results = audit_query.apply_filters(dashboard.filters)
        
        # Limit to 100 rows for preview
        results = results[:100]
        
        # Serialize results
        serializer = AuditLogSerializer(results, many=True, context={'view_action': 'list'})
        
        return Response({
            'dashboard': AuditDashboardSerializer(dashboard).data,
            'preview_data': serializer.data,
            'total_count': results.count() if hasattr(results, 'count') else len(results)
        })


class AuditAlertRuleViewSet(BaseViewSet):
    """
    ViewSet for managing audit alert rules
    """
    queryset = AuditAlertRule.objects.all()
    serializer_class = AuditAlertRuleSerializer
    permission_classes = [IsAdminUser]
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test an alert rule against recent logs
        """
        alert_rule = self.get_object()
        audit_query = AuditQuery(request.user)
        
        # Test the rule
        test_results = audit_query.test_alert_rule(alert_rule)
        
        return Response(test_results)
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """
        Enable an alert rule
        """
        alert_rule = self.get_object()
        alert_rule.enabled = True
        alert_rule.save()
        
        return Response({'message': 'Alert rule enabled'})
    
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """
        Disable an alert rule
        """
        alert_rule = self.get_object()
        alert_rule.enabled = False
        alert_rule.save()
        
        return Response({'message': 'Alert rule disabled'})
    
    @action(detail=False, methods=['get'])
    def triggered(self, request):
        """
        Get recently triggered alert rules
        """
        # Get rules triggered in last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        rules = AuditAlertRule.objects.filter(
            last_triggered__gte=yesterday
        ).order_by('-last_triggered')
        
        serializer = self.get_serializer(rules, many=True)
        return Response(serializer.data)


class UserAuditLogView(generics.ListAPIView):
    """
    View for users to see their own audit logs
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AuditLogFilter
    ordering_fields = ['timestamp', 'created_at']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """
        Users can only see their own logs
        """
        return AuditLog.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get summary of user's audit logs
        """
        user_logs = self.get_queryset()
        
        summary = {
            'total_actions': user_logs.count(),
            'today_actions': user_logs.filter(
                timestamp__date=timezone.now().date()
            ).count(),
            'success_rate': (user_logs.filter(success=True).count() / 
                           max(user_logs.count(), 1)) * 100,
            'common_actions': list(
                user_logs.values('action')
                        .annotate(count=Count('id'))
                        .order_by('-count')[:5]
            ),
            'last_activity': user_logs.first().timestamp if user_logs.exists() else None
        }
        
        return Response(summary)


class AuditLogArchiveViewSet(BaseViewSet):
    """
    ViewSet for managing audit log archives
    """
    queryset = AuditLogArchive.objects.all()
    serializer_class = AuditLogArchiveSerializer
    permission_classes = [IsAdminUser]
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Download archived log file
        """
        archive = self.get_object()
        
        # Check if file exists
        import os
        if not os.path.exists(archive.storage_path):
            return Response(
                {'error': 'Archive file not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Read and return file
        with open(archive.storage_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="audit_archive_{archive.start_date.date()}_to_{archive.end_date.date()}.zip"'
            return response
    
    @action(detail=False, methods=['post'])
    def create_archive(self, request):
        """
        Create new archive from old logs
        """
        from .services.LogExporter import LogExporter
        
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        compression = request.data.get('compression', 'zip')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            exporter = LogExporter()
            archive = exporter.create_archive(start_date, end_date, compression)
            
            return Response({
                'message': 'Archive created successfully',
                'archive': AuditLogArchiveSerializer(archive).data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LiveAuditView(APIView):
    """
    Real-time audit log streaming (WebSocket/SSE would be better)
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """
        Stream recent audit logs (simulated with polling)
        """
        # Get recent logs (last 5 minutes)
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        
        logs = AuditLog.objects.filter(
            timestamp__gte=five_minutes_ago
        ).order_by('-timestamp')[:100]
        
        serializer = AuditLogSerializer(logs, many=True)
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'logs': serializer.data,
            'count': logs.count()
        })


class AuditHealthCheckView(APIView):
    """
    Health check for audit logging system
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Check health of audit logging system
        """
        from django.db import connection
        
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {}
        }
        
        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_status['checks']['database'] = 'ok'
        except Exception as e:
            health_status['checks']['database'] = f'error: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Check table existence
        try:
            table_count = AuditLog.objects.count()
            health_status['checks']['audit_logs_table'] = f'ok ({table_count} records)'
        except Exception as e:
            health_status['checks']['audit_logs_table'] = f'error: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Check recent logs
        try:
            recent_logs = AuditLog.objects.filter(
                timestamp__gte=timezone.now() - timedelta(minutes=5)
            ).count()
            health_status['checks']['recent_activity'] = f'ok ({recent_logs} logs in last 5 minutes)'
        except Exception as e:
            health_status['checks']['recent_activity'] = f'error: {str(e)}'
        
        # Check storage
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT pg_size_pretty(pg_total_relation_size('audit_logs'::regclass))
                """)
                size = cursor.fetchone()[0]
                health_status['checks']['storage'] = f'ok ({size})'
        except Exception as e:
            health_status['checks']['storage'] = f'error: {str(e)}'
        
        return Response(health_status)