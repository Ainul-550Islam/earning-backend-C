"""
Bidding Optimization Views

This module provides DRF ViewSets for bidding optimization including
bid management, strategy management, budget optimization, and automated bidding.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.bidding_model import Bid, BidStrategy, BidOptimization, BudgetAllocation
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    BiddingService, BidStrategyService, BudgetOptimizationService,
    PerformanceBiddingService, AutomatedBiddingService
)

User = get_user_model()


class BiddingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing bids."""
    
    queryset = Bid.objects.all()
    serializer_class = None  # Will be set in serializers.py
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['campaign', 'bid_type', 'bid_strategy', 'status']
    
    def get_queryset(self):
        """Filter bids by advertiser."""
        user = self.request.user
        if user.is_superuser:
            return Bid.objects.all()
        
        # Get advertiser for the user
        try:
            advertiser = Advertiser.objects.get(user=user, is_deleted=False)
            return Bid.objects.filter(campaign__advertiser=advertiser)
        except Advertiser.DoesNotExist:
            return Bid.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a new bid."""
        try:
            bid_data = request.data
            bid = BiddingService.create_bid(bid_data, request.user)
            
            # Serialize response
            response_data = {
                'id': str(bid.id),
                'campaign_id': str(bid.campaign.id),
                'bid_type': bid.bid_type,
                'bid_amount': float(bid.bid_amount),
                'bid_currency': bid.bid_currency,
                'bid_strategy': bid.bid_strategy,
                'max_bid': float(bid.max_bid),
                'min_bid': float(bid.min_bid),
                'status': bid.status,
                'created_at': bid.created_at.isoformat()
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating bid: {str(e)}")
            return Response({'error': 'Failed to create bid'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def optimize(self, request, pk=None):
        """Optimize bid."""
        try:
            bid_id = UUID(pk)
            optimization_data = request.data
            
            bid = BiddingService.optimize_bid(bid_id, optimization_data, request.user)
            
            response_data = {
                'id': str(bid.id),
                'bid_amount': float(bid.bid_amount),
                'optimized_at': bid.optimized_at.isoformat(),
                'optimization_metadata': bid.optimization_metadata
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error optimizing bid: {str(e)}")
            return Response({'error': 'Failed to optimize bid'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get bid performance."""
        try:
            bid_id = UUID(pk)
            performance_data = BiddingService.get_bid_performance(bid_id)
            
            return Response(performance_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting bid performance: {str(e)}")
            return Response({'error': 'Failed to get bid performance'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get bidding statistics."""
        try:
            user = request.user
            if user.is_superuser:
                bids = Bid.objects.all()
            else:
                advertiser = Advertiser.objects.get(user=user, is_deleted=False)
                bids = Bid.objects.filter(campaign__advertiser=advertiser)
            
            # Calculate statistics
            total_bids = bids.count()
            active_bids = bids.filter(status='active').count()
            
            # Calculate by bid type
            bids_by_type = {}
            for bid_type in ['cpc', 'cpm', 'cpa', 'cpv']:
                count = bids.filter(bid_type=bid_type).count()
                bids_by_type[bid_type] = count
            
            # Calculate average bid amounts
            avg_bid_amount = bids.aggregate(
                avg=Avg('bid_amount')
            )['avg'] or 0
            
            return Response({
                'total_bids': total_bids,
                'active_bids': active_bids,
                'bids_by_type': bids_by_type,
                'average_bid_amount': float(avg_bid_amount)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting bidding statistics: {str(e)}")
            return Response({'error': 'Failed to get statistics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BidStrategyViewSet(viewsets.ModelViewSet):
    """ViewSet for managing bid strategies."""
    
    queryset = BidStrategy.objects.all()
    serializer_class = None  # Will be set in serializers.py
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'strategy_type', 'is_active']
    
    def get_queryset(self):
        """Filter strategies by advertiser."""
        user = self.request.user
        if user.is_superuser:
            return BidStrategy.objects.all()
        
        try:
            advertiser = Advertiser.objects.get(user=user, is_deleted=False)
            return BidStrategy.objects.filter(advertiser=advertiser)
        except Advertiser.DoesNotExist:
            return BidStrategy.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a new bid strategy."""
        try:
            strategy_data = request.data
            strategy = BidStrategyService.create_strategy(strategy_data, request.user)
            
            response_data = {
                'id': str(strategy.id),
                'advertiser_id': str(strategy.advertiser.id),
                'strategy_type': strategy.strategy_type,
                'name': strategy.name,
                'description': strategy.description,
                'target_metric': strategy.target_metric,
                'target_value': float(strategy.target_value),
                'is_active': strategy.is_active,
                'created_at': strategy.created_at.isoformat()
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating bid strategy: {str(e)}")
            return Response({'error': 'Failed to create bid strategy'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Apply bid strategy to campaigns."""
        try:
            strategy_id = UUID(pk)
            campaign_ids = request.data.get('campaign_ids', [])
            
            if not campaign_ids:
                return Response({'error': 'campaign_ids is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Convert string IDs to UUIDs
            campaign_uuids = [UUID(cid) for cid in campaign_ids]
            
            success = BidStrategyService.apply_strategy(strategy_id, campaign_uuids, request.user)
            
            if success:
                return Response({'message': 'Strategy applied successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to apply strategy'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error applying bid strategy: {str(e)}")
            return Response({'error': 'Failed to apply strategy'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate bid strategy."""
        try:
            strategy = self.get_object()
            strategy.is_active = True
            strategy.save(update_fields=['is_active'])
            
            return Response({'message': 'Strategy activated'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error activating strategy: {str(e)}")
            return Response({'error': 'Failed to activate strategy'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate bid strategy."""
        try:
            strategy = self.get_object()
            strategy.is_active = False
            strategy.save(update_fields=['is_active'])
            
            return Response({'message': 'Strategy deactivated'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deactivating strategy: {str(e)}")
            return Response({'error': 'Failed to deactivate strategy'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BudgetOptimizationViewSet(viewsets.ViewSet):
    """ViewSet for budget optimization."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def optimize(self, request):
        """Optimize campaign budget."""
        try:
            campaign_id = request.data.get('campaign_id')
            optimization_data = request.data
            
            if not campaign_id:
                return Response({'error': 'campaign_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            result = BudgetOptimizationService.optimize_budget(
                UUID(campaign_id), optimization_data, request.user
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error optimizing budget: {str(e)}")
            return Response({'error': 'Failed to optimize budget'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Get budget optimization recommendations."""
        try:
            user = request.user
            if user.is_superuser:
                campaigns = Campaign.objects.filter(is_deleted=False)
            else:
                advertiser = Advertiser.objects.get(user=user, is_deleted=False)
                campaigns = Campaign.objects.filter(advertiser=advertiser, is_deleted=False)
            
            recommendations = []
            
            for campaign in campaigns:
                # Mock recommendation logic
                if campaign.daily_budget and campaign.daily_budget > 100:
                    recommendations.append({
                        'campaign_id': str(campaign.id),
                        'campaign_name': campaign.name,
                        'current_budget': float(campaign.daily_budget),
                        'recommended_budget': float(campaign.daily_budget * 1.1),
                        'reason': 'Performance indicates potential for increased budget',
                        'confidence': 0.8
                    })
            
            return Response({'recommendations': recommendations}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting budget recommendations: {str(e)}")
            return Response({'error': 'Failed to get recommendations'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PerformanceBiddingViewSet(viewsets.ViewSet):
    """ViewSet for performance-based bidding."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def enable(self, request):
        """Enable performance-based bidding."""
        try:
            campaign_id = request.data.get('campaign_id')
            config = request.data.get('config', {})
            
            if not campaign_id:
                return Response({'error': 'campaign_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            success = PerformanceBiddingService.enable_performance_bidding(
                UUID(campaign_id), config, request.user
            )
            
            if success:
                return Response({'message': 'Performance bidding enabled'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to enable performance bidding'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error enabling performance bidding: {str(e)}")
            return Response({'error': 'Failed to enable performance bidding'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutomatedBiddingViewSet(viewsets.ViewSet):
    """ViewSet for automated bidding."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def create_rule(self, request):
        """Create automated bidding rule."""
        try:
            rule_data = request.data
            result = AutomatedBiddingService.create_automated_rule(rule_data, request.user)
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating automated bidding rule: {str(e)}")
            return Response({'error': 'Failed to create automated bidding rule'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def rules(self, request):
        """Get automated bidding rules."""
        try:
            user = request.user
            
            # Mock rules data
            rules = [
                {
                    'id': 'rule_1',
                    'name': 'Increase bid on high CTR',
                    'condition': 'ctr > 5%',
                    'action': 'increase_bid_by_10%',
                    'is_active': True
                },
                {
                    'id': 'rule_2',
                    'name': 'Decrease bid on low CPA',
                    'condition': 'cpa < target_cpa',
                    'action': 'decrease_bid_by_5%',
                    'is_active': False
                }
            ]
            
            return Response({'rules': rules}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting automated bidding rules: {str(e)}")
            return Response({'error': 'Failed to get rules'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
