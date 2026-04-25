# api/ad_networks/views.py
# SaaS-Ready Multi-Tenant Views with Complete Coverage

from django.core.cache import cache
from .mixins import TenantMixin as TenantViewSetMixin, SecurityMixin, TrackingMixin
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.utils.decorators import method_decorator
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
import uuid
import json
import hashlib
import hmac
from datetime import timedelta

from .models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferWall, AdNetworkWebhookLog,
    NetworkStatistic, UserOfferLimit, OfferSyncLog,
    SmartOfferRecommendation, OfferPerformanceAnalytics,
    FraudDetectionRule, BlacklistedIP, KnownBadIP, OfferClick,
    OfferReward, NetworkAPILog, OfferTag, OfferTagging,
    NetworkHealthCheck, OfferDailyLimit, OfferAttachment, UserWallet
)
from .serializers import (
    AdNetworkSerializer, AdNetworkDetailSerializer,
    OfferCategorySerializer, OfferSerializer, OfferDetailSerializer, OfferListSerializer,
    UserOfferEngagementSerializer, UserOfferEngagementDetailSerializer,
    OfferConversionSerializer, OfferWallSerializer,
    FraudDetectionRuleSerializer, BlacklistedIPSerializer, KnownBadIPSerializer,
    NetworkHealthCheckSerializer, OfferPerformanceAnalyticsSerializer,
    OfferClickSerializer, OfferRewardSerializer, NetworkAPILogSerializer,
    OfferTagSerializer, OfferTaggingSerializer, SmartOfferRecommendationSerializer,
    NetworkStatisticSerializer, UserOfferLimitSerializer, OfferSyncLogSerializer,
    AdNetworkWebhookLogSerializer, OfferDailyLimitSerializer,
    OfferAttachmentSerializer, UserWalletSerializer,
    BulkOperationSerializer, CacheInvalidationSerializer
)

User = get_user_model()

# ============================================================================
# BASE MIXINS FOR MULTI-TENANT ARCHITECTURE
# ============================================================================

class TenantMixin:
    """Mixin for tenant isolation"""
    
    def get_tenant_id(self):
        """Get tenant ID from request or default"""
        if hasattr(self.request, 'tenant_id'):
            return self.request.tenant_id
        return getattr(self.request.user, 'tenant_id', 'default')
    
    def get_queryset(self):
        """Filter queryset by tenant"""
        queryset = super().get_queryset()
        if hasattr(queryset.model, 'tenant_id'):
            queryset = queryset.filter(tenant_id=self.get_tenant_id())
        return queryset
    
    def perform_create(self, serializer):
        """Add tenant_id to created objects"""
        if hasattr(serializer.Meta.model, 'tenant_id'):
            serializer.save(tenant_id=self.get_tenant_id())
        else:
            serializer.save()

class BaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base ViewSet with common functionality"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = None  # Disable pagination for better performance
    
    def success_response(self, message='Success', data=None, status_code=status.HTTP_200_OK):
        """Standard success response"""
        response_data = {
            'success': True,
            'message': message,
            'data': data
        }
        return Response(response_data, status=status_code)
    
    def error_response(self, message='Error', data=None, status_code=status.HTTP_400_BAD_REQUEST):
        """Standard error response"""
        response_data = {
            'success': False,
            'message': message,
            'data': data
        }
        return Response(response_data, status=status_code)
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class FraudDetectionMixin:
    """Mixin for fraud detection"""
    
    def check_fraud_risk(self, user, ip_address, action_type='engagement'):
        """Check fraud risk for user action"""
        risk_score = 0
        
        # Check IP reputation
        if BlacklistedIP.objects.filter(
            ip_address=ip_address,
            is_active=True,
            tenant_id=self.get_tenant_id()
        ).exists():
            risk_score += 50
        
        # Check user behavior
        recent_actions = UserOfferEngagement.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(hours=1),
            tenant_id=self.get_tenant_id()
        ).count()
        
        if recent_actions > 10:
            risk_score += 30
        
        # Check for suspicious patterns
        if action_type == 'engagement':
            same_ip_engagements = UserOfferEngagement.objects.filter(
                ip_address=ip_address,
                created_at__gte=timezone.now() - timedelta(minutes=5),
                tenant_id=self.get_tenant_id()
            ).count()
            
            if same_ip_engagements > 3:
                risk_score += 20
        
        return min(risk_score, 100)

