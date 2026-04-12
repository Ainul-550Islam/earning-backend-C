"""
Offerwall API views
"""
import logging
from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Avg
from .models import *
from .serializers import *
from .mixins import *
from .constants import *
from .exceptions import *
from .utils.OfferValidator import OfferValidator
from .utils.RewardCalculator import RewardCalculator
from .utils.FraudDetector import FraudDetector
from .utils.AnalyticsTracker import AnalyticsTracker

logger = logging.getLogger(__name__)


class OfferViewSet(viewsets.ModelViewSet, OfferFilterMixin, OfferSortMixin,
                    CacheMixin, AnalyticsMixin, ResponseMixin):
    """
    ViewSet for offers — full CRUD for admins, read-only for users
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                           'toggle_featured', 'toggle_trending', 'calculate_quality']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        queryset = Offer.objects.select_related('provider', 'category').filter(
            status=STATUS_ACTIVE
        )
        
        # Apply filters
        queryset = self.apply_filters(queryset)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OfferDetailSerializer
        return OfferListSerializer
    
    def list(self, request, *args, **kwargs):
        """List offers with filters and pagination"""
        try:
            queryset = self.get_queryset()
            
            # Sort
            sort_by = request.query_params.get('sort_by', 'quality_score')
            queryset = self.sort_offers(queryset, sort_by)
            
            # Paginate
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        
        except Exception as e:
            logger.error(f"Error listing offers: {e}")
            return self.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def retrieve(self, request, *args, **kwargs):
        """Get offer detail"""
        try:
            offer = self.get_object()
            
            # Track view
            self.track_offer_view(offer, request.user, request)
            
            serializer = self.get_serializer(offer)
            return Response(serializer.data)
        
        except Offer.DoesNotExist:
            return self.error_response("Offer not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving offer: {e}")
            return self.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def click(self, request, pk=None):
        """
        Track offer click and return click URL
        
        POST /api/offerwall/offers/{id}/click/
        """
        try:
            offer = self.get_object()
            user = request.user
            
            # Validate offer availability
            validator = OfferValidator(offer)
            validator.validate_offer_availability(user)
            
            # Check rate limit
            if not self.check_rate_limit(user, 'offer_click', 100, 3600):
                raise RateLimitException("Too many clicks. Please try again later.")
            
            # Get device/location data
            click_data = {
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'device_type': request.data.get('device_type', ''),
                'device_model': request.data.get('device_model', ''),
                'os': request.data.get('os', ''),
                'os_version': request.data.get('os_version', ''),
                'browser': request.data.get('browser', ''),
                'country': request.data.get('country', ''),
                'city': request.data.get('city', ''),
                'referrer_url': request.META.get('HTTP_REFERER', ''),
                'session_id': request.data.get('session_id', ''),
                'tracking_params': request.data.get('tracking_params', {}),
            }
            
            # Fraud detection
            fraud_detector = FraudDetector(user, offer)
            fraud_check = fraud_detector.comprehensive_fraud_check(
                click_data=click_data,
                device_data=request.data.get('device_data')
            )
            
            if fraud_check['should_block']:
                fraud_detector.create_fraud_attempt_record(fraud_check)
                raise FraudException("Suspicious activity detected")
            
            # Track click
            tracker = AnalyticsTracker(offer, user)
            click_record = tracker.track_offer_click(click_data)
            
            if not click_record:
                return self.error_response("Failed to track click")
            
            # Build click URL
            from .services.OfferProcessor import OfferProcessorFactory
            processor = OfferProcessorFactory.create(offer.provider)
            click_url = processor.build_click_url(offer, user)
            
            return self.success_response({
                'click_id': click_record.click_id,
                'click_url': click_url,
                'offer': OfferListSerializer(offer).data
            })
        
        except (OfferNotFoundException, OfferInactiveException, OfferNotAvailableException, 
                OfferLimitReachedException, RateLimitException, FraudException) as e:
            return self.error_response(str(e), status_code=e.status_code)
        except Exception as e:
            logger.error(f"Error tracking click: {e}")
            return self.error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured offers"""
        queryset = self.get_queryset().filter(is_featured=True)[:20]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending offers"""
        tracker = AnalyticsTracker()
        trending_offers = tracker.get_trending_offers(limit=20)
        serializer = self.get_serializer(trending_offers, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recommended(self, request):
        """Get recommended offers for user"""
        # Simple recommendation based on user's previous completions
        from .models import OfferConversion
        
        # Get user's favorite categories
        user_categories = OfferConversion.objects.filter(
            user=request.user,
            status=CONVERSION_APPROVED
        ).values('offer__category').annotate(
            count=Count('id')
        ).order_by('-count')[:3]
        
        category_ids = [uc['offer__category'] for uc in user_categories if uc['offer__category']]
        
        queryset = self.get_queryset()
        
        if category_ids:
            queryset = queryset.filter(category_id__in=category_ids)
        
        queryset = queryset.order_by('-quality_score')[:20]
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get offer statistics"""
        queryset = Offer.objects.all()
        
        from django.db.models import Sum
        stats = {
            'total_offers': queryset.count(),
            'active_offers': queryset.filter(status=STATUS_ACTIVE).count(),
            'featured_offers': queryset.filter(is_featured=True).count(),
            'total_views': queryset.aggregate(total=Sum('view_count'))['total'] or 0,
            'total_clicks': queryset.aggregate(total=Sum('click_count'))['total'] or 0,
            'total_conversions': queryset.aggregate(total=Sum('conversion_count'))['total'] or 0,
            'total_revenue': float(queryset.aggregate(total=Sum('total_revenue'))['total'] or 0),
            'total_payout': float(queryset.aggregate(total=Sum('total_payout'))['total'] or 0),
            'average_completion_rate': queryset.aggregate(avg=Avg('completion_rate'))['avg'] or 0,
            'average_quality_score': queryset.aggregate(avg=Avg('quality_score'))['avg'] or 0,
        }
        
        return Response(stats)
    
    def apply_filters(self, queryset):
        """Apply query parameter filters"""
        params = self.request.query_params
        
        # Category filter
        category_id = params.get('category')
        if category_id:
            queryset = self.filter_by_category(queryset, category_id)
        
        # Offer type filter
        offer_type = params.get('offer_type')
        if offer_type:
            queryset = self.filter_by_offer_type(queryset, offer_type)
        
        # Platform filter
        platform = params.get('platform')
        if platform:
            queryset = self.filter_by_platform(queryset, platform)
        
        # Country filter
        country = params.get('country')
        if country:
            queryset = self.filter_by_country(queryset, country)
        
        # Payout range
        min_payout = params.get('min_payout')
        max_payout = params.get('max_payout')
        if min_payout or max_payout:
            queryset = self.filter_by_payout_range(queryset, min_payout, max_payout)
        
        # Featured filter
        featured = params.get('featured')
        if featured is not None:
            queryset = self.filter_featured(queryset, featured.lower() == 'true')
        
        # Search query
        query = params.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(description__icontains=query) |
                Q(tags__contains=[query])
            )
        
        return queryset


