"""Webhook Template ViewSet

This module contains the ViewSet for webhook template management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookTemplate, WebhookEndpoint
from ..serializers import (
    WebhookTemplateSerializer,
    WebhookTemplateCreateSerializer,
    WebhookTemplateUpdateSerializer,
    WebhookTemplateDetailSerializer,
    WebhookTemplateListSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import WebhookTemplateFilter


class WebhookTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook template management."""
    
    queryset = WebhookTemplate.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WebhookTemplateFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'create':
            return WebhookTemplateCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return WebhookTemplateUpdateSerializer
        elif self.action == 'retrieve':
            return WebhookTemplateDetailSerializer
        elif self.action == 'list':
            return WebhookTemplateListSerializer
        else:
            return WebhookTemplateSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own templates."""
        return super().get_queryset().filter(created_by=self.request.user)
    
    def perform_create(self, serializer):
        """Set created_by field on creation."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a template."""
        template = self.get_object()
        template.is_active = True
        template.save()
        
        serializer = self.get_serializer(template)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a template."""
        template = self.get_object()
        template.is_active = False
        template.save()
        
        serializer = self.get_serializer(template)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Preview template rendering with sample data."""
        template = self.get_object()
        
        sample_payload = request.data.get('sample_payload', {
            'user_id': 12345,
            'email': 'test@example.com',
            'amount': 100.00,
            'status': 'active',
            'created_at': timezone.now().isoformat()
        })
        
        try:
            from ..services.core import TemplateEngine
            template_engine = TemplateEngine()
            
            rendered = template_engine.render_template(
                template.payload_template,
                sample_payload
            )
            
            return Response({
                'success': True,
                'template_id': str(template.id),
                'template_name': template.name,
                'sample_payload': sample_payload,
                'rendered_payload': rendered,
                'message': 'Template preview generated successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Template preview failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test the template with sample data and send to endpoint."""
        template = self.get_object()
        
        endpoint_id = request.data.get('endpoint_id')
        if not endpoint_id:
            return Response({
                'error': 'endpoint_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get endpoint
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
            
            # Prepare sample payload
            sample_payload = request.data.get('sample_payload', {
                'user_id': 12345,
                'email': 'test@example.com',
                'amount': 100.00,
                'status': 'active',
                'created_at': timezone.now().isoformat()
            })
            
            # Render template
            from ..services.core import TemplateEngine
            template_engine = TemplateEngine()
            
            rendered_payload = template_engine.render_template(
                template.payload_template,
                sample_payload
            )
            
            # Send test webhook
            from ..services.core import DispatchService
            dispatch_service = DispatchService()
            
            result = dispatch_service.emit(
                endpoint=endpoint,
                event_type='webhook.template.test',
                payload=rendered_payload
            )
            
            return Response({
                'success': result,
                'template_id': str(template.id),
                'template_name': template.name,
                'endpoint_id': str(endpoint_id),
                'sample_payload': sample_payload,
                'rendered_payload': rendered_payload,
                'message': 'Template test webhook sent successfully' if result else 'Template test webhook failed'
            })
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Template test failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone a template."""
        template = self.get_object()
        
        new_name = request.data.get('name', f"{template.name} (Clone)")
        
        try:
            new_template = WebhookTemplate.objects.create(
                name=new_name,
                description=template.description,
                event_type=template.event_type,
                payload_template=template.payload_template,
                schema_validation=template.schema_validation,
                required_fields=template.required_fields,
                is_active=False,  # Start as inactive
                created_by=request.user
            )
            
            serializer = self.get_serializer(new_template)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'error': str(e),
                'message': 'Template clone failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get template statistics."""
        template = self.get_object()
        
        # Get usage statistics
        endpoint_count = template.endpoints.count()
        
        # Get delivery statistics for templates
        from ..models import WebhookDeliveryLog
        
        template_deliveries = WebhookDeliveryLog.objects.filter(
            endpoint__payload_template=template
        )
        
        total_deliveries = template_deliveries.count()
        successful_deliveries = template_deliveries.filter(status='success').count()
        failed_deliveries = template_deliveries.filter(status='failed').count()
        success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        
        # Get last used time
        last_delivery = template_deliveries.order_by('-created_at').first()
        last_used_at = last_delivery.created_at if last_delivery else None
        
        return Response({
            'template_id': str(template.id),
            'template_name': template.name,
            'endpoint_count': endpoint_count,
            'total_deliveries': total_deliveries,
            'successful_deliveries': successful_deliveries,
            'failed_deliveries': failed_deliveries,
            'success_rate': round(success_rate, 2),
            'last_used_at': last_used_at.isoformat() if last_used_at else None,
            'created_at': template.created_at,
            'updated_at': template.updated_at
        })
    
    @action(detail=False, methods=['get'])
    def by_event_type(self, request):
        """Get templates by event type."""
        event_type = request.query_params.get('event_type')
        if not event_type:
            return Response({
                'error': 'event_type parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        templates = self.queryset.filter(event_type=event_type)
        
        page = self.paginate_queryset(templates)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Activate multiple templates."""
        template_ids = request.data.get('template_ids', [])
        if not template_ids:
            return Response({
                'error': 'template_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        templates = self.queryset.filter(id__in=template_ids)
        updated_count = templates.update(is_active=True)
        
        return Response({
            'message': f'Activated {updated_count} templates',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Deactivate multiple templates."""
        template_ids = request.data.get('template_ids', [])
        if not template_ids:
            return Response({
                'error': 'template_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        templates = self.queryset.filter(id__in=template_ids)
        updated_count = templates.update(is_active=False)
        
        return Response({
            'message': f'Deactivated {updated_count} templates',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['post'])
    def validate_template(self, request):
        """Validate template syntax."""
        payload_template = request.data.get('payload_template')
        test_data = request.data.get('test_data', {
            'user_id': 12345,
            'email': 'test@example.com'
        })
        
        if not payload_template:
            return Response({
                'error': 'payload_template parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from ..services.core import TemplateEngine
            template_engine = TemplateEngine()
            
            # Test template rendering
            rendered = template_engine.render_template(payload_template, test_data)
            
            return Response({
                'valid': True,
                'payload_template': payload_template,
                'test_data': test_data,
                'rendered_output': rendered,
                'message': 'Template syntax is valid'
            })
        except Exception as e:
            return Response({
                'valid': False,
                'error': str(e),
                'message': 'Template syntax is invalid'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular templates."""
        templates = self.queryset.annotate(
            endpoint_count=models.Count('endpoints')
        ).filter(endpoint_count__gt=0).order_by('-endpoint_count')[:10]
        
        serializer = self.get_serializer(templates, many=True)
        return Response({
            'templates': serializer.data,
            'total_count': len(serializer.data)
        })
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recently used templates."""
        from ..models import WebhookDeliveryLog
        
        # Get templates used in recent deliveries
        recent_template_ids = WebhookDeliveryLog.objects.filter(
            endpoint__owner=request.user,
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).values_list('endpoint__payload_template', flat=True).distinct()
        
        templates = self.queryset.filter(id__in=recent_template_ids)
        
        serializer = self.get_serializer(templates, many=True)
        return Response({
            'templates': serializer.data,
            'total_count': len(serializer.data)
        })
