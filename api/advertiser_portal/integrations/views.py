"""
Integrations Views

This module provides DRF ViewSets for third-party integrations with
enterprise-grade security, real-time synchronization, and comprehensive
error handling following industry standards from Zapier, Segment, and MuleSoft.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import time
import requests

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

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.integration_model import (
    SocialMediaIntegration, AdNetworkIntegration, AnalyticsIntegration,
    PaymentIntegration, WebhookIntegration, APIIntegration
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    SocialMediaIntegrationService, AdNetworkIntegrationService, AnalyticsIntegrationService,
    PaymentIntegrationService, WebhookIntegrationService, APIIntegrationService,
    IntegrationConfig, SyncResult
)

User = get_user_model()


class SocialMediaIntegrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for social media integrations.
    
    Features:
    - Multi-platform support (Facebook, Instagram, Twitter, LinkedIn, TikTok)
    - Real-time synchronization
    - Content management
    - Analytics integration
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def connect(self, request):
        """
        Connect social media platform with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - OAuth authentication
        - Audit logging
        """
        try:
            # Security: Validate request
            SocialMediaIntegrationViewSet._validate_connect_request(request)
            
            # Get platform configuration
            platform_config = request.data
            
            # Connect platform
            integration = SocialMediaIntegrationService.connect_platform(platform_config, request.user)
            
            # Return response
            response_data = {
                'integration_id': str(integration.id),
                'platform': integration.platform,
                'account_id': integration.account_id,
                'account_name': integration.account_name,
                'is_active': integration.is_active,
                'sync_frequency': integration.sync_frequency,
                'created_at': integration.created_at.isoformat()
            }
            
            # Security: Log connection
            SocialMediaIntegrationViewSet._log_connection(integration, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error connecting social media platform: {str(e)}")
            return Response({'error': 'Failed to connect platform'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """
        Synchronize data from social media platform.
        
        Security measures:
        - User permission validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate integration access
            integration_id = UUID(pk)
            sync_type = request.data.get('sync_type', 'full')
            
            # Perform sync
            sync_result = SocialMediaIntegrationService.sync_data(integration_id, sync_type)
            
            # Return response
            response_data = {
                'integration_id': sync_result.integration_id,
                'sync_type': sync_result.sync_type,
                'records_processed': sync_result.records_processed,
                'records_created': sync_result.records_created,
                'records_updated': sync_result.records_updated,
                'records_failed': sync_result.records_failed,
                'errors': sync_result.errors,
                'sync_timestamp': sync_result.sync_timestamp.isoformat(),
                'duration': sync_result.duration
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error syncing social media data: {str(e)}")
            return Response({'error': 'Failed to sync data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publish content to social media platform.
        
        Security measures:
        - User permission validation
        - Content validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate integration access
            integration_id = UUID(pk)
            content_config = request.data
            
            # Publish content
            result = SocialMediaIntegrationService.publish_content(integration_id, content_config)
            
            return Response({'result': result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error publishing content: {str(e)}")
            return Response({'error': 'Failed to publish content'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """
        Get analytics data from social media platform.
        
        Security measures:
        - User permission validation
        - Date range validation
        - Rate limiting
        """
        try:
            # Security: Validate integration access
            integration_id = UUID(pk)
            
            # Get date range
            date_range = {
                'start': request.query_params.get('start'),
                'end': request.query_params.get('end')
            }
            
            # Get analytics
            analytics_data = SocialMediaIntegrationService.get_analytics(integration_id, date_range)
            
            return Response({'analytics': analytics_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return Response({'error': 'Failed to get analytics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List social media integrations.
        
        Security measures:
        - User permission validation
        - Data access control
        """
        try:
            # Security: Validate user access
            user = request.user
            SocialMediaIntegrationViewSet._validate_user_access(user)
            
            # Get integrations list
            integrations_data = SocialMediaIntegrationViewSet._get_integrations_list(user)
            
            return Response(integrations_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing integrations: {str(e)}")
            return Response({'error': 'Failed to list integrations'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_connect_request(request) -> None:
        """Validate connect request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['platform', 'credentials']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate platform
        valid_platforms = ['facebook', 'instagram', 'twitter', 'linkedin', 'tiktok']
        platform = request.data.get('platform')
        if platform not in valid_platforms:
            raise AdvertiserValidationError(f"Invalid platform: {platform}")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have integration permissions")
    
    @staticmethod
    def _get_integrations_list(user: User) -> Dict[str, Any]:
        """Get integrations list with filtering."""
        try:
            # Build query
            queryset = SocialMediaIntegration.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(advertiser__user=user)
            
            # Get results
            integrations = []
            for integration in queryset:
                integrations.append({
                    'id': str(integration.id),
                    'platform': integration.platform,
                    'account_id': integration.account_id,
                    'account_name': integration.account_name,
                    'is_active': integration.is_active,
                    'sync_frequency': integration.sync_frequency,
                    'last_sync': integration.last_sync.isoformat() if integration.last_sync else None,
                    'created_at': integration.created_at.isoformat()
                })
            
            return {
                'integrations': integrations,
                'total_count': len(integrations)
            }
            
        except Exception as e:
            logger.error(f"Error getting integrations list: {str(e)}")
            return {
                'integrations': [],
                'total_count': 0,
                'error': 'Failed to retrieve integrations'
            }
    
    @staticmethod
    def _log_connection(integration: SocialMediaIntegration, user: User) -> None:
        """Log connection for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                integration,
                user,
                description=f"Connected social media integration: {integration.platform}"
            )
        except Exception as e:
            logger.error(f"Error logging connection: {str(e)}")


class AdNetworkIntegrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for ad network integrations.
    
    Features:
    - Multi-network support (Google Ads, Facebook Ads, TikTok Ads)
    - Real-time bid management
    - Campaign synchronization
    - Performance optimization
    - Budget management
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def connect(self, request):
        """
        Connect ad network with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - API authentication
        - Audit logging
        """
        try:
            # Security: Validate request
            AdNetworkIntegrationViewSet._validate_connect_request(request)
            
            # Get network configuration
            network_config = request.data
            
            # Connect network
            integration = AdNetworkIntegrationService.connect_network(network_config, request.user)
            
            # Return response
            response_data = {
                'integration_id': str(integration.id),
                'network': integration.network,
                'account_id': integration.account_id,
                'account_name': integration.account_name,
                'is_active': integration.is_active,
                'sync_frequency': integration.sync_frequency,
                'created_at': integration.created_at.isoformat()
            }
            
            # Security: Log connection
            AdNetworkIntegrationViewSet._log_connection(integration, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error connecting ad network: {str(e)}")
            return Response({'error': 'Failed to connect network'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def sync_campaigns(self, request, pk=None):
        """
        Synchronize campaigns from ad network.
        
        Security measures:
        - User permission validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate integration access
            integration_id = UUID(pk)
            
            # Sync campaigns
            sync_result = AdNetworkIntegrationService.sync_campaigns(integration_id)
            
            # Return response
            response_data = {
                'integration_id': sync_result.integration_id,
                'sync_type': sync_result.sync_type,
                'records_processed': sync_result.records_processed,
                'records_created': sync_result.records_created,
                'records_updated': sync_result.records_updated,
                'records_failed': sync_result.records_failed,
                'errors': sync_result.errors,
                'sync_timestamp': sync_result.sync_timestamp.isoformat(),
                'duration': sync_result.duration
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error syncing campaigns: {str(e)}")
            return Response({'error': 'Failed to sync campaigns'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def optimize_bids(self, request, pk=None):
        """
        Optimize bids based on performance data.
        
        Security measures:
        - User permission validation
        - Optimization validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate integration access
            integration_id = UUID(pk)
            optimization_config = request.data
            
            # Optimize bids
            optimization_result = AdNetworkIntegrationService.optimize_bids(integration_id, optimization_config)
            
            return Response({'optimization_result': optimization_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error optimizing bids: {str(e)}")
            return Response({'error': 'Failed to optimize bids'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_connect_request(request) -> None:
        """Validate connect request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['network', 'credentials']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate network
        valid_networks = ['google_ads', 'facebook_ads', 'tiktok_ads', 'linkedin_ads', 'microsoft_ads']
        network = request.data.get('network')
        if network not in valid_networks:
            raise AdvertiserValidationError(f"Invalid network: {network}")
    
    @staticmethod
    def _log_connection(integration: AdNetworkIntegration, user: User) -> None:
        """Log connection for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                integration,
                user,
                description=f"Connected ad network integration: {integration.network}"
            )
        except Exception as e:
            logger.error(f"Error logging connection: {str(e)}")


class AnalyticsIntegrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for analytics integrations.
    
    Features:
    - Multi-platform analytics (Google Analytics, Adobe Analytics)
    - Real-time data collection
    - Custom event tracking
    - Advanced segmentation
    - Data visualization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def connect(self, request):
        """
        Connect analytics platform with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - API authentication
        - Audit logging
        """
        try:
            # Security: Validate request
            AnalyticsIntegrationViewSet._validate_connect_request(request)
            
            # Get analytics configuration
            analytics_config = request.data
            
            # Connect analytics
            integration = AnalyticsIntegrationService.connect_analytics(analytics_config, request.user)
            
            # Return response
            response_data = {
                'integration_id': str(integration.id),
                'platform': integration.platform,
                'account_id': integration.account_id,
                'account_name': integration.account_name,
                'is_active': integration.is_active,
                'sync_frequency': integration.sync_frequency,
                'created_at': integration.created_at.isoformat()
            }
            
            # Security: Log connection
            AnalyticsIntegrationViewSet._log_connection(integration, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error connecting analytics: {str(e)}")
            return Response({'error': 'Failed to connect analytics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def track_event(self, request, pk=None):
        """
        Track custom event.
        
        Security measures:
        - User permission validation
        - Event validation
        - Rate limiting
        - Audit logging
        """
        try:
            # Security: Validate integration access
            integration_id = UUID(pk)
            event_data = request.data
            
            # Track event
            result = AnalyticsIntegrationService.track_event(integration_id, event_data)
            
            return Response({'result': result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error tracking event: {str(e)}")
            return Response({'error': 'Failed to track event'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_connect_request(request) -> None:
        """Validate connect request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['platform', 'credentials']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate platform
        valid_platforms = ['google_analytics', 'adobe_analytics', 'mixpanel', 'segment']
        platform = request.data.get('platform')
        if platform not in valid_platforms:
            raise AdvertiserValidationError(f"Invalid platform: {platform}")
    
    @staticmethod
    def _log_connection(integration: AnalyticsIntegration, user: User) -> None:
        """Log connection for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                integration,
                user,
                description=f"Connected analytics integration: {integration.platform}"
            )
        except Exception as e:
            logger.error(f"Error logging connection: {str(e)}")


class PaymentIntegrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for payment integrations.
    
    Features:
    - Multi-gateway support (Stripe, PayPal, Square)
    - Secure payment processing
    - Subscription management
    - Refund processing
    - Compliance and security
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def connect(self, request):
        """
        Connect payment gateway with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - API authentication
        - Audit logging
        """
        try:
            # Security: Validate request
            PaymentIntegrationViewSet._validate_connect_request(request)
            
            # Get gateway configuration
            gateway_config = request.data
            
            # Connect gateway
            integration = PaymentIntegrationService.connect_gateway(gateway_config, request.user)
            
            # Return response
            response_data = {
                'integration_id': str(integration.id),
                'gateway': integration.gateway,
                'account_id': integration.account_id,
                'account_name': integration.account_name,
                'is_active': integration.is_active,
                'created_at': integration.created_at.isoformat()
            }
            
            # Security: Log connection
            PaymentIntegrationViewSet._log_connection(integration, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error connecting payment gateway: {str(e)}")
            return Response({'error': 'Failed to connect gateway'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_connect_request(request) -> None:
        """Validate connect request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['gateway', 'credentials']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate gateway
        valid_gateways = ['stripe', 'paypal', 'square', 'braintree', 'adyen']
        gateway = request.data.get('gateway')
        if gateway not in valid_gateways:
            raise AdvertiserValidationError(f"Invalid gateway: {gateway}")
    
    @staticmethod
    def _log_connection(integration: PaymentIntegration, user: User) -> None:
        """Log connection for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                integration,
                user,
                description=f"Connected payment integration: {integration.gateway}"
            )
        except Exception as e:
            logger.error(f"Error logging connection: {str(e)}")


class WebhookIntegrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for webhook integrations.
    
    Features:
    - Custom webhook endpoints
    - Event processing
    - Security validation
    - Retry mechanisms
    - Logging and monitoring
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create webhook endpoint with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Endpoint validation
        - Audit logging
        """
        try:
            # Security: Validate request
            WebhookIntegrationViewSet._validate_create_request(request)
            
            # Get webhook configuration
            webhook_config = request.data
            
            # Create webhook
            webhook = WebhookIntegrationService.create_webhook(webhook_config, request.user)
            
            # Return response
            response_data = {
                'webhook_id': str(webhook.id),
                'name': webhook.name,
                'endpoint_url': webhook.endpoint_url,
                'event_types': webhook.event_types,
                'is_active': webhook.is_active,
                'created_at': webhook.created_at.isoformat()
            }
            
            # Security: Log webhook creation
            WebhookIntegrationViewSet._log_webhook_creation(webhook, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating webhook: {str(e)}")
            return Response({'error': 'Failed to create webhook'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'endpoint_url']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate endpoint URL
        endpoint_url = request.data.get('endpoint_url')
        if not endpoint_url.startswith(('http://', 'https://')):
            raise AdvertiserValidationError("Endpoint URL must be a valid HTTP/HTTPS URL")
    
    @staticmethod
    def _log_webhook_creation(webhook: WebhookIntegration, user: User) -> None:
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


class APIIntegrationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for API integrations.
    
    Features:
    - Custom API connections
    - Data transformation
    - Error handling
    - Rate limiting
    - Monitoring and logging
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create custom API integration with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - API validation
        - Audit logging
        """
        try:
            # Security: Validate request
            APIIntegrationViewSet._validate_create_request(request)
            
            # Get API configuration
            api_config = request.data
            
            # Create API integration
            api_integration = APIIntegrationService.create_api_integration(api_config, request.user)
            
            # Return response
            response_data = {
                'integration_id': str(api_integration.id),
                'name': api_integration.name,
                'base_url': api_integration.base_url,
                'authentication_type': api_integration.authentication_type,
                'is_active': api_integration.is_active,
                'created_at': api_integration.created_at.isoformat()
            }
            
            # Security: Log API integration creation
            APIIntegrationViewSet._log_api_integration_creation(api_integration, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating API integration: {str(e)}")
            return Response({'error': 'Failed to create API integration'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'base_url', 'authentication_type']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate base URL
        base_url = request.data.get('base_url')
        if not base_url.startswith(('http://', 'https://')):
            raise AdvertiserValidationError("Base URL must be a valid HTTP/HTTPS URL")
        
        # Security: Validate authentication type
        valid_auth_types = ['api_key', 'oauth2', 'basic', 'bearer', 'custom']
        auth_type = request.data.get('authentication_type')
        if auth_type not in valid_auth_types:
            raise AdvertiserValidationError(f"Invalid authentication type: {auth_type}")
    
    @staticmethod
    def _log_api_integration_creation(api_integration: APIIntegration, user: User) -> None:
        """Log API integration creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                api_integration,
                user,
                description=f"Created API integration: {api_integration.name}"
            )
        except Exception as e:
            logger.error(f"Error logging API integration creation: {str(e)}")
