"""
Base ViewSet Classes

This module contains base viewset classes that other tenant management
viewsets inherit from, providing common functionality and utilities.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend

from ..models.core import Tenant
from ..serializers.core import TenantSerializer


class BaseTenantViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for tenant management operations.
    
    Provides common functionality including:
    - Permission checking
    - Tenant filtering
    - Common actions
    - Error handling
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            # Staff users can see all tenants
            return self.queryset.filter(is_deleted=False)
        else:
            # Non-staff users can only see their own tenants
            return self.queryset.filter(
                Q(owner=user) | Q(parent_tenant__owner=user),
                is_deleted=False
            )
    
    def perform_create(self, serializer):
        """Set owner for new objects."""
        if not self.request.user.is_staff:
            serializer.save(owner=self.request.user)
        else:
            serializer.save()
    
    def perform_destroy(self, instance):
        """Soft delete instead of hard delete."""
        instance.soft_delete()
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics for the model."""
        queryset = self.get_queryset()
        
        stats = {
            'total_count': queryset.count(),
            'active_count': queryset.filter(is_active=True).count(),
            'created_today': queryset.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'created_this_week': queryset.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'created_this_month': queryset.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete objects."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ids = request.data.get('ids', [])
        if not ids:
            return Response(
                {'error': 'No IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(id__in=ids)
        count = queryset.count()
        
        # Soft delete
        for obj in queryset:
            obj.soft_delete()
        
        return Response({
            'deleted_count': count,
            'message': f'Successfully deleted {count} objects'
        })
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk update objects."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ids = request.data.get('ids', [])
        update_data = request.data.get('data', {})
        
        if not ids or not update_data:
            return Response(
                {'error': 'IDs and update data are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(id__in=ids)
        count = queryset.count()
        
        # Update objects
        for obj in queryset:
            for field, value in update_data.items():
                if hasattr(obj, field):
                    setattr(obj, field, value)
            obj.save()
        
        return Response({
            'updated_count': count,
            'message': f'Successfully updated {count} objects'
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export data to CSV."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        format_type = request.query_params.get('format', 'csv')
        
        try:
            if format_type == 'csv':
                csv_data = self._export_to_csv()
                return Response(csv_data, content_type='text/csv')
            elif format_type == 'json':
                json_data = self._export_to_json()
                return Response(json_data, content_type='application/json')
            else:
                return Response(
                    {'error': 'Invalid format. Use csv or json'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_to_csv(self):
        """Export queryset to CSV format."""
        import csv
        from io import StringIO
        
        queryset = self.get_queryset()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        if queryset.exists():
            headers = list(queryset.first().__dict__.keys())
            writer.writerow(headers)
            
            # Write data rows
            for obj in queryset:
                row = [getattr(obj, field, '') for field in headers]
                writer.writerow(row)
        
        return output.getvalue()
    
    def _export_to_json(self):
        """Export queryset to JSON format."""
        import json
        
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return json.dumps(serializer.data, indent=2)


class BaseTenantRelatedViewSet(BaseTenantViewSet):
    """
    Base ViewSet for tenant-related operations.
    
    Extends BaseTenantViewSet with tenant-specific functionality.
    """
    
    def get_queryset(self):
        """Filter queryset based on user's tenant."""
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            # Staff users can see all tenant-related objects
            return self.queryset.filter(tenant__is_deleted=False)
        else:
            # Non-staff users can only see objects related to their tenants
            user_tenants = Tenant.objects.filter(
                Q(owner=user) | Q(parent_tenant__owner=user),
                is_deleted=False
            )
            
            return self.queryset.filter(tenant__in=user_tenants)
    
    @action(detail=False, methods=['get'])
    def by_tenant(self, request):
        """Filter objects by tenant."""
        tenant_id = request.query_params.get('tenant_id')
        
        if not tenant_id:
            return Response(
                {'error': 'tenant_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tenant = Tenant.objects.get(id=tenant_id, is_deleted=False)
            
            # Check permission
            if not request.user.is_staff and tenant.owner != request.user:
                user_tenants = Tenant.objects.filter(
                    Q(owner=request.user) | Q(parent_tenant__owner=request.user),
                    is_deleted=False
                )
                if tenant not in user_tenants:
                    return Response(
                        {'error': 'Permission denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            queryset = self.get_queryset().filter(tenant=tenant)
            serializer = self.get_serializer(queryset, many=True)
            
            return Response(serializer.data)
            
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def tenant_statistics(self, request):
        """Get statistics grouped by tenant."""
        queryset = self.get_queryset()
        
        stats = {}
        for tenant in Tenant.objects.filter(is_deleted=False):
            tenant_objects = queryset.filter(tenant=tenant)
            stats[tenant.id] = {
                'tenant_name': tenant.name,
                'tenant_slug': tenant.slug,
                'count': tenant_objects.count(),
                'active_count': tenant_objects.filter(is_active=True).count(),
            }
        
        return Response(stats)


class BaseAdminViewSet(BaseTenantViewSet):
    """
    Base ViewSet for admin operations.
    
    Provides admin-specific functionality and permissions.
    """
    
    def get_permissions(self):
        """Get permissions based on action."""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_delete', 'bulk_update']:
            self.permission_classes = [IsAuthenticated]
        else:
            self.permission_classes = [IsAuthenticated]
        
        return super().get_permissions()
    
    def check_admin_permissions(self, request):
        """Check if user has admin permissions."""
        return request.user.is_staff or request.user.is_superuser
    
    def create(self, request, *args, **kwargs):
        """Create with admin permission check."""
        if not self.check_admin_permissions(request):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update with admin permission check."""
        if not self.check_admin_permissions(request):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete with admin permission check."""
        if not self.check_admin_permissions(request):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def admin_statistics(self, request):
        """Get admin-level statistics."""
        if not self.check_admin_permissions(request):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset()
        
        stats = {
            'total_count': queryset.count(),
            'active_count': queryset.filter(is_active=True).count(),
            'inactive_count': queryset.filter(is_active=False).count(),
            'created_today': queryset.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'created_this_week': queryset.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'created_this_month': queryset.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
            'updated_today': queryset.filter(
                updated_at__date=timezone.now().date()
            ).count(),
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def admin_bulk_delete(self, request):
        """Admin bulk delete with permission check."""
        if not self.check_admin_permissions(request):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().bulk_delete(request)
    
    @action(detail=False, methods=['post'])
    def admin_bulk_update(self, request):
        """Admin bulk update with permission check."""
        if not self.check_admin_permissions(request):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().bulk_update(request)


class BaseReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Base read-only ViewSet for tenant management operations.
    
    Provides read-only functionality with permission checking.
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            # Staff users can see all objects
            return self.queryset.filter(is_deleted=False)
        else:
            # Non-staff users can only see their own objects
            return self.queryset.filter(
                Q(owner=user) | Q(tenant__owner=user),
                is_deleted=False
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics for the model."""
        queryset = self.get_queryset()
        
        stats = {
            'total_count': queryset.count(),
            'active_count': queryset.filter(is_active=True).count(),
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export data to CSV."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        format_type = request.query_params.get('format', 'csv')
        
        try:
            if format_type == 'csv':
                csv_data = self._export_to_csv()
                return Response(csv_data, content_type='text/csv')
            elif format_type == 'json':
                json_data = self._export_to_json()
                return Response(json_data, content_type='application/json')
            else:
                return Response(
                    {'error': 'Invalid format. Use csv or json'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_to_csv(self):
        """Export queryset to CSV format."""
        import csv
        from io import StringIO
        
        queryset = self.get_queryset()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        if queryset.exists():
            headers = list(queryset.first().__dict__.keys())
            writer.writerow(headers)
            
            # Write data rows
            for obj in queryset:
                row = [getattr(obj, field, '') for field in headers]
                writer.writerow(row)
        
        return output.getvalue()
    
    def _export_to_json(self):
        """Export queryset to JSON format."""
        import json
        
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return json.dumps(serializer.data, indent=2)
