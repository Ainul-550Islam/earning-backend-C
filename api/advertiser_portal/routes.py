"""
API Routes and ViewSets for Advertiser Portal

This module contains Django REST Framework ViewSets and API views
for handling HTTP requests and responses.
"""

from typing import Optional, List, Dict, Any
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django_filters.rest_framework import DjangoFilterBackend

from .models import *
from .schemas import *
from .serializers import *
from .permissions import *
from .services import *
from .utils import *


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination class."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdvertiserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing advertisers.
    
    Provides CRUD operations and additional actions for advertiser management.
    """
    queryset = Advertiser.objects.filter(is_deleted=False)
    serializer_class = AdvertiserSerializer
    permission_classes = [IsAuthenticated, IsAdvertiserOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'industry', 'is_verified']
    search_fields = ['company_name', 'contact_email', 'website']
    ordering_fields = ['created_at', 'company_name', 'status']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        summary="List Advertisers",
        description="Retrieve a list of advertisers with optional filtering and search",
        parameters=[
            OpenApiParameter(name='status', type=OpenApiTypes.STR, description='Filter by status'),
            OpenApiParameter(name='industry', type=OpenApiTypes.STR, description='Filter by industry'),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, description='Search in company name, email, website'),
        ]
    )
    def list(self, request, *args, **kwargs):
        """List advertisers with filtering."""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create Advertiser",
        description="Create a new advertiser account",
        request=AdvertiserCreate,
        responses={201: AdvertiserResponse}
    )
    def create(self, request, *args, **kwargs):
        """Create a new advertiser."""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve Advertiser",
        description="Get detailed information about a specific advertiser"
    )
    def retrieve(self, request, *args, **kwargs):
        """Get advertiser details."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update Advertiser",
        description="Update advertiser information",
        request=AdvertiserUpdate,
        responses={200: AdvertiserResponse}
    )
    def update(self, request, *args, **kwargs):
        """Update advertiser."""
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partial Update Advertiser",
        description="Partially update advertiser information",
        request=AdvertiserUpdate,
        responses={200: AdvertiserResponse}
    )
    def partial_update(self, request, *args, **kwargs):
        """Partially update advertiser."""
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Advertiser",
        description="Soft delete an advertiser account"
    )
    def destroy(self, request, *args, **kwargs):
        """Soft delete advertiser."""
        advertiser = self.get_object()
        advertiser.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Get Advertiser Campaigns",
        description="Retrieve all campaigns for a specific advertiser"
    )
    @action(detail=True, methods=['get'])
    def campaigns(self, request, pk=None):
        """Get all campaigns for this advertiser."""
        advertiser = self.get_object()
        campaigns = Campaign.objects.filter(
            advertiser=advertiser,
            is_deleted=False
        ).order_by('-created_at')
        
        page = self.paginate_queryset(campaigns)
        if page is not None:
            serializer = CampaignSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CampaignSerializer(campaigns, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get Advertiser Analytics",
        description="Retrieve analytics data for a specific advertiser",
        parameters=[
            OpenApiParameter(name='start_date', type=OpenApiTypes.DATE, required=True),
            OpenApiParameter(name='end_date', type=OpenApiTypes.DATE, required=True),
            OpenApiParameter(name='metrics', type=OpenApiTypes.STR, description='Comma-separated metrics'),
        ]
    )
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get analytics for this advertiser."""
        advertiser = self.get_object()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        metrics = request.query_params.get('metrics', 'impressions,clicks,conversions,cost')
        
        if not start_date or not end_date:
            raise ValidationError("start_date and end_date are required")
        
        analytics_service = AnalyticsService()
        data = analytics_service.get_advertiser_analytics(
            advertiser_id=advertiser.id,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics.split(',')
        )
        
        return Response(data)

    @extend_schema(
        summary="Verify Advertiser",
        description="Verify advertiser account (Admin only)"
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """Verify advertiser account."""
        advertiser = self.get_object()
        advertiser_service = AdvertiserService()
        result = advertiser_service.verify_advertiser(advertiser, verified_by=request.user)
        
        if result['success']:
            return Response({
                'message': 'Advertiser verified successfully',
                'data': AdvertiserSerializer(advertiser).data
            })
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Regenerate API Key",
        description="Generate new API key for advertiser"
    )
    @action(detail=True, methods=['post'])
    def regenerate_api_key(self, request, pk=None):
        """Regenerate API key for advertiser."""
        advertiser = self.get_object()
        advertiser_service = AdvertiserService()
        new_api_key = advertiser_service.generate_api_key(advertiser)
        
        return Response({
            'message': 'API key regenerated successfully',
            'api_key': new_api_key
        })


class CampaignViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing advertising campaigns.
    """
    queryset = Campaign.objects.filter(is_deleted=False)
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated, IsCampaignOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'objective', 'advertiser', 'bidding_strategy']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'status', 'daily_budget']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Filter campaigns based on user permissions."""
        user = self.request.user
        if user.is_staff:
            return Campaign.objects.filter(is_deleted=False)
        else:
            return Campaign.objects.filter(
                advertiser__user=user,
                is_deleted=False
            )

    @extend_schema(
        summary="List Campaigns",
        description="Retrieve a list of campaigns with optional filtering"
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create Campaign",
        description="Create a new advertising campaign",
        request=CampaignCreate,
        responses={201: CampaignResponse}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Activate Campaign",
        description="Activate a campaign for serving ads"
    )
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate campaign."""
        campaign = self.get_object()
        campaign_service = CampaignService()
        result = campaign_service.activate_campaign(campaign)
        
        if result['success']:
            return Response({'message': 'Campaign activated successfully'})
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Pause Campaign",
        description="Pause a campaign temporarily"
    )
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause campaign."""
        campaign = self.get_object()
        campaign_service = CampaignService()
        result = campaign_service.pause_campaign(campaign)
        
        if result['success']:
            return Response({'message': 'Campaign paused successfully'})
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Get Campaign Performance",
        description="Retrieve performance metrics for a campaign"
    )
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get campaign performance data."""
        campaign = self.get_object()
        analytics_service = AnalyticsService()
        performance_data = analytics_service.get_campaign_performance(campaign.id)
        
        return Response(performance_data)

    @extend_schema(
        summary="Duplicate Campaign",
        description="Create a copy of an existing campaign"
    )
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate campaign."""
        campaign = self.get_object()
        campaign_service = CampaignService()
        new_campaign = campaign_service.duplicate_campaign(campaign, request.data.get('name'))
        
        serializer = CampaignSerializer(new_campaign)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreativeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ad creatives.
    """
    queryset = Creative.objects.filter(is_deleted=False)
    serializer_class = CreativeSerializer
    permission_classes = [IsAuthenticated, IsCreativeOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'type', 'campaign', 'is_approved']
    search_fields = ['name', 'title', 'description']
    ordering_fields = ['created_at', 'name', 'status']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        summary="Upload Creative",
        description="Upload a new creative file",
        request=CreativeCreate,
        responses={201: CreativeResponse}
    )
    def create(self, request, *args, **kwargs):
        """Upload creative."""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Approve Creative",
        description="Approve a creative for serving (Admin only)"
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve creative."""
        creative = self.get_object()
        creative_service = CreativeService()
        result = creative_service.approve_creative(creative, approved_by=request.user)
        
        if result['success']:
            return Response({'message': 'Creative approved successfully'})
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Reject Creative",
        description="Reject a creative with reason (Admin only)"
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Reject creative."""
        creative = self.get_object()
        reason = request.data.get('reason', 'Creative rejected')
        creative_service = CreativeService()
        result = creative_service.reject_creative(creative, reason, rejected_by=request.user)
        
        if result['success']:
            return Response({'message': 'Creative rejected successfully'})
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )


class TargetingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing campaign targeting.
    """
    queryset = Targeting.objects.filter(is_deleted=False)
    serializer_class = TargetingSerializer
    permission_classes = [IsAuthenticated, IsTargetingOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['campaign']
    ordering = ['-created_at']

    @extend_schema(
        summary="Validate Targeting",
        description="Validate targeting configuration
    )
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Validate targeting configuration."""
        targeting = self.get_object()
        targeting_service = TargetingService()
        result = targeting_service.validate_targeting(targeting)
        
        return Response({
            'is_valid': result['is_valid'],
            'errors': result.get('errors', []),
            'warnings': result.get('warnings', [])
        })


class AnalyticsViewSet(viewsets.GenericViewSet):
    """
    ViewSet for analytics and reporting.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        summary="Get Analytics Data",
        description="Retrieve analytics data with custom dimensions and metrics",
        parameters=[
            OpenApiParameter(name='start_date', type=OpenApiTypes.DATE, required=True),
            OpenApiParameter(name='end_date', type=OpenApiTypes.DATE, required=True),
            OpenApiParameter(name='advertiser_ids', type=OpenApiTypes.STR),
            OpenApiParameter(name='campaign_ids', type=OpenApiTypes.STR),
            OpenApiParameter(name='metrics', type=OpenApiTypes.STR),
            OpenApiParameter(name='dimensions', type=OpenApiTypes.STR),
        ]
    )
    @action(detail=False, methods=['get'])
    def data(self, request):
        """Get analytics data."""
        query_params = AnalyticsQuery(**request.query_params.dict())
        analytics_service = AnalyticsService()
        data = analytics_service.get_analytics_data(query_params)
        
        return Response(AnalyticsResponse(
            data=data['rows'],
            total_rows=data['total'],
            has_more=data['has_more'],
            query=query_params
        ).dict())

    @extend_schema(
        summary="Get Real-time Dashboard",
        description="Get real-time dashboard data"
    )
    @action(detail=False, methods=['get'])
    def realtime(self, request):
        """Get real-time dashboard data."""
        analytics_service = AnalyticsService()
        dashboard_data = analytics_service.get_realtime_dashboard(
            user=request.user
        )
        
        return Response(dashboard_data)


class BillingViewSet(viewsets.GenericViewSet):
    """
    ViewSet for billing and payment operations.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Billing Summary",
        description="Get billing summary for advertiser"
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get billing summary."""
        billing_service = BillingService()
        summary = billing_service.get_billing_summary(request.user)
        
        return Response(summary)

    @extend_schema(
        summary="Get Invoices",
        description="Get list of invoices"
    )
    @action(detail=False, methods=['get'])
    def invoices(self, request):
        """Get invoices."""
        billing_service = BillingService()
        invoices = billing_service.get_invoices(request.user)
        
        page = self.paginate_queryset(invoices)
        if page is not None:
            serializer = InvoiceSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Make Payment",
        description="Process a payment"
    )
    @action(detail=False, methods=['post'])
    def payment(self, request):
        """Process payment."""
        billing_service = BillingService()
        result = billing_service.process_payment(
            user=request.user,
            amount=request.data.get('amount'),
            payment_method_id=request.data.get('payment_method_id')
        )
        
        if result['success']:
            return Response(result['data'])
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )


# API Root View
class APIRootView(viewsets.GenericViewSet):
    """
    API Root view showing available endpoints.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Show API endpoints."""
        return Response({
            'advertisers': '/api/advertiser_portal/advertisers/',
            'campaigns': '/api/advertiser_portal/campaigns/',
            'creatives': '/api/advertiser_portal/creatives/',
            'targeting': '/api/advertiser_portal/targeting/',
            'analytics': '/api/advertiser_portal/analytics/',
            'billing': '/api/advertiser_portal/billing/',
        })
