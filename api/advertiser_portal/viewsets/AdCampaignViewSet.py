"""
AdCampaign ViewSet

Comprehensive ViewSet for campaign management,
including CRUD operations, lifecycle management, and cloning.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction

from ..models.campaign import AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid
try:
    from ..services import CampaignService
except ImportError:
    CampaignService = None
try:
    from ..services import CampaignBudgetService
except ImportError:
    CampaignBudgetService = None
try:
    from ..services import CampaignOptimizer
except ImportError:
    CampaignOptimizer = None
from ..serializers import AdCampaignSerializer, CampaignCreativeSerializer, CampaignTargetingSerializer, CampaignBidSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdCampaignViewSet(viewsets.ModelViewSet):
    """
    ViewSet for campaign management.
    
    Provides CRUD operations, lifecycle management,
    budget enforcement, and campaign optimization.
    """
    
    queryset = AdCampaign.objects.all()
    serializer_class = AdCampaignSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all campaigns
            return AdCampaign.objects.all()
        else:
            # Advertisers can only see their own campaigns
            return AdCampaign.objects.filter(advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create campaign with associated advertiser."""
        user = self.request.user
        
        # Get advertiser for user
        from ..models.advertiser import Advertiser
        advertiser = get_object_or_404(Advertiser, user=user)
        
        campaign_service = CampaignService()
        campaign = campaign_service.create_campaign(advertiser, serializer.validated_data)
        serializer.instance = campaign
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """
        Start campaign.
        
        Activates campaign and begins serving ads.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if campaign.status != 'draft':
            return Response(
                {'detail': f'Cannot start campaign in {campaign.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign_service = CampaignService()
            started_campaign = campaign_service.start_campaign(campaign)
            
            return Response({
                'detail': 'Campaign started successfully',
                'status': started_campaign.status,
                'started_at': started_campaign.actual_start_date.isoformat() if started_campaign.actual_start_date else None
            })
            
        except Exception as e:
            logger.error(f"Error starting campaign: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """
        Pause campaign.
        
        Temporarily stops campaign serving.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if campaign.status != 'active':
            return Response(
                {'detail': f'Cannot pause campaign in {campaign.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Manual pause')
        
        try:
            campaign_service = CampaignService()
            paused_campaign = campaign_service.pause_campaign(campaign, reason)
            
            return Response({
                'detail': 'Campaign paused successfully',
                'status': paused_campaign.status,
                'paused_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error pausing campaign: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """
        Resume paused campaign.
        
        Restarts campaign serving.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if campaign.status != 'paused':
            return Response(
                {'detail': f'Cannot resume campaign in {campaign.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign_service = CampaignService()
            resumed_campaign = campaign_service.resume_campaign(campaign)
            
            return Response({
                'detail': 'Campaign resumed successfully',
                'status': resumed_campaign.status,
                'resumed_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error resuming campaign: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        """
        End campaign.
        
        Permanently stops campaign and finalizes reporting.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if campaign.status not in ['active', 'paused']:
            return Response(
                {'detail': f'Cannot end campaign in {campaign.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Manual end')
        
        try:
            campaign_service = CampaignService()
            ended_campaign = campaign_service.end_campaign(campaign, reason)
            
            return Response({
                'detail': 'Campaign ended successfully',
                'status': ended_campaign.status,
                'ended_at': ended_campaign.actual_end_date.isoformat() if ended_campaign.actual_end_date else None
            })
            
        except Exception as e:
            logger.error(f"Error ending campaign: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel campaign.
        
        Cancels campaign and reverses charges if applicable.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if campaign.status in ['ended', 'cancelled']:
            return Response(
                {'detail': f'Cannot cancel campaign in {campaign.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Manual cancellation')
        
        try:
            campaign_service = CampaignService()
            cancelled_campaign = campaign_service.cancel_campaign(campaign, reason)
            
            return Response({
                'detail': 'Campaign cancelled successfully',
                'status': cancelled_campaign.status,
                'cancelled_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error cancelling campaign: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """
        Clone campaign.
        
        Creates a copy of the campaign with all settings.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_name = request.data.get('name')
        if not new_name:
            return Response(
                {'detail': 'New campaign name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign_service = CampaignService()
            cloned_campaign = campaign_service.clone_campaign(campaign, new_name)
            
            serializer = self.get_serializer(cloned_campaign)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error cloning campaign: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Get campaign statistics.
        
        Returns performance metrics and budget information.
        """
        campaign = self.get_object()
        
        try:
            campaign_service = CampaignService()
            stats = campaign_service.get_campaign_stats(campaign)
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting campaign statistics: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def budget_status(self, request, pk=None):
        """
        Get budget status for campaign.
        
        Returns daily and total budget information.
        """
        campaign = self.get_object()
        
        try:
            budget_service = CampaignBudgetService()
            budget_status = budget_service.get_campaign_budget_status(campaign)
            
            return Response(budget_status)
            
        except Exception as e:
            logger.error(f"Error getting budget status: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def optimize(self, request, pk=None):
        """
        Optimize campaign bids.
        
        Runs optimization algorithm to improve performance.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if campaign.status != 'active':
            return Response(
                {'detail': 'Campaign must be active to optimize'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            optimizer = CampaignOptimizer()
            optimization_result = optimizer.optimize_campaign_bids(campaign)
            
            return Response(optimization_result)
            
        except Exception as e:
            logger.error(f"Error optimizing campaign: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def creatives(self, request, pk=None):
        """
        Get campaign creatives.
        
        Returns all creative assets for the campaign.
        """
        campaign = self.get_object()
        
        creatives = CampaignCreative.objects.filter(campaign=campaign).order_by('-created_at')
        serializer = CampaignCreativeSerializer(creatives, many=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_creative(self, request, pk=None):
        """
        Add creative to campaign.
        
        Upload and attach creative asset.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        creative_data = request.data.copy()
        creative_data['campaign'] = campaign.id
        
        serializer = CampaignCreativeSerializer(data=creative_data)
        if serializer.is_valid():
            creative = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def targeting(self, request, pk=None):
        """
        Get campaign targeting rules.
        
        Returns all targeting configurations.
        """
        campaign = self.get_object()
        
        targeting_rules = CampaignTargeting.objects.filter(campaign=campaign)
        serializer = CampaignTargetingSerializer(targeting_rules, many=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_targeting(self, request, pk=None):
        """
        Update campaign targeting rules.
        
        Add or modify targeting configurations.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        targeting_data = request.data.get('targeting_rules', [])
        updated_rules = []
        
        try:
            with transaction.atomic():
                # Delete existing targeting rules
                CampaignTargeting.objects.filter(campaign=campaign).delete()
                
                # Create new targeting rules
                for rule_data in targeting_data:
                    rule_data['campaign'] = campaign.id
                    serializer = CampaignTargetingSerializer(data=rule_data)
                    if serializer.is_valid():
                        rule = serializer.save()
                        updated_rules.append(serializer.data)
                    else:
                        raise ValueError(f"Invalid targeting rule: {serializer.errors}")
            
            return Response({
                'detail': 'Targeting rules updated successfully',
                'targeting_rules': updated_rules
            })
            
        except Exception as e:
            logger.error(f"Error updating targeting: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def bids(self, request, pk=None):
        """
        Get campaign bid configurations.
        
        Returns bid settings and optimization status.
        """
        campaign = self.get_object()
        
        try:
            bids = CampaignBid.objects.filter(campaign=campaign)
            serializer = CampaignBidSerializer(bids, many=True)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting bids: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_bids(self, request, pk=None):
        """
        Update campaign bid settings.
        
        Modify bid amounts and optimization settings.
        """
        campaign = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        bid_data = request.data.get('bid_settings', {})
        
        try:
            with transaction.atomic():
                # Update or create bid settings
                bid, created = CampaignBid.objects.get_or_create(
                    campaign=campaign,
                    defaults={
                        'base_bid': bid_data.get('base_bid', 0.50),
                        'max_bid': bid_data.get('max_bid', 2.00),
                        'auto_optimize': bid_data.get('auto_optimize', False),
                        'optimization_frequency': bid_data.get('optimization_frequency', 'daily'),
                        'target_cpa': bid_data.get('target_cpa'),
                        'target_ctr': bid_data.get('target_ctr'),
                    }
                )
                
                if not created:
                    bid.base_bid = bid_data.get('base_bid', bid.base_bid)
                    bid.max_bid = bid_data.get('max_bid', bid.max_bid)
                    bid.auto_optimize = bid_data.get('auto_optimize', bid.auto_optimize)
                    bid.optimization_frequency = bid_data.get('optimization_frequency', bid.optimization_frequency)
                    bid.target_cpa = bid_data.get('target_cpa', bid.target_cpa)
                    bid.target_ctr = bid_data.get('target_ctr', bid.target_ctr)
                    bid.save()
                
                serializer = CampaignBidSerializer(bid)
                return Response({
                    'detail': 'Bid settings updated successfully',
                    'bid_settings': serializer.data
                })
            
        except Exception as e:
            logger.error(f"Error updating bids: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Search campaigns.
        
        Query parameters:
        - q: Search query
        - status: Filter by status
        - advertiser_id: Filter by advertiser
        """
        query = request.query_params.get('q', '')
        status = request.query_params.get('status')
        advertiser_id = request.query_params.get('advertiser_id')
        
        campaign_service = CampaignService()
        
        filters = {}
        if status:
            filters['status'] = status
        if advertiser_id:
            filters['advertiser_id'] = advertiser_id
        
        try:
            campaigns = campaign_service.search_campaigns(query, filters)
            
            # Serialize results
            serializer = self.get_serializer(campaigns, many=True)
            
            return Response({
                'results': serializer.data,
                'count': len(campaigns),
                'query': query,
                'filters': filters
            })
            
        except Exception as e:
            logger.error(f"Error searching campaigns: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_start(self, request):
        """
        Bulk start multiple campaigns.
        """
        campaign_ids = request.data.get('campaign_ids', [])
        
        if not campaign_ids:
            return Response(
                {'detail': 'No campaign IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign_service = CampaignService()
            
            results = {
                'started': 0,
                'failed': 0,
                'errors': []
            }
            
            for campaign_id in campaign_ids:
                try:
                    campaign = AdCampaign.objects.get(id=campaign_id)
                    
                    # Check permissions
                    if not (request.user.is_staff or campaign.advertiser.user == request.user):
                        results['failed'] += 1
                        results['errors'].append({
                            'campaign_id': campaign_id,
                            'error': 'Permission denied'
                        })
                        continue
                    
                    if campaign.status == 'draft':
                        campaign_service.start_campaign(campaign)
                        results['started'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'campaign_id': campaign_id,
                            'error': f'Cannot start campaign in {campaign.status} status'
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'campaign_id': campaign_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk start: {e}")
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
        status = request.query_params.get('status')
        advertiser_id = request.query_params.get('advertiser_id')
        search = request.query_params.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
