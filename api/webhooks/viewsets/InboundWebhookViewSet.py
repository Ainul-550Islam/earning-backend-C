"""Inbound Webhook ViewSet

This module contains the ViewSet for inbound webhook management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError
from ..serializers import (
    InboundWebhookSerializer,
    InboundWebhookCreateSerializer,
    InboundWebhookUpdateSerializer,
    InboundWebhookDetailSerializer,
    InboundWebhookListSerializer,
    InboundWebhookProcessSerializer,
    InboundWebhookValidateSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import InboundWebhookFilter


class InboundWebhookViewSet(viewsets.ModelViewSet):
    """ViewSet for inbound webhook management."""
    
    queryset = InboundWebhook.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = InboundWebhookFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'create':
            return InboundWebhookCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return InboundWebhookUpdateSerializer
        elif self.action == 'retrieve':
            return InboundWebhookDetailSerializer
        elif self.action == 'list':
            return InboundWebhookListSerializer
        else:
            return InboundWebhookSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own inbound webhooks."""
        return super().get_queryset().filter(created_by=self.request.user)
    
    def perform_create(self, serializer):
        """Set created_by field on creation."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate an inbound webhook."""
        inbound_webhook = self.get_object()
        inbound_webhook.is_active = True
        inbound_webhook.save()
        
        serializer = self.get_serializer(inbound_webhook)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an inbound webhook."""
        inbound_webhook = self.get_object()
        inbound_webhook.is_active = False
        inbound_webhook.save()
        
        serializer = self.get_serializer(inbound_webhook)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process an inbound webhook."""
        inbound_webhook = self.get_object()
        
        serializer = InboundWebhookProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            from ..services.inbound import InboundWebhookService
            service = InboundWebhookService()
            
            result = service.process_inbound_webhook(
                inbound=inbound_webhook,
                payload=serializer.validated_data['raw_payload'],
                headers=serializer.validated_data.get('headers', {}),
                signature=serializer.validated_data.get('signature'),
                ip_address=serializer.validated_data.get('ip_address')
            )
            
            return Response({
                'success': result['success'],
                'inbound_webhook_id': str(inbound_webhook.id),
                'source': inbound_webhook.source,
                'processed': result.get('processed', False),
                'message': result.get('message', 'Webhook processed successfully')
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Webhook processing failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate_signature(self, request, pk=None):
        """Validate signature for an inbound webhook."""
        inbound_webhook = self.get_object()
        
        serializer = InboundWebhookValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            from ..services.signature_engine import SignatureEngine
            signature_engine = SignatureEngine()
            
            is_valid = signature_engine.verify_signature(
                serializer.validated_data['signature'],
                serializer.validated_data['payload'],
                inbound_webhook.secret
            )
            
            return Response({
                'valid': is_valid,
                'inbound_webhook_id': str(inbound_webhook.id),
                'source': inbound_webhook.source,
                'message': 'Signature is valid' if is_valid else 'Signature is invalid'
            })
        except Exception as e:
            return Response({
                'valid': False,
                'error': str(e),
                'message': 'Signature validation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def rotate_secret(self, request, pk=None):
        """Rotate secret for an inbound webhook."""
        inbound_webhook = self.get_object()
        
        try:
            from ..services.core import SecretRotationService
            rotation_service = SecretRotationService()
            
            new_secret = rotation_service.rotate_inbound_secret(inbound_webhook)
            
            return Response({
                'success': True,
                'inbound_webhook_id': str(inbound_webhook.id),
                'new_secret': new_secret[:8] + "...",  # Only show first 8 chars
                'message': 'Secret rotated successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Secret rotation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get inbound webhook statistics."""
        inbound_webhook = self.get_object()
        
        # Get log statistics
        logs = inbound_webhook.logs.all()
        total_logs = logs.count()
        processed_logs = logs.filter(processed=True).count()
        signature_valid_logs = logs.filter(signature_valid=True).count()
        
        processing_rate = (processed_logs / total_logs * 100) if total_logs > 0 else 0
        signature_validity_rate = (signature_valid_logs / total_logs * 100) if total_logs > 0 else 0
        
        # Get route statistics
        routes = inbound_webhook.routes.all()
        active_routes = routes.filter(is_active=True).count()
        
        # Get last processed time
        last_log = logs.order_by('-created_at').first()
        last_processed_at = last_log.created_at if last_log else None
        
        return Response({
            'inbound_webhook_id': str(inbound_webhook.id),
            'source': inbound_webhook.source,
            'url_token': inbound_webhook.url_token,
            'is_active': inbound_webhook.is_active,
            'total_logs': total_logs,
            'processed_logs': processed_logs,
            'signature_valid_logs': signature_valid_logs,
            'processing_rate': round(processing_rate, 2),
            'signature_validity_rate': round(signature_validity_rate, 2),
            'total_routes': routes.count(),
            'active_routes': active_routes,
            'last_processed_at': last_processed_at.isoformat() if last_processed_at else None,
            'created_at': inbound_webhook.created_at,
            'updated_at': inbound_webhook.updated_at
        })
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get logs for an inbound webhook."""
        inbound_webhook = self.get_object()
        
        logs = inbound_webhook.logs.all()
        
        # Apply filters
        processed_filter = request.query_params.get('processed')
        if processed_filter is not None:
            logs = logs.filter(processed=processed_filter.lower() == 'true')
        
        signature_valid_filter = request.query_params.get('signature_valid')
        if signature_valid_filter is not None:
            logs = logs.filter(signature_valid=signature_valid_filter.lower() == 'true')
        
        # Apply pagination
        page = self.paginate_queryset(logs)
        if page is not None:
            from ..serializers import InboundWebhookLogListSerializer
            serializer = InboundWebhookLogListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        from ..serializers import InboundWebhookLogListSerializer
        serializer = InboundWebhookLogListSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def routes(self, request, pk=None):
        """Get routes for an inbound webhook."""
        inbound_webhook = self.get_object()
        
        routes = inbound_webhook.routes.all()
        
        # Apply filters
        active_filter = request.query_params.get('is_active')
        if active_filter is not None:
            routes = routes.filter(is_active=active_filter.lower() == 'true')
        
        # Apply pagination
        page = self.paginate_queryset(routes)
        if page is not None:
            from ..serializers import InboundWebhookRouteSerializer
            serializer = InboundWebhookRouteSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        from ..serializers import InboundWebhookRouteSerializer
        serializer = InboundWebhookRouteSerializer(routes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_source(self, request):
        """Get inbound webhooks by source."""
        source = request.query_params.get('source')
        if not source:
            return Response({
                'error': 'source parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        inbound_webhooks = self.queryset.filter(source=source)
        
        page = self.paginate_queryset(inbound_webhooks)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(inbound_webhooks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Activate multiple inbound webhooks."""
        inbound_webhook_ids = request.data.get('inbound_webhook_ids', [])
        if not inbound_webhook_ids:
            return Response({
                'error': 'inbound_webhook_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        inbound_webhooks = self.queryset.filter(id__in=inbound_webhook_ids)
        updated_count = inbound_webhooks.update(is_active=True)
        
        return Response({
            'message': f'Activated {updated_count} inbound webhooks',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Deactivate multiple inbound webhooks."""
        inbound_webhook_ids = request.data.get('inbound_webhook_ids', [])
        if not inbound_webhook_ids:
            return Response({
                'error': 'inbound_webhook_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        inbound_webhooks = self.queryset.filter(id__in=inbound_webhook_ids)
        updated_count = inbound_webhooks.update(is_active=False)
        
        return Response({
            'message': f'Deactivated {updated_count} inbound webhooks',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get overall inbound webhook statistics."""
        inbound_webhooks = self.queryset
        
        total_webhooks = inbound_webhooks.count()
        active_webhooks = inbound_webhooks.filter(is_active=True).count()
        
        # Get log statistics
        from ..models import InboundWebhookLog
        
        logs = InboundWebhookLog.objects.filter(inbound__in=inbound_webhooks)
        total_logs = logs.count()
        processed_logs = logs.filter(processed=True).count()
        signature_valid_logs = logs.filter(signature_valid=True).count()
        
        processing_rate = (processed_logs / total_logs * 100) if total_logs > 0 else 0
        signature_validity_rate = (signature_valid_logs / total_logs * 100) if total_logs > 0 else 0
        
        # Get source statistics
        source_stats = inbound_webhooks.values('source').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        return Response({
            'total_webhooks': total_webhooks,
            'active_webhooks': active_webhooks,
            'total_logs': total_logs,
            'processed_logs': processed_logs,
            'signature_valid_logs': signature_valid_logs,
            'processing_rate': round(processing_rate, 2),
            'signature_validity_rate': round(signature_validity_rate, 2),
            'source_statistics': list(source_stats)
        })
    
    @action(detail=False, methods=['get'])
    def recent_activity(self, request):
        """Get recent inbound webhook activity."""
        from ..models import InboundWebhookLog
        
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        recent_logs = InboundWebhookLog.objects.filter(
            inbound__in=self.queryset,
            created_at__gte=since
        ).order_by('-created_at')
        
        page = self.paginate_queryset(recent_logs)
        if page is not None:
            from ..serializers import InboundWebhookLogListSerializer
            serializer = InboundWebhookLogListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        from ..serializers import InboundWebhookLogListSerializer
        serializer = InboundWebhookLogListSerializer(recent_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def test_endpoint(self, request):
        """Test inbound webhook endpoint."""
        url_token = request.data.get('url_token')
        if not url_token:
            return Response({
                'error': 'url_token parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            inbound_webhook = self.queryset.get(url_token=url_token)
        except InboundWebhook.DoesNotExist:
            return Response({
                'error': 'Inbound webhook not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create test payload
        test_payload = {
            'event': {
                'type': 'webhook.test',
                'data': {
                    'test': True,
                    'timestamp': timezone.now().isoformat(),
                    'source': inbound_webhook.source
                }
            }
        }
        
        # Create test headers
        test_headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Source': inbound_webhook.source,
            'X-Webhook-Timestamp': timezone.now().isoformat()
        }
        
        # Generate test signature
        from ..services.signature_engine import SignatureEngine
        signature_engine = SignatureEngine()
        test_signature = signature_engine.generate_signature(test_payload, inbound_webhook.secret)
        test_headers['X-Webhook-Signature'] = test_signature
        
        try:
            from ..services.inbound import InboundWebhookService
            service = InboundWebhookService()
            
            result = service.process_inbound_webhook(
                inbound=inbound_webhook,
                payload=test_payload,
                headers=test_headers,
                signature=test_signature,
                ip_address='127.0.0.1'
            )
            
            return Response({
                'success': result['success'],
                'inbound_webhook_id': str(inbound_webhook.id),
                'source': inbound_webhook.source,
                'url_token': inbound_webhook.url_token,
                'test_payload': test_payload,
                'test_headers': test_headers,
                'processed': result.get('processed', False),
                'message': result.get('message', 'Test webhook processed successfully')
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Test webhook processing failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
