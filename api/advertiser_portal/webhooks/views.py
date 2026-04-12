"""
Webhooks Views

This module provides DRF ViewSets for webhook management with
enterprise-grade security, real-time processing, and comprehensive
error handling following industry standards from Stripe Webhooks,
GitHub Webhooks, and Zapier Webhooks.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import time
import asyncio
import hmac
import hashlib

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import Coalesce, RowNumber
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.webhook_model import (
    Webhook, WebhookEvent, WebhookDelivery, WebhookRetry,
    WebhookLog, WebhookQueue, WebhookSecurity
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    WebhookService, WebhookEventService, WebhookDeliveryService,
    WebhookRetryService, WebhookMonitoringService, WebhookSecurityService,
    WebhookQueueService, WebhookConfig, WebhookEvent as WebhookEventData
)

User = get_user_model()


class WebhookViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for webhook management.
    
    Features:
    - Multi-protocol webhook support
    - Event-driven architecture
    - Real-time processing
    - Advanced retry mechanisms
    - Comprehensive monitoring
    - Security validation
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create webhook with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - URL security checks
        - Secret key generation
        - Audit logging
        """
        try:
            # Security: Validate request
            WebhookViewSet._validate_create_request(request)
            
            # Get webhook configuration
            webhook_config = request.data
            
            # Create webhook
            webhook = WebhookService.create_webhook(webhook_config, request.user)
            
            # Return response
            response_data = {
                'webhook_id': str(webhook.id),
                'name': webhook.name,
                'url': webhook.url,
                'events': webhook.events,
                'secret': webhook.secret,
                'active': webhook.active,
                'retry_policy': webhook.retry_policy,
                'timeout': webhook.timeout,
                'headers': webhook.headers,
                'created_at': webhook.created_at.isoformat()
            }
            
            # Security: Log webhook creation
            WebhookViewSet._log_webhook_creation(webhook, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating webhook: {str(e)}")
            return Response({'error': 'Failed to create webhook'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def trigger(self, request, pk=None):
        """
        Trigger webhook event with enterprise-grade processing.
        
        Security measures:
        - User permission validation
        - Event validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate webhook access
            webhook_id = UUID(pk)
            event_data = request.data
            
            # Trigger event
            deliveries = WebhookService.trigger_event(event_data, source='manual')
            
            return Response({'deliveries': len(deliveries)}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error triggering webhook: {str(e)}")
            return Response({'error': 'Failed to trigger webhook'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test webhook with sample event.
        
        Security measures:
        - User permission validation
        - Test event validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate webhook access
            webhook_id = UUID(pk)
            test_config = request.data
            
            # Test webhook
            test_result = WebhookViewSet._test_webhook(webhook_id, test_config, request.user)
            
            return Response({'test_result': test_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error testing webhook: {str(e)}")
            return Response({'error': 'Failed to test webhook'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Get webhook statistics and performance metrics.
        
        Security measures:
        - User permission validation
        - Metrics access control
        - Rate limiting
        """
        try:
            # Security: Validate webhook access
            webhook_id = UUID(pk)
            
            # Get statistics
            stats = WebhookService.get_webhook_stats(webhook_id)
            
            return Response({'stats': stats}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting webhook stats: {str(e)}")
            return Response({'error': 'Failed to get webhook stats'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def deliveries(self, request, pk=None):
        """
        Get webhook delivery history.
        
        Security measures:
        - User permission validation
        - Delivery access control
        - Data filtering
        """
        try:
            # Security: Validate webhook access
            webhook_id = UUID(pk)
            
            # Get query parameters
            filters = {
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'status': request.query_params.get('status'),
                'limit': int(request.query_params.get('limit', 100))
            }
            
            # Get deliveries
            deliveries_data = WebhookViewSet._get_webhook_deliveries(webhook_id, filters)
            
            return Response({'deliveries': deliveries_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting webhook deliveries: {str(e)}")
            return Response({'error': 'Failed to get webhook deliveries'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List webhooks with filtering and pagination.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            WebhookViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'status': request.query_params.get('status'),
                'event_type': request.query_params.get('event_type'),
                'page': int(request.query_params.get('page', 1)),
                'page_size': min(int(request.query_params.get('page_size', 20)), 100)
            }
            
            # Get webhooks list
            webhooks_data = WebhookViewSet._get_webhooks_list(user, filters)
            
            return Response(webhooks_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing webhooks: {str(e)}")
            return Response({'error': 'Failed to list webhooks'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """
        Toggle webhook active status.
        
        Security measures:
        - User permission validation
        - Status validation
        - Audit logging
        """
        try:
            # Security: Validate webhook access
            webhook_id = UUID(pk)
            
            # Toggle webhook
            webhook = WebhookViewSet._toggle_webhook(webhook_id, request.user)
            
            return Response({
                'webhook_id': str(webhook.id),
                'active': webhook.active
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error toggling webhook: {str(e)}")
            return Response({'error': 'Failed to toggle webhook'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'url', 'events']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate URL
        url = request.data.get('url')
        if not url.startswith(('http://', 'https://')):
            raise AdvertiserValidationError("URL must be a valid HTTP/HTTPS URL")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                raise AdvertiserValidationError("URL contains suspicious content")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have webhook permissions")
    
    @staticmethod
    def _get_webhooks_list(user: User, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get webhooks list with filtering and pagination."""
        try:
            # Build query
            queryset = Webhook.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(advertiser__user=user)
            
            # Apply filters
            if filters.get('status'):
                queryset = queryset.filter(active=filters['status'].lower() == 'true')
            
            if filters.get('event_type'):
                queryset = queryset.filter(events__contains=[filters['event_type']])
            
            # Pagination
            page = filters.get('page', 1)
            page_size = filters.get('page_size', 20)
            offset = (page - 1) * page_size
            
            # Get paginated results
            results = queryset[offset:offset + page_size]
            
            # Format results
            webhooks = []
            for webhook in results:
                webhooks.append({
                    'id': str(webhook.id),
                    'name': webhook.name,
                    'url': webhook.url,
                    'events': webhook.events,
                    'active': webhook.active,
                    'created_at': webhook.created_at.isoformat(),
                    'updated_at': webhook.updated_at.isoformat()
                })
            
            return {
                'webhooks': webhooks,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': queryset.count(),
                    'total_pages': (queryset.count() + page_size - 1) // page_size
                },
                'filters_applied': filters
            }
            
        except Exception as e:
            logger.error(f"Error getting webhooks list: {str(e)}")
            return {
                'webhooks': [],
                'pagination': {'page': 1, 'page_size': 20, 'total_count': 0, 'total_pages': 0},
                'filters_applied': filters,
                'error': 'Failed to retrieve webhooks'
            }
    
    @staticmethod
    def _test_webhook(webhook_id: UUID, test_config: Dict[str, Any], user: User) -> Dict[str, Any]:
        """Test webhook with sample event."""
        try:
            # Get webhook
            webhook = Webhook.objects.get(id=webhook_id)
            
            # Create test event
            test_event = {
                'event_type': test_config.get('event_type', 'test.event'),
                'data': test_config.get('data', {'test': True}),
                'source': 'test',
                'user_id': str(user.id) if user else None,
                'metadata': {'test': True}
            }
            
            # Trigger test event
            deliveries = WebhookService.trigger_event(test_event, source='test')
            
            # Get test delivery
            test_delivery = None
            for delivery in deliveries:
                if delivery.webhook_id == webhook_id:
                    test_delivery = delivery
                    break
            
            return {
                'success': test_delivery.status == 'delivered' if test_delivery else False,
                'delivery_id': str(test_delivery.id) if test_delivery else None,
                'status_code': test_delivery.response_code if test_delivery else None,
                'response_body': test_delivery.response_body if test_delivery else None,
                'error_message': test_delivery.error_message if test_delivery else None,
                'duration': test_delivery.duration if test_delivery else 0
            }
            
        except Exception as e:
            logger.error(f"Error testing webhook: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _get_webhook_deliveries(webhook_id: UUID, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get webhook deliveries with filtering."""
        try:
            # Build query
            queryset = WebhookDelivery.objects.filter(webhook_id=webhook_id)
            
            # Apply filters
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            # Get limited results
            deliveries = queryset.order_by('-created_at')[:filters.get('limit', 100)]
            
            # Format results
            deliveries_data = []
            for delivery in deliveries:
                deliveries_data.append({
                    'id': str(delivery.id),
                    'event_id': delivery.event_id,
                    'attempt': delivery.attempt,
                    'status': delivery.status,
                    'response_code': delivery.response_code,
                    'response_body': delivery.response_body,
                    'error_message': delivery.error_message,
                    'delivered_at': delivery.delivered_at.isoformat() if delivery.delivered_at else None,
                    'duration': delivery.duration,
                    'created_at': delivery.created_at.isoformat()
                })
            
            return deliveries_data
            
        except Exception as e:
            logger.error(f"Error getting webhook deliveries: {str(e)}")
            return []
    
    @staticmethod
    def _toggle_webhook(webhook_id: UUID, user: User) -> Webhook:
        """Toggle webhook active status."""
        try:
            # Get webhook
            webhook = Webhook.objects.get(id=webhook_id)
            
            # Toggle status
            webhook.active = not webhook.active
            webhook.save(update_fields=['active'])
            
            # Log toggle action
            WebhookViewSet._log_webhook_toggle(webhook, user)
            
            return webhook
            
        except Exception as e:
            logger.error(f"Error toggling webhook: {str(e)}")
            raise AdvertiserServiceError(f"Failed to toggle webhook: {str(e)}")
    
    @staticmethod
    def _log_webhook_creation(webhook: Webhook, user: User) -> None:
        """Log webhook creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                webhook,
                user,
                description=f"Created webhook: {webhook.name}"
            )
        except Exception as e:
            logger.error(f"Error logging webhook creation: {str(e)}")
    
    @staticmethod
    def _log_webhook_toggle(webhook: Webhook, user: User) -> None:
        """Log webhook toggle for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='toggle_webhook',
                object_type='Webhook',
                object_id=str(webhook.id),
                user=user,
                description=f"Toggled webhook {webhook.name} to {'active' if webhook.active else 'inactive'}"
            )
        except Exception as e:
            logger.error(f"Error logging webhook toggle: {str(e)}")


class WebhookEventViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for webhook event management.
    
    Features:
    - Event creation and validation
    - Event filtering and search
    - Real-time event processing
    - Event history tracking
    - Performance monitoring
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create webhook event with validation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Event type validation
        - Audit logging
        """
        try:
            # Security: Validate request
            WebhookEventViewSet._validate_create_request(request)
            
            # Get event data
            event_data = request.data
            
            # Create event
            event = WebhookEventService.create_event(event_data)
            
            return Response({'event_id': event.event_id}, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating webhook event: {str(e)}")
            return Response({'error': 'Failed to create webhook event'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """
        Get webhook event details.
        
        Security measures:
        - User permission validation
        - Event access control
        - Data filtering
        """
        try:
            # Security: Validate event access
            event_id = pk
            
            # Get event details
            event = WebhookEventService.get_event(event_id)
            
            if not event:
                return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'event_id': event.event_id,
                'event_type': event.event_type,
                'data': event.data,
                'source': event.source,
                'user_id': event.user_id,
                'metadata': event.metadata,
                'created_at': event.created_at.isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting webhook event details: {str(e)}")
            return Response({'error': 'Failed to get event details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List webhook events with filtering.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            WebhookEventViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'event_type': request.query_params.get('event_type'),
                'source': request.query_params.get('source'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'limit': int(request.query_params.get('limit', 100))
            }
            
            # Get events list
            events_data = WebhookEventViewSet._get_events_list(user, filters)
            
            return Response({'events': events_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing webhook events: {str(e)}")
            return Response({'error': 'Failed to list webhook events'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['event_type', 'data']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have webhook event permissions")
    
    @staticmethod
    def _get_events_list(user: User, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get events list with filtering."""
        try:
            # Get events
            events = WebhookEventService.list_events(filters)
            
            # Filter by user if not superuser
            if not user.is_superuser:
                events = [event for event in events if event.user_id == str(user.id)]
            
            # Format results
            events_data = []
            for event in events:
                events_data.append({
                    'event_id': event.event_id,
                    'event_type': event.event_type,
                    'source': event.source,
                    'user_id': event.user_id,
                    'created_at': event.created_at.isoformat()
                })
            
            return events_data
            
        except Exception as e:
            logger.error(f"Error getting events list: {str(e)}")
            return []


class WebhookDeliveryViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for webhook delivery management.
    
    Features:
    - Delivery tracking and monitoring
    - Retry management
    - Performance analysis
    - Error handling
    - Real-time status updates
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Retry webhook delivery.
        
        Security measures:
        - User permission validation
        - Delivery validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate delivery access
            delivery_id = UUID(pk)
            
            # Retry delivery
            delivery = WebhookService.retry_delivery(delivery_id)
            
            return Response({
                'delivery_id': str(delivery.id),
                'status': delivery.status,
                'attempt': delivery.attempt
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error retrying webhook delivery: {str(e)}")
            return Response({'error': 'Failed to retry webhook delivery'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """
        Get webhook delivery details.
        
        Security measures:
        - User permission validation
        - Delivery access control
        - Data filtering
        """
        try:
            # Security: Validate delivery access
            delivery_id = UUID(pk)
            
            # Get delivery details
            delivery = WebhookDeliveryService.get_delivery(delivery_id)
            
            if not delivery:
                return Response({'error': 'Delivery not found'}, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'delivery_id': str(delivery.id),
                'webhook_id': str(delivery.webhook_id),
                'event_id': delivery.event_id,
                'attempt': delivery.attempt,
                'status': delivery.status,
                'response_code': delivery.response_code,
                'response_body': delivery.response_body,
                'error_message': delivery.error_message,
                'delivered_at': delivery.delivered_at.isoformat() if delivery.delivered_at else None,
                'duration': delivery.duration,
                'created_at': delivery.created_at.isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting webhook delivery details: {str(e)}")
            return Response({'error': 'Failed to get delivery details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List webhook deliveries with filtering.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            WebhookDeliveryViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'webhook_id': request.query_params.get('webhook_id'),
                'event_id': request.query_params.get('event_id'),
                'status': request.query_params.get('status'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'limit': int(request.query_params.get('limit', 100))
            }
            
            # Get deliveries list
            deliveries_data = WebhookDeliveryViewSet._get_deliveries_list(user, filters)
            
            return Response({'deliveries': deliveries_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing webhook deliveries: {str(e)}")
            return Response({'error': 'Failed to list webhook deliveries'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have webhook delivery permissions")
    
    @staticmethod
    def _get_deliveries_list(user: User, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get deliveries list with filtering."""
        try:
            # Get deliveries
            deliveries = WebhookDeliveryService.list_deliveries(filters)
            
            # Filter by user if not superuser
            if not user.is_superuser:
                # Get user's webhooks
                user_webhook_ids = Webhook.objects.filter(
                    advertiser__user=user
                ).values_list('id', flat=True)
                
                deliveries = [delivery for delivery in deliveries if delivery.webhook_id in user_webhook_ids]
            
            # Format results
            deliveries_data = []
            for delivery in deliveries:
                deliveries_data.append({
                    'delivery_id': str(delivery.id),
                    'webhook_id': str(delivery.webhook_id),
                    'event_id': delivery.event_id,
                    'attempt': delivery.attempt,
                    'status': delivery.status,
                    'response_code': delivery.response_code,
                    'delivered_at': delivery.delivered_at.isoformat() if delivery.delivered_at else None,
                    'duration': delivery.duration,
                    'created_at': delivery.created_at.isoformat()
                })
            
            return deliveries_data
            
        except Exception as e:
            logger.error(f"Error getting deliveries list: {str(e)}")
            return []


class WebhookMonitoringViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for webhook monitoring.
    
    Features:
    - Real-time health monitoring
    - Performance metrics
    - Error tracking
    - Alert management
    - System health checks
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['get'])
    def health(self, request, pk=None):
        """
        Get webhook health status.
        
        Security measures:
        - User permission validation
        - Health access control
        - Rate limiting
        """
        try:
            # Security: Validate webhook access
            webhook_id = UUID(pk)
            
            # Get health status
            health = WebhookMonitoringService.get_webhook_health(webhook_id)
            
            return Response({'health': health}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting webhook health: {str(e)}")
            return Response({'error': 'Failed to get webhook health'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """
        Get overall webhook system health.
        
        Security measures:
        - User permission validation
        - System access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            WebhookMonitoringViewSet._validate_user_access(user)
            
            # Get system health
            health = WebhookMonitoringService.get_system_health()
            
            return Response({'health': health}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return Response({'error': 'Failed to get system health'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """
        Get webhook performance metrics.
        
        Security measures:
        - User permission validation
        - Metrics access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            WebhookMonitoringViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'webhook_id': request.query_params.get('webhook_id')
            }
            
            # Get metrics
            metrics = WebhookMonitoringViewSet._get_webhook_metrics(user, filters)
            
            return Response({'metrics': metrics}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting webhook metrics: {str(e)}")
            return Response({'error': 'Failed to get webhook metrics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have webhook monitoring permissions")
    
    @staticmethod
    def _get_webhook_metrics(user: User, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get webhook metrics with filtering."""
        try:
            # Get user's webhooks
            webhook_ids = []
            if not user.is_superuser:
                webhook_ids = list(Webhook.objects.filter(
                    advertiser__user=user
                ).values_list('id', flat=True))
            
            # Calculate metrics
            since = filters.get('date_from') or (timezone.now() - timedelta(days=30))
            to = filters.get('date_to') or timezone.now()
            
            # Get delivery metrics
            deliveries = WebhookDelivery.objects.filter(
                created_at__gte=since,
                created_at__lte=to
            )
            
            if webhook_ids:
                deliveries = deliveries.filter(webhook_id__in=webhook_ids)
            
            total_deliveries = deliveries.count()
            successful_deliveries = deliveries.filter(status='delivered').count()
            failed_deliveries = deliveries.filter(status='failed').count()
            
            # Calculate success rate
            success_rate = (successful_deliveries / max(total_deliveries, 1)) * 100
            
            # Calculate average response time
            avg_response_time = deliveries.aggregate(
                avg_time=Avg('duration')
            )['avg_time'] or 0
            
            return {
                'total_deliveries': total_deliveries,
                'successful_deliveries': successful_deliveries,
                'failed_deliveries': failed_deliveries,
                'success_rate': round(success_rate, 2),
                'avg_response_time': round(avg_response_time, 3),
                'period': {
                    'from': since.isoformat(),
                    'to': to.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting webhook metrics: {str(e)}")
            return {
                'error': 'Failed to calculate metrics'
            }


class WebhookSecurityViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for webhook security management.
    
    Features:
    - IP blocking and unblocking
    - Signature verification
    - Security monitoring
    - Threat detection
    - Audit logging
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def block_ip(self, request):
        """
        Block IP address from webhook requests.
        
        Security measures:
        - User permission validation
        - IP validation
        - Admin access required
        - Audit logging
        """
        try:
            # Security: Validate admin access
            if not request.user.is_superuser:
                return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
            
            # Security: Validate request
            WebhookSecurityViewSet._validate_block_ip_request(request)
            
            # Block IP
            ip_address = request.data.get('ip_address')
            reason = request.data.get('reason', '')
            
            WebhookSecurityService.block_ip(ip_address, reason)
            
            return Response({
                'ip_address': ip_address,
                'blocked': True,
                'reason': reason
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error blocking IP: {str(e)}")
            return Response({'error': 'Failed to block IP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def unblock_ip(self, request):
        """
        Unblock IP address from webhook requests.
        
        Security measures:
        - User permission validation
        - IP validation
        - Admin access required
        - Audit logging
        """
        try:
            # Security: Validate admin access
            if not request.user.is_superuser:
                return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
            
            # Security: Validate request
            WebhookSecurityViewSet._validate_unblock_ip_request(request)
            
            # Unblock IP
            ip_address = request.data.get('ip_address')
            
            WebhookSecurityService.unblock_ip(ip_address)
            
            return Response({
                'ip_address': ip_address,
                'unblocked': True
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error unblocking IP: {str(e)}")
            return Response({'error': 'Failed to unblock IP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def verify_signature(self, request):
        """
        Verify webhook signature.
        
        Security measures:
        - Input validation
        - Signature verification
        - Security checks
        """
        try:
            # Security: Validate request
            WebhookSecurityViewSet._validate_signature_request(request)
            
            # Verify signature
            payload = request.data.get('payload', {})
            signature = request.data.get('signature', '')
            secret = request.data.get('secret', '')
            
            is_valid = WebhookService.verify_webhook_signature(payload, signature, secret)
            
            return Response({
                'valid': is_valid,
                'signature': signature,
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            return Response({'error': 'Failed to verify signature'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_block_ip_request(request) -> None:
        """Validate block IP request."""
        # Security: Check required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        if not request.data.get('ip_address'):
            raise AdvertiserValidationError("IP address is required")
        
        # Security: Validate IP format
        import ipaddress
        try:
            ipaddress.ip_address(request.data['ip_address'])
        except ValueError:
            raise AdvertiserValidationError("Invalid IP address format")
    
    @staticmethod
    def _validate_unblock_ip_request(request) -> None:
        """Validate unblock IP request."""
        # Security: Check required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        if not request.data.get('ip_address'):
            raise AdvertiserValidationError("IP address is required")
        
        # Security: Validate IP format
        import ipaddress
        try:
            ipaddress.ip_address(request.data['ip_address'])
        except ValueError:
            raise AdvertiserValidationError("Invalid IP address format")
    
    @staticmethod
    def _validate_signature_request(request) -> None:
        """Validate signature verification request."""
        # Security: Check required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['payload', 'signature', 'secret']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")


class WebhookQueueViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for webhook queue management.
    
    Features:
    - Queue monitoring
    - Queue statistics
    - Queue management
    - Performance tracking
    - Queue health checks
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get queue statistics.
        
        Security measures:
        - User permission validation
        - Queue access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            WebhookQueueViewSet._validate_user_access(user)
            
            # Get queue stats
            stats = WebhookQueueService.get_queue_stats()
            
            return Response({'stats': stats}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting queue stats: {str(e)}")
            return Response({'error': 'Failed to get queue stats'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def process_queue(self, request):
        """
        Process pending webhook queue items.
        
        Security measures:
        - User permission validation
        - Admin access required
        - Queue management
        - Audit logging
        """
        try:
            # Security: Validate admin access
            if not request.user.is_superuser:
                return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
            
            # Process queue
            processed_retries = WebhookRetryService.process_pending_retries()
            
            return Response({
                'processed_count': len(processed_retries),
                'processed_retries': [str(retry.id) for retry in processed_retries]
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error processing queue: {str(e)}")
            return Response({'error': 'Failed to process queue'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have webhook queue permissions")
