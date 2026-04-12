"""
Campaign Management Views

This module contains Django REST Framework ViewSets for managing
campaigns, optimization, targeting, and analytics.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..database_models.campaign_model import Campaign
from ..database_models.targeting_model import Targeting
from ..database_models.analytics_model import AnalyticsReport
from .services import (
    CampaignService, CampaignOptimizationService, CampaignTargetingService,
    CampaignAnalyticsService, CampaignBudgetService
)
from .serializers import *
from ..exceptions import *
from ..utils import *


class CampaignViewSet(viewsets.ModelViewSet):
    """ViewSet for managing campaigns."""
    
    queryset = Campaign.objects.filter(is_deleted=False)
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'objective', 'bidding_strategy', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'status', 'current_spend']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return CampaignCreateSerializer
        elif self.action == 'update':
            return CampaignUpdateSerializer
        elif self.action in ['retrieve', 'list']:
            return CampaignDetailSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show campaigns from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no campaigns
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new campaign."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            campaign = CampaignService.create_campaign(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = CampaignDetailSerializer(campaign)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update campaign."""
        try:
            campaign = self.get_object()
            
            serializer = self.get_serializer(campaign, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_campaign = CampaignService.update_campaign(
                campaign.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = CampaignDetailSerializer(updated_campaign)
            return Response(response_serializer.data)
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating campaign: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Delete campaign."""
        try:
            campaign = self.get_object()
            
            success = CampaignService.delete_campaign(
                campaign.id,
                deleted_by=request.user
            )
            
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {'error': 'Failed to delete campaign'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error deleting campaign: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate campaign."""
        try:
            campaign = self.get_object()
            
            success = CampaignService.activate_campaign(
                campaign.id,
                activated_by=request.user
            )
            
            if success:
                return Response({'message': 'Campaign activated successfully'})
            else:
                return Response(
                    {'error': 'Failed to activate campaign'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error activating campaign: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause campaign."""
        try:
            campaign = self.get_object()
            
            success = CampaignService.pause_campaign(
                campaign.id,
                paused_by=request.user
            )
            
            if success:
                return Response({'message': 'Campaign paused successfully'})
            else:
                return Response(
                    {'error': 'Failed to pause campaign'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error pausing campaign: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate campaign."""
        try:
            campaign = self.get_object()
            
            new_name = request.data.get('name')
            duplicated_campaign = CampaignService.duplicate_campaign(
                campaign.id,
                new_name,
                duplicated_by=request.user
            )
            
            response_serializer = CampaignDetailSerializer(duplicated_campaign)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error duplicating campaign: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get campaign performance metrics."""
        try:
            campaign = self.get_object()
            performance_data = CampaignService.get_campaign_performance(campaign.id)
            
            return Response(performance_data)
            
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting campaign performance: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def can_spend(self, request, pk=None):
        """Check if campaign can spend specified amount."""
        try:
            campaign = self.get_object()
            
            amount = Decimal(str(request.query_params.get('amount', 0)))
            can_spend = CampaignService.can_spend(campaign.id, amount)
            
            return Response({
                'can_spend': can_spend,
                'amount': float(amount),
                'current_spend': float(campaign.current_spend),
                'remaining_budget': float(campaign.remaining_budget)
            })
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error checking spend capability: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_spend(self, request, pk=None):
        """Add spend amount to campaign."""
        try:
            campaign = self.get_object()
            
            amount = Decimal(str(request.data.get('amount', 0)))
            description = request.data.get('description', '')
            
            success = CampaignService.add_spend(campaign.id, amount, description)
            
            if success:
                return Response({'message': 'Spend added successfully'})
            else:
                return Response(
                    {'error': 'Failed to add spend'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error adding spend: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def targeting(self, request, pk=None):
        """Get campaign targeting configuration."""
        try:
            campaign = self.get_object()
            targeting = campaign.targeting
            
            if targeting:
                serializer = TargetingSerializer(targeting)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'No targeting configuration found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Error getting targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignOptimizationViewSet(viewsets.ViewSet):
    """ViewSet for campaign optimization operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def optimize(self, request):
        """Optimize campaign."""
        try:
            campaign_id = request.data.get('campaign_id')
            optimization_type = request.data.get('type', 'auto')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CampaignOptimizationService.optimize_campaign(
                campaign_id,
                optimization_type,
                optimized_by=request.user
            )
            
            if success:
                return Response({'message': 'Campaign optimized successfully'})
            else:
                return Response(
                    {'error': 'Failed to optimize campaign'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error optimizing campaign: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def optimization_report(self, request):
        """Get optimization report for campaign."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            report = CampaignOptimizationService.get_optimization_report(campaign_id)
            return Response(report)
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting optimization report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignTargetingViewSet(viewsets.ViewSet):
    """ViewSet for campaign targeting operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def update_targeting(self, request):
        """Update campaign targeting."""
        try:
            campaign_id = request.data.get('campaign_id')
            targeting_data = request.data.get('targeting', {})
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CampaignTargetingService.update_targeting(
                campaign_id,
                targeting_data,
                updated_by=request.user
            )
            
            if success:
                return Response({'message': 'Targeting updated successfully'})
            else:
                return Response(
                    {'error': 'Failed to update targeting'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_targeting(self, request):
        """Validate campaign targeting."""
        try:
            campaign_id = request.data.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            validation_result = CampaignTargetingService.validate_targeting(campaign_id)
            return Response(validation_result)
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error validating targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def targeting_summary(self, request):
        """Get targeting summary for campaign."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            summary = CampaignTargetingService.get_targeting_summary(campaign_id)
            return Response(summary)
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting targeting summary: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def expand_targeting(self, request):
        """Get targeting expansion suggestions."""
        try:
            campaign_id = request.data.get('campaign_id')
            expansion_type = request.data.get('type', 'similar')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            suggestions = CampaignTargetingService.expand_targeting(
                campaign_id,
                expansion_type
            )
            return Response(suggestions)
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error expanding targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for campaign analytics operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get campaign analytics data."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            date_range = {
                'start_date': request.query_params.get('start_date'),
                'end_date': request.query_params.get('end_date')
            }
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter out None values from date_range
            date_range = {k: v for k, v in date_range.items() if v is not None}
            
            analytics_data = CampaignAnalyticsService.get_analytics(
                campaign_id,
                date_range if date_range else None
            )
            return Response(analytics_data)
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def generate_report(self, request):
        """Generate campaign report."""
        try:
            campaign_id = request.data.get('campaign_id')
            report_type = request.data.get('type', 'performance')
            date_range = {
                'start_date': request.data.get('start_date'),
                'end_date': request.data.get('end_date')
            }
            format_type = request.data.get('format', 'pdf')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter out None values from date_range
            date_range = {k: v for k, v in date_range.items() if v is not None}
            
            report_file = CampaignAnalyticsService.generate_report(
                campaign_id,
                report_type,
                date_range if date_range else None,
                format_type
            )
            
            return Response({
                'message': 'Report generated successfully',
                'file_path': report_file
            })
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignBudgetViewSet(viewsets.ViewSet):
    """ViewSet for campaign budget operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def update_budget(self, request):
        """Update campaign budget settings."""
        try:
            campaign_id = request.data.get('campaign_id')
            budget_data = request.data.get('budget', {})
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CampaignBudgetService.update_budget(
                campaign_id,
                budget_data,
                updated_by=request.user
            )
            
            if success:
                return Response({'message': 'Budget updated successfully'})
            else:
                return Response(
                    {'error': 'Failed to update budget'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating budget: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def budget_summary(self, request):
        """Get budget summary for campaign."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            summary = CampaignBudgetService.get_budget_summary(campaign_id)
            return Response(summary)
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CampaignServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting budget summary: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def budget_alerts(self, request):
        """Check for budget alerts."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            alerts = CampaignBudgetService.check_budget_alerts(campaign_id)
            return Response({
                'alerts': alerts,
                'has_alerts': len(alerts) > 0
            })
            
        except CampaignNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error checking budget alerts: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
