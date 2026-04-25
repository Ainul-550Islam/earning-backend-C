"""
Campaign Bid ViewSet

ViewSet for campaign bid management,
including bid configuration and auto-optimization.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from ..models.campaign import AdCampaign, CampaignBid
try:
    from ..services import CampaignOptimizer
except ImportError:
    CampaignOptimizer = None
from ..serializers import CampaignBidSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class CampaignBidViewSet(viewsets.ModelViewSet):
    """
    ViewSet for campaign bid management.
    
    Handles bid configuration, optimization settings,
    and performance-based bid adjustments.
    """
    
    queryset = CampaignBid.objects.all()
    serializer_class = CampaignBidSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all bid configurations
            return CampaignBid.objects.all()
        else:
            # Advertisers can only see their own bid configurations
            return CampaignBid.objects.filter(campaign__advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create bid configuration with associated campaign."""
        campaign_id = serializer.validated_data.get('campaign')
        
        if not campaign_id:
            raise ValueError("Campaign ID is required")
        
        campaign = get_object_or_404(AdCampaign, id=campaign_id)
        
        # Check permissions
        if not (self.request.user.is_staff or campaign.advertiser.user == self.request.user):
            raise PermissionError("Permission denied")
        
        bid_config = serializer.save()
        # Set the campaign for the serializer
        serializer.instance = bid_config
    
    @action(detail=True, methods=['post'])
    def enable_auto_optimize(self, request, pk=None):
        """
        Enable automatic bid optimization.
        
        Activates AI-driven bid optimization.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            bid_config.auto_optimize = True
            bid_config.last_optimized_at = timezone.now()
            bid_config.save()
            
            return Response({
                'detail': 'Auto-optimization enabled successfully',
                'auto_optimize': True,
                'last_optimized_at': bid_config.last_optimized_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error enabling auto-optimization: {e}")
            return Response(
                {'detail': 'Failed to enable auto-optimization'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def disable_auto_optimize(self, request, pk=None):
        """
        Disable automatic bid optimization.
        
        Deactivates AI-driven bid optimization.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            bid_config.auto_optimize = False
            bid_config.save()
            
            return Response({
                'detail': 'Auto-optimization disabled successfully',
                'auto_optimize': False
            })
            
        except Exception as e:
            logger.error(f"Error disabling auto-optimization: {e}")
            return Response(
                {'detail': 'Failed to disable auto-optimization'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def optimize_now(self, request, pk=None):
        """
        Run immediate bid optimization.
        
        Manually triggers bid optimization algorithm.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if bid_config.campaign.status != 'active':
            return Response(
                {'detail': 'Campaign must be active to optimize bids'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            optimizer = CampaignOptimizer()
            optimization_result = optimizer.optimize_campaign_bids(bid_config.campaign)
            
            # Update last optimized timestamp
            bid_config.last_optimized_at = timezone.now()
            bid_config.save()
            
            return Response({
                'detail': 'Bid optimization completed successfully',
                'optimization_result': optimization_result,
                'last_optimized_at': bid_config.last_optimized_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error optimizing bids: {e}")
            return Response(
                {'detail': 'Failed to optimize bids'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_base_bid(self, request, pk=None):
        """
        Update base bid amount.
        
        Sets the minimum bid for the campaign.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        base_bid = request.data.get('base_bid')
        
        if base_bid is None:
            return Response(
                {'detail': 'Base bid amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if base_bid <= 0:
            return Response(
                {'detail': 'Base bid must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bid_config.base_bid = base_bid
            bid_config.save()
            
            return Response({
                'detail': 'Base bid updated successfully',
                'base_bid': float(bid_config.base_bid)
            })
            
        except Exception as e:
            logger.error(f"Error updating base bid: {e}")
            return Response(
                {'detail': 'Failed to update base bid'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_max_bid(self, request, pk=None):
        """
        Update maximum bid amount.
        
        Sets the upper limit for bid adjustments.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        max_bid = request.data.get('max_bid')
        
        if max_bid is None:
            return Response(
                {'detail': 'Max bid amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if max_bid <= 0:
            return Response(
                {'detail': 'Max bid must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bid_config.max_bid = max_bid
            bid_config.save()
            
            return Response({
                'detail': 'Max bid updated successfully',
                'max_bid': float(bid_config.max_bid)
            })
            
        except Exception as e:
            logger.error(f"Error updating max bid: {e}")
            return Response(
                {'detail': 'Failed to update max bid'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def set_target_cpa(self, request, pk=None):
        """
        Set target CPA (Cost Per Acquisition).
        
        Sets the desired cost per conversion for optimization.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        target_cpa = request.data.get('target_cpa')
        
        if target_cpa is None:
            return Response(
                {'detail': 'Target CPA is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if target_cpa <= 0:
            return Response(
                {'detail': 'Target CPA must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bid_config.target_cpa = target_cpa
            bid_config.save()
            
            return Response({
                'detail': 'Target CPA set successfully',
                'target_cpa': float(bid_config.target_cpa)
            })
            
        except Exception as e:
            logger.error(f"Error setting target CPA: {e}")
            return Response(
                {'detail': 'Failed to set target CPA'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def set_target_ctr(self, request, pk=None):
        """
        Set target CTR (Click Through Rate).
        
        Sets the desired click through rate for optimization.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        target_ctr = request.data.get('target_ctr')
        
        if target_ctr is None:
            return Response(
                {'detail': 'Target CTR is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if target_ctr <= 0 or target_ctr > 100:
            return Response(
                {'detail': 'Target CTR must be between 0 and 100'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bid_config.target_ctr = target_ctr
            bid_config.save()
            
            return Response({
                'detail': 'Target CTR set successfully',
                'target_ctr': float(bid_config.target_ctr)
            })
            
        except Exception as e:
            logger.error(f"Error setting target CTR: {e}")
            return Response(
                {'detail': 'Failed to set target CTR'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_optimization_frequency(self, request, pk=None):
        """
        Update optimization frequency.
        
        Sets how often bids should be optimized.
        """
        bid_config = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or bid_config.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        frequency = request.data.get('frequency')
        
        if frequency is None:
            return Response(
                {'detail': 'Optimization frequency is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_frequencies = ['hourly', 'daily', 'weekly', 'monthly']
        if frequency not in valid_frequencies:
            return Response(
                {'detail': f'Invalid frequency. Valid options: {", ".join(valid_frequencies)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bid_config.optimization_frequency = frequency
            bid_config.save()
            
            return Response({
                'detail': 'Optimization frequency updated successfully',
                'optimization_frequency': bid_config.optimization_frequency
            })
            
        except Exception as e:
            logger.error(f"Error updating optimization frequency: {e}")
            return Response(
                {'detail': 'Failed to update optimization frequency'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        Get bid performance metrics.
        
        Returns performance data for bid optimization.
        """
        bid_config = self.get_object()
        
        try:
            # This would implement actual performance tracking
            # For now, return placeholder data
            performance_data = {
                'bid_id': bid_config.id,
                'campaign_id': bid_config.campaign.id,
                'campaign_name': bid_config.campaign.name,
                'period_days': 30,
                'current_bid': float(bid_config.base_bid),
                'max_bid': float(bid_config.max_bid),
                'target_cpa': float(bid_config.target_cpa) if bid_config.target_cpa else None,
                'target_ctr': float(bid_config.target_ctr) if bid_config.target_ctr else None,
                'auto_optimize': bid_config.auto_optimize,
                'optimization_frequency': bid_config.optimization_frequency,
                'last_optimized_at': bid_config.last_optimized_at.isoformat() if bid_config.last_optimized_at else None,
                'metrics': {
                    'impressions': 0,
                    'clicks': 0,
                    'conversions': 0,
                    'spend': 0.0,
                    'ctr': 0.0,
                    'cpa': 0.0,
                    'cpc': 0.0,
                    'actual_cpa': 0.0,
                    'actual_ctr': 0.0,
                },
                'optimization_history': [],
                'recommendations': [],
            }
            
            return Response(performance_data)
            
        except Exception as e:
            logger.error(f"Error getting bid performance: {e}")
            return Response(
                {'detail': 'Failed to get performance data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def optimization_history(self, request, pk=None):
        """
        Get optimization history.
        
        Returns historical bid adjustments and optimization results.
        """
        bid_config = self.get_object()
        
        try:
            # This would implement actual optimization history tracking
            # For now, return placeholder data
            history = {
                'bid_id': bid_config.id,
                'optimizations': [],
                'total_optimizations': 0,
                'last_optimization': None,
            }
            
            return Response(history)
            
        except Exception as e:
            logger.error(f"Error getting optimization history: {e}")
            return Response(
                {'detail': 'Failed to get optimization history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """
        Get bid optimization recommendations.
        
        Returns AI-powered recommendations for bid improvements.
        """
        bid_config = self.get_object()
        
        try:
            optimizer = CampaignOptimizer()
            recommendations = optimizer.get_bid_recommendations(bid_config.campaign)
            
            return Response(recommendations)
            
        except Exception as e:
            logger.error(f"Error getting bid recommendations: {e}")
            return Response(
                {'detail': 'Failed to get recommendations'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def optimization_settings(self, request):
        """
        Get available optimization settings.
        
        Returns configuration options for bid optimization.
        """
        try:
            settings = {
                'frequencies': {
                    'hourly': {
                        'name': 'Hourly',
                        'description': 'Optimize bids every hour',
                        'recommended_for': 'High-traffic campaigns',
                    },
                    'daily': {
                        'name': 'Daily',
                        'description': 'Optimize bids once per day',
                        'recommended_for': 'Standard campaigns',
                    },
                    'weekly': {
                        'name': 'Weekly',
                        'description': 'Optimize bids once per week',
                        'recommended_for': 'Low-traffic campaigns',
                    },
                    'monthly': {
                        'name': 'Monthly',
                        'description': 'Optimize bids once per month',
                        'recommended_for': 'Seasonal campaigns',
                    },
                },
                'algorithms': {
                    'cpa_optimization': {
                        'name': 'CPA Optimization',
                        'description': 'Optimize bids to achieve target CPA',
                        'requires': 'target_cpa',
                    },
                    'ctr_optimization': {
                        'name': 'CTR Optimization',
                        'description': 'Optimize bids to achieve target CTR',
                        'requires': 'target_ctr',
                    },
                    'hybrid_optimization': {
                        'name': 'Hybrid Optimization',
                        'description': 'Balance CPA and CTR optimization',
                        'requires': 'target_cpa, target_ctr',
                    },
                    'budget_optimization': {
                        'name': 'Budget Optimization',
                        'description': 'Optimize bids to maximize budget efficiency',
                        'requires': 'campaign_budget',
                    },
                },
                'bid_strategies': {
                    'fixed_bid': {
                        'name': 'Fixed Bid',
                        'description': 'Use fixed bid amount',
                        'suitable_for': 'Predictable traffic patterns',
                    },
                    'dynamic_bid': {
                        'name': 'Dynamic Bid',
                        'description': 'Adjust bids based on performance',
                        'suitable_for': 'Variable traffic patterns',
                    },
                    'adaptive_bid': {
                        'name': 'Adaptive Bid',
                        'description': 'Learn and adapt bid strategy',
                        'suitable_for': 'Complex campaigns',
                    },
                },
            }
            
            return Response(settings)
            
        except Exception as e:
            logger.error(f"Error getting optimization settings: {e}")
            return Response(
                {'detail': 'Failed to get optimization settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_optimize(self, request):
        """
        Bulk optimize multiple bid configurations.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        bid_ids = request.data.get('bid_ids', [])
        
        if not bid_ids:
            return Response(
                {'detail': 'No bid IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            optimizer = CampaignOptimizer()
            
            results = {
                'optimized': 0,
                'failed': 0,
                'errors': []
            }
            
            for bid_id in bid_ids:
                try:
                    bid_config = CampaignBid.objects.get(id=bid_id)
                    
                    if bid_config.campaign.status == 'active':
                        optimizer.optimize_campaign_bids(bid_config.campaign)
                        bid_config.last_optimized_at = timezone.now()
                        bid_config.save()
                        results['optimized'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'bid_id': bid_id,
                            'error': f'Campaign is not active (status: {bid_config.campaign.status})'
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'bid_id': bid_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk optimize: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        campaign_id = request.query_params.get('campaign_id')
        auto_optimize = request.query_params.get('auto_optimize')
        optimization_frequency = request.query_params.get('optimization_frequency')
        search = request.query_params.get('search')
        
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        if auto_optimize is not None:
            queryset = queryset.filter(auto_optimize=auto_optimize.lower() == 'true')
        
        if optimization_frequency:
            queryset = queryset.filter(optimization_frequency=optimization_frequency)
        
        if search:
            queryset = queryset.filter(
                Q(campaign__name__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
