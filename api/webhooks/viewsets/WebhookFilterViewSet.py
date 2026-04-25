"""Webhook Filter ViewSet

This module contains the ViewSet for webhook filter management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookFilter, WebhookEndpoint
from ..serializers import (
    WebhookFilterSerializer,
    WebhookFilterCreateSerializer,
    WebhookFilterUpdateSerializer,
    WebhookFilterDetailSerializer,
    WebhookFilterListSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import WebhookFilterFilter


class WebhookFilterViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook filter management."""
    
    queryset = WebhookFilter.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WebhookFilterFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'create':
            return WebhookFilterCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return WebhookFilterUpdateSerializer
        elif self.action == 'retrieve':
            return WebhookFilterDetailSerializer
        elif self.action == 'list':
            return WebhookFilterListSerializer
        else:
            return WebhookFilterSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own filters."""
        return super().get_queryset().filter(endpoint__owner=self.request.user)
    
    def perform_create(self, serializer):
        """Set created_by field on creation."""
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a filter."""
        webhook_filter = self.get_object()
        webhook_filter.is_active = True
        webhook_filter.save()
        
        serializer = self.get_serializer(webhook_filter)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a filter."""
        webhook_filter = self.get_object()
        webhook_filter.is_active = False
        webhook_filter.save()
        
        serializer = self.get_serializer(webhook_filter)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test the filter with sample data."""
        webhook_filter = self.get_object()
        
        test_payload = request.data.get('test_payload', {
            'user_id': 12345,
            'email': 'test@example.com',
            'amount': 100.00,
            'status': 'active'
        })
        
        try:
            from ..services.filtering import FilterService
            filter_service = FilterService()
            
            result = filter_service.evaluate_filter(
                webhook_filter.filter_config,
                test_payload
            )
            
            return Response({
                'success': True,
                'filter_id': str(webhook_filter.id),
                'field_path': webhook_filter.field_path,
                'operator': webhook_filter.operator,
                'value': webhook_filter.value,
                'test_payload': test_payload,
                'result': result,
                'message': 'Filter test completed'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Filter test failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get filter statistics."""
        webhook_filter = self.get_object()
        
        # Get subscription statistics
        from ..models import WebhookSubscription, WebhookDeliveryLog
        
        # Get deliveries that match this filter
        matching_deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=webhook_filter.endpoint,
            created_at__gte=webhook_filter.created_at
        )
        
        # Test filter against deliveries (this could be optimized)
        from ..services.filtering import FilterService
        filter_service = FilterService()
        
        matched_count = 0
        total_count = matching_deliveries.count()
        
        for delivery in matching_deliveries[:100]:  # Limit to 100 for performance
            try:
                if filter_service.evaluate_filter(
                    webhook_filter.filter_config,
                    delivery.payload
                ):
                    matched_count += 1
            except:
                continue
        
        # Estimate total matches
        estimated_matches = (matched_count / total_count * 100) if total_count > 0 else 0
        
        return Response({
            'filter_id': str(webhook_filter.id),
            'field_path': webhook_filter.field_path,
            'operator': webhook_filter.operator,
            'value': webhook_filter.value,
            'is_active': webhook_filter.is_active,
            'total_deliveries_tested': total_count,
            'matched_deliveries': matched_count,
            'estimated_match_rate': round(estimated_matches, 2),
            'created_at': webhook_filter.created_at,
            'updated_at': webhook_filter.updated_at
        })
    
    @action(detail=False, methods=['get'])
    def by_endpoint(self, request):
        """Get filters by endpoint ID."""
        endpoint_id = request.query_params.get('endpoint_id')
        if not endpoint_id:
            return Response({
                'error': 'endpoint_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        filters = self.queryset.filter(endpoint=endpoint)
        
        page = self.paginate_queryset(filters)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(filters, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Activate multiple filters."""
        filter_ids = request.data.get('filter_ids', [])
        if not filter_ids:
            return Response({
                'error': 'filter_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        filters = self.queryset.filter(id__in=filter_ids)
        updated_count = filters.update(is_active=True)
        
        return Response({
            'message': f'Activated {updated_count} filters',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Deactivate multiple filters."""
        filter_ids = request.data.get('filter_ids', [])
        if not filter_ids:
            return Response({
                'error': 'filter_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        filters = self.queryset.filter(id__in=filter_ids)
        updated_count = filters.update(is_active=False)
        
        return Response({
            'message': f'Deactivated {updated_count} filters',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['post'])
    def validate_filter(self, request):
        """Validate filter configuration."""
        filter_config = request.data.get('filter_config')
        test_payload = request.data.get('test_payload', {
            'user_id': 12345,
            'email': 'test@example.com'
        })
        
        if not filter_config:
            return Response({
                'error': 'filter_config parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from ..services.filtering import FilterService
            filter_service = FilterService()
            
            # Validate filter configuration
            filter_service.validate_filter_config(filter_config)
            
            # Test filter
            result = filter_service.evaluate_filter(filter_config, test_payload)
            
            return Response({
                'valid': True,
                'filter_config': filter_config,
                'test_payload': test_payload,
                'result': result,
                'message': 'Filter configuration is valid'
            })
        except Exception as e:
            return Response({
                'valid': False,
                'error': str(e),
                'message': 'Filter configuration is invalid'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def common_fields(self, request):
        """Get common filter fields."""
        common_fields = [
            {
                'field_path': 'user_id',
                'description': 'User ID field',
                'data_type': 'integer',
                'common_operators': ['equals', 'not_equals', 'in', 'not_in']
            },
            {
                'field_path': 'email',
                'description': 'Email field',
                'data_type': 'string',
                'common_operators': ['equals', 'not_equals', 'contains', 'starts_with', 'ends_with']
            },
            {
                'field_path': 'amount',
                'description': 'Amount field',
                'data_type': 'number',
                'common_operators': ['equals', 'not_equals', 'greater_than', 'less_than', 'between']
            },
            {
                'field_path': 'status',
                'description': 'Status field',
                'data_type': 'string',
                'common_operators': ['equals', 'not_equals', 'in', 'not_in']
            },
            {
                'field_path': 'created_at',
                'description': 'Created at field',
                'data_type': 'datetime',
                'common_operators': ['equals', 'not_equals', 'greater_than', 'less_than', 'between']
            },
            {
                'field_path': 'event_type',
                'description': 'Event type field',
                'data_type': 'string',
                'common_operators': ['equals', 'not_equals', 'contains', 'in', 'not_in']
            }
        ]
        
        return Response({
            'common_fields': common_fields,
            'total_count': len(common_fields)
        })
    
    @action(detail=False, methods=['get'])
    def operators(self, request):
        """Get available filter operators."""
        operators = [
            {
                'operator': 'equals',
                'description': 'Exact match',
                'data_types': ['string', 'integer', 'number', 'boolean', 'datetime']
            },
            {
                'operator': 'not_equals',
                'description': 'Not equal to',
                'data_types': ['string', 'integer', 'number', 'boolean', 'datetime']
            },
            {
                'operator': 'contains',
                'description': 'Contains substring',
                'data_types': ['string']
            },
            {
                'operator': 'not_contains',
                'description': 'Does not contain substring',
                'data_types': ['string']
            },
            {
                'operator': 'starts_with',
                'description': 'Starts with',
                'data_types': ['string']
            },
            {
                'operator': 'ends_with',
                'description': 'Ends with',
                'data_types': ['string']
            },
            {
                'operator': 'in',
                'description': 'In list of values',
                'data_types': ['string', 'integer', 'number', 'boolean']
            },
            {
                'operator': 'not_in',
                'description': 'Not in list of values',
                'data_types': ['string', 'integer', 'number', 'boolean']
            },
            {
                'operator': 'greater_than',
                'description': 'Greater than',
                'data_types': ['integer', 'number', 'datetime']
            },
            {
                'operator': 'less_than',
                'description': 'Less than',
                'data_types': ['integer', 'number', 'datetime']
            },
            {
                'operator': 'between',
                'description': 'Between two values',
                'data_types': ['integer', 'number', 'datetime']
            },
            {
                'operator': 'exists',
                'description': 'Field exists',
                'data_types': ['any']
            },
            {
                'operator': 'not_exists',
                'description': 'Field does not exist',
                'data_types': ['any']
            }
        ]
        
        return Response({
            'operators': operators,
            'total_count': len(operators)
        })