class OfferConversionViewSet(viewsets.ReadOnlyModelViewSet, ResponseMixin):
    """
    ViewSet for user's offer conversions
    
    Endpoints:
    - GET /api/offerwall/conversions/ - List user's conversions
    - GET /api/offerwall/conversions/{id}/ - Conversion detail
    - GET /api/offerwall/conversions/stats/ - User conversion stats
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OfferConversionSerializer
    
    def get_queryset(self):
        return OfferConversion.objects.filter(
            user=self.request.user
        ).select_related('offer', 'offer__provider').order_by('-converted_at')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OfferConversionDetailSerializer
        return OfferConversionSerializer
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get user's conversion statistics"""
        tracker = AnalyticsTracker(user=request.user)
        stats = tracker.get_user_offer_stats()
        return Response(stats)


class OfferCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for offer categories — full CRUD for admins, read-only for users
    """
    serializer_class = OfferCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return OfferCategory.objects.all()
        return OfferCategory.objects.filter(is_active=True)

    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    @action(detail=True, methods=['get'])
    def offers(self, request, pk=None):
        """Get offers in category"""
        category = self.get_object()
        
        offers = Offer.objects.filter(
            category=category,
            status=STATUS_ACTIVE
        ).order_by('-quality_score')[:50]
        
        serializer = OfferListSerializer(offers, many=True, context={'request': request})
        return Response(serializer.data)


class OfferProviderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for offer providers (Admin only)
    """
    queryset = OfferProvider.objects.all()
    serializer_class = OfferProviderSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'sync']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OfferProviderDetailSerializer
        return OfferProviderSerializer
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Sync offers from provider"""
        provider = self.get_object()

        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        try:
            from .services.OfferProcessor import OfferProcessorFactory
            processor = OfferProcessorFactory.create(provider)
            results = processor.sync_offers()
            provider.last_sync = timezone.now()
            provider.save(update_fields=['last_sync'])
            return Response(results)
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            msg = str(e)
            if 'No processor registered' in msg:
                return Response({
                    'error': f"Provider type '{provider.provider_type}' has no sync processor. Manual sync not supported for this provider.",
                    'provider_type': provider.provider_type,
                    'valid_types': ['tapjoy', 'adgem', 'adgate', 'persona', 'custom'],
                }, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get provider statistics"""
        provider = self.get_object()
        return Response({
            'total_offers':      provider.total_offers,
            'total_conversions': provider.total_conversions,
            'total_revenue':     float(provider.total_revenue),
            'last_sync':         provider.last_sync,
            'status':            provider.status,
        })