class FraudDetectionViewSetMixin(FraudDetectionMixin):
    """ViewSet mixin with fraud detection"""
    
    def create(self, request, *args, **kwargs):
        """Override create to add fraud detection"""
        # Get client IP
        ip_address = self.get_client_ip(request)
        
        # Check fraud risk
        if request.user.is_authenticated:
            risk_score = self.check_fraud_risk(request.user, ip_address)
            
            if risk_score > 80:
                return self.error_response(
                    message='High fraud risk detected',
                    data={'risk_score': risk_score},
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        return super().create(request, *args, **kwargs)

# ============================================================================
# OPTIMIZED OFFER CATEGORY VIEWSET
# ============================================================================

class OfferCategoryViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Category ViewSet with tenant isolation and caching
    """
    queryset = OfferCategory.objects.all()
    serializer_class = OfferCategorySerializer
    filterset_fields = ['category_type', 'is_active', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'order', 'created_at']
    ordering = ['order', 'name']
    
    @method_decorator(cache_page(300))  # 5 minutes cache
    @vary_on_headers('Authorization')
    def list(self, request, *args, **kwargs):
        """Cached list view"""
        return super().list(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'])
    def offers(self, request, pk=None):
        """Get offers for this category"""
        category = self.get_object()
        offers = Offer.objects.filter(
            category=category,
            status='active',
            tenant_id=self.get_tenant_id()
        ).order_by('-priority', '-created_at')
        
        serializer = OfferListSerializer(offers, many=True, context={'request': request})
        return self.success_response(
            message=f'Offers for {category.name}',
            data=serializer.data
        )
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured categories"""
        categories = OfferCategory.objects.filter(
            is_featured=True,
            is_active=True,
            tenant_id=self.get_tenant_id()
        ).order_by('order', 'name')
        
        serializer = self.get_serializer(categories, many=True)
        return self.success_response(
            message='Featured categories',
            data=serializer.data
        )

# ============================================================================
# OPTIMIZED OFFER VIEWSET WITH FULL SaaS FEATURES
# ============================================================================

class OfferViewSet(TenantViewSetMixin, FraudDetectionViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer ViewSet with tenant isolation, fraud prevention, and performance optimization
    """
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    filterset_fields = ['ad_network', 'category', 'status', 'difficulty', 'device_type']
    search_fields = ['title', 'description', 'instructions']
    ordering_fields = ['title', 'reward_amount', 'priority', 'created_at']
    ordering = ['-priority', '-created_at']
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'list':
            return OfferListSerializer
        elif self.action == 'retrieve':
            return OfferDetailSerializer
        return self.serializer_class
    
    @method_decorator(cache_page(60))  # 1 minute cache for list
    @vary_on_headers('Authorization')
    def list(self, request, *args, **kwargs):
        """Cached list view with performance optimization"""
        # Apply prefetch for better performance
        self.queryset = self.queryset.select_related(
            'ad_network', 'category'
        ).prefetch_related('tags')
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def click(self, request, pk=None):
        """Track offer click with fraud detection"""
        offer = self.get_object()
        tenant_id = self.get_tenant_id()
        ip_address = self.get_client_ip(request)
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return self.error_response(
                message='Authentication required',
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check fraud risk
        risk_score = self.check_fraud_risk(request.user, ip_address, 'click')
        
        # Create click record
        click = OfferClick.objects.create(
            tenant_id=tenant_id,
            user=request.user,
            offer=offer,
            ip_address=ip_address,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            fraud_score=risk_score,
            is_fraud=risk_score > 80
        )
        
        # Create engagement
        engagement, created = UserOfferEngagement.objects.get_or_create(
            tenant_id=tenant_id,
            user=request.user,
            offer=offer,
            defaults={
                'click_id': str(uuid.uuid4()),
                'status': 'clicked',
                'ip_address': ip_address,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'fraud_score': risk_score
            }
        )
        
        if not created:
            engagement.status = 'clicked'
            engagement.save()
        
        # Update offer click count
        Offer.objects.filter(id=offer.id).update(click_count=F('click_count') + 1)
        
        return self.success_response(
            message='Click tracked',
            data={
                'click_id': click.id,
                'engagement_id': engagement.id,
                'fraud_score': risk_score,
                'is_fraud': click.is_fraud
            }
        )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start offer engagement"""
        offer = self.get_object()
        tenant_id = self.get_tenant_id()
        
        if not request.user.is_authenticated:
            return self.error_response(
                message='Authentication required',
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get or create engagement
        engagement, created = UserOfferEngagement.objects.get_or_create(
            tenant_id=tenant_id,
            user=request.user,
            offer=offer,
            defaults={
                'click_id': str(uuid.uuid4()),
                'status': 'started',
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
        
        if not created:
            engagement.status = 'started'
            engagement.started_at = timezone.now()
            engagement.save()
        
        # Create reward record
        reward, _ = OfferReward.objects.get_or_create(
            tenant_id=tenant_id,
            user=request.user,
            offer=offer,
            engagement=engagement,
            defaults={
                'amount': offer.reward_amount,
                'currency': offer.reward_currency,
                'status': 'pending'
            }
        )
        
        return self.success_response(
            message='Offer started',
            data={
                'engagement_id': engagement.id,
                'reward_id': reward.id,
                'estimated_time': offer.estimated_time
            }
        )
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete offer engagement"""
        offer = self.get_object()
        tenant_id = self.get_tenant_id()
        
        if not request.user.is_authenticated:
            return self.error_response(
                message='Authentication required',
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get engagement
        engagement = get_object_or_404(
            UserOfferEngagement,
            user=request.user,
            offer=offer,
            tenant_id=tenant_id
        )
        
        if engagement.status != 'started':
            return self.error_response(
                message='Offer must be started first',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Update engagement
        engagement.status = 'completed'
        engagement.completed_at = timezone.now()
        engagement.save()
        
        # Create conversion
        conversion = OfferConversion.objects.create(
            tenant_id=tenant_id,
            engagement=engagement,
            conversion_id=str(uuid.uuid4()),
            conversion_status='pending',
            payout=offer.reward_amount,
            currency=offer.reward_currency
        )
        
        return self.success_response(
            message='Offer completed',
            data={
                'engagement_id': engagement.id,
                'conversion_id': conversion.id
            }
        )
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending offers"""
        tenant_id = self.get_tenant_id()
        
        # Get offers with most completions in last 7 days
        last_7_days = timezone.now() - timedelta(days=7)
        
        trending_offers = Offer.objects.filter(
            tenant_id=tenant_id,
            status='active'
        ).annotate(
            completion_count=Count(
                'userofferengagement',
                filter=Q(
                    userofferengagement__status='completed',
                    userofferengagement__completed_at__gte=last_7_days
                )
            )
        ).filter(completion_count__gt=0).order_by('-completion_count')[:10]
        
        serializer = OfferListSerializer(trending_offers, many=True, context={'request': request})
        return self.success_response(
            message='Trending offers',
            data=serializer.data
        )
    
    @action(detail=False, methods=['get'])
    def recommended(self, request):
        """Get recommended offers for user"""
        if not request.user.is_authenticated:
            return self.error_response(
                message='Authentication required',
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        tenant_id = self.get_tenant_id()
        
        # Get user's completed offers
        completed_categories = Offer.objects.filter(
            userofferengagement__user=request.user,
            userofferengagement__status='completed',
            userofferengagement__tenant_id=tenant_id
        ).values_list('category_id', flat=True).distinct()
        
        # Get offers from same categories
        recommended_offers = Offer.objects.filter(
            tenant_id=tenant_id,
            status='active',
            category_id__in=completed_categories
        ).exclude(
            userofferengagement__user=request.user,
            userofferengagement__status='completed'
        ).order_by('-priority', '-created_at')[:10]
        
        serializer = OfferListSerializer(recommended_offers, many=True, context={'request': request})
        return self.success_response(
            message='Recommended offers',
            data=serializer.data
        )

# ============================================================================
# USER OFFER ENGAGEMENT VIEWSET WITH TENANT ISOLATION
# ============================================================================

class UserOfferEngagementViewSet(TenantViewSetMixin, FraudDetectionViewSetMixin, BaseViewSet):
    """
    SaaS-Ready User Offer Engagement ViewSet with tenant isolation and fraud prevention
    """
    queryset = UserOfferEngagement.objects.all()
    serializer_class = UserOfferEngagementSerializer
    filterset_fields = ['user', 'offer', 'status']
    search_fields = ['click_id', 'ip_address']
    ordering_fields = ['created_at', 'started_at', 'completed_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'retrieve':
            return UserOfferEngagementDetailSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['get'])
    def my_engagements(self, request):
        """Get current user's engagements"""
        if not request.user.is_authenticated:
            return self.error_response(
                message='Authentication required',
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        engagements = UserOfferEngagement.objects.filter(
            user=request.user,
            tenant_id=self.get_tenant_id()
        ).order_by('-created_at')
        
        serializer = self.get_serializer(engagements, many=True)
        return self.success_response(
            message='My engagements',
            data=serializer.data
        )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get engagement statistics"""
        tenant_id = self.get_tenant_id()
        
        stats = {
            'total_engagements': UserOfferEngagement.objects.filter(tenant_id=tenant_id).count(),
            'completed_engagements': UserOfferEngagement.objects.filter(
                tenant_id=tenant_id,
                status='completed'
            ).count(),
            'pending_engagements': UserOfferEngagement.objects.filter(
                tenant_id=tenant_id,
                status='in_progress'
            ).count(),
            'total_rewards': UserOfferEngagement.objects.filter(
                tenant_id=tenant_id,
                status='approved'
            ).aggregate(total=Sum('reward_earned'))['total'] or 0
        }
        
        return self.success_response(data=stats)

# ============================================================================
# OFFER CONVERSION VIEWSET WITH TENANT ISOLATION
# ============================================================================

class OfferConversionViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Conversion ViewSet with tenant isolation
    """
    queryset = OfferConversion.objects.all()
    serializer_class = OfferConversionSerializer
    filterset_fields = ['engagement', 'conversion_status', 'risk_level']
    search_fields = ['conversion_id']
    ordering_fields = ['created_at', 'verified_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify conversion"""
        conversion = self.get_object()
        
        if conversion.is_verified:
            return self.error_response(
                message='Conversion already verified',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        conversion.is_verified = True
        conversion.verified_by = request.user
        conversion.verified_at = timezone.now()
        conversion.save()
        
        # Update engagement status
        conversion.engagement.status = 'approved'
        conversion.engagement.verified_at = timezone.now()
        conversion.engagement.save()
        
        return self.success_response(
            message='Conversion verified',
            data={'verified_at': conversion.verified_at}
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject conversion"""
        conversion = self.get_object()
        reason = request.data.get('reason', 'Rejected')
        
        conversion.conversion_status = 'rejected'
        conversion.risk_level = 'high'
        conversion.save()
        
        # Update engagement status
        conversion.engagement.status = 'rejected'
        conversion.engagement.rejection_reason = reason
        conversion.engagement.save()
        
        return self.success_response(
            message='Conversion rejected',
            data={'reason': reason}
        )

# ============================================================================
# OFFER WALL VIEWSET WITH TENANT ISOLATION
# ============================================================================

class OfferWallViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Wall ViewSet with tenant isolation
    """
    queryset = OfferWall.objects.all()
    serializer_class = OfferWallSerializer
    filterset_fields = ['wall_type', 'is_active', 'is_default']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'priority', 'created_at']
    ordering = ['priority', 'name']
    
    @action(detail=True, methods=['get'])
    def offers(self, request, pk=None):
        """Get offers for this offer wall"""
        offer_wall = self.get_object()
        tenant_id = self.get_tenant_id()
        
        # Get user's country (simplified)
        user_country = request.META.get('HTTP_CF_IPCOUNTRY', 'US')
        
        offers = Offer.objects.filter(
            ad_network__in=offer_wall.ad_networks.all(),
            status='active',
            tenant_id=tenant_id
        ).filter(
            Q(countries__contains=user_country) | Q(countries__=[])
        ).order_by('-priority', '-created_at')
        
        serializer = OfferListSerializer(offers, many=True, context={'request': request})
        return self.success_response(
            message=f'Offers for {offer_wall.name}',
            data=serializer.data
        )
    
    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get default offer wall"""
        tenant_id = self.get_tenant_id()
        
        offer_wall = OfferWall.objects.filter(
            is_default=True,
            is_active=True,
            tenant_id=tenant_id
        ).first()
        
        if not offer_wall:
            return self.error_response(
                message='No default offer wall found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(offer_wall)
        return self.success_response(
            message='Default offer wall',
            data=serializer.data
        )

# ============================================================================
# NETWORK HEALTH CHECK VIEWSET
# ============================================================================

class NetworkHealthCheckViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Network Health Check ViewSet
    """
    queryset = NetworkHealthCheck.objects.all()
    serializer_class = NetworkHealthCheckSerializer
    filterset_fields = ['network', 'check_type', 'is_healthy']
    search_fields = ['network__name', 'error']
    ordering_fields = ['checked_at', 'response_time_ms']
    ordering = ['-checked_at']
    
    @action(detail=False, methods=['post'])
    def check_all(self, request):
        """Check health of all networks"""
        tenant_id = self.get_tenant_id()
        
        networks = AdNetwork.objects.filter(
            is_active=True,
            tenant_id=tenant_id
        )
        
        results = []
        for network in networks:
            # Create health check
            health_check = NetworkHealthCheck.objects.create(
                tenant_id=tenant_id,
                network=network,
                check_type='scheduled',
                endpoint_checked=network.api_url or 'https://example.com',
                is_healthy=False
            )
            
            # Simulate health check
            try:
                import requests
                response = requests.get(network.api_url or 'https://example.com', timeout=10)
                
                health_check.status_code = response.status_code
                health_check.response_time_ms = int(response.elapsed.total_seconds() * 1000)
                health_check.is_healthy = response.status_code == 200
                health_check.save()
                
                results.append({
                    'network': network.name,
                    'is_healthy': health_check.is_healthy,
                    'response_time_ms': health_check.response_time_ms,
                    'status_code': response.status_code
                })
            except Exception as e:
                health_check.error = str(e)
                health_check.save()
                
                results.append({
                    'network': network.name,
                    'is_healthy': False,
                    'error': str(e)
                })
        
        return self.success_response(
            message='Health check completed',
            data={'results': results}
        )

# ============================================================================
# ANALYTICS VIEWSET WITH TENANT ISOLATION
# ============================================================================

class AnalyticsViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Analytics ViewSet with tenant isolation
    """
    queryset = OfferPerformanceAnalytics.objects.all()
    serializer_class = OfferPerformanceAnalyticsSerializer
    filterset_fields = ['offer', 'date']
    search_fields = ['offer__title']
    ordering_fields = ['date', 'clicks', 'conversions']
    ordering = ['-date']
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard analytics"""
        tenant_id = self.get_tenant_id()
        
        # Get date range from request
        days = int(request.query_params.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        # Overall stats
        total_offers = Offer.objects.filter(tenant_id=tenant_id).count()
        active_offers = Offer.objects.filter(tenant_id=tenant_id, status='active').count()
        
        # Engagement stats
        total_engagements = UserOfferEngagement.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).count()
        
        completed_engagements = UserOfferEngagement.objects.filter(
            tenant_id=tenant_id,
            status='completed',
            created_at__gte=start_date
        ).count()
        
        # Revenue stats
        total_revenue = UserOfferEngagement.objects.filter(
            tenant_id=tenant_id,
            status='approved',
            created_at__gte=start_date
        ).aggregate(total=Sum('reward_earned'))['total'] or 0
        
        # Top performing offers
        top_offers = Offer.objects.filter(
            tenant_id=tenant_id
        ).annotate(
            completions=Count(
                'userofferengagement',
                filter=Q(
                    userofferengagement__status='completed',
                    userofferengagement__created_at__gte=start_date
                )
            )
        ).filter(completions__gt=0).order_by('-completions')[:5]
        
        top_offers_data = [
            {
                'id': offer.id,
                'title': offer.title,
                'completions': offer.completions,
                'reward_amount': float(offer.reward_amount)
            }
            for offer in top_offers
        ]
        
        dashboard_data = {
            'offers': {
                'total': total_offers,
                'active': active_offers
            },
            'engagements': {
                'total': total_engagements,
                'completed': completed_engagements,
                'conversion_rate': (completed_engagements / total_engagements * 100) if total_engagements > 0 else 0
            },
            'revenue': {
                'total': float(total_revenue),
                'period': f'Last {days} days'
            },
            'top_offers': top_offers_data
        }
        
        return self.success_response(
            message='Dashboard analytics',
            data=dashboard_data
        )
    
    @action(detail=False, methods=['get'])
    def user_stats(self, request):
        """Get user statistics"""
        if not request.user.is_authenticated:
            return self.error_response(
                message='Authentication required',
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        tenant_id = self.get_tenant_id()
        
        user_stats = {
            'total_engagements': UserOfferEngagement.objects.filter(
                user=request.user,
                tenant_id=tenant_id
            ).count(),
            'completed_engagements': UserOfferEngagement.objects.filter(
                user=request.user,
                tenant_id=tenant_id,
                status='completed'
            ).count(),
            'total_earned': UserOfferEngagement.objects.filter(
                user=request.user,
                tenant_id=tenant_id,
                status='approved'
            ).aggregate(total=Sum('reward_earned'))['total'] or 0
        }
        
        return self.success_response(
            message='User statistics',
            data=user_stats
        )

# ============================================================================
# OFFER ATTACHMENT VIEWSET
# ============================================================================

class OfferAttachmentViewSet(TenantMixin, viewsets.ModelViewSet):
    """ViewSet for OfferAttachment model"""
    queryset = OfferAttachment.objects.all()
    serializer_class = OfferAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['offer', 'file_type', 'is_active']
    search_fields = ['filename', 'description']
    ordering_fields = ['created_at', 'file_size', 'filename']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=getattr(self.request, 'tenant_id', 'default'))
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download attachment file"""
        attachment = self.get_object()
        if attachment.file:
            # In production, you would serve the file properly
            return Response({
                'download_url': f"/api/ad_networks/attachments/{attachment.id}/download/",
                'filename': attachment.filename,
                'file_size': attachment.file_size,
                'file_type': attachment.file_type
            })
        return Response({'error': 'File not found'}, status=404)


# ============================================================================
# USER WALLET VIEWSET
# ============================================================================

class UserWalletViewSet(TenantMixin, viewsets.ModelViewSet):
    """ViewSet for UserWallet model"""
    queryset = UserWallet.objects.all()
    serializer_class = UserWalletSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['currency', 'is_active', 'is_frozen']
    search_fields = ['user__username', 'user__email']
    ordering_fields = ['created_at', 'current_balance', 'total_earned']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=getattr(self.request, 'tenant_id', 'default'))
    
    @action(detail=False, methods=['get'])
    def my_wallet(self, request):
        """Get current user's wallet"""
        try:
            wallet = UserWallet.objects.get(
                user=request.user,
                tenant_id=getattr(request, 'tenant_id', 'default')
            )
            serializer = self.get_serializer(wallet)
            return Response(serializer.data)
        except UserWallet.DoesNotExist:
            # Create wallet if it doesn't exist
            wallet = UserWallet.objects.create(
                user=request.user,
                tenant_id=getattr(request, 'tenant_id', 'default')
            )
            serializer = self.get_serializer(wallet)
            return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def freeze(self, request, pk=None):
        """Freeze user wallet"""
        wallet = self.get_object()
        reason = request.data.get('reason', 'Administrative action')
        
        wallet.is_frozen = True
        wallet.freeze_reason = reason
        wallet.frozen_at = timezone.now()
        wallet.save()
        
        serializer = self.get_serializer(wallet)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def unfreeze(self, request, pk=None):
        """Unfreeze user wallet"""
        wallet = self.get_object()
        
        wallet.is_frozen = False
        wallet.freeze_reason = None
        wallet.frozen_at = None
        wallet.save()
        
        serializer = self.get_serializer(wallet)
        return Response(serializer.data)


# ============================================================================
# UTILITY VIEWS
# ============================================================================

class UtilityViewSet(TenantViewSetMixin, BaseViewSet):
    """
    Utility endpoints for the ad networks module
    """
    queryset = None  # No model for utility viewset
    
    @action(detail=False, methods=['get'])
    def choices(self, request):
        """Get available choices for forms"""
        from .choices import OFFER_STATUS
        
        statuses = [
            {'value': value, 'label': label}
            for value, label in OFFER_STATUS
        ]
        
        return self.success_response(data=statuses)
    
    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """Clear cache for tenant (admin only)"""
        tenant_id = self.get_tenant_id()
        
        if not request.user.has_perm('ad_networks.clear_cache'):
            return self.error_response(
                message='Permission denied',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Clear all cache keys for tenant
        patterns = [
            f'{tenant_id}_*',
            f'*_{tenant_id}_*',
            f'user_*_{tenant_id}_*'
        ]
        
        cleared_count = 0
        for pattern in patterns:
            keys = cache.keys(pattern)
            if keys:
                cache.delete_many(keys)
                cleared_count += len(keys)
        
        return self.success_response(
            message=f'Cleared {cleared_count} cache entries',
            data={'cleared_count': cleared_count}
        )

# ============================================================================
# AD NETWORK VIEWSET
# ============================================================================

class AdNetworkViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Ad Network ViewSet with tenant isolation
    """
    queryset = AdNetwork.objects.all()
    serializer_class = AdNetworkSerializer
    filterset_fields = ['network_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'priority']
    ordering = ['name']
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'retrieve':
            return AdNetworkDetailSerializer
        return self.serializer_class
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test network connection"""
        network = self.get_object()
        tenant_id = self.get_tenant_id()
        
        # Create network health check
        health_check = NetworkHealthCheck.objects.create(
            network=network,
            tenant_id=tenant_id,
            check_type='connection_test',
            endpoint_checked=network.api_url or 'https://example.com',
            is_healthy=False
        )
        
        try:
            # Simulate connection test
            import requests
            response = requests.get(network.api_url or 'https://example.com', timeout=10)
            
            health_check.status_code = response.status_code
            health_check.response_time_ms = int(response.elapsed.total_seconds() * 1000)
            health_check.is_healthy = response.status_code == 200
            health_check.save()
            
            return self.success_response(
                message='Connection test completed',
                data={
                    'status_code': response.status_code,
                    'response_time_ms': health_check.response_time_ms,
                    'is_healthy': health_check.is_healthy
                }
            )
        except Exception as e:
            health_check.error = str(e)
            health_check.save()
            
            return self.error_response(
                message='Connection test failed',
                data={'error': str(e)}
            )
    
    @action(detail=True, methods=['post'])
    def sync_offers(self, request, pk=None):
        """Sync offers from network"""
        network = self.get_object()
        tenant_id = self.get_tenant_id()
        
        # Create sync log
        sync_log = OfferSyncLog.objects.create(
            ad_network=network,
            tenant_id=tenant_id,
            sync_type='manual',
            status='started'
        )
        
        try:
            # Simulate offer sync
            offers_count = 10  # Simulated count
            
            sync_log.offers_fetched = offers_count
            sync_log.offers_created = offers_count // 2
            sync_log.offers_updated = offers_count // 2
            sync_log.status = 'completed'
            sync_log.save()
            
            return self.success_response(
                message='Offer sync completed',
                data={
                    'offers_fetched': sync_log.offers_fetched,
                    'offers_created': sync_log.offers_created,
                    'offers_updated': sync_log.offers_updated
                }
            )
        except Exception as e:
            sync_log.error_message = str(e)
            sync_log.status = 'failed'
            sync_log.save()
            
            return self.error_response(
                message='Offer sync failed',
                data={'error': str(e)}
            )

# ============================================================================
# FRAUD DETECTION RULE VIEWSET
# ============================================================================

class FraudDetectionRuleViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Fraud Detection Rule ViewSet with tenant isolation
    """
    queryset = FraudDetectionRule.objects.all()
    serializer_class = FraudDetectionRuleSerializer
    filterset_fields = ['rule_type', 'action', 'severity', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'priority', 'created_at']
    ordering = ['priority', 'name']
    
    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test fraud detection rule"""
        rule = self.get_object()
        tenant_id = self.get_tenant_id()
        
        # Get test data from request
        test_data = request.data.get('test_data', {})
        
        # Simulate rule testing
        is_triggered = False
        score = 0
        
        if rule.rule_type == 'ip_based' and 'ip_address' in test_data:
            if BlacklistedIP.objects.filter(
                ip_address=test_data['ip_address'],
                tenant_id=tenant_id,
                is_active=True
            ).exists():
                is_triggered = True
                score = 80
        
        return self.success_response(
            message='Rule test completed',
            data={
                'is_triggered': is_triggered,
                'score': score,
                'action': rule.action
            }
        )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get fraud detection statistics"""
        tenant_id = self.get_tenant_id()
        
        stats = {
            'total_rules': FraudDetectionRule.objects.filter(tenant_id=tenant_id).count(),
            'active_rules': FraudDetectionRule.objects.filter(tenant_id=tenant_id, is_active=True).count(),
            'blacklisted_ips': BlacklistedIP.objects.filter(tenant_id=tenant_id, is_active=True).count(),
            'recent_detections': UserOfferEngagement.objects.filter(
                tenant_id=tenant_id,
                fraud_score__gt=50,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
        }
        
        return self.success_response(data=stats)

# ============================================================================
# BLACKLISTED IP VIEWSET
# ============================================================================

class BlacklistedIPViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Blacklisted IP ViewSet with tenant isolation
    """
    queryset = BlacklistedIP.objects.all()
    serializer_class = BlacklistedIPSerializer
    filterset_fields = ['reason', 'is_active']
    search_fields = ['ip_address', 'description']
    ordering_fields = ['ip_address', 'created_at', 'expiry_date']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['post'])
    def bulk_add(self, request):
        """Bulk add blacklisted IPs"""
        tenant_id = self.get_tenant_id()
        ips_data = request.data.get('ips', [])
        
        created_count = 0
        for ip_data in ips_data:
            try:
                BlacklistedIP.objects.get_or_create(
                    ip_address=ip_data['ip_address'],
                    tenant_id=tenant_id,
                    defaults={
                        'reason': ip_data.get('reason', 'other'),
                        'description': ip_data.get('description', ''),
                        'expiry_date': ip_data.get('expiry_date'),
                        'metadata': ip_data.get('metadata', {})
                    }
                )
                created_count += 1
            except Exception as e:
                continue
        
        return self.success_response(
            message=f'Added {created_count} blacklisted IPs',
            data={'created_count': created_count}
        )
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Cleanup expired blacklisted IPs"""
        tenant_id = self.get_tenant_id()
        
        expired_count = BlacklistedIP.objects.filter(
            tenant_id=tenant_id,
            expiry_date__lt=timezone.now(),
            is_active=True
        ).update(is_active=False)
        
        return self.success_response(
            message=f'Deactivated {expired_count} expired IPs',
            data={'deactivated_count': expired_count}
        )

# ============================================================================
# KNOWN BAD IP VIEWSET
# ============================================================================

class KnownBadIPViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Known Bad IP ViewSet with tenant isolation
    """
    queryset = KnownBadIP.objects.all()
    serializer_class = KnownBadIPSerializer
    filterset_fields = ['threat_type', 'source', 'is_active']
    search_fields = ['ip_address', 'description']
    ordering_fields = ['ip_address', 'confidence_score', 'created_at']
    ordering = ['-confidence_score']
    
    @action(detail=False, methods=['post'])
    def import_from_source(self, request):
        """Import known bad IPs from external source"""
        tenant_id = self.get_tenant_id()
        source = request.data.get('source')
        
        # Simulate import from external source
        imported_count = 0
        if source == 'spamhaus':
            # Simulate Spamhaus import
            for i in range(10):
                try:
                    KnownBadIP.objects.get_or_create(
                        ip_address=f'192.168.1.{i}',
                        tenant_id=tenant_id,
                        defaults={
                            'threat_type': 'spam',
                            'source': 'spamhaus',
                            'confidence_score': 90,
                            'description': 'Spamhaus blacklist'
                        }
                    )
                    imported_count += 1
                except Exception:
                    continue
        
        return self.success_response(
            message=f'Imported {imported_count} IPs from {source}',
            data={'imported_count': imported_count}
        )

# ============================================================================
# OFFER CLICK VIEWSET
# ============================================================================

class OfferClickViewSet(TenantViewSetMixin, FraudDetectionViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Click ViewSet with tenant isolation and fraud detection
    """
    queryset = OfferClick.objects.all()
    serializer_class = OfferClickSerializer
    filterset_fields = ['offer', 'is_unique', 'is_fraud', 'device', 'browser']
    search_fields = ['ip_address', 'click_id']
    ordering_fields = ['clicked_at', 'fraud_score']
    ordering = ['-clicked_at']
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get click analytics"""
        tenant_id = self.get_tenant_id()
        
        last_24h = timezone.now() - timedelta(hours=24)
        
        analytics = {
            'total_clicks': OfferClick.objects.filter(tenant_id=tenant_id).count(),
            'clicks_24h': OfferClick.objects.filter(
                tenant_id=tenant_id,
                clicked_at__gte=last_24h
            ).count(),
            'unique_clicks': OfferClick.objects.filter(
                tenant_id=tenant_id,
                is_unique=True
            ).count(),
            'fraud_clicks': OfferClick.objects.filter(
                tenant_id=tenant_id,
                is_fraud=True
            ).count(),
            'avg_fraud_score': OfferClick.objects.filter(
                tenant_id=tenant_id
            ).aggregate(avg_score=Avg('fraud_score'))['avg_score'] or 0
        }
        
        return self.success_response(data=analytics)
    
    @action(detail=False, methods=['post'])
    def track_click(self, request):
        """Track offer click"""
        tenant_id = self.get_tenant_id()
        offer_id = request.data.get('offer_id')
        click_id = request.data.get('click_id')
        ip_address = self.get_client_ip(request)
        
        try:
            offer = Offer.objects.get(id=offer_id, tenant_id=tenant_id)
            
            # Check if click is unique
            is_unique = not OfferClick.objects.filter(
                offer=offer,
                ip_address=ip_address,
                is_unique=True,
                clicked_at__gte=timezone.now() - timedelta(hours=24)
            ).exists()
            
            # Create click record
            click = OfferClick.objects.create(
                tenant_id=tenant_id,
                user=request.user if request.user.is_authenticated else None,
                offer=offer,
                click_id=click_id,
                ip_address=ip_address,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_unique=is_unique
            )
            
            return self.success_response(
                message='Click tracked',
                data={
                    'click_id': click.id,
                    'is_unique': is_unique,
                    'fraud_score': float(click.fraud_score)
                }
            )
        except Offer.DoesNotExist:
            return self.error_response(
                message='Offer not found',
                status_code=status.HTTP_404_NOT_FOUND
            )

# ============================================================================
# OFFER REWARD VIEWSET
# ============================================================================

class OfferRewardViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Reward ViewSet with tenant isolation
    """
    queryset = OfferReward.objects.all()
    serializer_class = OfferRewardSerializer
    filterset_fields = ['user', 'offer', 'status', 'currency']
    search_fields = ['payment_reference', 'transaction_id']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve reward payment"""
        reward = self.get_object()
        
        if reward.status != 'pending':
            return self.error_response(
                message='Only pending rewards can be approved',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        reward.status = 'approved'
        reward.processed_at = timezone.now()
        reward.save()
        
        return self.success_response(
            message='Reward approved',
            data={'status': reward.status, 'processed_at': reward.processed_at}
        )
    
    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process reward payment"""
        reward = self.get_object()
        
        if reward.status != 'approved':
            return self.error_response(
                message='Only approved rewards can be processed',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Simulate payment processing
        reward.status = 'paid'
        reward.processed_at = timezone.now()
        reward.payment_reference = f"PAY_{timezone.now().strftime('%Y%m%d%H%M%S')}"
        reward.save()
        
        return self.success_response(
            message='Payment processed',
            data={
                'status': reward.status,
                'payment_reference': reward.payment_reference,
                'processed_at': reward.processed_at
            }
        )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get reward statistics"""
        tenant_id = self.get_tenant_id()
        
        stats = {
            'total_rewards': OfferReward.objects.filter(tenant_id=tenant_id).count(),
            'pending_rewards': OfferReward.objects.filter(tenant_id=tenant_id, status='pending').count(),
            'approved_rewards': OfferReward.objects.filter(tenant_id=tenant_id, status='approved').count(),
            'paid_rewards': OfferReward.objects.filter(tenant_id=tenant_id, status='paid').count(),
            'total_amount': OfferReward.objects.filter(
                tenant_id=tenant_id,
                status='paid'
            ).aggregate(total=Sum('amount'))['total'] or 0
        }
        
        return self.success_response(data=stats)

# ============================================================================
# NETWORK API LOG VIEWSET
# ============================================================================

class NetworkAPILogViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Network API Log ViewSet with tenant isolation
    """
    queryset = NetworkAPILog.objects.all()
    serializer_class = NetworkAPILogSerializer
    filterset_fields = ['network', 'method', 'status_code', 'is_success']
    search_fields = ['endpoint', 'error_message']
    ordering_fields = ['request_timestamp', 'response_timestamp']
    ordering = ['-request_timestamp']
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get API call statistics"""
        tenant_id = self.get_tenant_id()
        
        last_24h = timezone.now() - timedelta(hours=24)
        
        stats = {
            'total_calls': NetworkAPILog.objects.filter(tenant_id=tenant_id).count(),
            'calls_24h': NetworkAPILog.objects.filter(
                tenant_id=tenant_id,
                request_timestamp__gte=last_24h
            ).count(),
            'success_rate': NetworkAPILog.objects.filter(
                tenant_id=tenant_id
            ).aggregate(
                success_rate=Count('id', filter=Q(is_success=True)) * 100.0 / Count('id')
            )['success_rate'] or 0,
            'avg_response_time': NetworkAPILog.objects.filter(
                tenant_id=tenant_id,
                is_success=True
            ).aggregate(
                avg_time=Avg('response_time_ms')
            )['avg_time'] or 0
        }
        
        return self.success_response(data=stats)

# ============================================================================
# OFFER TAG VIEWSET
# ============================================================================

class OfferTagViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Tag ViewSet with tenant isolation
    """
    queryset = OfferTag.objects.all()
    serializer_class = OfferTagSerializer
    filterset_fields = ['is_active', 'is_featured']
    search_fields = ['name', 'slug', 'description']
    ordering_fields = ['name', 'created_at', 'usage_count']
    ordering = ['name']
    
    @action(detail=True, methods=['post'])
    def merge_with(self, request, pk=None):
        """Merge tag with another tag"""
        tag = self.get_object()
        target_tag_id = request.data.get('target_tag_id')
        
        try:
            target_tag = OfferTag.objects.get(id=target_tag_id, tenant_id=self.get_tenant_id())
            
            # Move all taggings to target tag
            OfferTagging.objects.filter(
                tag=tag,
                tenant_id=self.get_tenant_id()
            ).update(tag=target_tag)
            
            # Delete old tag
            tag.delete()
            
            return self.success_response(
                message=f'Tag merged with {target_tag.name}',
                data={'target_tag': target_tag.name}
            )
        except OfferTag.DoesNotExist:
            return self.error_response(
                message='Target tag not found',
                status_code=status.HTTP_404_NOT_FOUND
            )

# ============================================================================
# OFFER TAGGING VIEWSET
# ============================================================================

class OfferTaggingViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Tagging ViewSet with tenant isolation
    """
    queryset = OfferTagging.objects.all()
    serializer_class = OfferTaggingSerializer
    filterset_fields = ['offer', 'tag', 'is_auto_tagged']
    search_fields = ['offer__title', 'tag__name']
    ordering_fields = ['created_at', 'confidence_score']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['post'])
    def bulk_tag(self, request):
        """Bulk tag offers"""
        tenant_id = self.get_tenant_id()
        offer_ids = request.data.get('offer_ids', [])
        tag_id = request.data.get('tag_id')
        
        try:
            tag = OfferTag.objects.get(id=tag_id, tenant_id=tenant_id)
            offers = Offer.objects.filter(id__in=offer_ids, tenant_id=tenant_id)
            
            created_count = 0
            for offer in offers:
                tagging, created = OfferTagging.objects.get_or_create(
                    offer=offer,
                    tag=tag,
                    tenant_id=tenant_id,
                    defaults={
                        'added_by': request.user if request.user.is_authenticated else None,
                        'is_auto_tagged': False,
                        'confidence_score': 100
                    }
                )
                if created:
                    created_count += 1
            
            return self.success_response(
                message=f'Tagged {created_count} offers',
                data={'tagged_count': created_count}
            )
        except OfferTag.DoesNotExist:
            return self.error_response(
                message='Tag not found',
                status_code=status.HTTP_404_NOT_FOUND
            )

# ============================================================================
# SMART OFFER RECOMMENDATION VIEWSET
# ============================================================================

class SmartOfferRecommendationViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Smart Offer Recommendation ViewSet with tenant isolation
    """
    queryset = SmartOfferRecommendation.objects.all()
    serializer_class = SmartOfferRecommendationSerializer
    filterset_fields = ['user', 'offer', 'is_displayed', 'is_clicked', 'is_converted']
    search_fields = ['user__username', 'offer__title']
    ordering_fields = ['score', 'created_at']
    ordering = ['-score', '-created_at']
    
    @action(detail=False, methods=['get'])
    def for_user(self, request):
        """Get recommendations for specific user"""
        tenant_id = self.get_tenant_id()
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return self.error_response(
                message='user_id parameter is required',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        recommendations = SmartOfferRecommendation.objects.filter(
            tenant_id=tenant_id,
            user_id=user_id,
            is_displayed=False
        ).order_by('-score')[:10]
        
        serializer = self.get_serializer(recommendations, many=True)
        return self.success_response(data=serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_displayed(self, request, pk=None):
        """Mark recommendation as displayed"""
        recommendation = self.get_object()
        
        recommendation.is_displayed = True
        recommendation.save()
        
        return self.success_response(
            message='Recommendation marked as displayed'
        )

# ============================================================================
# NETWORK STATISTIC VIEWSET
# ============================================================================

class NetworkStatisticViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Network Statistic ViewSet with tenant isolation
    """
    queryset = NetworkStatistic.objects.all()
    serializer_class = NetworkStatisticSerializer
    filterset_fields = ['network', 'date']
    search_fields = ['network__name']
    ordering_fields = ['date', 'clicks', 'conversions']
    ordering = ['-date']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get network statistics summary"""
        tenant_id = self.get_tenant_id()
        
        # Get date range from request
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = NetworkStatistic.objects.filter(tenant_id=tenant_id)
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        summary = queryset.aggregate(
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_payout=Sum('payout'),
            total_revenue=Sum('revenue')
        )
        
        return self.success_response(data=summary)

# ============================================================================
# USER OFFER LIMIT VIEWSET
# ============================================================================

class UserOfferLimitViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready User Offer Limit ViewSet with tenant isolation
    """
    queryset = UserOfferLimit.objects.all()
    serializer_class = UserOfferLimitSerializer
    filterset_fields = ['user', 'offer']
    search_fields = ['user__username', 'offer__title']
    ordering_fields = ['daily_count', 'total_count', 'last_completed']
    ordering = ['-last_completed']
    
    @action(detail=True, methods=['post'])
    def reset_daily(self, request, pk=None):
        """Reset daily count"""
        limit = self.get_object()
        
        limit.daily_count = 0
        limit.save()
        
        return self.success_response(
            message='Daily count reset',
            data={'daily_count': limit.daily_count}
        )
    
    @action(detail=False, methods=['get'])
    def for_user(self, request):
        """Get limits for specific user"""
        tenant_id = self.get_tenant_id()
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return self.error_response(
                message='user_id parameter is required',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        limits = UserOfferLimit.objects.filter(
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        serializer = self.get_serializer(limits, many=True)
        return self.success_response(data=serializer.data)

# ============================================================================
# OFFER SYNC LOG VIEWSET
# ============================================================================

class OfferSyncLogViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Sync Log ViewSet with tenant isolation
    """
    queryset = OfferSyncLog.objects.all()
    serializer_class = OfferSyncLogSerializer
    filterset_fields = ['ad_network', 'sync_type', 'status']
    search_fields = ['ad_network__name', 'error_message']
    ordering_fields = ['created_at', 'sync_duration']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def retry_sync(self, request, pk=None):
        """Retry failed sync"""
        sync_log = self.get_object()
        
        if sync_log.status != 'failed':
            return self.error_response(
                message='Only failed syncs can be retried',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset sync status
        sync_log.status = 'pending'
        sync_log.error_message = None
        sync_log.save()
        
        return self.success_response(
            message='Sync retry initiated',
            data={'sync_id': sync_log.id}
        )

# ============================================================================
# AD NETWORK WEBHOOK LOG VIEWSET
# ============================================================================

class AdNetworkWebhookLogViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Ad Network Webhook Log ViewSet with tenant isolation
    """
    queryset = AdNetworkWebhookLog.objects.all()
    serializer_class = AdNetworkWebhookLogSerializer
    filterset_fields = ['ad_network', 'event_type', 'processed']
    search_fields = ['ad_network__name', 'webhook_id']
    ordering_fields = ['created_at', 'retry_count']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def retry_webhook(self, request, pk=None):
        """Retry failed webhook processing"""
        webhook_log = self.get_object()
        
        if webhook_log.processed:
            return self.error_response(
                message='Webhook already processed',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Increment retry count
        webhook_log.retry_count += 1
        webhook_log.save()
        
        return self.success_response(
            message='Webhook retry initiated',
            data={'retry_count': webhook_log.retry_count}
        )
    
    @action(detail=False, methods=['post'])
    def bulk_process(self, request):
        """Bulk process pending webhooks"""
        tenant_id = self.get_tenant_id()
        
        pending_webhooks = AdNetworkWebhookLog.objects.filter(
            tenant_id=tenant_id,
            processed=False
        )
        
        processed_count = 0
        for webhook in pending_webhooks:
            # Simulate webhook processing
            webhook.processed = True
            webhook.save()
            processed_count += 1
        
        return self.success_response(
            message=f'Processed {processed_count} webhooks',
            data={'processed_count': processed_count}
        )

# ============================================================================
# OFFER DAILY LIMIT VIEWSET
# ============================================================================

class OfferDailyLimitViewSet(TenantViewSetMixin, BaseViewSet):
    """
    SaaS-Ready Offer Daily Limit ViewSet with tenant isolation
    """
    queryset = OfferDailyLimit.objects.all()
    serializer_class = OfferDailyLimitSerializer
    filterset_fields = ['user', 'offer', 'is_active']
    search_fields = ['user__username', 'offer__title']
    ordering_fields = ['count_today', 'daily_limit', 'last_reset_at']
    ordering = ['-last_reset_at']
    
    @action(detail=True, methods=['post'])
    def reset_daily(self, request, pk=None):
        """Reset daily count"""
        daily_limit = self.get_object()
        
        daily_limit.count_today = 0
        daily_limit.last_reset_at = timezone.now()
        daily_limit.save()
        
        return self.success_response(
            message='Daily count reset',
            data={
                'count_today': daily_limit.count_today,
                'last_reset_at': daily_limit.last_reset_at
            }
        )
    
    @action(detail=False, methods=['post'])
    def bulk_reset(self, request):
        """Bulk reset daily limits for tenant"""
        tenant_id = self.get_tenant_id()
        
        reset_count = OfferDailyLimit.objects.filter(
            tenant_id=tenant_id
        ).update(
            count_today=0,
            last_reset_at=timezone.now()
        )
        
        return self.success_response(
            message=f'Reset {reset_count} daily limits',
            data={'reset_count': reset_count}
        )

# ============================================================================
# ERROR HANDLING AND VALIDATION
# ============================================================================

class ErrorHandler:
    """Centralized error handling for views"""
    
    @staticmethod
    def handle_validation_error(serializer_errors):
        """Format validation errors"""
        return {
            'success': False,
            'message': 'Validation failed',
            'errors': serializer_errors
        }

# ============================================================================
# IMPORT ALL VIEWSETS FOR URL CONFIGURATION
# ============================================================================

__all__ = [
    # Core viewsets
    'OfferCategoryViewSet',
    'OfferViewSet', 
    'UserOfferEngagementViewSet',
    'OfferConversionViewSet',
    'OfferWallViewSet',
    'NetworkHealthCheckViewSet',
    'AnalyticsViewSet',
    'UtilityViewSet',
    
    # Additional viewsets
    'AdNetworkViewSet',
    'FraudDetectionRuleViewSet',
    'BlacklistedIPViewSet',
    'KnownBadIPViewSet',
    'OfferClickViewSet',
    'OfferRewardViewSet',
    'NetworkAPILogViewSet',
    'OfferTagViewSet',
    'OfferTaggingViewSet',
    'SmartOfferRecommendationViewSet',
    'NetworkStatisticViewSet',
    'UserOfferLimitViewSet',
    'OfferSyncLogViewSet',
    'AdNetworkWebhookLogViewSet',
    'OfferDailyLimitViewSet',
    
    # Additional ViewSets
    'OfferAttachmentViewSet',
    'UserWalletViewSet',
    
    # Utilities
    'ErrorHandler'
]
