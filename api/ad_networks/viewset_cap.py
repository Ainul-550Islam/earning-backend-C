"""
api/ad_networks/viewset_cap.py
Capitalized ViewSets for ad networks module
SaaS-ready with tenant support
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from decimal import Decimal

from .models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferReward, UserWallet, OfferClick,
    NetworkHealthCheck, OfferDailyLimit, OfferTag, OfferTagging
)
from .serializers import (
    AdNetworkSerializer, OfferCategorySerializer, OfferSerializer,
    UserOfferEngagementSerializer, OfferConversionSerializer,
    OfferRewardSerializer, UserWalletSerializer, OfferClickSerializer,
    NetworkHealthCheckSerializer, OfferDailyLimitSerializer,
    OfferTagSerializer, OfferTaggingSerializer
)
from .permissions import (
    IsAdNetworkAdmin, IsOwnerOrReadOnly, IsVerifiedUser,
    HasTenantAccess
)
from .filters import (
    AdNetworkFilter, OfferFilter, UserOfferEngagementFilter,
    OfferConversionFilter, OfferRewardFilter, OfferClickFilter
)
from .services import (
    OfferSyncService, ConversionService, RewardService,
    FraudDetectionService, NetworkHealthService, OfferRecommendService
)
from .decorators import tenant_required, rate_limit, require_verification
from .constants import CACHE_KEY_PATTERNS

import logging

logger = logging.getLogger(__name__)


class AdNetworkViewSet(viewsets.ModelViewSet):
    """
    Capitalized ViewSet for AdNetwork model
    Admin-only access
    """
    
    queryset = AdNetwork.objects.all()
    serializer_class = AdNetworkSerializer
    permission_classes = [IsAuthenticated, IsAdNetworkAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AdNetworkFilter
    search_fields = ['name', 'network_type', 'category']
    ordering_fields = ['name', 'priority', 'created_at', 'rating', 'trust_score']
    ordering = ['-priority', 'name']
    
    def get_queryset(self):
        """Filter by tenant"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        if tenant_id:
            return super().get_queryset().filter(tenant_id=tenant_id)
        return super().get_queryset()
    
    @action(detail=True, methods=['post'])
    def SyncOffers(self, request, pk=None):
        """Sync offers from this network"""
        network = self.get_object()
        
        try:
            service = OfferSyncService(tenant_id=network.tenant_id)
            result = service.sync_network_offers(network.id)
            
            if result['success']:
                return Response({
                    'Success': True,
                    'Message': f"Synced {result['offers_synced']} offers",
                    'Details': result
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'Success': False,
                    'Error': result.get('error', 'Sync failed')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error syncing offers for network {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def HealthCheck(self, request, pk=None):
        """Check network health"""
        network = self.get_object()
        
        try:
            service = NetworkHealthService(tenant_id=network.tenant_id)
            result = service.check_single_network(network.id)
            
            return Response({
                'Success': True,
                'HealthData': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error checking health for network {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Health check failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def ToggleStatus(self, request, pk=None):
        """Toggle network status"""
        network = self.get_object()
        
        try:
            new_status = request.data.get('status')
            if new_status not in ['active', 'inactive', 'maintenance', 'suspended']:
                return Response({
                    'Success': False,
                    'Error': 'Invalid status'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            network.status = new_status
            network.save(update_fields=['status'])
            
            return Response({
                'Success': True,
                'Message': f"Network status changed to {new_status}",
                'Status': new_status
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error toggling status for network {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Status update failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferCategoryViewSet(viewsets.ModelViewSet):
    """
    Capitalized ViewSet for OfferCategory model
    """
    
    queryset = OfferCategory.objects.all()
    serializer_class = OfferCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'slug', 'description']
    ordering_fields = ['name', 'priority', 'created_at']
    ordering = ['priority', 'name']
    
    def get_queryset(self):
        """Filter by tenant and active status"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = super().get_queryset()
        
        if tenant_id:
            # OfferCategory doesn't have tenant_id, so we filter offers by tenant
            queryset = queryset.annotate(
                offer_count=Count('offer', filter=Q(offer__tenant_id=tenant_id))
            ).filter(offer_count__gt=0)
        
        return queryset.filter(is_active=True)
    
    @action(detail=True, methods=['get'])
    def Offers(self, request, pk=None):
        """Get offers for this category"""
        category = self.get_object()
        tenant_id = getattr(self.request, 'tenant_id', None)
        
        offers = Offer.objects.filter(
            category=category,
            status='active'
        )
        
        if tenant_id:
            offers = offers.filter(tenant_id=tenant_id)
        
        page = self.paginate_queryset(offers)
        if page is not None:
            serializer = OfferSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = OfferSerializer(offers, many=True)
        return Response(serializer.data)


class OfferViewSet(viewsets.ModelViewSet):
    """
    Capitalized ViewSet for Offer model
    """
    
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OfferFilter
    search_fields = ['title', 'description', 'short_description']
    ordering_fields = ['title', 'reward_amount', 'created_at', 'priority', 'conversion_rate']
    ordering = ['-priority', '-created_at']
    
    def get_queryset(self):
        """Filter by tenant and status"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = super().get_queryset()
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Filter by status for non-admin users
        if not self.request.user.is_staff:
            queryset = queryset.filter(status='active')
        
        return queryset.select_related('ad_network', 'category')
    
    @action(detail=True, methods=['post'])
    def Click(self, request, pk=None):
        """Track offer click"""
        offer = self.get_object()
        
        try:
            # Create click record
            click_data = {
                'user': request.user if request.user.is_authenticated else None,
                'offer': offer,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'country': self._get_country_from_ip(self._get_client_ip(request)),
                'referrer_url': request.META.get('HTTP_REFERER', ''),
                'session_id': request.COOKIES.get('sessionid', ''),
                'tenant_id': getattr(request, 'tenant_id', None)
            }
            
            click = OfferClick.objects.create(**click_data)
            
            # Update click cache
            cache_key = f"offer_clicks_{offer.id}_{getattr(request, 'tenant_id', 'default')}"
            current_clicks = cache.get(cache_key, 0)
            cache.set(cache_key, current_clicks + 1, timeout=3600)
            
            return Response({
                'Success': True,
                'ClickID': click.id,
                'TrackingURL': offer.tracking_url
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error tracking click for offer {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Click tracking failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def Engage(self, request, pk=None):
        """Start offer engagement"""
        offer = self.get_object()
        
        if not request.user.is_authenticated:
            return Response({
                'Success': False,
                'Error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            # Check daily limit
            tenant_id = getattr(request, 'tenant_id', None)
            daily_limit = OfferDailyLimit.objects.filter(
                user=request.user,
                offer=offer,
                tenant_id=tenant_id
            ).first()
            
            if daily_limit and daily_limit.count_today >= daily_limit.daily_limit:
                return Response({
                    'Success': False,
                    'Error': 'Daily limit exceeded'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create or update engagement
            engagement, created = UserOfferEngagement.objects.update_or_create(
                user=request.user,
                offer=offer,
                tenant_id=tenant_id,
                defaults={
                    'status': 'started',
                    'ip_address': self._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'started_at': timezone.now()
                }
            )
            
            if not created:
                engagement.status = 'started'
                engagement.started_at = timezone.now()
                engagement.save(update_fields=['status', 'started_at'])
            
            # Update daily limit
            if daily_limit:
                daily_limit.count_today += 1
                daily_limit.save(update_fields=['count_today'])
            else:
                OfferDailyLimit.objects.create(
                    user=request.user,
                    offer=offer,
                    daily_limit=10,  # Default limit
                    count_today=1,
                    last_reset_at=timezone.now(),
                    tenant_id=tenant_id
                )
            
            return Response({
                'Success': True,
                'EngagementID': engagement.id,
                'OfferURL': offer.tracking_url
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error creating engagement for offer {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Engagement creation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def Analytics(self, request, pk=None):
        """Get offer analytics"""
        offer = self.get_object()
        tenant_id = getattr(request, 'tenant_id', None)
        
        try:
            # Get click statistics
            clicks = OfferClick.objects.filter(offer=offer)
            if tenant_id:
                clicks = clicks.filter(tenant_id=tenant_id)
            
            total_clicks = clicks.count()
            unique_clicks = clicks.values('ip_address').distinct().count()
            
            # Get conversion statistics
            conversions = OfferConversion.objects.filter(engagement__offer=offer)
            if tenant_id:
                conversions = conversions.filter(engagement__tenant_id=tenant_id)
            
            total_conversions = conversions.count()
            approved_conversions = conversions.filter(conversion_status='approved').count()
            total_payout = conversions.aggregate(
                total=Sum('payout')
            )['total'] or 0
            
            # Calculate rates
            conversion_rate = (approved_conversions / total_clicks * 100) if total_clicks > 0 else 0
            approval_rate = (approved_conversions / total_conversions * 100) if total_conversions > 0 else 0
            
            return Response({
                'Success': True,
                'Analytics': {
                    'TotalClicks': total_clicks,
                    'UniqueClicks': unique_clicks,
                    'TotalConversions': total_conversions,
                    'ApprovedConversions': approved_conversions,
                    'ConversionRate': round(conversion_rate, 2),
                    'ApprovalRate': round(approval_rate, 2),
                    'TotalPayout': float(total_payout),
                    'AvgPayout': float(total_payout / approved_conversions) if approved_conversions > 0 else 0
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting analytics for offer {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Analytics retrieval failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def _get_country_from_ip(self, ip_address):
        """Get country from IP address"""
        # This would integrate with GeoIP service
        # For now, return US as default
        return 'US'


class UserOfferEngagementViewSet(viewsets.ModelViewSet):
    """
    Capitalized ViewSet for UserOfferEngagement model
    """
    
    serializer_class = UserOfferEngagementSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = UserOfferEngagementFilter
    search_fields = ['offer__title', 'offer__description']
    ordering_fields = ['created_at', 'started_at', 'completed_at', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by user and tenant"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = UserOfferEngagement.objects.filter(user=self.request.user)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset.select_related('offer', 'offer__ad_network')
    
    @action(detail=False, methods=['get'])
    def MyEngagements(self, request):
        """Get current user's engagements"""
        return self.list(request)
    
    @action(detail=True, methods=['post'])
    def Complete(self, request, pk=None):
        """Complete engagement"""
        engagement = self.get_object()
        
        if engagement.status != 'started':
            return Response({
                'Success': False,
                'Error': 'Engagement cannot be completed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Update engagement
            engagement.status = 'completed'
            engagement.completed_at = timezone.now()
            engagement.save(update_fields=['status', 'completed_at'])
            
            # Process conversion if applicable
            service = ConversionService(tenant_id=engagement.tenant_id)
            result = service.process_conversion(engagement.id)
            
            return Response({
                'Success': True,
                'Message': 'Engagement completed',
                'ConversionResult': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error completing engagement {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Engagement completion failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferConversionViewSet(viewsets.ModelViewSet):
    """
    Capitalized ViewSet for OfferConversion model
    Admin access for verification
    """
    
    queryset = OfferConversion.objects.all()
    serializer_class = OfferConversionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OfferConversionFilter
    search_fields = ['engagement__offer__title', 'engagement__user__username']
    ordering_fields = ['created_at', 'payout', 'fraud_score', 'conversion_status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by tenant and user role"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = super().get_queryset()
        
        if tenant_id:
            queryset = queryset.filter(engagement__tenant_id=tenant_id)
        
        # Non-admin users can only see their own conversions
        if not self.request.user.is_staff:
            queryset = queryset.filter(engagement__user=self.request.user)
        
        return queryset.select_related('engagement', 'engagement__user', 'engagement__offer')
    
    @action(detail=True, methods=['post'])
    def Verify(self, request, pk=None):
        """Verify conversion"""
        conversion = self.get_object()
        
        if not self.request.user.is_staff:
            return Response({
                'Success': False,
                'Error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            approved = request.data.get('approved', False)
            notes = request.data.get('notes', '')
            
            service = ConversionService(tenant_id=conversion.engagement.tenant_id)
            result = service.verify_conversion(conversion.id, approved, notes)
            
            return Response({
                'Success': True,
                'Message': f"Conversion {'approved' if approved else 'rejected'}",
                'Result': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error verifying conversion {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Verification failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def AnalyzeFraud(self, request, pk=None):
        """Analyze conversion for fraud"""
        conversion = self.get_object()
        
        try:
            service = FraudDetectionService(tenant_id=conversion.engagement.tenant_id)
            result = service.analyze_conversion(
                {'conversion_id': conversion.id},
                conversion.engagement
            )
            
            return Response({
                'Success': True,
                'FraudAnalysis': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error analyzing fraud for conversion {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Fraud analysis failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def Chargeback(self, request, pk=None):
        """Process chargeback"""
        conversion = self.get_object()
        
        if not self.request.user.is_staff:
            return Response({
                'Success': False,
                'Error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            reason = request.data.get('reason', 'Chargeback requested')
            
            service = ConversionService(tenant_id=conversion.engagement.tenant_id)
            result = service.process_chargeback(conversion.id, reason)
            
            return Response({
                'Success': True,
                'Message': 'Chargeback processed',
                'Result': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing chargeback for conversion {pk}: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Chargeback processing failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferRewardViewSet(viewsets.ModelViewSet):
    """
    Capitalized ViewSet for OfferReward model
    """
    
    queryset = OfferReward.objects.all()
    serializer_class = OfferRewardSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OfferRewardFilter
    search_fields = ['offer__title', 'offer__description']
    ordering_fields = ['created_at', 'amount', 'status', 'approved_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by user and tenant"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = OfferReward.objects.filter(user=self.request.user)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset.select_related('offer', 'offer__ad_network', 'engagement')
    
    @action(detail=False, methods=['get'])
    def MyRewards(self, request):
        """Get current user's rewards"""
        return self.list(request)
    
    @action(detail=False, methods=['get'])
    def WalletBalance(self, request):
        """Get user's wallet balance"""
        tenant_id = getattr(request, 'tenant_id', None)
        
        try:
            wallet, created = UserWallet.objects.get_or_create(
                user=request.user,
                defaults={
                    'balance': Decimal('0.00'),
                    'total_earned': Decimal('0.00'),
                    'currency': 'USD',
                    'tenant_id': tenant_id
                }
            )
            
            # Calculate pending rewards
            pending_amount = OfferReward.objects.filter(
                user=request.user,
                status='pending',
                tenant_id=tenant_id
            ).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            return Response({
                'Success': True,
                'Wallet': {
                    'Balance': float(wallet.balance),
                    'TotalEarned': float(wallet.total_earned),
                    'PendingRewards': float(pending_amount),
                    'Currency': wallet.currency,
                    'AvailableBalance': float(wallet.balance)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting wallet balance: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Wallet balance retrieval failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def RequestPayout(self, request):
        """Request payout"""
        tenant_id = getattr(request, 'tenant_id', None)
        
        try:
            reward_ids = request.data.get('reward_ids', [])
            payment_method = request.data.get('payment_method')
            payout_address = request.data.get('payout_address')
            
            if not reward_ids or not payment_method or not payout_address:
                return Response({
                    'Success': False,
                    'Error': 'Missing required fields'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            service = RewardService(tenant_id=tenant_id)
            result = service.process_payout_request(
                request.user.id,
                reward_ids,
                payment_method,
                payout_address
            )
            
            return Response({
                'Success': True,
                'Message': 'Payout request processed',
                'Result': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing payout request: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Payout request failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NetworkHealthCheckViewSet(viewsets.ModelViewSet):
    """
    Capitalized ViewSet for NetworkHealthCheck model
    Admin access only
    """
    
    queryset = NetworkHealthCheck.objects.all()
    serializer_class = NetworkHealthCheckSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['network__name', 'error']
    ordering_fields = ['checked_at', 'response_time_ms', 'is_healthy']
    ordering = ['-checked_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        queryset = super().get_queryset()
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset.select_related('network')
    
    @action(detail=False, methods=['post'])
    def CheckAllNetworks(self, request):
        """Check health of all networks"""
        tenant_id = getattr(request, 'tenant_id', None)
        
        try:
            service = NetworkHealthService(tenant_id=tenant_id)
            result = service.check_all_networks()
            
            return Response({
                'Success': True,
                'HealthCheckResults': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error checking all networks health: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Health check failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def HealthSummary(self, request):
        """Get health summary for all networks"""
        tenant_id = getattr(request, 'tenant_id', None)
        
        try:
            service = NetworkHealthService(tenant_id=tenant_id)
            result = service.get_health_summary()
            
            return Response({
                'Success': True,
                'HealthSummary': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting health summary: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Health summary retrieval failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Generic views for additional functionality
class OfferRecommendationsView(generics.ListAPIView):
    """
    Capitalized View for personalized offer recommendations
    """
    
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get personalized recommendations"""
        tenant_id = getattr(self.request, 'tenant_id', None)
        
        try:
            service = OfferRecommendService(tenant_id=tenant_id)
            result = service.get_personalized_recommendations(
                self.request.user.id,
                limit=20
            )
            
            if result['success']:
                return result['recommendations']
            else:
                return Offer.objects.none()
                
        except Exception as e:
            logger.error(f"Error getting offer recommendations: {str(e)}")
            return Offer.objects.none()


class OfferStatsView(generics.RetrieveAPIView):
    """
    Capitalized View for offer statistics
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get offer statistics"""
        tenant_id = getattr(request, 'tenant_id', None)
        
        try:
            # Get overall stats
            offers = Offer.objects.filter(tenant_id=tenant_id)
            total_offers = offers.count()
            active_offers = offers.filter(status='active').count()
            
            # Get engagement stats
            engagements = UserOfferEngagement.objects.filter(tenant_id=tenant_id)
            total_engagements = engagements.count()
            completed_engagements = engagements.filter(status='completed').count()
            
            # Get conversion stats
            conversions = OfferConversion.objects.filter(engagement__tenant_id=tenant_id)
            total_conversions = conversions.count()
            approved_conversions = conversions.filter(conversion_status='approved').count()
            total_payout = conversions.aggregate(
                total=Sum('payout')
            )['total'] or 0
            
            # Calculate rates
            engagement_rate = (completed_engagements / total_engagements * 100) if total_engagements > 0 else 0
            conversion_rate = (approved_conversions / total_conversions * 100) if total_conversions > 0 else 0
            
            return Response({
                'Success': True,
                'Stats': {
                    'Offers': {
                        'Total': total_offers,
                        'Active': active_offers
                    },
                    'Engagements': {
                        'Total': total_engagements,
                        'Completed': completed_engagements,
                        'EngagementRate': round(engagement_rate, 2)
                    },
                    'Conversions': {
                        'Total': total_conversions,
                        'Approved': approved_conversions,
                        'ConversionRate': round(conversion_rate, 2),
                        'TotalPayout': float(total_payout)
                    }
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting offer stats: {str(e)}")
            return Response({
                'Success': False,
                'Error': 'Stats retrieval failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Export all capitalized ViewSets
__all__ = [
    'AdNetworkViewSet',
    'OfferCategoryViewSet',
    'OfferViewSet',
    'UserOfferEngagementViewSet',
    'OfferConversionViewSet',
    'OfferRewardViewSet',
    'NetworkHealthCheckViewSet',
    'OfferRecommendationsView',
    'OfferStatsView'
]
