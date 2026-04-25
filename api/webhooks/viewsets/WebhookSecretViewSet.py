"""Webhook Secret ViewSet

This module contains the ViewSet for webhook secret management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookSecret, WebhookEndpoint
from ..serializers import (
    WebhookSecretSerializer,
    WebhookSecretCreateSerializer,
    WebhookSecretUpdateSerializer,
    WebhookSecretDetailSerializer,
    WebhookSecretListSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import WebhookSecretFilter


class WebhookSecretViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook secret management."""
    
    queryset = WebhookSecret.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WebhookSecretFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'create':
            return WebhookSecretCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return WebhookSecretUpdateSerializer
        elif self.action == 'retrieve':
            return WebhookSecretDetailSerializer
        elif self.action == 'list':
            return WebhookSecretListSerializer
        else:
            return WebhookSecretSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own secrets."""
        return super().get_queryset().filter(endpoint__owner=self.request.user)
    
    def perform_create(self, serializer):
        """Set created_by field on creation."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a secret."""
        secret = self.get_object()
        secret.is_active = True
        secret.save()
        
        serializer = self.get_serializer(secret)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a secret."""
        secret = self.get_object()
        secret.is_active = False
        secret.save()
        
        serializer = self.get_serializer(secret)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Rotate a secret."""
        secret = self.get_object()
        
        try:
            from ..services.core import SecretRotationService
            rotation_service = SecretRotationService()
            
            new_secret = rotation_service.rotate_secret(secret.endpoint)
            
            return Response({
                'success': True,
                'secret_id': str(secret.id),
                'new_secret': new_secret[:8] + "...",  # Only show first 8 chars
                'message': 'Secret rotated successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Secret rotation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke a secret."""
        secret = self.get_object()
        
        try:
            from ..services.core import SecretRotationService
            rotation_service = SecretRotationService()
            
            # Deactivate the secret
            secret.is_active = False
            secret.save()
            
            return Response({
                'success': True,
                'secret_id': str(secret.id),
                'message': 'Secret revoked successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Secret revocation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """Get detailed secret information (without exposing the actual secret)."""
        secret = self.get_object()
        
        # Get usage statistics
        from ..models import WebhookDeliveryLog
        
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=secret.endpoint,
            created_at__gte=secret.created_at
        )
        
        total_usage = deliveries.count()
        successful_usage = deliveries.filter(status='success').count()
        failed_usage = deliveries.filter(status='failed').count()
        
        success_rate = (successful_usage / total_usage * 100) if total_usage > 0 else 0
        
        # Get last used time
        last_delivery = deliveries.order_by('-created_at').first()
        last_used_at = last_delivery.created_at if last_delivery else None
        
        return Response({
            'secret_id': str(secret.id),
            'endpoint_id': str(secret.endpoint.id),
            'endpoint_label': secret.endpoint.label,
            'is_active': secret.is_active,
            'secret_hash_preview': secret.secret_hash[:16] + "..." if secret.secret_hash else None,
            'expires_at': secret.expires_at.isoformat() if secret.expires_at else None,
            'total_usage': total_usage,
            'successful_usage': successful_usage,
            'failed_usage': failed_usage,
            'success_rate': round(success_rate, 2),
            'last_used_at': last_used_at.isoformat() if last_used_at else None,
            'created_at': secret.created_at,
            'updated_at': secret.updated_at
        })
    
    @action(detail=True, methods=['get'])
    def usage_history(self, request, pk=None):
        """Get usage history for a secret."""
        secret = self.get_object()
        
        # Get usage statistics over time
        from ..models import WebhookDeliveryLog
        from datetime import timedelta
        
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=secret.endpoint,
            created_at__gte=since
        )
        
        # Group by day
        usage_history = []
        for day in range(days):
            date = (timezone.now() - timedelta(days=day)).date()
            
            day_deliveries = deliveries.filter(created_at__date=date)
            total_count = day_deliveries.count()
            success_count = day_deliveries.filter(status='success').count()
            
            usage_history.append({
                'date': date.isoformat(),
                'total_usage': total_count,
                'successful_usage': success_count,
                'failed_usage': total_count - success_count
            })
        
        return Response({
            'secret_id': str(secret.id),
            'usage_history': usage_history,
            'days': days
        })
    
    @action(detail=False, methods=['get'])
    def by_endpoint(self, request):
        """Get secrets by endpoint ID."""
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
        
        secrets = self.queryset.filter(endpoint=endpoint)
        
        page = self.paginate_queryset(secrets)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(secrets, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_rotate(self, request):
        """Rotate multiple secrets."""
        secret_ids = request.data.get('secret_ids', [])
        if not secret_ids:
            return Response({
                'error': 'secret_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        secrets = self.queryset.filter(id__in=secret_ids)
        
        rotated_count = 0
        from ..services.core import SecretRotationService
        rotation_service = SecretRotationService()
        
        for secret in secrets:
            try:
                new_secret = rotation_service.rotate_secret(secret.endpoint)
                rotated_count += 1
            except Exception as e:
                continue
        
        return Response({
            'message': f'Rotated {rotated_count} secrets',
            'rotated_count': rotated_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_revoke(self, request):
        """Revoke multiple secrets."""
        secret_ids = request.data.get('secret_ids', [])
        if not secret_ids:
            return Response({
                'error': 'secret_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        secrets = self.queryset.filter(id__in=secret_ids)
        revoked_count = secrets.update(is_active=False)
        
        return Response({
            'message': f'Revoked {revoked_count} secrets',
            'revoked_count': revoked_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Activate multiple secrets."""
        secret_ids = request.data.get('secret_ids', [])
        if not secret_ids:
            return Response({
                'error': 'secret_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        secrets = self.queryset.filter(id__in=secret_ids)
        activated_count = secrets.update(is_active=True)
        
        return Response({
            'message': f'Activated {activated_count} secrets',
            'activated_count': activated_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Deactivate multiple secrets."""
        secret_ids = request.data.get('secret_ids', [])
        if not secret_ids:
            return Response({
                'error': 'secret_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        secrets = self.queryset.filter(id__in=secret_ids)
        deactivated_count = secrets.update(is_active=False)
        
        return Response({
            'message': f'Deactivated {deactivated_count} secrets',
            'deactivated_count': deactivated_count
        })
    
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """Get expired secrets."""
        now = timezone.now()
        expired_secrets = self.queryset.filter(
            expires_at__lt=now,
            is_active=True
        )
        
        page = self.paginate_queryset(expired_secrets)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(expired_secrets, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Clean up expired secrets."""
        now = timezone.now()
        expired_secrets = self.queryset.filter(expires_at__lt=now)
        
        # Deactivate expired secrets
        deactivated_count = expired_secrets.update(is_active=False)
        
        return Response({
            'message': f'Deactivated {deactivated_count} expired secrets',
            'deactivated_count': deactivated_count
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get overall secret statistics."""
        secrets = self.queryset
        
        total_secrets = secrets.count()
        active_secrets = secrets.filter(is_active=True).count()
        inactive_secrets = secrets.filter(is_active=False).count()
        
        # Get expired secrets
        now = timezone.now()
        expired_secrets = secrets.filter(expires_at__lt=now).count()
        
        # Get usage statistics
        from ..models import WebhookDeliveryLog
        
        total_usage = WebhookDeliveryLog.objects.filter(
            endpoint__in=secrets.values('endpoint')
        ).count()
        
        return Response({
            'total_secrets': total_secrets,
            'active_secrets': active_secrets,
            'inactive_secrets': inactive_secrets,
            'expired_secrets': expired_secrets,
            'total_usage': total_usage
        })
    
    @action(detail=False, methods=['post'])
    def generate_secret(self, request):
        """Generate a new secret for an endpoint."""
        endpoint_id = request.data.get('endpoint_id')
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
        
        try:
            from ..services.core import SecretRotationService
            rotation_service = SecretRotationService()
            
            new_secret = rotation_service.rotate_secret(endpoint)
            
            return Response({
                'success': True,
                'endpoint_id': str(endpoint_id),
                'new_secret': new_secret[:8] + "...",  # Only show first 8 chars
                'message': 'New secret generated successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Secret generation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
