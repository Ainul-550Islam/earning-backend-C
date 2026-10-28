"""
Enhanced ViewSet Module
Advanced ViewSet base classes and utilities for security module
"""
from django.conf import settings

import logging
from typing import Dict, List, Any, Optional, Type, Union
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, Sum
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .mixins import SecurityAuditMixin, RateLimitMixin, SecurityHeadersMixin
from .registry import security_registry
from .permissions import IsSecurityAdmin, IsOwnerOrStaff as IsOwnerOrSecurityAdmin
from typing import Dict, List, Any, Optional, Type, Callable
from django.db.models import Q
from .registry import security_registry, ComponentType

User = get_user_model()
logger = logging.getLogger('security.viewset')


class BaseSecurityViewSet(
    SecurityAuditMixin,
    RateLimitMixin,
    SecurityHeadersMixin,
    viewsets.ModelViewSet
):
    """Base ViewSet for security module with common functionality"""
    
    # Default permissions
    permission_classes = [permissions.IsAuthenticated]
    
    # Default filter backends
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    
    # Rate limiting configuration
    rate_limit_config = {
        'limit': 1000,  # 1000 requests per hour
        'window': 3600
    }
    
    # Pagination
    pagination_class = PageNumberPagination
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_queryset(self):
        """Get base queryset with user filtering"""
        queryset = super().get_queryset()
        
        # Non-admin users can only see their own data
        if not self.request.user.is_superuser and not getattr(self.request.user, 'is_security_admin', False):
            if hasattr(queryset.model, 'user'):
                queryset = queryset.filter(user=self.request.user)
        
        return queryset
    
    def get_serializer_class(self):
        """Get appropriate serializer class based on action"""
        if self.action == 'list':
            return getattr(self, 'list_serializer_class', self.serializer_class)
        elif self.action == 'create':
            return getattr(self, 'create_serializer_class', self.serializer_class)
        elif self.action in ['update', 'partial_update']:
            return getattr(self, 'update_serializer_class', self.serializer_class)
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Perform create with audit logging"""
        # Add user if model has user field
        if hasattr(serializer.Meta.model, 'user'):
            serializer.save(user=self.request.user)
        else:
            serializer.save()
    
    def list(self, request, *args, **kwargs):
        """Enhanced list with statistics"""
        response = super().list(request, *args, **kwargs)
        
        # Add statistics if requested
        if request.query_params.get('include_stats') == 'true':
            stats = self.get_queryset_stats()
            response.data['statistics'] = stats
        
        return response
    
    def get_queryset_stats(self) -> Dict[str, Any]:
        """Get queryset statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_count': queryset.count(),
        }
        
        # Add field-specific statistics
        if hasattr(queryset.model, 'severity'):
            severity_stats = queryset.values('severity').annotate(count=Count('id'))
            stats['by_severity'] = {item['severity']: item['count'] for item in severity_stats}
        
        if hasattr(queryset.model, 'status'):
            status_stats = queryset.values('status').annotate(count=Count('id'))
            stats['by_status'] = {item['status']: item['count'] for item in status_stats}
        
        if hasattr(queryset.model, 'created_at'):
            date_stats = queryset.extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(count=Count('id')).order_by('day')[:30]
            stats['by_date'] = list(date_stats)
        
        return stats
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get detailed statistics"""
        return Response(self.get_queryset_stats())
    
    @action(detail=False, methods=['get'])
    def metadata(self, request):
        """Get ViewSet metadata"""
        meta = {
            'model': self.queryset.model.__name__,
            'fields': [field.name for field in self.queryset.model._meta.fields],
            'filters': self.get_filter_fields(),
            'ordering': self.get_ordering_fields(),
            'search': self.get_search_fields(),
            'actions': self.get_available_actions(),
            'permissions': self.get_permission_info(),
        }
        return Response(meta)
    
    def get_filter_fields(self) -> List[str]:
        """Get available filter fields"""
        if hasattr(self, 'filterset_fields'):
            return list(self.filterset_fields.keys()) if isinstance(self.filterset_fields, dict) else self.filterset_fields
        return []
    
    def get_ordering_fields(self) -> List[str]:
        """Get available ordering fields"""
        return getattr(self, 'ordering_fields', [])
    
    def get_search_fields(self) -> List[str]:
        """Get available search fields"""
        return getattr(self, 'search_fields', [])
    
    def get_available_actions(self) -> List[str]:
        """Get available actions"""
        actions = ['list', 'create', 'retrieve', 'update', 'partial_update', 'destroy']
        
        # Add custom actions
        for method_name in dir(self):
            if hasattr(getattr(self, method_name), 'mapping'):
                actions.append(method_name)
        
        return actions
    
    def get_permission_info(self) -> Dict[str, Any]:
        """Get permission information"""
        return {
            'authenticated_required': True,
            'admin_required': any(
                perm.__class__.__name__ in ['IsAdminUser', 'IsSecurityAdmin']
                for perm in self.permission_classes
            ),
            'owner_access': any(
                perm.__class__.__name__ == 'IsOwnerOrSecurityAdmin'
                for perm in self.permission_classes
            )
        }


class SecurityAdminViewSet(BaseSecurityViewSet):
    """ViewSet for security administrators"""
    
    permission_classes = [permissions.IsAuthenticated, IsSecurityAdmin]
    
    def get_queryset(self):
        """Admin can see all data"""
        return super().get_queryset()
    
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """Bulk approve items"""
        ids = request.data.get('ids', [])
        
        if not ids:
            return Response({'error': 'IDs required'}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(id__in=ids)
        count = queryset.count()
        
        # Approve logic depends on model
        if hasattr(queryset.model, 'is_active'):
            queryset.update(is_active=True)
        elif hasattr(queryset.model, 'status'):
            queryset.update(status='approved')
        else:
            return Response({'error': 'Model does not support approval'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'approved_count': count})
    
    @action(detail=False, methods=['post'])
    def bulk_reject(self, request):
        """Bulk reject items"""
        ids = request.data.get('ids', [])
        reason = request.data.get('reason', 'Rejected by admin')
        
        if not ids:
            return Response({'error': 'IDs required'}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(id__in=ids)
        count = queryset.count()
        
        # Reject logic depends on model
        if hasattr(queryset.model, 'is_active'):
            queryset.update(is_active=False)
        elif hasattr(queryset.model, 'status'):
            queryset.update(status='rejected')
        else:
            return Response({'error': 'Model does not support rejection'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Log the action
        for item in queryset:
            self._log_admin_action('bulk_reject', item, reason)
        
        return Response({'rejected_count': count})
    
    def _log_admin_action(self, action: str, instance, reason: str = '') -> None:
        """Log admin action"""
        try:
            from .models import SecurityLog
            
            SecurityLog.objects.create(
                user=self.request.user,
                security_type='admin_action',
                severity='medium',
                description=f'Admin {action}: {instance.__class__.__name__}',
                metadata={
                    'action': action,
                    'instance_id': instance.id,
                    'instance_type': instance.__class__.__name__,
                    'reason': reason
                }
            )
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")


class ReadOnlySecurityViewSet(BaseSecurityViewSet):
    """Read-only ViewSet for security data"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        """Disable create"""
        return Response({'error': 'Create operation not allowed'}, status=status.HTTP_403_FORBIDDEN)
    
    def update(self, request, *args, **kwargs):
        """Disable update"""
        return Response({'error': 'Update operation not allowed'}, status=status.HTTP_403_FORBIDDEN)
    
    def partial_update(self, request, *args, **kwargs):
        """Disable partial update"""
        return Response({'error': 'Update operation not allowed'}, status=status.HTTP_403_FORBIDDEN)
    
    def destroy(self, request, *args, **kwargs):
        """Disable destroy"""
        return Response({'error': 'Delete operation not allowed'}, status=status.HTTP_403_FORBIDDEN)


class ConfigurableViewSet(BaseSecurityViewSet):
    """ViewSet with configurable behavior"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._config = self.get_viewset_config()
    
    def get_viewset_config(self) -> Dict[str, Any]:
        """Get ViewSet configuration from registry or settings"""
        config_name = f"viewset_{self.__class__.__name__.lower()}"
        
        # Try to get from registry
        registration = security_registry.get_component(config_name)
        if registration:
            return registration.config
        
        # Try to get from settings
        return getattr(settings, f'SECURITY_{config_name.upper()}_CONFIG', {})
    
    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Get rate limit configuration"""
        return self._config.get('rate_limit', super().rate_limit_config)
    
    def get_pagination_config(self) -> Dict[str, Any]:
        """Get pagination configuration"""
        return self._config.get('pagination', {
            'page_size': self.page_size,
            'max_page_size': self.max_page_size
        })
    
    def get_filter_config(self) -> Dict[str, Any]:
        """Get filter configuration"""
        return self._config.get('filters', {})
    
    def get_permission_config(self) -> Dict[str, Any]:
        """Get permission configuration"""
        return self._config.get('permissions', {})


class MultiModelViewSet(BaseSecurityViewSet):
    """ViewSet that handles multiple related models"""
    
    model_map = {}  # Override in subclasses
    
    def get_model_class(self, model_name: str) -> Type:
        """Get model class by name"""
        if model_name not in self.model_map:
            raise ValueError(f"Model '{model_name}' not supported")
        return self.model_map[model_name]
    
    def get_queryset(self):
        """Get queryset based on model parameter"""
        model_name = self.request.query_params.get('model')
        if model_name:
            model_class = self.get_model_class(model_name)
            return model_class.objects.all()
        return super().get_queryset()
    
    def get_serializer_class(self):
        """Get serializer based on model and action"""
        model_name = self.request.query_params.get('model')
        if model_name:
            # Try to get model-specific serializer
            serializer_name = f"{model_name.title()}Serializer"
            if hasattr(self, serializer_name):
                return getattr(self, serializer_name)
        
        return super().get_serializer_class()
    
    @action(detail=False, methods=['get'])
    def models(self, request):
        """Get available models"""
        return Response({
            'available_models': list(self.model_map.keys()),
            'current_model': self.request.query_params.get('model')
        })


class RealTimeViewSet(BaseSecurityViewSet):
    """ViewSet with real-time capabilities"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._websocket_enabled = self._config.get('websocket_enabled', False)
    
    @action(detail=False, methods=['get'])
    def stream(self, request):
        """Stream real-time updates"""
        if not self._websocket_enabled:
            return Response({'error': 'WebSocket streaming not enabled'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        
        # This would typically be handled by WebSocket consumers
        return Response({
            'message': 'WebSocket streaming available',
            'endpoint': f"/ws/security/{self.__class__.__name__.lower()}/"
        })
    
    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """Subscribe to real-time updates"""
        if not self._websocket_enabled:
            return Response({'error': 'WebSocket streaming not enabled'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        
        # Add user to subscription list
        subscription_key = f"security_subscriptions_{self.__class__.__name__.lower()}"
        subscriptions = cache.get(subscription_key, [])
        
        user_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'subscribed_at': timezone.now().isoformat(),
            'filters': request.data.get('filters', {})
        }
        
        subscriptions.append(user_data)
        cache.set(subscription_key, subscriptions, timeout=3600)  # 1 hour
        
        return Response({'message': 'Subscribed to real-time updates'})
    
    @action(detail=False, methods=['post'])
    def unsubscribe(self, request):
        """Unsubscribe from real-time updates"""
        if not self._websocket_enabled:
            return Response({'error': 'WebSocket streaming not enabled'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        
        # Remove user from subscription list
        subscription_key = f"security_subscriptions_{self.__class__.__name__.lower()}"
        subscriptions = cache.get(subscription_key, [])
        
        subscriptions = [
            sub for sub in subscriptions 
            if sub['user_id'] != request.user.id
        ]
        
        cache.set(subscription_key, subscriptions, timeout=3600)
        
        return Response({'message': 'Unsubscribed from real-time updates'})


# ViewSet factory utilities
class ViewSetFactory:
    """Factory for creating ViewSets with common patterns"""
    
    @staticmethod
    def create_admin_viewset(model_class: Type, serializer_class: Type, 
                            capabilities: List[str] = None) -> Type[BaseSecurityViewSet]:
        """Create admin ViewSet with standard capabilities"""
        
        class_name = f"{model_class.__name__}AdminViewSet"
        
        attrs = {
            'queryset': model_class.objects.all(),
            'serializer_class': serializer_class,
            'permission_classes': [permissions.IsAuthenticated, IsSecurityAdmin],
        }
        
        # Create ViewSet class
        viewset_class = type(class_name, (SecurityAdminViewSet,), attrs)
        
        # Apply capabilities if specified
        if capabilities:
            viewset_class = with_capabilities(*capabilities)(viewset_class)
        
        return viewset_class
    
    @staticmethod
    def create_readonly_viewset(model_class: Type, serializer_class: Type,
                               capabilities: List[str] = None) -> Type[BaseSecurityViewSet]:
        """Create read-only ViewSet"""
        
        class_name = f"{model_class.__name__}ReadOnlyViewSet"
        
        attrs = {
            'queryset': model_class.objects.all(),
            'serializer_class': serializer_class,
            'permission_classes': [permissions.IsAuthenticated],
        }
        
        # Create ViewSet class
        viewset_class = type(class_name, (ReadOnlySecurityViewSet,), attrs)
        
        # Apply capabilities if specified
        if capabilities:
            viewset_class = with_capabilities(*capabilities)(viewset_class)
        
        return viewset_class
    
    @staticmethod
    def create_user_viewset(model_class: Type, serializer_class: Type,
                          capabilities: List[str] = None) -> Type[BaseSecurityViewSet]:
        """Create user-specific ViewSet"""
        
        class_name = f"{model_class.__name__}UserViewSet"
        
        attrs = {
            'queryset': model_class.objects.all(),
            'serializer_class': serializer_class,
            'permission_classes': [permissions.IsAuthenticated, IsOwnerOrSecurityAdmin],
        }
        
        # Create ViewSet class
        viewset_class = type(class_name, (BaseSecurityViewSet,), attrs)
        
        # Apply capabilities if specified
        if capabilities:
            viewset_class = with_capabilities(*capabilities)(viewset_class)
        
        return viewset_class


# Export classes and utilities
__all__ = [
    'BaseSecurityViewSet',
    'SecurityAdminViewSet',
    'ReadOnlySecurityViewSet',
    'AuditTrailViewSet',
    'ConfigurableViewSet',
    'MultiModelViewSet',
    'RealTimeViewSet',
    'ViewSetFactory'
]



# ============================================================================
# Content migrated from viewset_cap.py
# ============================================================================


class ViewSetCapability:
    """Base class for ViewSet capabilities"""
    
    def __init__(self, name: str, description: str = '', enabled: bool = True):
        self.name = name
        self.description = description
        self.enabled = enabled
    
    def apply_to_viewset(self, viewset_class: Type[viewsets.ModelViewSet]) -> Type[viewsets.ModelViewSet]:
        """Apply capability to a ViewSet class"""
        raise NotImplementedError("Subclasses must implement apply_to_viewset")



class BulkOperationCapability(ViewSetCapability):
    """Capability for bulk operations"""
    
    def __init__(self, max_bulk_size: int = 100, enabled: bool = True):
        super().__init__('bulk_operations', 'Enable bulk CRUD operations', enabled)
        self.max_bulk_size = max_bulk_size
    
    def apply_to_viewset(self, viewset_class: Type[viewsets.ModelViewSet]) -> Type[viewsets.ModelViewSet]:
        """Add bulk operation methods to ViewSet"""
        
        @action(detail=False, methods=['post'])
        def bulk_create(self, request):
            """Bulk create objects"""
            if not self.enabled:
                return Response({'error': 'Bulk operations disabled'}, status=status.HTTP_403_FORBIDDEN)
            
            data = request.data if isinstance(request.data, list) else [request.data]
            
            if len(data) > self.max_bulk_size:
                return Response({
                    'error': f'Bulk size exceeds maximum of {self.max_bulk_size}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(data=data, many=True)
            serializer.is_valid(raise_exception=True)
            
            instances = serializer.save()
            
            # Log bulk operation
            logger.info(f"Bulk created {len(instances)} {self.queryset.model.__name__} objects")
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        @action(detail=False, methods=['patch'])
        def bulk_update(self, request):
            """Bulk update objects"""
            if not self.enabled:
                return Response({'error': 'Bulk operations disabled'}, status=status.HTTP_403_FORBIDDEN)
            
            data = request.data if isinstance(request.data, list) else [request.data]
            
            if len(data) > self.max_bulk_size:
                return Response({
                    'error': f'Bulk size exceeds maximum of {self.max_bulk_size}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            updated_count = 0
            errors = []
            
            for item in data:
                pk = item.get('id')
                if not pk:
                    errors.append({'error': 'ID required for bulk update', 'data': item})
                    continue
                
                try:
                    instance = self.get_queryset().get(pk=pk)
                    serializer = self.get_serializer(instance, data=item, partial=True)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    updated_count += 1
                except Exception as e:
                    errors.append({'id': pk, 'error': str(e)})
            
            logger.info(f"Bulk updated {updated_count} {self.queryset.model.__name__} objects")
            
            return Response({
                'updated_count': updated_count,
                'errors': errors
            })
        
        @action(detail=False, methods=['delete'])
        def bulk_delete(self, request):
            """Bulk delete objects"""
            if not self.enabled:
                return Response({'error': 'Bulk operations disabled'}, status=status.HTTP_403_FORBIDDEN)
            
            ids = request.data.get('ids', [])
            
            if not ids:
                return Response({'error': 'IDs required for bulk delete'}, status=status.HTTP_400_BAD_REQUEST)
            
            if len(ids) > self.max_bulk_size:
                return Response({
                    'error': f'Bulk size exceeds maximum of {self.max_bulk_size}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            deleted_count, _ = self.get_queryset().filter(id__in=ids).delete()
            
            logger.info(f"Bulk deleted {deleted_count} {self.queryset.model.__name__} objects")
            
            return Response({'deleted_count': deleted_count})
        
        # Add methods to ViewSet
        viewset_class.bulk_create = bulk_create
        viewset_class.bulk_update = bulk_update
        viewset_class.bulk_delete = bulk_delete
        
        return viewset_class



class ExportCapability(ViewSetCapability):
    """Capability for data export"""
    
    def __init__(self, supported_formats: List[str] = None, enabled: bool = True):
        super().__init__('export', 'Enable data export functionality', enabled)
        self.supported_formats = supported_formats or ['csv', 'json', 'xlsx']
    
    def apply_to_viewset(self, viewset_class: Type[viewsets.ModelViewSet]) -> Type[viewsets.ModelViewSet]:
        """Add export methods to ViewSet"""
        
        @action(detail=False, methods=['get'])
        def export(self, request):
            """Export data in various formats"""
            if not self.enabled:
                return Response({'error': 'Export functionality disabled'}, status=status.HTTP_403_FORBIDDEN)
            
            export_format = request.query_params.get('format', 'csv')
            
            if export_format not in self.supported_formats:
                return Response({
                    'error': f'Unsupported format. Supported: {", ".join(self.supported_formats)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            queryset = self.get_queryset()
            
            # Apply filters
            queryset = self.filter_queryset(queryset)
            
            # Export based on format
            if export_format == 'csv':
                return self._export_csv(queryset, request)
            elif export_format == 'json':
                return self._export_json(queryset, request)
            elif export_format == 'xlsx':
                return self._export_xlsx(queryset, request)
        
        def _export_csv(self, queryset, request):
            """Export to CSV format"""
            import csv
            from django.http import HttpResponse
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Get field names from serializer
            serializer_class = self.get_serializer_class()
            serializer = serializer_class()
            
            # Write header
            field_names = list(serializer.fields.keys())
            writer.writerow(field_names)
            
            # Write data
            for obj in queryset:
                serializer = serializer_class(obj)
                row = [serializer.data.get(field, '') for field in field_names]
                writer.writerow(row)
            
            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{self.queryset.model.__name__}_export.csv"'
            
            logger.info(f"Exported {queryset.count()} {self.queryset.model.__name__} objects to CSV")
            
            return response
        
        def _export_json(self, queryset, request):
            """Export to JSON format"""
            from django.http import HttpResponse
            import json
            
            serializer_class = self.get_serializer_class()
            serializer = serializer_class(queryset, many=True)
            
            response = HttpResponse(
                json.dumps(serializer.data, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="{self.queryset.model.__name__}_export.json"'
            
            logger.info(f"Exported {queryset.count()} {self.queryset.model.__name__} objects to JSON")
            
            return response
        
        def _export_xlsx(self, queryset, request):
            """Export to Excel format"""
            try:
                import pandas as pd
                from django.http import HttpResponse
                from io import BytesIO
                
                # Convert queryset to DataFrame
                serializer_class = self.get_serializer_class()
                serializer = serializer_class(queryset, many=True)
                
                df = pd.DataFrame(serializer.data)
                
                # Create Excel file
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=self.queryset.model.__name__, index=False)
                
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{self.queryset.model.__name__}_export.xlsx"'
                
                logger.info(f"Exported {queryset.count()} {self.queryset.model.__name__} objects to Excel")
                
                return response
                
            except ImportError:
                return Response({
                    'error': 'Excel export requires pandas and openpyxl packages'
                }, status=status.HTTP_501_NOT_IMPLEMENTED)
        
        # Add methods to ViewSet
        viewset_class.export = export
        viewset_class._export_csv = _export_csv
        viewset_class._export_json = _export_json
        viewset_class._export_xlsx = _export_xlsx
        
        return viewset_class



class AdvancedFilterCapability(ViewSetCapability):
    """Capability for advanced filtering"""
    
    def __init__(self, enabled: bool = True):
        super().__init__('advanced_filter', 'Enable advanced filtering capabilities', enabled)
    
    def apply_to_viewset(self, viewset_class: Type[viewsets.ModelViewSet]) -> Type[viewsets.ModelViewSet]:
        """Add advanced filtering methods to ViewSet"""
        
        @action(detail=False, methods=['get'])
        def advanced_search(self, request):
            """Advanced search with multiple criteria"""
            if not self.enabled:
                return Response({'error': 'Advanced search disabled'}, status=status.HTTP_403_FORBIDDEN)
            
            queryset = self.get_queryset()
            
            # Build complex query from request parameters
            query = Q()
            
            # Text search
            search_text = request.query_params.get('search')
            if search_text:
                # Search in text fields
                text_fields = []
                for field in self.queryset.model._meta.fields:
                    if field.__class__.__name__ in ['CharField', 'TextField']:
                        text_fields.append(field.name)
                
                if text_fields:
                    search_query = Q()
                    for field in text_fields:
                        search_query |= Q(**{f"{field}__icontains": search_text})
                    query &= search_query
            
            # Date range filters
            date_fields = []
            for field in self.queryset.model._meta.fields:
                if field.__class__.__name__ in ['DateTimeField', 'DateField']:
                    date_fields.append(field.name)
            
            for field in date_fields:
                date_from = request.query_params.get(f"{field}_from")
                date_to = request.query_params.get(f"{field}_to")
                
                if date_from:
                    query &= Q(**{f"{field}__gte": date_from})
                if date_to:
                    query &= Q(**{f"{field}__lte": date_to})
            
            # Numeric range filters
            numeric_fields = []
            for field in self.queryset.model._meta.fields:
                if field.__class__.__name__ in ['IntegerField', 'FloatField', 'DecimalField']:
                    numeric_fields.append(field.name)
            
            for field in numeric_fields:
                min_value = request.query_params.get(f"{field}_min")
                max_value = request.query_params.get(f"{field}_max")
                
                if min_value:
                    query &= Q(**{f"{field}__gte": min_value})
                if max_value:
                    query &= Q(**{f"{field}__lte": max_value})
            
            # Apply query
            queryset = queryset.filter(query)
            
            # Apply standard filtering
            queryset = self.filter_queryset(queryset)
            
            # Serialize and return
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        
        @action(detail=False, methods=['get'])
        def filter_options(self, request):
            """Get available filter options"""
            if not self.enabled:
                return Response({'error': 'Filter options disabled'}, status=status.HTTP_403_FORBIDDEN)
            
            options = {
                'text_fields': [],
                'date_fields': [],
                'numeric_fields': [],
                'choice_fields': {}
            }
            
            # Analyze model fields
            for field in self.queryset.model._meta.fields:
                field_name = field.name
                field_type = field.__class__.__name__
                
                if field_type in ['CharField', 'TextField']:
                    options['text_fields'].append(field_name)
                elif field_type in ['DateTimeField', 'DateField']:
                    options['date_fields'].append(field_name)
                elif field_type in ['IntegerField', 'FloatField', 'DecimalField']:
                    options['numeric_fields'].append(field_name)
                elif hasattr(field, 'choices') and field.choices:
                    options['choice_fields'][field_name] = [
                        {'value': choice[0], 'label': choice[1]}
                        for choice in field.choices
                    ]
            
            return Response(options)
        
        # Add methods to ViewSet
        viewset_class.advanced_search = advanced_search
        viewset_class.filter_options = filter_options
        
        return viewset_class



class AuditCapability(ViewSetCapability):
    """Capability for audit logging"""
    
    def __init__(self, log_reads: bool = False, log_writes: bool = True, enabled: bool = True):
        super().__init__('audit', 'Enable audit logging for ViewSet operations', enabled)
        self.log_reads = log_reads
        self.log_writes = log_writes
    
    def apply_to_viewset(self, viewset_class: Type[viewsets.ModelViewSet]) -> Type[viewsets.ModelViewSet]:
        """Add audit logging to ViewSet methods"""
        
        # Wrap existing methods with audit logging
        original_create = viewset_class.create
        original_update = viewset_class.update
        original_partial_update = viewset_class.partial_update
        original_destroy = viewset_class.destroy
        original_list = viewset_class.list
        original_retrieve = viewset_class.retrieve
        
        def audited_create(self, request, *args, **kwargs):
            """Create with audit logging"""
            if self.enabled and self.log_writes:
                self._log_audit_event('create', request, None)
            
            response = original_create(self, request, *args, **kwargs)
            
            if self.enabled and self.log_writes:
                self._log_audit_event('create_success', request, response.data)
            
            return response
        
        def audited_update(self, request, *args, **kwargs):
            """Update with audit logging"""
            instance = self.get_object()
            
            if self.enabled and self.log_writes:
                self._log_audit_event('update', request, instance)
            
            response = original_update(self, request, *args, **kwargs)
            
            if self.enabled and self.log_writes:
                self._log_audit_event('update_success', request, response.data)
            
            return response
        
        def audited_partial_update(self, request, *args, **kwargs):
            """Partial update with audit logging"""
            instance = self.get_object()
            
            if self.enabled and self.log_writes:
                self._log_audit_event('partial_update', request, instance)
            
            response = original_partial_update(self, request, *args, **kwargs)
            
            if self.enabled and self.log_writes:
                self._log_audit_event('partial_update_success', request, response.data)
            
            return response
        
        def audited_destroy(self, request, *args, **kwargs):
            """Destroy with audit logging"""
            instance = self.get_object()
            
            if self.enabled and self.log_writes:
                self._log_audit_event('destroy', request, instance)
            
            response = original_destroy(self, request, *args, **kwargs)
            
            if self.enabled and self.log_writes:
                self._log_audit_event('destroy_success', request, None)
            
            return response
        
        def audited_list(self, request, *args, **kwargs):
            """List with audit logging"""
            if self.enabled and self.log_reads:
                self._log_audit_event('list', request, None)
            
            return original_list(self, request, *args, **kwargs)
        
        def audited_retrieve(self, request, *args, **kwargs):
            """Retrieve with audit logging"""
            instance = self.get_object()
            
            if self.enabled and self.log_reads:
                self._log_audit_event('retrieve', request, instance)
            
            return original_retrieve(self, request, *args, **kwargs)
        
        def _log_audit_event(self, action: str, request, instance_or_data):
            """Log audit event"""
            try:
                from .models import SecurityLog
                
                user = request.user if request.user.is_authenticated else None
                ip_address = self._get_client_ip(request)
                
                # Create description based on action
                descriptions = {
                    'create': f'Created {self.queryset.model.__name__}',
                    'create_success': f'Successfully created {self.queryset.model.__name__}',
                    'update': f'Updated {self.queryset.model.__name__}',
                    'update_success': f'Successfully updated {self.queryset.model.__name__}',
                    'partial_update': f'Partially updated {self.queryset.model.__name__}',
                    'partial_update_success': f'Successfully partially updated {self.queryset.model.__name__}',
                    'destroy': f'Deleted {self.queryset.model.__name__}',
                    'destroy_success': f'Successfully deleted {self.queryset.model.__name__}',
                    'list': f'Listed {self.queryset.model.__name__}',
                    'retrieve': f'Retrieved {self.queryset.model.__name__}'
                }
                
                description = descriptions.get(action, f'{action} on {self.queryset.model.__name__}')
                
                # Prepare metadata
                metadata = {
                    'action': action,
                    'model': self.queryset.model.__name__,
                    'viewset': self.__class__.__name__,
                    'method': request.method,
                    'path': request.path,
                }
                
                if instance_or_data:
                    if hasattr(instance_or_data, 'id'):
                        metadata['instance_id'] = instance_or_data.id
                    elif isinstance(instance_or_data, dict) and 'id' in instance_or_data:
                        metadata['instance_id'] = instance_or_data['id']
                
                SecurityLog.objects.create(
                    user=user,
                    security_type='viewset_operation',
                    severity='info',
                    ip_address=ip_address,
                    description=description,
                    metadata=metadata
                )
                
            except Exception as e:
                logger.error(f"Failed to log audit event: {e}")
        
        def _get_client_ip(self, request):
            """Get client IP address"""
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            return ip or '0.0.0.0'
        
        # Replace methods
        viewset_class.create = audited_create
        viewset_class.update = audited_update
        viewset_class.partial_update = audited_partial_update
        viewset_class.destroy = audited_destroy
        viewset_class.list = audited_list
        viewset_class.retrieve = audited_retrieve
        viewset_class._log_audit_event = _log_audit_event
        viewset_class._get_client_ip = _get_client_ip
        
        return viewset_class



class CacheCapability(ViewSetCapability):
    """Capability for caching ViewSet responses"""
    
    def __init__(self, default_timeout: int = 300, enabled: bool = True):
        super().__init__('cache', 'Enable response caching', enabled)
        self.default_timeout = default_timeout
    
    def apply_to_viewset(self, viewset_class: Type[viewsets.ModelViewSet]) -> Type[viewsets.ModelViewSet]:
        """Add caching to ViewSet methods"""
        
        original_list = viewset_class.list
        original_retrieve = viewset_class.retrieve
        
        def cached_list(self, request, *args, **kwargs):
            """List with caching"""
            if not self.enabled:
                return original_list(self, request, *args, **kwargs)
            
            # Generate cache key
            cache_key = self._generate_cache_key('list', request)
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response)
            
            # Get fresh response
            response = original_list(self, request, *args, **kwargs)
            
            # Cache the response
            if response.status_code == 200:
                cache.set(cache_key, response.data, self.default_timeout)
            
            return response
        
        def cached_retrieve(self, request, *args, **kwargs):
            """Retrieve with caching"""
            if not self.enabled:
                return original_retrieve(self, request, *args, **kwargs)
            
            # Generate cache key
            cache_key = self._generate_cache_key('retrieve', request, kwargs.get('pk'))
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response)
            
            # Get fresh response
            response = original_retrieve(self, request, *args, **kwargs)
            
            # Cache the response
            if response.status_code == 200:
                cache.set(cache_key, response.data, self.default_timeout)
            
            return response
        
        def _generate_cache_key(self, action: str, request, pk: str = None) -> str:
            """Generate cache key"""
            key_parts = [
                'security_viewset',
                self.queryset.model.__name__,
                action,
                request.user.id if request.user.is_authenticated else 'anonymous',
                str(hash(str(request.query_params)))
            ]
            
            if pk:
                key_parts.append(str(pk))
            
            return ':'.join(key_parts)
        
        @action(detail=False, methods=['post'])
        def clear_cache(self, request):
            """Clear cache for this ViewSet"""
            if not self.enabled:
                return Response({'error': 'Cache functionality disabled'}, status=status.HTTP_403_FORBIDDEN)
            
            # Clear all cache keys for this ViewSet
            pattern = f"security_viewset:{self.queryset.model.__name__}:*"
            
            # Note: This is a simplified cache clearing
            # In production, you might want to use Redis pattern matching
            cache_keys = [
                f"security_viewset:{self.queryset.model.__name__}:list:{request.user.id if request.user.is_authenticated else 'anonymous'}",
            ]
            
            for key in cache_keys:
                cache.delete(key)
            
            return Response({'message': 'Cache cleared'})
        
        # Replace methods
        viewset_class.list = cached_list
        viewset_class.retrieve = cached_retrieve
        viewset_class._generate_cache_key = _generate_cache_key
        viewset_class.clear_cache = clear_cache
        
        return viewset_class



class ViewSetCapabilityManager:
    """Manager for applying capabilities to ViewSets"""
    
    def __init__(self):
        self.capabilities: Dict[str, ViewSetCapability] = {}
    
    def register_capability(self, capability: ViewSetCapability) -> None:
        """Register a capability"""
        self.capabilities[capability.name] = capability
    
    def apply_capabilities(self, viewset_class: Type[viewsets.ModelViewSet], 
                          capability_names: List[str]) -> Type[viewsets.ModelViewSet]:
        """Apply multiple capabilities to a ViewSet"""
        for name in capability_names:
            if name in self.capabilities:
                capability = self.capabilities[name]
                viewset_class = capability.apply_to_viewset(viewset_class)
                logger.info(f"Applied capability '{name}' to {viewset_class.__name__}")
            else:
                logger.warning(f"Capability '{name}' not found")
        
        return viewset_class
    
    def get_available_capabilities(self) -> Dict[str, ViewSetCapability]:
        """Get all available capabilities"""
        return self.capabilities.copy()


# Global capability manager
capability_manager = ViewSetCapabilityManager()

# Register default capabilities
capability_manager.register_capability(BulkOperationCapability())
capability_manager.register_capability(ExportCapability())
capability_manager.register_capability(AdvancedFilterCapability())
capability_manager.register_capability(AuditCapability())
capability_manager.register_capability(CacheCapability())


# Decorator for applying capabilities
def with_capabilities(*capability_names):
    """Decorator to apply capabilities to a ViewSet"""
    def decorator(viewset_class: Type[viewsets.ModelViewSet]) -> Type[viewsets.ModelViewSet]:
        return capability_manager.apply_capabilities(viewset_class, list(capability_names))
    
    return decorator


# Export classes and utilities
__all__ = [
    'ViewSetCapability',
    'BulkOperationCapability',
    'ExportCapability',
    'AdvancedFilterCapability',
    'AuditCapability',
    'CacheCapability',
    'ViewSetCapabilityManager',
    'capability_manager',
    'with_capabilities'
]