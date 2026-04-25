"""
Advertiser Offer ViewSet

Comprehensive ViewSet for offer management,
including CRUD operations, submission, and preview.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction

from ..models.offer import AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist
try:
    from ..services import OfferService
except ImportError:
    OfferService = None
try:
    from ..services import OfferModerationService
except ImportError:
    OfferModerationService = None
try:
    from ..services import OfferPublishService
except ImportError:
    OfferPublishService = None
from ..serializers import AdvertiserOfferSerializer, OfferRequirementSerializer, OfferCreativeSerializer, OfferBlacklistSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdvertiserOfferViewSet(viewsets.ModelViewSet):
    """
    ViewSet for advertiser offer management.
    
    Provides CRUD operations, submission workflows,
    and offer lifecycle management.
    """
    
    queryset = AdvertiserOffer.objects.all()
    serializer_class = AdvertiserOfferSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all offers
            return AdvertiserOffer.objects.all()
        else:
            # Advertisers can only see their own offers
            return AdvertiserOffer.objects.filter(advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create offer with associated advertiser."""
        user = self.request.user
        
        # Get advertiser for user
        from ..models.advertiser import Advertiser
        advertiser = get_object_or_404(Advertiser, user=user)
        
        offer_service = OfferService()
        offer = offer_service.create_offer(advertiser, serializer.validated_data)
        serializer.instance = offer
    
    @action(detail=True, methods=['post'])
    def submit_for_review(self, request, pk=None):
        """
        Submit offer for review.
        
        Initiates the approval workflow.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if offer.status not in ['draft', 'rejected']:
            return Response(
                {'detail': f'Cannot submit offer in {offer.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        
        try:
            offer_service = OfferService()
            submitted_offer = offer_service.submit_for_review(offer, notes)
            
            return Response({
                'detail': 'Offer submitted for review successfully',
                'status': submitted_offer.status,
                'submitted_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error submitting offer for review: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve offer.
        
        Only staff members can approve offers.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        offer = self.get_object()
        
        if offer.status != 'pending_review':
            return Response(
                {'detail': f'Cannot approve offer in {offer.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        
        try:
            offer_service = OfferService()
            approved_offer = offer_service.approve_offer(offer, request.user, notes)
            
            return Response({
                'detail': 'Offer approved successfully',
                'status': approved_offer.status,
                'approved_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error approving offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject offer.
        
        Only staff members can reject offers.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        offer = self.get_object()
        
        if offer.status != 'pending_review':
            return Response(
                {'detail': f'Cannot reject offer in {offer.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')
        
        if not reason:
            return Response(
                {'detail': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            offer_service = OfferService()
            rejected_offer = offer_service.reject_offer(offer, request.user, reason, notes)
            
            return Response({
                'detail': 'Offer rejected',
                'status': rejected_offer.status,
                'rejected_at': timezone.now().isoformat(),
                'rejection_reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error rejecting offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """
        Pause offer.
        
        Temporarily stops offer from being served.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if offer.status != 'active':
            return Response(
                {'detail': f'Cannot pause offer in {offer.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Manual pause')
        
        try:
            offer_service = OfferService()
            paused_offer = offer_service.pause_offer(offer, reason)
            
            return Response({
                'detail': 'Offer paused successfully',
                'status': paused_offer.status,
                'paused_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error pausing offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """
        Resume paused offer.
        
        Restarts offer serving.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if offer.status != 'paused':
            return Response(
                {'detail': f'Cannot resume offer in {offer.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            offer_service = OfferService()
            resumed_offer = offer_service.resume_offer(offer)
            
            return Response({
                'detail': 'Offer resumed successfully',
                'status': resumed_offer.status,
                'resumed_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error resuming offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def expire(self, request, pk=None):
        """
        Expire offer.
        
        Permanently ends offer.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if offer.status in ['expired', 'cancelled']:
            return Response(
                {'detail': f'Cannot expire offer in {offer.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Manual expiration')
        
        try:
            offer_service = OfferService()
            expired_offer = offer_service.expire_offer(offer, reason)
            
            return Response({
                'detail': 'Offer expired successfully',
                'status': expired_offer.status,
                'expired_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error expiring offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Get offer preview.
        
        Returns preview data for the offer.
        """
        offer = self.get_object()
        
        try:
            preview_data = {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'payout_type': offer.payout_type,
                'payout_amount': float(offer.payout_amount),
                'currency': offer.currency,
                'tracking_url': offer.tracking_url,
                'preview_url': offer.preview_url,
                'requirements': [],
                'creatives': [],
                'status': offer.status,
                'is_private': offer.is_private,
                'allowed_countries': offer.allowed_countries,
                'blocked_countries': offer.blocked_countries,
                'allowed_devices': offer.allowed_devices,
                'blocked_devices': offer.blocked_devices,
                'quality_score': float(offer.quality_score),
                'conversion_rate': float(offer.conversion_rate),
                'start_date': offer.start_date.isoformat() if offer.start_date else None,
                'end_date': offer.end_date.isoformat() if offer.end_date else None,
            }
            
            # Add requirements
            requirements = OfferRequirement.objects.filter(offer=offer)
            preview_data['requirements'] = [
                {
                    'id': req.id,
                    'requirement_type': req.requirement_type,
                    'instructions': req.instructions,
                    'status': req.status,
                    'proof_required': req.proof_required,
                }
                for req in requirements
            ]
            
            # Add creatives
            creatives = OfferCreative.objects.filter(offer=offer)
            preview_data['creatives'] = [
                {
                    'id': creative.id,
                    'name': creative.name,
                    'creative_type': creative.creative_type,
                    'file_url': creative.file.url if creative.file else None,
                    'status': creative.status,
                    'is_approved': creative.is_approved,
                }
                for creative in creatives
            ]
            
            return Response(preview_data)
            
        except Exception as e:
            logger.error(f"Error getting offer preview: {e}")
            return Response(
                {'detail': 'Failed to get preview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Get offer statistics.
        
        Returns performance metrics and analytics.
        """
        offer = self.get_object()
        
        try:
            offer_service = OfferService()
            stats = offer_service.get_offer_stats(offer)
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting offer statistics: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def moderate(self, request, pk=None):
        """
        Moderate offer content.
        
        Runs content review and brand safety checks.
        """
        offer = self.get_object()
        
        # Check permissions
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            moderation_service = OfferModerationService()
            moderation_result = moderation_service.review_offer_content(offer, request.user)
            
            return Response(moderation_result)
            
        except Exception as e:
            logger.error(f"Error moderating offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publish offer to network.
        
        Makes offer available for serving.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if offer.status != 'active':
            return Response(
                {'detail': 'Offer must be active to publish'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        publish_config = request.data.get('config', {})
        
        try:
            publish_service = OfferPublishService()
            publish_result = publish_service.publish_offer(offer, request.user, publish_config)
            
            return Response(publish_result)
            
        except Exception as e:
            logger.error(f"Error publishing offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """
        Unpublish offer from network.
        
        Removes offer from serving.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        reason = request.data.get('reason', 'Manual unpublish')
        
        try:
            publish_service = OfferPublishService()
            unpublish_result = publish_service.unpublish_offer(offer, request.user, reason)
            
            return Response(unpublish_result)
            
        except Exception as e:
            logger.error(f"Error unpublishing offer: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def requirements(self, request, pk=None):
        """
        Get offer requirements.
        
        Returns all requirements for the offer.
        """
        offer = self.get_object()
        
        requirements = OfferRequirement.objects.filter(offer=offer).order_by('-created_at')
        serializer = OfferRequirementSerializer(requirements, many=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_requirement(self, request, pk=None):
        """
        Add requirement to offer.
        
        Create new requirement for the offer.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        requirement_data = request.data.copy()
        requirement_data['offer'] = offer.id
        
        serializer = OfferRequirementSerializer(data=requirement_data)
        if serializer.is_valid():
            requirement = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def creatives(self, request, pk=None):
        """
        Get offer creatives.
        
        Returns all creative assets for the offer.
        """
        offer = self.get_object()
        
        creatives = OfferCreative.objects.filter(offer=offer).order_by('-created_at')
        serializer = OfferCreativeSerializer(creatives, many=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_creative(self, request, pk=None):
        """
        Add creative to offer.
        
        Upload and attach creative asset.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        creative_data = request.data.copy()
        creative_data['offer'] = offer.id
        
        serializer = OfferCreativeSerializer(data=creative_data)
        if serializer.is_valid():
            creative = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def blacklists(self, request, pk=None):
        """
        Get offer blacklists.
        
        Returns all blacklist rules for the offer.
        """
        offer = self.get_object()
        
        blacklists = OfferBlacklist.objects.filter(offer=offer).order_by('-created_at')
        serializer = OfferBlacklistSerializer(blacklists, many=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_blacklist(self, request, pk=None):
        """
        Add blacklist rule to offer.
        
        Create new blacklist rule for the offer.
        """
        offer = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        blacklist_data = request.data.copy()
        blacklist_data['offer'] = offer.id
        
        serializer = OfferBlacklistSerializer(data=blacklist_data)
        if serializer.is_valid():
            blacklist = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Search offers.
        
        Query parameters:
        - q: Search query
        - status: Filter by status
        - payout_type: Filter by payout type
        - is_private: Filter by privacy
        """
        query = request.query_params.get('q', '')
        status = request.query_params.get('status')
        payout_type = request.query_params.get('payout_type')
        is_private = request.query_params.get('is_private')
        
        offer_service = OfferService()
        
        filters = {}
        if status:
            filters['status'] = status
        if payout_type:
            filters['payout_type'] = payout_type
        if is_private is not None:
            filters['is_private'] = is_private.lower() == 'true'
        
        try:
            offers = offer_service.search_offers(query, filters)
            
            # Serialize results
            serializer = self.get_serializer(offers, many=True)
            
            return Response({
                'results': serializer.data,
                'count': len(offers),
                'query': query,
                'filters': filters
            })
            
        except Exception as e:
            logger.error(f"Error searching offers: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def published_offers(self, request):
        """
        Get published offers.
        
        Returns all active and published offers.
        """
        try:
            offer_service = OfferService()
            filters = {}
            
            # Apply filters from query parameters
            payout_type = request.query_params.get('payout_type')
            min_payout = request.query_params.get('min_payout')
            max_payout = request.query_params.get('max_payout')
            countries = request.query_params.getlist('countries')
            
            if payout_type:
                filters['payout_type'] = payout_type
            if min_payout:
                filters['min_payout'] = float(min_payout)
            if max_payout:
                filters['max_payout'] = float(max_payout)
            if countries:
                filters['countries'] = countries
            
            published_offers = offer_service.get_published_offers(filters=filters)
            
            return Response(published_offers)
            
        except Exception as e:
            logger.error(f"Error getting published offers: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """
        Bulk approve multiple offers.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        offer_ids = request.data.get('offer_ids', [])
        notes = request.data.get('notes', '')
        
        if not offer_ids:
            return Response(
                {'detail': 'No offer IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            offer_service = OfferService()
            
            results = {
                'approved': 0,
                'failed': 0,
                'errors': []
            }
            
            for offer_id in offer_ids:
                try:
                    offer = AdvertiserOffer.objects.get(id=offer_id)
                    if offer.status == 'pending_review':
                        offer_service.approve_offer(offer, request.user, notes)
                        results['approved'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'offer_id': offer_id,
                            'error': f'Cannot approve offer in {offer.status} status'
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'offer_id': offer_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk approve: {e}")
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
        payout_type = request.query_params.get('payout_type')
        is_private = request.query_params.get('is_private')
        search = request.query_params.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if payout_type:
            queryset = queryset.filter(payout_type=payout_type)
        
        if is_private is not None:
            queryset = queryset.filter(is_private=is_private.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