class OfferClickViewSet(viewsets.ReadOnlyModelViewSet, ResponseMixin):
    """
    ViewSet for offer clicks (admin read-only)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OfferClickSerializer

    def get_queryset(self):
        from rest_framework.permissions import IsAdminUser
        if self.request.user.is_staff:
            return OfferClick.objects.select_related('offer', 'user').order_by('-clicked_at')
        return OfferClick.objects.filter(user=self.request.user).order_by('-clicked_at')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from django.db.models import Sum, Count, Avg
        qs = self.get_queryset()
        total = qs.count()
        converted = qs.filter(is_converted=True).count()
        top_offers = qs.values('offer__title').annotate(c=Count('id')).order_by('-c')[:5]
        top_countries = qs.values('country').annotate(c=Count('id')).order_by('-c')[:5]
        return Response({
            'total': total,
            'converted': converted,
            'conversion_rate': round((converted / total * 100), 2) if total else 0,
            'top_offers': list(top_offers),
            'top_countries': list(top_countries),
        })


class OfferWallViewSet(viewsets.ModelViewSet):
    """
    ViewSet for offer walls
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OfferWallSerializer

    def get_queryset(self):
        return OfferWall.objects.all()

    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'], url_path='offers')
    def get_offers(self, request, pk=None):
        """Get filtered offers for this wall"""
        wall = self.get_object()
        offers = wall.get_offers(user=request.user)
        page = self.paginate_queryset(offers)
        if page is not None:
            serializer = OfferListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = OfferListSerializer(offers, many=True, context={'request': request})
        return Response(serializer.data)






# ============================================================
# PUBLIC OFFER API - No auth required (for landing page)
# ============================================================
from rest_framework.views import APIView

class PublicOfferListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import Offer
        offers = Offer.objects.filter(
            status='active'
        ).order_by('-is_featured', '-reward_amount', '-created_at')

        seen = set()
        unique_offers = []
        for offer in offers:
            key = offer.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_offers.append(offer)

        unique_offers = unique_offers[:100]

        data = []
        for offer in unique_offers:
            data.append({
                'id': offer.id,
                'title': offer.title,
                'description': offer.short_description or offer.description[:200],
                'offer_type': offer.offer_type,
                'payout': str(offer.payout),
                'currency': offer.currency,
                'reward_amount': str(offer.reward_amount),
                'reward_currency': offer.reward_currency,
                'countries': offer.countries,
                'image_url': offer.image_url or offer.thumbnail_url or offer.icon_url,
                'click_url': offer.click_url,
                'is_featured': offer.is_featured,
                'created_at': offer.created_at.strftime('%Y-%m-%d'),
                'category': offer.category.name if offer.category else 'General',
            })

        return Response({'count': len(data), 'results': data})
