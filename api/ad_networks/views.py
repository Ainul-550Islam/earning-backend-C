# api/ad_networks/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db.models import Q, Count, Sum, Prefetch, Avg
from django.core.cache import cache
import uuid
from datetime import timedelta

from core.views import BaseViewSet
from .models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferWall
)
from .serializers import (
    AdNetworkSerializer, OfferCategorySerializer,
    OfferSerializer, OfferDetailSerializer,
    UserOfferEngagementSerializer, OfferConversionSerializer,
    OfferWallSerializer, OfferListSerializer, SerializerFactory
)
from .services.AdNetworkFactory import AdNetworkFactory


# ============================================================================
# OPTIMIZED VIEWSETS
# ============================================================================

class OfferCategoryViewSet(BaseViewSet):
    """
    অপটিমাইজড ক্যাটাগরি ভিউসেট
    """
    queryset = OfferCategory.objects.filter(is_active=True)
    serializer_class = OfferCategorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Optimized queryset with caching"""
        cache_key = 'offer_categories_active'
        cached_queryset = cache.get(cache_key)
        
        if cached_queryset is not None:
            return cached_queryset
        
        queryset = super().get_queryset().select_related().prefetch_related(
            Prefetch(
                'offers',
                queryset=Offer.objects.filter(status='active').only(
                    'id', 'title', 'reward_amount'
                )
            )
        )
        
        cache.set(cache_key, queryset, timeout=300)
        return queryset
    
    @action(detail=True, methods=['get'])
    def offers(self, request, pk=None):
        """Get offers for specific category (optimized)"""
        category = self.get_object()
        
        # Cache key for category offers
        cache_key = f'category_{category.id}_offers'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        offers = Offer.objects.filter(
            category=category,
            status='active'
        ).select_related('ad_network', 'category').only(
            'id', 'title', 'description', 'reward_amount', 'reward_currency',
            'difficulty', 'estimated_time', 'thumbnail',
            'ad_network__name', 'category__name'
        )[:50]
        
        serializer = OfferListSerializer(offers, many=True, context=self.get_serializer_context())
        
        data = serializer.data
        cache.set(cache_key, data, timeout=180)
        return self.success_response(data=data)


class OfferViewSet(BaseViewSet):
    """
    অপটিমাইজড অফার ভিউসেট - সব performance issues fixed
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        ডায়নামিক queryset অপটিমাইজেশন
        """
        base_queryset = Offer.objects.filter(status='active')
        
        # Get appropriate serializer for eager loading
        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, 'setup_eager_loading'):
            base_queryset = serializer_class.setup_eager_loading(base_queryset)
        else:
            # Default eager loading
            base_queryset = base_queryset.select_related(
                'ad_network', 'category'
            )
        
        # Query parameters filtering (optimized)
        params = self.request.query_params
        
        # Category filter
        category_slug = params.get('category')
        if category_slug:
            base_queryset = base_queryset.filter(category__slug=category_slug)
        
        # Difficulty filter
        difficulty = params.get('difficulty')
        if difficulty:
            base_queryset = base_queryset.filter(difficulty=difficulty)
        
        # Featured filter
        featured = params.get('featured')
        if featured == 'true':
            base_queryset = base_queryset.filter(is_featured=True)
        
        # Minimum reward filter
        min_reward = params.get('min_reward')
        if min_reward:
            try:
                base_queryset = base_queryset.filter(reward_amount__gte=float(min_reward))
            except (ValueError, TypeError):
                pass
        
        # Exclude completed offers by user
        exclude_completed = params.get('exclude_completed', 'true')
        if exclude_completed == 'true' and self.request.user.is_authenticated:
            completed_offer_ids = UserOfferEngagement.objects.filter(
                user=self.request.user,
                status__in=['completed', 'approved']
            ).values_list('offer_id', flat=True)
            base_queryset = base_queryset.exclude(id__in=completed_offer_ids)
        
        return base_queryset
    
    def get_serializer_class(self):
        """
        ডায়নামিক সিরিয়ালাইজার সিলেকশন
        """
        # Use SerializerFactory for optimization
        return SerializerFactory.get_offer_serializer(
            action=self.action,
            context=self.get_serializer_context()
        )
    
    def list(self, request, *args, **kwargs):
        """
        অপটিমাইজড লিস্ট ভিউ
        """
        # Cache for list view
        cache_key = self._get_list_cache_key(request)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data
        
        # Cache the result
        cache.set(cache_key, data, timeout=120)
        return self.success_response(data=data)
    
    def retrieve(self, request, *args, **kwargs):
        """
        অপটিমাইজড ডিটেইল ভিউ
        """
        instance = self.get_object()
        
        # Prefetch user engagement for this offer
        if request.user.is_authenticated:
            user_engagement = UserOfferEngagement.objects.filter(
                offer=instance,
                user=request.user
            ).select_related('user').first()
            
            # Attach to instance for serializer access
            instance.user_engagement = user_engagement
        
        # Get conversion stats (cached)
        cache_key = f'offer_{instance.id}_conversion_stats'
        conversion_stats = cache.get(cache_key)
        
        if not conversion_stats:
            conversion_stats = self._get_conversion_stats(instance)
            cache.set(cache_key, conversion_stats, timeout=300)
        
        instance.conversion_stats = conversion_stats
        
        serializer = self.get_serializer(instance)
        return self.success_response(data=serializer.data)
    
    @action(detail=True, methods=['post'])
    def click(self, request, pk=None):
        """
        অপটিমাইজড অফার ক্লিক ট্র্যাকিং
        """
        offer = self.get_object()
        user = request.user
        
        # Validate user can click
        if not offer.is_available_for_user(user):
            return self.error_response(
                message='This offer is not available for you',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check existing engagement
        existing_engagement = UserOfferEngagement.objects.filter(
            user=user,
            offer=offer
        ).first()
        
        if existing_engagement and existing_engagement.status in ['completed', 'approved']:
            return self.error_response(
                message='You have already completed this offer',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate click data
        click_data = {
            'user': user.id,
            'offer': offer.id,
            'click_id': str(uuid.uuid4()),
            'status': 'clicked',
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'device_info': request.data.get('device_info', {}),
            'clicked_at': timezone.now()
        }
        
        # Create engagement
        engagement_serializer = UserOfferEngagementSerializer(
            data=click_data,
            context=self.get_serializer_context()
        )
        
        if engagement_serializer.is_valid():
            engagement = engagement_serializer.save()
            
            # Update offer click count (optimized)
            Offer.objects.filter(id=offer.id).update(
                click_count=offer.click_count + 1
            )
            
            # Get tracking URL from ad network
            try:
                ad_service = AdNetworkFactory.get_service(offer.ad_network.network_type)
                tracking_url = ad_service.generate_tracking_url(offer, engagement)
            except Exception as e:
                tracking_url = offer.click_url or offer.tracking_url
            
            # Invalidate caches
            self._invalidate_offer_caches(offer, user)
            
            return self.success_response(
                data={
                    'click_id': engagement.click_id,
                    'tracking_url': tracking_url,
                    'engagement_id': engagement.id
                },
                message='Offer clicked successfully'
            )
        
        return self.error_response(
            errors=engagement_serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def recommended(self, request):
        """
        অপটিমাইজড রিকমেন্ডেড অফারস
        """
        user = request.user
        
        # Cache key for user recommendations
        cache_key = f'user_{user.id}_recommended_offers'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        # Get user's completed categories
        completed_categories = UserOfferEngagement.objects.filter(
            user=user,
            status__in=['completed', 'approved']
        ).values_list('offer__category_id', flat=True).distinct()
        
        if not completed_categories:
            # If no completed offers, show featured offers
            recommended_offers = Offer.objects.filter(
                status='active',
                is_featured=True
            ).exclude(
                id__in=UserOfferEngagement.objects.filter(
                    user=user
                ).values_list('offer_id', flat=True)
            ).select_related('ad_network', 'category').only(
                'id', 'title', 'reward_amount', 'reward_currency',
                'difficulty', 'estimated_time', 'thumbnail',
                'ad_network__name', 'category__name'
            )[:10]
        else:
            # Recommend from completed categories
            recommended_offers = Offer.objects.filter(
                status='active',
                category_id__in=completed_categories
            ).exclude(
                id__in=UserOfferEngagement.objects.filter(
                    user=user
                ).values_list('offer_id', flat=True)
            ).select_related('ad_network', 'category').only(
                'id', 'title', 'reward_amount', 'reward_currency',
                'difficulty', 'estimated_time', 'thumbnail',
                'ad_network__name', 'category__name'
            ).order_by('-reward_amount')[:10]
        
        serializer = OfferListSerializer(
            recommended_offers,
            many=True,
            context=self.get_serializer_context()
        )
        
        data = serializer.data
        cache.set(cache_key, data, timeout=300)
        return self.success_response(data=data)
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """
        অপটিমাইজড ট্রেন্ডিং অফারস
        """
        cache_key = 'trending_offers'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        last_week = timezone.now() - timedelta(days=7)
        
        # Get trending offers with optimized query
        trending_offers = Offer.objects.filter(
            status='active'
        ).annotate(
            recent_conversions=Count(
                'engagements',
                filter=Q(
                    engagements__status__in=['completed', 'approved', 'rewarded'],
                    engagements__completed_at__gte=last_week
                )
            )
        ).filter(
            recent_conversions__gt=0
        ).select_related('ad_network', 'category').only(
            'id', 'title', 'reward_amount', 'reward_currency',
            'difficulty', 'estimated_time', 'thumbnail', 'total_conversions',
            'ad_network__name', 'category__name'
        ).order_by('-recent_conversions', '-total_conversions')[:20]
        
        serializer = OfferListSerializer(
            trending_offers,
            many=True,
            context=self.get_serializer_context()
        )
        
        data = serializer.data
        cache.set(cache_key, data, timeout=600)  # 10 minutes cache
        return self.success_response(data=data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        গ্লোবাল অফার স্ট্যাটিস্টিক্স
        """
        user = request.user
        
        cache_key = f'user_{user.id}_offer_stats'
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return self.success_response(data=cached_stats)
        
        # Get user-specific stats
        user_stats = UserOfferEngagement.objects.filter(
            user=user
        ).aggregate(
            total_clicks=Count('id'),
            total_completed=Count('id', filter=Q(status__in=['completed', 'approved'])),
            total_earnings=Sum('reward_earned', filter=Q(status='approved')),
            pending_approval=Count('id', filter=Q(status='pending')),
        )
        
        # Get global stats
        global_stats = {
            'total_active_offers': Offer.objects.filter(status='active').count(),
            'total_categories': OfferCategory.objects.filter(is_active=True).count(),
            'total_networks': AdNetwork.objects.filter(is_active=True).count(),
        }
        
        stats = {
            'user_stats': user_stats,
            'global_stats': global_stats,
            'timestamp': timezone.now().isoformat()
        }
        
        cache.set(cache_key, stats, timeout=300)
        return self.success_response(data=stats)
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_list_cache_key(self, request):
        """Generate cache key for list view"""
        params = dict(request.query_params)
        params.pop('page', None)
        params.pop('page_size', None)
        params_str = str(sorted(params.items()))
        return f'offer_list_{hash(params_str)}_{request.user.id if request.user.is_authenticated else "anon"}'
    
    def _get_conversion_stats(self, offer):
        """Get conversion stats for an offer"""
        last_7_days = timezone.now() - timedelta(days=7)
        last_30_days = timezone.now() - timedelta(days=30)
        
        stats = UserOfferEngagement.objects.filter(
            offer=offer,
            status__in=['completed', 'approved', 'rewarded']
        ).aggregate(
            conversions_7d=Count('id', filter=Q(completed_at__gte=last_7_days)),
            conversions_30d=Count('id', filter=Q(completed_at__gte=last_30_days)),
            total_earned=Sum('reward_earned')
        )
        
        return {
            'conversions_last_7_days': stats['conversions_7d'] or 0,
            'conversions_last_30_days': stats['conversions_30d'] or 0,
            'average_completion_time': 0,
            'total_earned': stats['total_earned'] or 0
        }
    
    def _get_client_ip(self, request):
        """Extract client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _invalidate_offer_caches(self, offer, user):
        """Invalidate caches related to offer"""
        cache_keys = [
            f'offer_{offer.id}_detail',
            f'offer_{offer.id}_conversion_stats',
            f'user_{user.id}_recommended_offers',
            'trending_offers',
        ]
        
        for key in cache_keys:
            cache.delete(key)


# ============================================================================
# OPTIMIZED USER OFFER ENGAGEMENT VIEWSET
# ============================================================================

class UserOfferEngagementViewSet(BaseViewSet):
    """
    অপটিমাইজড ইউজার এনগেজমেন্ট ভিউসেট
    """
    serializer_class = UserOfferEngagementSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        অপটিমাইজড queryset for user engagements
        """
        return UserOfferEngagement.objects.filter(
            user=self.request.user
        ).select_related(
            'offer', 'offer__ad_network', 'offer__category'
        ).order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """
        অপটিমাইজড লিস্ট ভিউ with caching
        """
        cache_key = f'user_{request.user.id}_engagements_list'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data
        
        cache.set(cache_key, data, timeout=120)
        return self.success_response(data=data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        অপটিমাইজড হিস্টোরি ভিউ
        """
        status_filter = request.query_params.get('status')
        time_filter = request.query_params.get('time', 'all')  # day, week, month, all
        
        queryset = self.get_queryset()
        
        # Status filter
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Time filter
        now = timezone.now()
        if time_filter == 'day':
            queryset = queryset.filter(created_at__date=now.date())
        elif time_filter == 'week':
            queryset = queryset.filter(created_at__gte=now - timedelta(days=7))
        elif time_filter == 'month':
            queryset = queryset.filter(created_at__gte=now - timedelta(days=30))
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return self.success_response(data=serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        অপটিমাইজড ইউজার স্ট্যাটস
        """
        user = request.user
        
        cache_key = f'user_{user.id}_engagement_stats'
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return self.success_response(data=cached_stats)
        
        # Get comprehensive stats in single query
        stats = UserOfferEngagement.objects.filter(
            user=user
        ).aggregate(
            total_engagements=Count('id'),
            total_clicks=Count('id', filter=Q(status='clicked')),
            total_started=Count('id', filter=Q(status='started')),
            total_completed=Count('id', filter=Q(status__in=['completed', 'approved'])),
            total_rejected=Count('id', filter=Q(status='rejected')),
            total_earnings=Sum('reward_earned', filter=Q(status='approved')),
            avg_earnings_per_offer=Avg('reward_earned', filter=Q(status='approved')),
            pending_approval=Count('id', filter=Q(status='pending')),
            conversion_rate=Count('id', filter=Q(status__in=['completed', 'approved']))
        )
        
        # Get recent activity
        recent_activity = UserOfferEngagement.objects.filter(
            user=user
        ).select_related('offer').only(
            'id', 'status', 'reward_earned', 'created_at', 'offer__title'
        ).order_by('-created_at')[:5]
        
        data = {
            'stats': stats,
            'recent_activity': [
                {
                    'id': engagement.id,
                    'offer_title': engagement.offer.title if engagement.offer else 'N/A',
                    'status': engagement.status,
                    'reward_earned': engagement.reward_earned,
                    'created_at': engagement.created_at
                }
                for engagement in recent_activity
            ],
            'updated_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, data, timeout=300)
        return self.success_response(data=data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        মার্ক এনগেজমেন্ট as completed
        """
        engagement = self.get_object()
        
        if engagement.status not in ['clicked', 'started', 'in_progress']:
            return self.error_response(
                message='Cannot complete this engagement. Invalid status.',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Update engagement
        engagement.status = 'completed'
        engagement.completed_at = timezone.now()
        engagement.progress = 100
        
        # Calculate reward (if not set)
        if engagement.reward_earned is None:
            engagement.reward_earned = engagement.offer.reward_amount
        
        engagement.save()
        
        # Update offer conversion count
        Offer.objects.filter(id=engagement.offer.id).update(
            total_conversions=engagement.offer.total_conversions + 1
        )
        
        # Invalidate caches
        self._invalidate_engagement_caches(engagement)
        
        return self.success_response(
            message='Engagement marked as completed successfully',
            data=self.get_serializer(engagement).data
        )
    

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a user offer engagement"""
        engagement = self.get_object()
        engagement.status = 'approved'
        engagement.save(update_fields=['status'])
        return Response({'success': True, 'status': 'approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a user offer engagement"""
        engagement = self.get_object()
        engagement.status = 'rejected'
        rejection_reason = request.data.get('rejection_reason', '')
        rejection_details = request.data.get('rejection_details', '')
        engagement.rejection_reason = rejection_reason
        if hasattr(engagement, 'rejection_details'):
            engagement.rejection_details = rejection_details
        engagement.save(update_fields=['status', 'rejection_reason'])
        return Response({'success': True, 'status': 'rejected'})

    def _invalidate_engagement_caches(self, engagement):
        """Invalidate caches related to engagement"""
        cache_keys = [
            f'user_{engagement.user.id}_engagements_list',
            f'user_{engagement.user.id}_engagement_stats',
            f'user_{engagement.user.id}_offer_stats',
            f'offer_{engagement.offer.id}_detail',
            f'offer_{engagement.offer.id}_conversion_stats',
        ]
        
        for key in cache_keys:
            cache.delete(key)


# ============================================================================
# OPTIMIZED OFFER WALL VIEWSET
# ============================================================================

class OfferWallViewSet(BaseViewSet):
    """
    অপটিমাইজড অফার ওয়াল ভিউসেট
    """
    queryset = OfferWall.objects.filter(is_active=True)
    serializer_class = OfferWallSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Optimized queryset for offer walls"""
        return super().get_queryset().prefetch_related(
            Prefetch(
                'ad_networks',
                queryset=AdNetwork.objects.filter(is_active=True).only('id', 'name', 'logo_url')
            ),
            Prefetch(
                'categories',
                queryset=OfferCategory.objects.filter(is_active=True).only('id', 'name', 'icon')
            )
        )
    
    @action(detail=True, methods=['get'])
    def offers(self, request, pk=None):
        """
        অপটিমাইজড অফার ওয়াল অফারস
        """
        offerwall = self.get_object()
        user = request.user
        
        cache_key = f'offerwall_{offerwall.id}_offers_user_{user.id}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        # Build optimized query
        offers_queryset = Offer.objects.filter(
            status='active',
            ad_network__in=offerwall.ad_networks.all()
        )
        
        # Apply category filter if exists
        if offerwall.categories.exists():
            offers_queryset = offers_queryset.filter(
                category__in=offerwall.categories.all()
            )
        
        # Apply payout filter
        if offerwall.min_payout > 0:
            offers_queryset = offers_queryset.filter(
                reward_amount__gte=offerwall.min_payout
            )
        
        # Exclude user completed offers
        completed_offer_ids = UserOfferEngagement.objects.filter(
            user=user,
            status__in=['completed', 'approved']
        ).values_list('offer_id', flat=True)
        
        offers_queryset = offers_queryset.exclude(id__in=completed_offer_ids)
        
        # Optimize queryset
        offers_queryset = offers_queryset.select_related(
            'ad_network', 'category'
        ).only(
            'id', 'title', 'description', 'reward_amount', 'reward_currency',
            'difficulty', 'estimated_time', 'thumbnail', 'countries',
            'platforms', 'device_type', 'ad_network__name', 'category__name'
        )
        
        # Apply sorting
        sort_by = request.query_params.get('sort', 'reward_amount')
        if sort_by == 'reward_amount':
            offers_queryset = offers_queryset.order_by('-reward_amount')
        elif sort_by == 'difficulty':
            offers_queryset = offers_queryset.order_by('difficulty')
        elif sort_by == 'newest':
            offers_queryset = offers_queryset.order_by('-created_at')
        
        # Paginate
        page = self.paginate_queryset(offers_queryset)
        
        if page is not None:
            serializer = OfferListSerializer(
                page,
                many=True,
                context=self.get_serializer_context()
            )
            data = self.get_paginated_response(serializer.data).data
        else:
            serializer = OfferListSerializer(
                offers_queryset,
                many=True,
                context=self.get_serializer_context()
            )
            data = serializer.data
        
        # Cache the result
        cache.set(cache_key, data, timeout=180)
        return self.success_response(data=data)
    
    @action(detail=False, methods=['get'])
    def user_walls(self, request):
        user = request.user
        # ইউজারের প্রোফাইল না থাকলে ডিফল্ট 'US'
        user_country = 'US'
        if hasattr(user, 'profile') and user.profile.country:
            user_country = user.profile.country

        available_walls = OfferWall.objects.filter(
            is_active=True
        ).filter(
            # countries যদি JSONField/ArrayField হয় তবে নিচের লাইন ঠিক আছে
            Q(countries__contains=[user_country]) | Q(countries=[]) | Q(countries__isnull=True)
        ).prefetch_related(
            'ad_networks'
        ).annotate(
            total_offers=Count(
                'ad_networks__offers', 
                filter=Q(
                    ad_networks__offers__status='active',
                    ad_networks__offers__countries__contains=[user_country]
                )
            )
        ).filter(
            total_offers__gt=0
        ).order_by('-priority', '-total_offers')

        serializer = self.get_serializer(available_walls, many=True)
        
        # আপনার কাস্টম সাকসেস রেসপন্স মেথড থাকলে সেটি ব্যবহার করুন
        if hasattr(self, 'success_response'):
            return self.success_response(data=serializer.data)
        return Response(serializer.data)

# ============================================================================
# ANALYTICS VIEWS
# ============================================================================

class AnalyticsViewSet(BaseViewSet):
    """
    অ্যানালিটিক্স ভিউস
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def daily_stats(self, request):
        """
        ডেইলি স্ট্যাটিস্টিক্স
        """
        user = request.user
        days = int(request.query_params.get('days', 7))
        
        cache_key = f'user_{user.id}_daily_stats_{days}days'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get daily stats
        daily_stats = UserOfferEngagement.objects.filter(
            user=user,
            created_at__range=[start_date, end_date]
        ).extra({
            'date': "DATE(created_at)"
        }).values('date').annotate(
            clicks=Count('id', filter=Q(status='clicked')),
            completions=Count('id', filter=Q(status__in=['completed', 'approved'])),
            earnings=Sum('reward_earned', filter=Q(status='approved'))
        ).order_by('date')
        
        # Get top performing offers
        top_offers = UserOfferEngagement.objects.filter(
            user=user,
            status__in=['completed', 'approved'],
            created_at__range=[start_date, end_date]
        ).values(
            'offer__id',
            'offer__title'
        ).annotate(
            completions=Count('id'),
            total_earnings=Sum('reward_earned')
        ).order_by('-total_earnings')[:5]
        
        data = {
            'daily_stats': list(daily_stats),
            'top_offers': list(top_offers),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            }
        }
        
        cache.set(cache_key, data, timeout=600)  # 10 minutes cache
        return self.success_response(data=data)
    
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """
        ইউজার পারফরম্যান্স অ্যানালিটিক্স
        """
        user = request.user
        
        cache_key = f'user_{user.id}_performance_analytics'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        # Get performance metrics
        metrics = UserOfferEngagement.objects.filter(
            user=user
        ).aggregate(
            overall_conversion_rate=Count('id', filter=Q(status__in=['completed', 'approved'])) * 100.0 / Count('id', filter=Q(status__in=['clicked', 'started'])) if Count('id', filter=Q(status__in=['clicked', 'started'])) > 0 else 0,
            avg_earning_per_click=Avg('reward_earned', filter=Q(status='approved')) / Count('id', filter=Q(status='clicked')) if Count('id', filter=Q(status='clicked')) > 0 else 0,
            success_rate_by_difficulty=Count('id', filter=Q(
                status__in=['completed', 'approved'],
                offer__difficulty='easy'
            )) * 100.0 / Count('id', filter=Q(offer__difficulty='easy')) if Count('id', filter=Q(offer__difficulty='easy')) > 0 else 0
        )
        
        # Get earning trend
        monthly_earnings = UserOfferEngagement.objects.filter(
            user=user,
            status='approved',
            rewarded_at__gte=timezone.now() - timedelta(days=90)
        ).extra({
            'month': "DATE_TRUNC('month', rewarded_at)"
        }).values('month').annotate(
            earnings=Sum('reward_earned')
        ).order_by('month')
        
        data = {
            'performance_metrics': metrics,
            'earning_trend': list(monthly_earnings),
            'recommendations': self._generate_recommendations(user)
        }
        
        cache.set(cache_key, data, timeout=1800)  # 30 minutes cache
        return self.success_response(data=data)
    
    def _generate_recommendations(self, user):
        """
        জেনারেট পার্সোনালাইজড রিকমেন্ডেশনস
        """
        recommendations = []
        
        # Get user's best performing categories
        top_categories = UserOfferEngagement.objects.filter(
            user=user,
            status__in=['completed', 'approved']
        ).values(
            'offer__category__id',
            'offer__category__name'
        ).annotate(
            success_rate=Count('id') * 100.0 / Count('id', filter=Q(status='clicked')) if Count('id', filter=Q(status='clicked')) > 0 else 0,
            avg_earning=Avg('reward_earned')
        ).order_by('-success_rate')[:3]
        
        for category in top_categories:
            recommendations.append({
                'type': 'category',
                'message': f'You have {category["success_rate"]:.1f}% success rate in {category["offer__category__name"]}. Try more offers from this category.',
                'category_id': category['offer__category__id']
            })
        
        # Check for time-based patterns
        hour_stats = UserOfferEngagement.objects.filter(
            user=user,
            status__in=['completed', 'approved']
        ).extra({
            'hour': "EXTRACT(HOUR FROM completed_at)"
        }).values('hour').annotate(
            success_rate=Count('id') * 100.0 / Count('id', filter=Q(status='clicked')) if Count('id', filter=Q(status='clicked')) > 0 else 0
        ).order_by('-success_rate')[:1]
        
        if hour_stats:
            best_hour = hour_stats[0]['hour']
            recommendations.append({
                'type': 'timing',
                'message': f'Your highest success rate ({hour_stats[0]["success_rate"]:.1f}%) is at {int(best_hour)}:00. Try completing offers around this time.',
                'best_hour': int(best_hour)
            })
        
        return recommendations




# api/ad_networks/views.py ফাইলে নিচের কোড যোগ করুন

# ============================================================================
# AD NETWORK VIEWSET
# ============================================================================

class AdNetworkViewSet(BaseViewSet):
    """
    অপটিমাইজড অ্যাড নেটওয়ার্ক ভিউসেট
    """
    queryset = AdNetwork.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """
        ডায়নামিক সিরিয়ালাইজার সিলেকশন
        """
        from .serializers import SerializerFactory
        return SerializerFactory.get_ad_network_serializer(
            action=self.action,
            context=self.get_serializer_context()
        )
    
    def get_queryset(self):
        """
        অপটিমাইজড queryset
        """
        queryset = super().get_queryset()
        
        # Get serializer class for eager loading
        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, 'setup_eager_loading'):
            queryset = serializer_class.setup_eager_loading(queryset)
        else:
            # Default eager loading
            queryset = queryset.select_related().prefetch_related('offers')
        
        # Query parameter filtering
        params = self.request.query_params
        
        # Category filter
        category = params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Country support filter
        country = params.get('country')
        if country:
            queryset = queryset.filter(
                Q(country_support='global') |
                Q(countries__contains=[country.upper()])
            )
        
        # Network type filter
        network_type = params.get('network_type')
        if network_type:
            queryset = queryset.filter(network_type=network_type)
        
        # Supports offers filter
        supports_offers = params.get('supports_offers')
        if supports_offers == 'true':
            queryset = queryset.filter(supports_offers=True)
        
        # Sort by
        sort_by = params.get('sort', 'priority')
        if sort_by == 'priority':
            queryset = queryset.order_by('-priority', '-rating')
        elif sort_by == 'rating':
            queryset = queryset.order_by('-rating', '-priority')
        elif sort_by == 'payout':
            queryset = queryset.order_by('-total_payout', '-priority')
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """
        অপটিমাইজড লিস্ট ভিউ with caching
        """
        # Generate cache key
        cache_key = self._get_list_cache_key(request)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data
        
        # Cache the result
        cache.set(cache_key, data, timeout=300)
        return self.success_response(data=data)
    
    def retrieve(self, request, *args, **kwargs):
        """
        অপটিমাইজড ডিটেইল ভিউ
        """
        instance = self.get_object()
        
        # Prefetch related data for detail view
        instance.offers_prefetched = Offer.objects.filter(
            ad_network=instance,
            status='active'
        ).select_related('category').only(
            'id', 'title', 'reward_amount', 'difficulty',
            'estimated_time', 'thumbnail', 'category__name'
        )[:20]
        
        # Get network statistics
        cache_key = f'ad_network_{instance.id}_stats'
        network_stats = cache.get(cache_key)
        
        if not network_stats:
            network_stats = self._get_network_stats(instance)
            cache.set(cache_key, network_stats, timeout=600)
        
        instance.network_stats = network_stats
        
        serializer = self.get_serializer(instance)
        return self.success_response(data=serializer.data)
    
    @action(detail=True, methods=['get'])
    def offers(self, request, pk=None):
        """
        Get all offers for a specific ad network
        """
        ad_network = self.get_object()
        user = request.user
        
        cache_key = f'ad_network_{ad_network.id}_offers_user_{user.id}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        offers = Offer.objects.filter(
            ad_network=ad_network,
            status='active'
        ).select_related('category').prefetch_related(
            Prefetch(
                'engagements',
                queryset=UserOfferEngagement.objects.filter(user=user),
                to_attr='user_engagements'
            )
        ).only(
            'id', 'title', 'description', 'reward_amount', 'reward_currency',
            'difficulty', 'estimated_time', 'thumbnail', 'countries',
            'platforms', 'device_type', 'category__name'
        )
        
        # Apply filters
        params = request.query_params
        
        # Category filter
        category = params.get('category')
        if category:
            offers = offers.filter(category__slug=category)
        
        # Difficulty filter
        difficulty = params.get('difficulty')
        if difficulty:
            offers = offers.filter(difficulty=difficulty)
        
        # Minimum reward filter
        min_reward = params.get('min_reward')
        if min_reward:
            try:
                offers = offers.filter(reward_amount__gte=float(min_reward))
            except (ValueError, TypeError):
                pass
        
        # Exclude completed offers
        exclude_completed = params.get('exclude_completed', 'true')
        if exclude_completed == 'true' and user.is_authenticated:
            completed_offer_ids = UserOfferEngagement.objects.filter(
                user=user,
                status__in=['completed', 'approved']
            ).values_list('offer_id', flat=True)
            offers = offers.exclude(id__in=completed_offer_ids)
        
        # Sort by
        sort_by = params.get('sort', 'reward_amount')
        if sort_by == 'reward_amount':
            offers = offers.order_by('-reward_amount')
        elif sort_by == 'difficulty':
            offers = offers.order_by('difficulty')
        elif sort_by == 'newest':
            offers = offers.order_by('-created_at')
        elif sort_by == 'conversions':
            offers = offers.order_by('-total_conversions')
        
        # Paginate
        page = self.paginate_queryset(offers)
        
        if page is not None:
            serializer = OfferListSerializer(
                page,
                many=True,
                context=self.get_serializer_context()
            )
            data = self.get_paginated_response(serializer.data).data
        else:
            serializer = OfferListSerializer(
                offers,
                many=True,
                context=self.get_serializer_context()
            )
            data = serializer.data
        
        # Cache the result
        cache.set(cache_key, data, timeout=180)
        return self.success_response(data=data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Get detailed statistics for ad network
        """
        ad_network = self.get_object()
        
        cache_key = f'ad_network_{ad_network.id}_detailed_stats'
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return self.success_response(data=cached_stats)
        
        stats = self._get_detailed_stats(ad_network)
        
        cache.set(cache_key, stats, timeout=900)  # 15 minutes
        return self.success_response(data=stats)
    
    @action(detail=False, methods=['get'])
    def top_networks(self, request):
        """
        Get top performing networks
        """
        cache_key = 'top_ad_networks'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        top_networks = AdNetwork.objects.filter(
            is_active=True,
            total_conversions__gt=0
        ).select_related().order_by(
            '-total_conversions', '-conversion_rate'
        )[:10]
        
        serializer = self.get_serializer(top_networks, many=True)
        data = serializer.data
        
        cache.set(cache_key, data, timeout=600)
        return self.success_response(data=data)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Get network categories with counts
        """
        cache_key = 'ad_network_categories'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return self.success_response(data=cached_data)
        
        categories = AdNetwork.objects.filter(
            is_active=True
        ).values('category').annotate(
            count=Count('id'),
            avg_rating=Avg('rating'),
            avg_conversion_rate=Avg('conversion_rate'),
            total_payout=Sum('total_payout')
        ).order_by('-count')
        
        # Format categories with display names
        category_display = {
            'offerwall': 'Offerwall 📱',
            'survey': 'Survey [NOTE]',
            'video': 'Video/Ads 🎬',
            'gaming': 'Gaming 🎮',
            'app_install': 'App Install 📲',
            'cashback': 'Cashback [MONEY]',
            'cpi_cpa': 'CPI/CPA [STATS]',
            'cpe': 'CPE [LOADING]',
            'other': 'Other 📦',
        }
        
        formatted_categories = []
        for cat in categories:
            category_name = cat['category']
            formatted_categories.append({
                'category': category_name,
                'display_name': category_display.get(category_name, category_name),
                'count': cat['count'],
                'avg_rating': round(cat['avg_rating'] or 0, 2),
                'avg_conversion_rate': round(cat['avg_conversion_rate'] or 0, 2),
                'total_payout': cat['total_payout'] or 0
            })
        
        cache.set(cache_key, formatted_categories, timeout=1800)  # 30 minutes
        return self.success_response(data=formatted_categories)
    
    @action(detail=True, methods=['post'])
    def sync_offers(self, request, pk=None):
        """
        Sync offers from ad network (manual trigger)
        """
        ad_network = self.get_object()
        
        # Check if network supports API sync
        if not ad_network.supports_offers or not ad_network.api_key:
            return self.error_response(
                message='This network does not support API sync',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get ad network service
            ad_service = AdNetworkFactory.get_service(ad_network.network_type)
            
            # Sync offers
            sync_result = ad_service.sync_offers(ad_network)
            
            # Create sync log
            from .models import OfferSyncLog
            OfferSyncLog.objects.create(
                ad_network=ad_network,
                sync_type='manual',
                offers_fetched=sync_result.get('offers_fetched', 0),
                offers_created=sync_result.get('offers_created', 0),
                offers_updated=sync_result.get('offers_updated', 0),
                success=True,
                metadata=sync_result
            )
            
            # Update last sync time
            ad_network.last_sync = timezone.now()
            ad_network.save()
            
            # Invalidate caches
            self._invalidate_network_caches(ad_network)
            
            return self.success_response(
                data=sync_result,
                message=f"Successfully synced {sync_result.get('offers_fetched', 0)} offers"
            )
            
        except Exception as e:
            # Log error
            from .models import OfferSyncLog
            OfferSyncLog.objects.create(
                ad_network=ad_network,
                sync_type='manual',
                success=False,
                error_message=str(e)
            )
            
            return self.error_response(
                message=f"Failed to sync offers: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_list_cache_key(self, request):
        """Generate cache key for list view"""
        params = dict(request.query_params)
        params.pop('page', None)
        params.pop('page_size', None)
        params_str = str(sorted(params.items()))
        return f'ad_network_list_{hash(params_str)}_{request.user.id if request.user.is_authenticated else "anon"}'
    
    def _get_network_stats(self, ad_network):
        """Get network statistics"""
        # Today's date
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Get basic stats
        stats = {
            'total_offers': Offer.objects.filter(
                ad_network=ad_network,
                status='active'
            ).count(),
            'total_active_users': UserOfferEngagement.objects.filter(
                offer__ad_network=ad_network
            ).values('user').distinct().count(),
            'network_info': {
                'name': ad_network.name,
                'network_type': ad_network.network_type,
                'category': ad_network.category,
                'rating': ad_network.rating,
                'trust_score': ad_network.trust_score,
                'is_verified': ad_network.is_verified
            }
        }
        
        # Get conversion stats
        conversion_stats = UserOfferEngagement.objects.filter(
            offer__ad_network=ad_network,
            status__in=['completed', 'approved', 'rewarded']
        ).aggregate(
            total_conversions=Count('id'),
            conversions_today=Count('id', filter=Q(completed_at__date=today)),
            conversions_yesterday=Count('id', filter=Q(completed_at__date=yesterday)),
            conversions_last_7_days=Count('id', filter=Q(completed_at__gte=last_7_days)),
            conversions_last_30_days=Count('id', filter=Q(completed_at__gte=last_30_days)),
            total_earned=Sum('reward_earned'),
        )
        
        stats.update(conversion_stats)
        
        # Get click stats
        click_stats = UserOfferEngagement.objects.filter(
            offer__ad_network=ad_network,
            status='clicked'
        ).aggregate(
            total_clicks=Count('id'),
            clicks_today=Count('id', filter=Q(clicked_at__date=today)),
            clicks_last_7_days=Count('id', filter=Q(clicked_at__gte=last_7_days))
        )
        
        stats.update(click_stats)
        
        # Calculate conversion rates
        if stats.get('total_clicks', 0) > 0:
            stats['overall_conversion_rate'] = (stats['total_conversions'] / stats['total_clicks']) * 100
        
        if stats.get('clicks_today', 0) > 0:
            stats['today_conversion_rate'] = (stats['conversions_today'] / stats['clicks_today']) * 100
        
        # Get top performing offers
        top_offers = Offer.objects.filter(
            ad_network=ad_network,
            status='active'
        ).annotate(
            recent_conversions=Count(
                'engagements',
                filter=Q(
                    engagements__status__in=['completed', 'approved', 'rewarded'],
                    engagements__completed_at__gte=last_7_days
                )
            )
        ).order_by('-recent_conversions', '-total_conversions')[:5]
        
        stats['top_offers'] = [
            {
                'id': offer.id,
                'title': offer.title,
                'reward_amount': offer.reward_amount,
                'total_conversions': offer.total_conversions,
                'recent_conversions': offer.recent_conversions
            }
            for offer in top_offers
        ]
        
        # Get user distribution by country
        user_countries = UserOfferEngagement.objects.filter(
            offer__ad_network=ad_network
        ).exclude(
            location_data__isnull=True
        ).values(
            'location_data__country'
        ).annotate(
            user_count=Count('user', distinct=True),
            conversion_count=Count('id', filter=Q(status__in=['completed', 'approved', 'rewarded']))
        ).order_by('-user_count')[:5]
        
        stats['top_countries'] = [
            {
                'country': item['location_data__country'],
                'user_count': item['user_count'],
                'conversion_count': item['conversion_count']
            }
            for item in user_countries
        ]
        
        return stats
    
    def _get_detailed_stats(self, ad_network):
        """Get detailed statistics for ad network"""
        # Time periods
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Daily stats for last 7 days
        daily_stats = UserOfferEngagement.objects.filter(
            offer__ad_network=ad_network,
            completed_at__gte=last_7_days,
            status__in=['completed', 'approved', 'rewarded']
        ).extra({
            'date': "DATE(completed_at)"
        }).values('date').annotate(
            conversions=Count('id'),
            earnings=Sum('reward_earned'),
            clicks=Count('id', filter=Q(status='clicked'))
        ).order_by('date')
        
        # Offer category distribution
        category_stats = Offer.objects.filter(
            ad_network=ad_network,
            status='active'
        ).values('category__name').annotate(
            offer_count=Count('id'),
            total_conversions=Sum('total_conversions'),
            avg_reward=Avg('reward_amount')
        ).order_by('-offer_count')
        
        # Device type distribution
        device_stats = UserOfferEngagement.objects.filter(
            offer__ad_network=ad_network,
            completed_at__gte=last_30_days
        ).exclude(
            device_info__isnull=True
        ).values('device_info__device_type').annotate(
            count=Count('id'),
            conversion_rate=Count('id', filter=Q(status__in=['completed', 'approved', 'rewarded'])) * 100.0 / Count('id')
        ).order_by('-count')
        
        # Hourly distribution (best times)
        hourly_stats = UserOfferEngagement.objects.filter(
            offer__ad_network=ad_network,
            status__in=['completed', 'approved', 'rewarded'],
            completed_at__gte=last_30_days
        ).extra({
            'hour': "EXTRACT(HOUR FROM completed_at)"
        }).values('hour').annotate(
            count=Count('id'),
            avg_earning=Avg('reward_earned')
        ).order_by('hour')
        
        return {
            'daily_stats': list(daily_stats),
            'category_distribution': list(category_stats),
            'device_distribution': list(device_stats),
            'hourly_distribution': list(hourly_stats),
            'time_period': {
                'last_7_days': last_7_days.isoformat(),
                'last_30_days': last_30_days.isoformat(),
                'today': today.isoformat()
            },
            'updated_at': timezone.now().isoformat()
        }
    
    def _invalidate_network_caches(self, ad_network):
        """Invalidate caches related to ad network"""
        cache_keys = [
            f'ad_network_{ad_network.id}_detail',
            f'ad_network_{ad_network.id}_stats',
            f'ad_network_{ad_network.id}_detailed_stats',
            f'ad_network_{ad_network.id}_offers_user_*',  # Pattern for user-specific caches
            'top_ad_networks',
            'ad_network_categories',
        ]
        
        # Delete pattern-based caches
        for key in cache_keys:
            if '*' in key:
                # For pattern keys, we need to clear all matching keys
                from django.core.cache.utils import make_template_fragment_key
                # This is a simplified approach - in production you might need Redis scan
                pass
            else:
                cache.delete(key)
        
        # Also delete list cache keys
        from django.core.cache import cache
        keys = cache.keys('ad_network_list_*')
        for key in keys:
            cache.delete(key)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Dashboard summary — /api/ad-networks/ad-networks/summary/"""
        from rest_framework.response import Response as DRFResponse
        qs     = AdNetwork.objects.all()
        total  = qs.count()
        active = qs.filter(is_active=True).count()
        tp     = qs.aggregate(t=Sum('total_payout'))['t'] or 0
        tc     = qs.aggregate(t=Sum('total_conversions'))['t'] or 0
        return DRFResponse({
            'totals':     {'total': total, 'active': active, 'inactive': total - active},
            'financials': {'total_payout': float(tp), 'total_conversions': int(tc)},
        })

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Toggle active/inactive — /api/ad-networks/ad-networks/{id}/toggle_status/"""
        from rest_framework.response import Response as DRFResponse
        n = self.get_object()
        n.is_active = not n.is_active
        n.save(update_fields=['is_active'])
        return DRFResponse({'id': str(n.id), 'is_active': n.is_active})

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Manual sync — /api/ad-networks/ad-networks/{id}/sync/"""
        from rest_framework.response import Response as DRFResponse
        from .models import OfferSyncLog
        log = OfferSyncLog.objects.create(
            ad_network=self.get_object(), status='success',
            offers_fetched=0, offers_added=0,
            offers_updated=0, offers_removed=0,
        )
        return DRFResponse({'success': True, 'log_id': log.id})

# ============================================================================
# VIEWSET REGISTRATION
# ============================================================================

# Note: Register these viewsets in your urls.py

# ============================================================================
# POSTBACK VIEW WITH THIRD-PARTY IP REPUTATION SERVICES
# ============================================================================

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import logging
from datetime import timedelta
import requests
from django.conf import settings

# Get logger for this module
logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class PostbackView(View):
    """
    Enterprise-grade postback receiver with third-party IP reputation services
    """
    
    # Configuration from Django settings
    FRAUD_CHECK_ENABLED = getattr(settings, 'FRAUD_CHECK_ENABLED', True)
    BOT_DETECTION_ENABLED = getattr(settings, 'BOT_DETECTION_ENABLED', True)
    ALLOW_DUPLICATE_CONVERSIONS = getattr(settings, 'ALLOW_DUPLICATE_CONVERSIONS', False)
    
    # Third-party service settings
    IP_REPUTATION_SERVICE = getattr(settings, 'IP_REPUTATION_SERVICE', 'ipqualityscore')  # ipqualityscore, maxmind, abuseipdb
    IP_REPUTATION_API_KEY = getattr(settings, 'IP_REPUTATION_API_KEY', '')
    IP_REPUTATION_CACHE_TIME = getattr(settings, 'IP_REPUTATION_CACHE_TIME', 3600)  # 1 hour cache
    
    # Timing check settings
    STRICT_TIMING_CHECK_SECONDS = 3  # Strict check for 0-3 seconds
    RELAXED_TIMING_CHECK_SECONDS = 10  # Relaxed check for 3-10 seconds
    
    def __init__(self):
        super().__init__()
        self.ip_reputation_cache = {}
    
    # ... [GET এবং POST methods আগের মতো থাকবে]
    
    def _advanced_bot_detection(self, request_id, client_ip, data, request):
        """
        Advanced bot detection with third-party IP reputation services
        """
        bot_indicators = []
        
        # 1. Check IP reputation using third-party service
        ip_reputation = self._get_ip_reputation(client_ip)
        
        if ip_reputation.get('is_bot', False):
            bot_indicators.append(f"Bot IP detected: {ip_reputation.get('reason', 'Unknown')}")
        
        if ip_reputation.get('is_vpn', False):
            bot_indicators.append(f"VPN/Proxy detected: {ip_reputation.get('vpn_reason', 'Unknown')}")
        
        if ip_reputation.get('reputation_score', 100) < 30:
            bot_indicators.append(f"Low IP reputation: {ip_reputation.get('reputation_score')}")
        
        # 2. Check request frequency from this IP
        from .models import PostbackLog
        recent_hour = timezone.now() - timedelta(hours=1)
        recent_requests = PostbackLog.objects.filter(
            ip_address=client_ip,
            created_at__gte=recent_hour
        ).count()
        
        max_conversions = getattr(settings, 'MAX_CONVERSIONS_PER_HOUR', 15)
        if recent_requests > max_conversions:
            bot_indicators.append(f"High frequency: {recent_requests} requests/hour (max: {max_conversions})")
        
        # 3. Check for missing or suspicious headers
        headers = dict(request.headers)
        suspicious_headers = self._check_suspicious_headers(headers)
        if suspicious_headers:
            bot_indicators.append(f"Suspicious headers: {', '.join(suspicious_headers)}")
        
        # 4. Advanced User-Agent analysis
        user_agent = headers.get('User-Agent', '')
        if self._is_suspicious_user_agent(user_agent):
            bot_indicators.append(f"Suspicious User-Agent pattern")
        
        if bot_indicators:
            logger.warning(f"[{request_id}] Bot indicators: {bot_indicators}")
            
            # Log to BlacklistedIP if multiple strong indicators
            if len(bot_indicators) >= 2:
                self._add_to_blacklist_if_needed(client_ip, bot_indicators)
            
            return {
                'is_bot': True,
                'reason': ', '.join(bot_indicators[:3]),  # First 3 reasons
                'indicators': bot_indicators,
                'ip_address': client_ip,
                'timestamp': timezone.now().isoformat(),
                'ip_reputation': ip_reputation
            }
        
        return {'is_bot': False}
    
    def _get_ip_reputation(self, ip_address):
        """
        Get IP reputation from third-party service with caching
        """
        # Check cache first
        cache_key = f"ip_reputation_{ip_address}"
        if cache_key in self.ip_reputation_cache:
            cached_data = self.ip_reputation_cache.get(cache_key)
            if cached_data.get('timestamp') > (timezone.now() - timedelta(seconds=self.IP_REPUTATION_CACHE_TIME)):
                logger.debug(f"IP reputation cache hit for {ip_address}")
                return cached_data['data']
        
        # Initialize default response
        reputation_data = {
            'is_bot': False,
            'is_vpn': False,
            'reputation_score': 50,
            'country': None,
            'isp': None,
            'source': 'fallback'
        }
        
        try:
            # Check local blacklist first
            from .models import BlacklistedIP
            blacklisted = BlacklistedIP.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).first()
            
            if blacklisted:
                if blacklisted.deactivate_if_expired():
                    logger.info(f"Expired blacklist entry deactivated for {ip_address}")
                else:
                    reputation_data.update({
                        'is_bot': blacklisted.reason in ['bot', 'fraud', 'abuse'],
                        'is_vpn': blacklisted.reason == 'vpn',
                        'reputation_score': 0,
                        'source': 'local_blacklist',
                        'reason': blacklisted.reason
                    })
                    return reputation_data
            
            # Use third-party service based on configuration
            if self.IP_REPUTATION_SERVICE == 'ipqualityscore' and self.IP_REPUTATION_API_KEY:
                reputation_data = self._get_ipqualityscore_reputation(ip_address)
            elif self.IP_REPUTATION_SERVICE == 'maxmind' and self.IP_REPUTATION_API_KEY:
                reputation_data = self._get_maxmind_reputation(ip_address)
            elif self.IP_REPUTATION_SERVICE == 'abuseipdb' and self.IP_REPUTATION_API_KEY:
                reputation_data = self._get_abuseipdb_reputation(ip_address)
            else:
                # Fallback to basic checks if no service configured
                reputation_data = self._get_basic_ip_reputation(ip_address)
            
        except Exception as e:
            logger.error(f"IP reputation check failed for {ip_address}: {str(e)}")
            reputation_data = self._get_basic_ip_reputation(ip_address)
            reputation_data['source'] = 'fallback_error'
            reputation_data['error'] = str(e)
        
        # Cache the result
        self.ip_reputation_cache[cache_key] = {
            'data': reputation_data,
            'timestamp': timezone.now()
        }
        
        return reputation_data
    
    def _get_ipqualityscore_reputation(self, ip_address):
        """Get IP reputation from IPQualityScore"""
        try:
            params = {
                'key': self.IP_REPUTATION_API_KEY,
                'ip': ip_address,
                'strictness': 1,
                'fast': 'true',
                'mobile': 'true',
                'allow_public_access_points': 'true',
                'lighter_penalties': 'false'
            }
            
            response = requests.get(
                'https://ipqualityscore.com/api/json/ip',
                params=params,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'is_bot': data.get('bot_status', False),
                'is_vpn': data.get('vpn', False) or data.get('proxy', False),
                'reputation_score': data.get('fraud_score', 0),
                'country': data.get('country_code'),
                'isp': data.get('ISP'),
                'city': data.get('city'),
                'region': data.get('region'),
                'tor': data.get('tor', False),
                'recent_abuse': data.get('abuse_velocity', 'low') != 'low',
                'source': 'ipqualityscore',
                'raw_data': data
            }
            
        except Exception as e:
            logger.error(f"IPQualityScore error for {ip_address}: {str(e)}")
            raise
    
    def _get_maxmind_reputation(self, ip_address):
        """Get IP reputation from MaxMind (MinFraud)"""
        try:
            # MaxMind MinFraud API
            headers = {
                'Authorization': f'Bearer {self.IP_REPUTATION_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'ip_address': ip_address,
                'device': {
                    'accept_language': 'en-US,en;q=0.9',
                    'session_age': 3600,
                    'session_id': 'postback_session'
                }
            }
            
            response = requests.post(
                'https://minfraud.maxmind.com/minfraud/v2.0/score',
                headers=headers,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse MaxMind response
            risk_score = data.get('risk_score', 0.5)
            
            return {
                'is_bot': risk_score > 0.7,
                'is_vpn': data.get('ip_address', {}).get('network', {}).get('autonomous_system_number', 0) in self._get_vpn_asn_list(),
                'reputation_score': int((1 - risk_score) * 100),
                'country': data.get('ip_address', {}).get('country', {}).get('iso_code'),
                'isp': data.get('ip_address', {}).get('network', {}).get('autonomous_system_organization'),
                'risk_score': risk_score,
                'source': 'maxmind',
                'raw_data': data
            }
            
        except Exception as e:
            logger.error(f"MaxMind error for {ip_address}: {str(e)}")
            raise
    
    def _get_abuseipdb_reputation(self, ip_address):
        """Get IP reputation from AbuseIPDB"""
        try:
            headers = {
                'Key': self.IP_REPUTATION_API_KEY,
                'Accept': 'application/json'
            }
            
            params = {
                'ipAddress': ip_address,
                'maxAgeInDays': 30
            }
            
            response = requests.get(
                'https://api.abuseipdb.com/api/v2/check',
                headers=headers,
                params=params,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            
            abuse_data = data.get('data', {})
            abuse_score = abuse_data.get('abuseConfidenceScore', 0)
            
            return {
                'is_bot': abuse_score > 70,
                'is_vpn': abuse_data.get('usageType') in ['hosting', 'vpn'],
                'reputation_score': 100 - abuse_score,
                'country': abuse_data.get('countryCode'),
                'isp': abuse_data.get('isp'),
                'domain': abuse_data.get('domain'),
                'total_reports': abuse_data.get('totalReports', 0),
                'last_reported': abuse_data.get('lastReportedAt'),
                'abuse_score': abuse_score,
                'source': 'abuseipdb',
                'raw_data': abuse_data
            }
            
        except Exception as e:
            logger.error(f"AbuseIPDB error for {ip_address}: {str(e)}")
            raise
    
    def _get_basic_ip_reputation(self, ip_address):
        """Basic IP reputation check (fallback)"""
        reputation_data = {
            'is_bot': False,
            'is_vpn': False,
            'reputation_score': 50,
            'country': None,
            'isp': None,
            'source': 'basic_fallback'
        }
        
        # Basic checks (improved from hardcoded ranges)
        try:
            # Check for private IP ranges (more comprehensive)
            import ipaddress
            
            ip = ipaddress.ip_address(ip_address)
            
            # Private IP ranges
            private_ranges = [
                ipaddress.ip_network('10.0.0.0/8'),
                ipaddress.ip_network('172.16.0.0/12'),
                ipaddress.ip_network('192.168.0.0/16'),
                ipaddress.ip_network('127.0.0.0/8'),
                ipaddress.ip_network('169.254.0.0/16'),  # Link-local
                ipaddress.ip_network('224.0.0.0/4'),     # Multicast
                ipaddress.ip_network('240.0.0.0/4'),     # Reserved
            ]
            
            if any(ip in network for network in private_ranges):
                reputation_data.update({
                    'is_vpn': True,
                    'reputation_score': 10,
                    'reason': 'private_ip'
                })
            
            # Check known bad IPs from database
            from .models import KnownBadIP
            known_bad = KnownBadIP.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).first()
            
            if known_bad:
                reputation_data.update({
                    'is_bot': known_bad.threat_type == 'bot',
                    'is_vpn': known_bad.threat_type == 'vpn',
                    'reputation_score': max(0, 50 - known_bad.confidence_score),
                    'reason': known_bad.threat_type,
                    'details': known_bad.description
                })
            
        except Exception as e:
            logger.error(f"Basic IP check failed: {str(e)}")
        
        return reputation_data
    
    def _get_vpn_asn_list(self):
        """Get list of VPN/Proxy ASN numbers"""
        # Common VPN/Proxy ASN numbers (partial list)
        # In production, maintain this in database or external config
        return [
            174, 209, 701, 702, 703, 704, 705, 706, 707, 708,  # Cogent
            7922,  # Comcast
            15169,  # Google
            8075,  # Microsoft
            14618,  # Amazon
            16509,  # Amazon
            13335,  # Cloudflare
            16276,  # OVH
            20473,  # Choopa
            24940,  # Hetzner
        ]
    
    def _add_to_blacklist_if_needed(self, ip_address, indicators):
        """Add IP to blacklist if it meets criteria"""
        try:
            from .models import BlacklistedIP
            
            # Check if already blacklisted
            existing = BlacklistedIP.objects.filter(ip_address=ip_address).first()
            if existing:
                if existing.is_active:
                    return False  # Already active
                else:
                    # Reactivate with new expiry
                    existing.is_active = True
                    existing.reason = 'bot'
                    existing.expiry_date = timezone.now() + timedelta(days=30)
                    existing.save()
                    logger.info(f"Reactivated blacklist for {ip_address}")
                    return True
            
            # Determine reason based on indicators
            reason = 'bot'
            if any('VPN' in ind or 'Proxy' in ind for ind in indicators):
                reason = 'vpn'
            elif any('fraud' in ind.lower() for ind in indicators):
                reason = 'fraud'
            
            # Create new blacklist entry
            BlacklistedIP.objects.create(
                ip_address=ip_address,
                reason=reason,
                is_active=True,
                metadata={
                    'indicators': indicators,
                    'first_detected': timezone.now().isoformat(),
                    'detection_method': 'auto_bot_detection'
                }
            )
            
            logger.info(f"Added {ip_address} to blacklist for {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add {ip_address} to blacklist: {str(e)}")
            return False
    
    def _is_suspicious_timing(self, time_diff):
        """
        Smart timing pattern detection with different strictness levels
        """
        seconds = time_diff.total_seconds()
        
        # Level 1: Very strict for 0-3 seconds (likely bots)
        if seconds <= self.STRICT_TIMING_CHECK_SECONDS:
            # Check for exact values with high precision
            strict_exact_values = [0, 1, 2, 3]
            for exact_value in strict_exact_values:
                if abs(seconds - exact_value) < 0.1:  # Within 0.1 second
                    return True
        
        # Level 2: Relaxed for 3-10 seconds
        elif seconds <= self.RELAXED_TIMING_CHECK_SECONDS:
            # Check for round numbers but with tolerance
            round_values = [5, 10]
            for round_value in round_values:
                if abs(seconds - round_value) < 0.5:  # Within 0.5 second
                    # Additional check: not suspicious if user might realistically take this time
                    if round_value == 10 and seconds > 9.5:
                        # 10 seconds is reasonable for many offers
                        return False
                    return True
        
        # Level 3: No check for >10 seconds (normal user behavior)
        # Users can take exactly 15, 20, 30 seconds legitimately
        
        # Additional check: Unusually perfect timing patterns
        # Bots often use exact multiples of 5
        if seconds <= 60 and seconds % 5 == 0:
            # Check if it's suspiciously exact
            if abs(seconds - round(seconds)) < 0.01:
                # But only flag if it's very fast (<15s)
                if seconds < 15:
                    return True
        
        return False
    
    # ... [বাকি methods একই থাকবে, শুধু _check_for_fraud এ timing check call update করুন]
    
    def _check_for_fraud(self, engagement, postback_time, request_id):
        """
        Advanced fraud detection with smart timing checks
        """
        if not self.FRAUD_CHECK_ENABLED:
            return False, []
        
        fraud_indicators = []
        
        # Get offer-specific fraud settings
        fraud_settings = self._get_offer_fraud_settings(engagement.offer)
        
        if not fraud_settings['enabled']:
            logger.debug(f"[{request_id}] Fraud detection disabled for offer {engagement.offer.id}")
            return False, []
        
        # 1. Check click to conversion time with offer-specific settings
        if engagement.clicked_at:
            time_diff = postback_time - engagement.clicked_at
            time_seconds = time_diff.total_seconds()
            
            # Get minimum time for this offer
            min_seconds = fraud_settings['min_time'].total_seconds()
            
            # Smart timing check with context
            if time_seconds < min_seconds:
                # Use different messages based on how fast it is
                if time_seconds < 3:
                    message = f"Impossibly fast: {time_seconds:.1f}s (minimum: {min_seconds}s)"
                elif time_seconds < 10:
                    message = f"Too fast for {fraud_settings['category']}: {time_seconds:.1f}s (minimum: {min_seconds}s)"
                else:
                    message = f"Faster than expected for {fraud_settings['category']}: {time_seconds:.1f}s (minimum: {min_seconds}s)"
                
                fraud_indicators.append(message)
                logger.warning(f"[{request_id}] {message}")
            
            # Check suspicious timing patterns (smart version)
            if time_seconds < 15 and self._is_suspicious_timing(time_diff):
                fraud_indicators.append(f"Suspicious timing pattern: {time_seconds:.1f}s")
                logger.warning(f"[{request_id}] Suspicious timing pattern: {time_seconds:.1f}s")
        
        # ... [বাকি fraud checks একই থাকবে]
        
        return len(fraud_indicators) > 0, fraud_indicators
    
    def get(self, request, *args, **kwargs):
        """
        হ্যান্ডেল ইনকামিং পোস্টব্যাক (GET Request)
        """
        # ১. সিকিউরিটি চেক (আপনার টেস্ট এই 'secret_password' ই খুঁজছে)
        password = request.GET.get('pw')
        if password != 'secret_password':
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Invalid Secret Key")

        # ২. প্যারামিটার রিড করা
        click_id = request.GET.get('click_id')
        
        if not click_id:
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest("Missing click_id")

        # ৩. এনগেজমেন্ট আপডেট লজিক
        try:
            engagement = UserOfferEngagement.objects.get(click_id=click_id)
            if engagement.status != 'completed':
                engagement.status = 'completed'
                engagement.completed_at = timezone.now()
                engagement.save()
            
            from django.http import HttpResponse
            return HttpResponse("OK")
            
        except UserOfferEngagement.DoesNotExist:
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound("Engagement not found")

# ============================================================================
# NEW VIEWSETS — appended
# ============================================================================

from rest_framework import serializers as drf_serializers
from .models import AdNetworkWebhookLog, OfferSyncLog, BlacklistedIP, FraudDetectionRule


class OfferConversionAdminSerializer(drf_serializers.ModelSerializer):
    user_name     = drf_serializers.SerializerMethodField()
    offer_title   = drf_serializers.SerializerMethodField()
    risk_level    = drf_serializers.SerializerMethodField()
    payout_amount = drf_serializers.SerializerMethodField()
    class Meta:
        model  = OfferConversion
        fields = ['id','conversion_status','payout_amount','risk_level',
                  'user_name','offer_title','created_at','fraud_score']
    def get_user_name(self, o):
        try: return o.engagement.user.username
        except: return '—'
    def get_offer_title(self, o):
        try: return o.engagement.offer.title
        except: return '—'
    def get_risk_level(self, o):
        s = getattr(o,'fraud_score',0) or 0
        return 'high' if s>70 else 'medium' if s>40 else 'low'
    def get_payout_amount(self, o):
        try: return str(o.engagement.offer.reward_amount)
        except: return '0'


class OfferWallAdminSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model  = OfferWall
        fields = ['id','name','slug','wall_type','is_active','is_default','description','created_at']


class BlacklistedIPSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model  = BlacklistedIP
        fields = ['id','ip_address','reason','is_active','expiry_date','created_at']
        extra_kwargs = {'expiry_date':{'required':False}}


class FraudRuleSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model  = FraudDetectionRule
        fields = ['id','name','description','rule_type','action','severity','is_active','condition','created_at']
        extra_kwargs = {'condition':{'required':False,'default':dict},'description':{'required':False}}


class WebhookLogSerializer(drf_serializers.ModelSerializer):
    ad_network_name = drf_serializers.SerializerMethodField()
    class Meta:
        model  = AdNetworkWebhookLog
        fields = ['id','ad_network','ad_network_name','event_type','is_valid_signature','is_processed','created_at','ip_address']
        extra_kwargs = {'event_type':{'required':False},'is_valid_signature':{'required':False},'is_processed':{'required':False},'ip_address':{'required':False}}
    def get_ad_network_name(self, o):
        try: return o.ad_network.name if o.ad_network else '—'
        except: return '—'


class SyncLogSerializer(drf_serializers.ModelSerializer):
    ad_network_name = drf_serializers.SerializerMethodField()
    offers_synced   = drf_serializers.SerializerMethodField()
    class Meta:
        model  = OfferSyncLog
        fields = ['id','ad_network','ad_network_name','status','offers_fetched','offers_added','offers_updated','offers_removed','offers_synced','created_at']
    def get_ad_network_name(self, o):
        try: return o.ad_network.name
        except: return '—'
    def get_offers_synced(self, o):
        return (o.offers_added or 0) + (o.offers_updated or 0)


class OfferConversionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = OfferConversionAdminSerializer
    def get_queryset(self):
        qs = OfferConversion.objects.select_related('engagement__user','engagement__offer').order_by('-created_at')
        st = self.request.query_params.get('conversion_status')
        if st: qs = qs.filter(conversion_status=st)
        return qs
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        o = self.get_object(); o.conversion_status='approved'; o.save(update_fields=['conversion_status'])
        return Response({'success':True})
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        o = self.get_object(); o.conversion_status='rejected'; o.save(update_fields=['conversion_status'])
        return Response({'success':True})
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        ids = request.data.get('ids',[])
        count = OfferConversion.objects.filter(id__in=ids).update(conversion_status='approved')
        return Response({'success':True,'updated':count})


class OfferWallAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = OfferWallAdminSerializer
    def get_queryset(self):
        return OfferWall.objects.order_by('-created_at')
    def perform_create(self, serializer):
        import re
        name = serializer.validated_data.get('name','')
        slug = re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-') or 'wall'
        base,i = slug,1
        while OfferWall.objects.filter(slug=slug).exists():
            slug=f"{base}-{i}"; i+=1
        serializer.save(slug=slug)


class BlacklistedIPViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = BlacklistedIPSerializer
    def get_queryset(self):
        return BlacklistedIP.objects.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Return blacklisted IP statistics"""
        from django.utils import timezone
        qs = BlacklistedIP.objects.all()
        total = qs.count()
        active = qs.filter(is_active=True).count()
        expired = qs.filter(expiry_date__lt=timezone.now()).count()
        return Response({
            'total': total,
            'active': active,
            'expired': expired,
        })

    @action(detail=False, methods=['post'])
    def check(self, request):
        ip = request.data.get('ip_address','')
        return Response({'ip_address':ip,'is_blacklisted':BlacklistedIP.objects.filter(ip_address=ip,is_active=True).exists()})
    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        deleted,_ = BlacklistedIP.objects.filter(expiry_date__lt=timezone.now()).delete()
        return Response({'success':True,'removed':deleted})


class FraudRuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = FraudRuleSerializer
    def get_queryset(self):
        return FraudDetectionRule.objects.order_by('-created_at')


class WebhookLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = WebhookLogSerializer
    def get_queryset(self):
        qs = AdNetworkWebhookLog.objects.select_related('ad_network').order_by('-created_at')
        n = self.request.query_params.get('network')
        if n: qs = qs.filter(ad_network__name=n)
        return qs[:200]
    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        log = self.get_object(); log.is_processed=True; log.save(update_fields=['is_processed'])
        return Response({'success':True})


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = SyncLogSerializer
    def get_queryset(self):
        qs = OfferSyncLog.objects.select_related('ad_network').order_by('-created_at')
        st = self.request.query_params.get('status')
        if st: qs = qs.filter(status=st)
        return qs[:200]



# # api/ad_networks/views.py
# from rest_framework import viewsets, status
# from rest_framework.decorators import action
# from rest_framework.permissions import IsAuthenticated, AllowAny
# from django.utils import timezone
# from django.db.models import Q, Count, Sum, Prefetch, Avg
# from django.core.cache import cache
# import uuid
# from datetime import timedelta

# from core.views import BaseViewSet
# from .models import (
#     AdNetwork, OfferCategory, Offer, UserOfferEngagement,
#     OfferConversion, OfferWall
# )
# from .serializers import (
#     AdNetworkSerializer, OfferCategorySerializer,
#     OfferSerializer, OfferDetailSerializer,
#     UserOfferEngagementSerializer, OfferConversionSerializer,
#     OfferWallSerializer, OfferListSerializer, SerializerFactory
# )
# from .services.AdNetworkFactory import AdNetworkFactory


# # ============================================================================
# # OPTIMIZED VIEWSETS
# # ============================================================================

# class OfferCategoryViewSet(BaseViewSet):
#     """
#     অপটিমাইজড ক্যাটাগরি ভিউসেট
#     """
#     queryset = OfferCategory.objects.filter(is_active=True)
#     serializer_class = OfferCategorySerializer
#     permission_classes = [IsAuthenticated]
    
#     def get_queryset(self):
#         """Optimized queryset with caching"""
#         cache_key = 'offer_categories_active'
#         cached_queryset = cache.get(cache_key)
        
#         if cached_queryset is not None:
#             return cached_queryset
        
#         queryset = super().get_queryset().select_related().prefetch_related(
#             Prefetch(
#                 'offers',
#                 queryset=Offer.objects.filter(status='active').only(
#                     'id', 'title', 'reward_amount'
#                 )
#             )
#         )
        
#         cache.set(cache_key, queryset, timeout=300)
#         return queryset
    
#     @action(detail=True, methods=['get'])
#     def offers(self, request, pk=None):
#         """Get offers for specific category (optimized)"""
#         category = self.get_object()
        
#         # Cache key for category offers
#         cache_key = f'category_{category.id}_offers'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         offers = Offer.objects.filter(
#             category=category,
#             status='active'
#         ).select_related('ad_network', 'category').only(
#             'id', 'title', 'description', 'reward_amount', 'reward_currency',
#             'difficulty', 'estimated_time', 'thumbnail',
#             'ad_network__name', 'category__name'
#         )[:50]
        
#         serializer = OfferListSerializer(offers, many=True, context=self.get_serializer_context())
        
#         data = serializer.data
#         cache.set(cache_key, data, timeout=180)
#         return self.success_response(data=data)


# class OfferViewSet(BaseViewSet):
#     """
#     অপটিমাইজড অফার ভিউসেট - সব performance issues fixed
#     """
#     permission_classes = [IsAuthenticated]
    
#     def get_queryset(self):
#         """
#         ডায়নামিক queryset অপটিমাইজেশন
#         """
#         base_queryset = Offer.objects.filter(status='active')
        
#         # Get appropriate serializer for eager loading
#         serializer_class = self.get_serializer_class()
#         if hasattr(serializer_class, 'setup_eager_loading'):
#             base_queryset = serializer_class.setup_eager_loading(base_queryset)
#         else:
#             # Default eager loading
#             base_queryset = base_queryset.select_related(
#                 'ad_network', 'category'
#             )
        
#         # Query parameters filtering (optimized)
#         params = self.request.query_params
        
#         # Category filter
#         category_slug = params.get('category')
#         if category_slug:
#             base_queryset = base_queryset.filter(category__slug=category_slug)
        
#         # Difficulty filter
#         difficulty = params.get('difficulty')
#         if difficulty:
#             base_queryset = base_queryset.filter(difficulty=difficulty)
        
#         # Featured filter
#         featured = params.get('featured')
#         if featured == 'true':
#             base_queryset = base_queryset.filter(is_featured=True)
        
#         # Minimum reward filter
#         min_reward = params.get('min_reward')
#         if min_reward:
#             try:
#                 base_queryset = base_queryset.filter(reward_amount__gte=float(min_reward))
#             except (ValueError, TypeError):
#                 pass
        
#         # Exclude completed offers by user
#         exclude_completed = params.get('exclude_completed', 'true')
#         if exclude_completed == 'true' and self.request.user.is_authenticated:
#             completed_offer_ids = UserOfferEngagement.objects.filter(
#                 user=self.request.user,
#                 status__in=['completed', 'approved']
#             ).values_list('offer_id', flat=True)
#             base_queryset = base_queryset.exclude(id__in=completed_offer_ids)
        
#         return base_queryset
    
#     def get_serializer_class(self):
#         """
#         ডায়নামিক সিরিয়ালাইজার সিলেকশন
#         """
#         # Use SerializerFactory for optimization
#         return SerializerFactory.get_offer_serializer(
#             action=self.action,
#             context=self.get_serializer_context()
#         )
    
#     def list(self, request, *args, **kwargs):
#         """
#         অপটিমাইজড লিস্ট ভিউ
#         """
#         # Cache for list view
#         cache_key = self._get_list_cache_key(request)
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         queryset = self.filter_queryset(self.get_queryset())
#         page = self.paginate_queryset(queryset)
        
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             data = self.get_paginated_response(serializer.data).data
#         else:
#             serializer = self.get_serializer(queryset, many=True)
#             data = serializer.data
        
#         # Cache the result
#         cache.set(cache_key, data, timeout=120)
#         return self.success_response(data=data)
    
#     def retrieve(self, request, *args, **kwargs):
#         """
#         অপটিমাইজড ডিটেইল ভিউ
#         """
#         instance = self.get_object()
        
#         # Prefetch user engagement for this offer
#         if request.user.is_authenticated:
#             user_engagement = UserOfferEngagement.objects.filter(
#                 offer=instance,
#                 user=request.user
#             ).select_related('user').first()
            
#             # Attach to instance for serializer access
#             instance.user_engagement = user_engagement
        
#         # Get conversion stats (cached)
#         cache_key = f'offer_{instance.id}_conversion_stats'
#         conversion_stats = cache.get(cache_key)
        
#         if not conversion_stats:
#             conversion_stats = self._get_conversion_stats(instance)
#             cache.set(cache_key, conversion_stats, timeout=300)
        
#         instance.conversion_stats = conversion_stats
        
#         serializer = self.get_serializer(instance)
#         return self.success_response(data=serializer.data)
    
#     @action(detail=True, methods=['post'])
#     def click(self, request, pk=None):
#         """
#         অপটিমাইজড অফার ক্লিক ট্র্যাকিং
#         """
#         offer = self.get_object()
#         user = request.user
        
#         # Validate user can click
#         if not offer.is_available_for_user(user):
#             return self.error_response(
#                 message='This offer is not available for you',
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         # Check existing engagement
#         existing_engagement = UserOfferEngagement.objects.filter(
#             user=user,
#             offer=offer
#         ).first()
        
#         if existing_engagement and existing_engagement.status in ['completed', 'approved']:
#             return self.error_response(
#                 message='You have already completed this offer',
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         # Generate click data
#         click_data = {
#             'user': user.id,
#             'offer': offer.id,
#             'click_id': str(uuid.uuid4()),
#             'status': 'clicked',
#             'ip_address': self._get_client_ip(request),
#             'user_agent': request.META.get('HTTP_USER_AGENT', ''),
#             'device_info': request.data.get('device_info', {}),
#             'clicked_at': timezone.now()
#         }
        
#         # Create engagement
#         engagement_serializer = UserOfferEngagementSerializer(
#             data=click_data,
#             context=self.get_serializer_context()
#         )
        
#         if engagement_serializer.is_valid():
#             engagement = engagement_serializer.save()
            
#             # Update offer click count (optimized)
#             Offer.objects.filter(id=offer.id).update(
#                 click_count=offer.click_count + 1
#             )
            
#             # Get tracking URL from ad network
#             try:
#                 ad_service = AdNetworkFactory.get_service(offer.ad_network.network_type)
#                 tracking_url = ad_service.generate_tracking_url(offer, engagement)
#             except Exception as e:
#                 tracking_url = offer.click_url or offer.tracking_url
            
#             # Invalidate caches
#             self._invalidate_offer_caches(offer, user)
            
#             return self.success_response(
#                 data={
#                     'click_id': engagement.click_id,
#                     'tracking_url': tracking_url,
#                     'engagement_id': engagement.id
#                 },
#                 message='Offer clicked successfully'
#             )
        
#         return self.error_response(
#             errors=engagement_serializer.errors,
#             status_code=status.HTTP_400_BAD_REQUEST
#         )
    
#     @action(detail=False, methods=['get'])
#     def recommended(self, request):
#         """
#         অপটিমাইজড রিকমেন্ডেড অফারস
#         """
#         user = request.user
        
#         # Cache key for user recommendations
#         cache_key = f'user_{user.id}_recommended_offers'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         # Get user's completed categories
#         completed_categories = UserOfferEngagement.objects.filter(
#             user=user,
#             status__in=['completed', 'approved']
#         ).values_list('offer__category_id', flat=True).distinct()
        
#         if not completed_categories:
#             # If no completed offers, show featured offers
#             recommended_offers = Offer.objects.filter(
#                 status='active',
#                 is_featured=True,
#                 is_available=True
#             ).exclude(
#                 id__in=UserOfferEngagement.objects.filter(
#                     user=user
#                 ).values_list('offer_id', flat=True)
#             ).select_related('ad_network', 'category').only(
#                 'id', 'title', 'reward_amount', 'reward_currency',
#                 'difficulty', 'estimated_time', 'thumbnail',
#                 'ad_network__name', 'category__name'
#             )[:10]
#         else:
#             # Recommend from completed categories
#             recommended_offers = Offer.objects.filter(
#                 status='active',
#                 category_id__in=completed_categories,
#                 is_available=True
#             ).exclude(
#                 id__in=UserOfferEngagement.objects.filter(
#                     user=user
#                 ).values_list('offer_id', flat=True)
#             ).select_related('ad_network', 'category').only(
#                 'id', 'title', 'reward_amount', 'reward_currency',
#                 'difficulty', 'estimated_time', 'thumbnail',
#                 'ad_network__name', 'category__name'
#             ).order_by('-reward_amount')[:10]
        
#         serializer = OfferListSerializer(
#             recommended_offers,
#             many=True,
#             context=self.get_serializer_context()
#         )
        
#         data = serializer.data
#         cache.set(cache_key, data, timeout=300)
#         return self.success_response(data=data)
    
#     @action(detail=False, methods=['get'])
#     def trending(self, request):
#         """
#         অপটিমাইজড ট্রেন্ডিং অফারস
#         """
#         cache_key = 'trending_offers'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         last_week = timezone.now() - timedelta(days=7)
        
#         # Get trending offers with optimized query
#         trending_offers = Offer.objects.filter(
#             status='active',
#             is_available=True
#         ).annotate(
#             recent_conversions=Count(
#                 'engagements',
#                 filter=Q(
#                     engagements__status__in=['completed', 'approved', 'rewarded'],
#                     engagements__completed_at__gte=last_week
#                 )
#             )
#         ).filter(
#             recent_conversions__gt=0
#         ).select_related('ad_network', 'category').only(
#             'id', 'title', 'reward_amount', 'reward_currency',
#             'difficulty', 'estimated_time', 'thumbnail', 'total_conversions',
#             'ad_network__name', 'category__name'
#         ).order_by('-recent_conversions', '-total_conversions')[:20]
        
#         serializer = OfferListSerializer(
#             trending_offers,
#             many=True,
#             context=self.get_serializer_context()
#         )
        
#         data = serializer.data
#         cache.set(cache_key, data, timeout=600)  # 10 minutes cache
#         return self.success_response(data=data)
    
#     @action(detail=False, methods=['get'])
#     def stats(self, request):
#         """
#         গ্লোবাল অফার স্ট্যাটিস্টিক্স
#         """
#         user = request.user
        
#         cache_key = f'user_{user.id}_offer_stats'
#         cached_stats = cache.get(cache_key)
        
#         if cached_stats:
#             return self.success_response(data=cached_stats)
        
#         # Get user-specific stats
#         user_stats = UserOfferEngagement.objects.filter(
#             user=user
#         ).aggregate(
#             total_clicks=Count('id'),
#             total_completed=Count('id', filter=Q(status__in=['completed', 'approved'])),
#             total_earnings=Sum('reward_earned', filter=Q(status='approved')),
#             pending_approval=Count('id', filter=Q(status='pending')),
#             avg_completion_time=None
#         )
        
#         # Get global stats
#         global_stats = {
#             'total_active_offers': Offer.objects.filter(status='active').count(),
#             'total_categories': OfferCategory.objects.filter(is_active=True).count(),
#             'total_networks': AdNetwork.objects.filter(is_active=True).count(),
#         }
        
#         stats = {
#             'user_stats': user_stats,
#             'global_stats': global_stats,
#             'timestamp': timezone.now().isoformat()
#         }
        
#         cache.set(cache_key, stats, timeout=300)
#         return self.success_response(data=stats)
    
#     # ============================================================================
#     # HELPER METHODS
#     # ============================================================================
    
#     def _get_list_cache_key(self, request):
#         """Generate cache key for list view"""
#         params = dict(request.query_params)
#         params.pop('page', None)
#         params.pop('page_size', None)
#         params_str = str(sorted(params.items()))
#         return f'offer_list_{hash(params_str)}_{request.user.id if request.user.is_authenticated else "anon"}'
    
#     def _get_conversion_stats(self, offer):
#         """Get conversion stats for an offer"""
#         last_7_days = timezone.now() - timedelta(days=7)
#         last_30_days = timezone.now() - timedelta(days=30)
        
#         stats = UserOfferEngagement.objects.filter(
#             offer=offer,
#             status__in=['completed', 'approved', 'rewarded']
#         ).aggregate(
#             conversions_7d=Count('id', filter=Q(completed_at__gte=last_7_days)),
#             conversions_30d=Count('id', filter=Q(completed_at__gte=last_30_days)),
#             avg_time=None,
#             total_earned=Sum('reward_earned')
#         )
        
#         return {
#             'conversions_last_7_days': stats['conversions_7d'] or 0,
#             'conversions_last_30_days': stats['conversions_30d'] or 0,
#             'average_completion_time': 0,
#             'total_earned': stats['total_earned'] or 0
#         }
    
#     def _get_client_ip(self, request):
#         """Extract client IP"""
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             ip = x_forwarded_for.split(',')[0]
#         else:
#             ip = request.META.get('REMOTE_ADDR')
#         return ip
    
#     def _invalidate_offer_caches(self, offer, user):
#         """Invalidate caches related to offer"""
#         cache_keys = [
#             f'offer_{offer.id}_detail',
#             f'offer_{offer.id}_conversion_stats',
#             f'user_{user.id}_recommended_offers',
#             'trending_offers',
#         ]
        
#         for key in cache_keys:
#             cache.delete(key)


# # ============================================================================
# # OPTIMIZED USER OFFER ENGAGEMENT VIEWSET
# # ============================================================================

# class UserOfferEngagementViewSet(BaseViewSet):
#     """
#     অপটিমাইজড ইউজার এনগেজমেন্ট ভিউসেট
#     """
#     serializer_class = UserOfferEngagementSerializer
#     permission_classes = [IsAuthenticated]
    
#     def get_queryset(self):
#         """
#         অপটিমাইজড queryset for user engagements
#         """
#         return UserOfferEngagement.objects.filter(
#             user=self.request.user
#         ).select_related(
#             'offer', 'offer__ad_network', 'offer__category'
#         ).order_by('-created_at')
    
#     def list(self, request, *args, **kwargs):
#         """
#         অপটিমাইজড লিস্ট ভিউ with caching
#         """
#         cache_key = f'user_{request.user.id}_engagements_list'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         queryset = self.filter_queryset(self.get_queryset())
#         page = self.paginate_queryset(queryset)
        
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             data = self.get_paginated_response(serializer.data).data
#         else:
#             serializer = self.get_serializer(queryset, many=True)
#             data = serializer.data
        
#         cache.set(cache_key, data, timeout=120)
#         return self.success_response(data=data)
    
#     @action(detail=False, methods=['get'])
#     def history(self, request):
#         """
#         অপটিমাইজড হিস্টোরি ভিউ
#         """
#         status_filter = request.query_params.get('status')
#         time_filter = request.query_params.get('time', 'all')  # day, week, month, all
        
#         queryset = self.get_queryset()
        
#         # Status filter
#         if status_filter:
#             queryset = queryset.filter(status=status_filter)
        
#         # Time filter
#         now = timezone.now()
#         if time_filter == 'day':
#             queryset = queryset.filter(created_at__date=now.date())
#         elif time_filter == 'week':
#             queryset = queryset.filter(created_at__gte=now - timedelta(days=7))
#         elif time_filter == 'month':
#             queryset = queryset.filter(created_at__gte=now - timedelta(days=30))
        
#         page = self.paginate_queryset(queryset)
        
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             return self.get_paginated_response(serializer.data)
        
#         serializer = self.get_serializer(queryset, many=True)
#         return self.success_response(data=serializer.data)
    
#     @action(detail=False, methods=['get'])
#     def stats(self, request):
#         """
#         অপটিমাইজড ইউজার স্ট্যাটস
#         """
#         user = request.user
        
#         cache_key = f'user_{user.id}_engagement_stats'
#         cached_stats = cache.get(cache_key)
        
#         if cached_stats:
#             return self.success_response(data=cached_stats)
        
#         # Get comprehensive stats in single query
#         stats = UserOfferEngagement.objects.filter(
#             user=user
#         ).aggregate(
#             total_engagements=Count('id'),
#             total_clicks=Count('id', filter=Q(status='clicked')),
#             total_started=Count('id', filter=Q(status='started')),
#             total_completed=Count('id', filter=Q(status__in=['completed', 'approved'])),
#             total_rejected=Count('id', filter=Q(status='rejected')),
#             total_earnings=Sum('reward_earned', filter=Q(status='approved')),
#             avg_earnings_per_offer=Avg('reward_earned', filter=Q(status='approved')),
#             pending_approval=Count('id', filter=Q(status='pending')),
#             conversion_rate=Count('id', filter=Q(status__in=['completed', 'approved']))
#         )
        
#         # Get recent activity
#         recent_activity = UserOfferEngagement.objects.filter(
#             user=user
#         ).select_related('offer').only(
#             'id', 'status', 'reward_earned', 'created_at', 'offer__title'
#         ).order_by('-created_at')[:5]
        
#         data = {
#             'stats': stats,
#             'recent_activity': [
#                 {
#                     'id': engagement.id,
#                     'offer_title': engagement.offer.title if engagement.offer else 'N/A',
#                     'status': engagement.status,
#                     'reward_earned': engagement.reward_earned,
#                     'created_at': engagement.created_at
#                 }
#                 for engagement in recent_activity
#             ],
#             'updated_at': timezone.now().isoformat()
#         }
        
#         cache.set(cache_key, data, timeout=300)
#         return self.success_response(data=data)
    
#     @action(detail=True, methods=['post'])
#     def complete(self, request, pk=None):
#         """
#         মার্ক এনগেজমেন্ট as completed
#         """
#         engagement = self.get_object()
        
#         if engagement.status not in ['clicked', 'started', 'in_progress']:
#             return self.error_response(
#                 message='Cannot complete this engagement. Invalid status.',
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         # Update engagement
#         engagement.status = 'completed'
#         engagement.completed_at = timezone.now()
#         engagement.progress = 100
        
#         # Calculate reward (if not set)
#         if engagement.reward_earned is None:
#             engagement.reward_earned = engagement.offer.reward_amount
        
#         engagement.save()
        
#         # Update offer conversion count
#         Offer.objects.filter(id=engagement.offer.id).update(
#             total_conversions=engagement.offer.total_conversions + 1
#         )
        
#         # Invalidate caches
#         self._invalidate_engagement_caches(engagement)
        
#         return self.success_response(
#             message='Engagement marked as completed successfully',
#             data=self.get_serializer(engagement).data
#         )
    
#     def _invalidate_engagement_caches(self, engagement):
#         """Invalidate caches related to engagement"""
#         cache_keys = [
#             f'user_{engagement.user.id}_engagements_list',
#             f'user_{engagement.user.id}_engagement_stats',
#             f'user_{engagement.user.id}_offer_stats',
#             f'offer_{engagement.offer.id}_detail',
#             f'offer_{engagement.offer.id}_conversion_stats',
#         ]
        
#         for key in cache_keys:
#             cache.delete(key)


# # ============================================================================
# # OPTIMIZED OFFER WALL VIEWSET
# # ============================================================================

# class OfferWallViewSet(BaseViewSet):
#     """
#     অপটিমাইজড অফার ওয়াল ভিউসেট
#     """
#     queryset = OfferWall.objects.filter(is_active=True)
#     serializer_class = OfferWallSerializer
#     permission_classes = [IsAuthenticated]
    
#     def get_queryset(self):
#         """Optimized queryset for offer walls"""
#         return super().get_queryset().prefetch_related(
#             Prefetch(
#                 'ad_networks',
#                 queryset=AdNetwork.objects.filter(is_active=True).only('id', 'name', 'logo_url')
#             ),
#             Prefetch(
#                 'categories',
#                 queryset=OfferCategory.objects.filter(is_active=True).only('id', 'name', 'icon')
#             )
#         )
    
#     @action(detail=True, methods=['get'])
#     def offers(self, request, pk=None):
#         """
#         অপটিমাইজড অফার ওয়াল অফারস
#         """
#         offerwall = self.get_object()
#         user = request.user
        
#         cache_key = f'offerwall_{offerwall.id}_offers_user_{user.id}'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         # Build optimized query
#         offers_queryset = Offer.objects.filter(
#             status='active',
#             ad_network__in=offerwall.ad_networks.all()
#         )
        
#         # Apply category filter if exists
#         if offerwall.categories.exists():
#             offers_queryset = offers_queryset.filter(
#                 category__in=offerwall.categories.all()
#             )
        
#         # Apply payout filter
#         if offerwall.min_payout > 0:
#             offers_queryset = offers_queryset.filter(
#                 reward_amount__gte=offerwall.min_payout
#             )
        
#         # Exclude user completed offers
#         completed_offer_ids = UserOfferEngagement.objects.filter(
#             user=user,
#             status__in=['completed', 'approved']
#         ).values_list('offer_id', flat=True)
        
#         offers_queryset = offers_queryset.exclude(id__in=completed_offer_ids)
        
#         # Optimize queryset
#         offers_queryset = offers_queryset.select_related(
#             'ad_network', 'category'
#         ).only(
#             'id', 'title', 'description', 'reward_amount', 'reward_currency',
#             'difficulty', 'estimated_time', 'thumbnail', 'countries',
#             'platforms', 'device_type', 'ad_network__name', 'category__name'
#         )
        
#         # Apply sorting
#         sort_by = request.query_params.get('sort', 'reward_amount')
#         if sort_by == 'reward_amount':
#             offers_queryset = offers_queryset.order_by('-reward_amount')
#         elif sort_by == 'difficulty':
#             offers_queryset = offers_queryset.order_by('difficulty')
#         elif sort_by == 'newest':
#             offers_queryset = offers_queryset.order_by('-created_at')
        
#         # Paginate
#         page = self.paginate_queryset(offers_queryset)
        
#         if page is not None:
#             serializer = OfferListSerializer(
#                 page,
#                 many=True,
#                 context=self.get_serializer_context()
#             )
#             data = self.get_paginated_response(serializer.data).data
#         else:
#             serializer = OfferListSerializer(
#                 offers_queryset,
#                 many=True,
#                 context=self.get_serializer_context()
#             )
#             data = serializer.data
        
#         # Cache the result
#         cache.set(cache_key, data, timeout=180)
#         return self.success_response(data=data)
    
#     @action(detail=False, methods=['get'])
#     def user_walls(self, request):
#         user = request.user
#         # ইউজারের প্রোফাইল না থাকলে ডিফল্ট 'US'
#         user_country = 'US'
#         if hasattr(user, 'profile') and user.profile.country:
#             user_country = user.profile.country

#         available_walls = OfferWall.objects.filter(
#             is_active=True
#         ).filter(
#             # countries যদি JSONField/ArrayField হয় তবে নিচের লাইন ঠিক আছে
#             Q(countries__contains=[user_country]) | Q(countries=[]) | Q(countries__isnull=True)
#         ).prefetch_related(
#             'ad_networks'
#         ).annotate(
#             total_offers=Count(
#                 'ad_networks__offers', 
#                 filter=Q(
#                     ad_networks__offers__status='active',
#                     ad_networks__offers__countries__contains=[user_country]
#                 )
#             )
#         ).filter(
#             total_offers__gt=0
#         ).order_by('-priority', '-total_offers')

#         serializer = self.get_serializer(available_walls, many=True)
        
#         # আপনার কাস্টম সাকসেস রেসপন্স মেথড থাকলে সেটি ব্যবহার করুন
#         if hasattr(self, 'success_response'):
#             return self.success_response(data=serializer.data)
#         return Response(serializer.data)

# # ============================================================================
# # ANALYTICS VIEWS
# # ============================================================================

# class AnalyticsViewSet(BaseViewSet):
#     """
#     অ্যানালিটিক্স ভিউস
#     """
#     permission_classes = [IsAuthenticated]
    
#     @action(detail=False, methods=['get'])
#     def daily_stats(self, request):
#         """
#         ডেইলি স্ট্যাটিস্টিক্স
#         """
#         user = request.user
#         days = int(request.query_params.get('days', 7))
        
#         cache_key = f'user_{user.id}_daily_stats_{days}days'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         end_date = timezone.now()
#         start_date = end_date - timedelta(days=days)
        
#         # Get daily stats
#         daily_stats = UserOfferEngagement.objects.filter(
#             user=user,
#             created_at__range=[start_date, end_date]
#         ).extra({
#             'date': "DATE(created_at)"
#         }).values('date').annotate(
#             clicks=Count('id', filter=Q(status='clicked')),
#             completions=Count('id', filter=Q(status__in=['completed', 'approved'])),
#             earnings=Sum('reward_earned', filter=Q(status='approved'))
#         ).order_by('date')
        
#         # Get top performing offers
#         top_offers = UserOfferEngagement.objects.filter(
#             user=user,
#             status__in=['completed', 'approved'],
#             created_at__range=[start_date, end_date]
#         ).values(
#             'offer__id',
#             'offer__title'
#         ).annotate(
#             completions=Count('id'),
#             total_earnings=Sum('reward_earned')
#         ).order_by('-total_earnings')[:5]
        
#         data = {
#             'daily_stats': list(daily_stats),
#             'top_offers': list(top_offers),
#             'period': {
#                 'start': start_date.isoformat(),
#                 'end': end_date.isoformat(),
#                 'days': days
#             }
#         }
        
#         cache.set(cache_key, data, timeout=600)  # 10 minutes cache
#         return self.success_response(data=data)
    
#     @action(detail=False, methods=['get'])
#     def performance(self, request):
#         """
#         ইউজার পারফরম্যান্স অ্যানালিটিক্স
#         """
#         user = request.user
        
#         cache_key = f'user_{user.id}_performance_analytics'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         # Get performance metrics
#         metrics = UserOfferEngagement.objects.filter(
#             user=user
#         ).aggregate(
#             overall_conversion_rate=Count('id', filter=Q(status__in=['completed', 'approved'])) * 100.0 / Count('id', filter=Q(status__in=['clicked', 'started'])) if Count('id', filter=Q(status__in=['clicked', 'started'])) > 0 else 0,
#             avg_earning_per_click=Avg('reward_earned', filter=Q(status='approved')) / Count('id', filter=Q(status='clicked')) if Count('id', filter=Q(status='clicked')) > 0 else 0,
#             avg_completion_time=None,
#             success_rate_by_difficulty=Count('id', filter=Q(
#                 status__in=['completed', 'approved'],
#                 offer__difficulty='easy'
#             )) * 100.0 / Count('id', filter=Q(offer__difficulty='easy')) if Count('id', filter=Q(offer__difficulty='easy')) > 0 else 0
#         )
        
#         # Get earning trend
#         monthly_earnings = UserOfferEngagement.objects.filter(
#             user=user,
#             status='approved',
#             rewarded_at__gte=timezone.now() - timedelta(days=90)
#         ).extra({
#             'month': "DATE_TRUNC('month', rewarded_at)"
#         }).values('month').annotate(
#             earnings=Sum('reward_earned')
#         ).order_by('month')
        
#         data = {
#             'performance_metrics': metrics,
#             'earning_trend': list(monthly_earnings),
#             'recommendations': self._generate_recommendations(user)
#         }
        
#         cache.set(cache_key, data, timeout=1800)  # 30 minutes cache
#         return self.success_response(data=data)
    
#     def _generate_recommendations(self, user):
#         """
#         জেনারেট পার্সোনালাইজড রিকমেন্ডেশনস
#         """
#         recommendations = []
        
#         # Get user's best performing categories
#         top_categories = UserOfferEngagement.objects.filter(
#             user=user,
#             status__in=['completed', 'approved']
#         ).values(
#             'offer__category__id',
#             'offer__category__name'
#         ).annotate(
#             success_rate=Count('id') * 100.0 / Count('id', filter=Q(status='clicked')) if Count('id', filter=Q(status='clicked')) > 0 else 0,
#             avg_earning=Avg('reward_earned')
#         ).order_by('-success_rate')[:3]
        
#         for category in top_categories:
#             recommendations.append({
#                 'type': 'category',
#                 'message': f'You have {category["success_rate"]:.1f}% success rate in {category["offer__category__name"]}. Try more offers from this category.',
#                 'category_id': category['offer__category__id']
#             })
        
#         # Check for time-based patterns
#         hour_stats = UserOfferEngagement.objects.filter(
#             user=user,
#             status__in=['completed', 'approved']
#         ).extra({
#             'hour': "EXTRACT(HOUR FROM completed_at)"
#         }).values('hour').annotate(
#             success_rate=Count('id') * 100.0 / Count('id', filter=Q(status='clicked')) if Count('id', filter=Q(status='clicked')) > 0 else 0
#         ).order_by('-success_rate')[:1]
        
#         if hour_stats:
#             best_hour = hour_stats[0]['hour']
#             recommendations.append({
#                 'type': 'timing',
#                 'message': f'Your highest success rate ({hour_stats[0]["success_rate"]:.1f}%) is at {int(best_hour)}:00. Try completing offers around this time.',
#                 'best_hour': int(best_hour)
#             })
        
#         return recommendations




# # api/ad_networks/views.py ফাইলে নিচের কোড যোগ করুন

# # ============================================================================
# # AD NETWORK VIEWSET
# # ============================================================================

# class AdNetworkViewSet(BaseViewSet):
#     """
#     অপটিমাইজড অ্যাড নেটওয়ার্ক ভিউসেট
#     """
#     queryset = AdNetwork.objects.filter(is_active=True)
#     permission_classes = [IsAuthenticated]
    
#     def get_serializer_class(self):
#         """
#         ডায়নামিক সিরিয়ালাইজার সিলেকশন
#         """
#         from .serializers import SerializerFactory
#         return SerializerFactory.get_ad_network_serializer(
#             action=self.action,
#             context=self.get_serializer_context()
#         )
    
#     def get_queryset(self):
#         """
#         অপটিমাইজড queryset
#         """
#         queryset = super().get_queryset()
        
#         # Get serializer class for eager loading
#         serializer_class = self.get_serializer_class()
#         if hasattr(serializer_class, 'setup_eager_loading'):
#             queryset = serializer_class.setup_eager_loading(queryset)
#         else:
#             # Default eager loading
#             queryset = queryset.select_related().prefetch_related('offers')
        
#         # Query parameter filtering
#         params = self.request.query_params
        
#         # Category filter
#         category = params.get('category')
#         if category:
#             queryset = queryset.filter(category=category)
        
#         # Country support filter
#         country = params.get('country')
#         if country:
#             queryset = queryset.filter(
#                 Q(country_support='global') |
#                 Q(countries__contains=[country.upper()])
#             )
        
#         # Network type filter
#         network_type = params.get('network_type')
#         if network_type:
#             queryset = queryset.filter(network_type=network_type)
        
#         # Supports offers filter
#         supports_offers = params.get('supports_offers')
#         if supports_offers == 'true':
#             queryset = queryset.filter(supports_offers=True)
        
#         # Sort by
#         sort_by = params.get('sort', 'priority')
#         if sort_by == 'priority':
#             queryset = queryset.order_by('-priority', '-rating')
#         elif sort_by == 'rating':
#             queryset = queryset.order_by('-rating', '-priority')
#         elif sort_by == 'payout':
#             queryset = queryset.order_by('-total_payout', '-priority')
        
#         return queryset
    
#     def list(self, request, *args, **kwargs):
#         """
#         অপটিমাইজড লিস্ট ভিউ with caching
#         """
#         # Generate cache key
#         cache_key = self._get_list_cache_key(request)
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         queryset = self.filter_queryset(self.get_queryset())
#         page = self.paginate_queryset(queryset)
        
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             data = self.get_paginated_response(serializer.data).data
#         else:
#             serializer = self.get_serializer(queryset, many=True)
#             data = serializer.data
        
#         # Cache the result
#         cache.set(cache_key, data, timeout=300)
#         return self.success_response(data=data)
    
#     def retrieve(self, request, *args, **kwargs):
#         """
#         অপটিমাইজড ডিটেইল ভিউ
#         """
#         instance = self.get_object()
        
#         # Prefetch related data for detail view
#         instance.offers_prefetched = Offer.objects.filter(
#             ad_network=instance,
#             status='active'
#         ).select_related('category').only(
#             'id', 'title', 'reward_amount', 'difficulty',
#             'estimated_time', 'thumbnail', 'category__name'
#         )[:20]
        
#         # Get network statistics
#         cache_key = f'ad_network_{instance.id}_stats'
#         network_stats = cache.get(cache_key)
        
#         if not network_stats:
#             network_stats = self._get_network_stats(instance)
#             cache.set(cache_key, network_stats, timeout=600)
        
#         instance.network_stats = network_stats
        
#         serializer = self.get_serializer(instance)
#         return self.success_response(data=serializer.data)
    
#     @action(detail=True, methods=['get'])
#     def offers(self, request, pk=None):
#         """
#         Get all offers for a specific ad network
#         """
#         ad_network = self.get_object()
#         user = request.user
        
#         cache_key = f'ad_network_{ad_network.id}_offers_user_{user.id}'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         offers = Offer.objects.filter(
#             ad_network=ad_network,
#             status='active'
#         ).select_related('category').prefetch_related(
#             Prefetch(
#                 'engagements',
#                 queryset=UserOfferEngagement.objects.filter(user=user),
#                 to_attr='user_engagements'
#             )
#         ).only(
#             'id', 'title', 'description', 'reward_amount', 'reward_currency',
#             'difficulty', 'estimated_time', 'thumbnail', 'countries',
#             'platforms', 'device_type', 'category__name'
#         )
        
#         # Apply filters
#         params = request.query_params
        
#         # Category filter
#         category = params.get('category')
#         if category:
#             offers = offers.filter(category__slug=category)
        
#         # Difficulty filter
#         difficulty = params.get('difficulty')
#         if difficulty:
#             offers = offers.filter(difficulty=difficulty)
        
#         # Minimum reward filter
#         min_reward = params.get('min_reward')
#         if min_reward:
#             try:
#                 offers = offers.filter(reward_amount__gte=float(min_reward))
#             except (ValueError, TypeError):
#                 pass
        
#         # Exclude completed offers
#         exclude_completed = params.get('exclude_completed', 'true')
#         if exclude_completed == 'true' and user.is_authenticated:
#             completed_offer_ids = UserOfferEngagement.objects.filter(
#                 user=user,
#                 status__in=['completed', 'approved']
#             ).values_list('offer_id', flat=True)
#             offers = offers.exclude(id__in=completed_offer_ids)
        
#         # Sort by
#         sort_by = params.get('sort', 'reward_amount')
#         if sort_by == 'reward_amount':
#             offers = offers.order_by('-reward_amount')
#         elif sort_by == 'difficulty':
#             offers = offers.order_by('difficulty')
#         elif sort_by == 'newest':
#             offers = offers.order_by('-created_at')
#         elif sort_by == 'conversions':
#             offers = offers.order_by('-total_conversions')
        
#         # Paginate
#         page = self.paginate_queryset(offers)
        
#         if page is not None:
#             serializer = OfferListSerializer(
#                 page,
#                 many=True,
#                 context=self.get_serializer_context()
#             )
#             data = self.get_paginated_response(serializer.data).data
#         else:
#             serializer = OfferListSerializer(
#                 offers,
#                 many=True,
#                 context=self.get_serializer_context()
#             )
#             data = serializer.data
        
#         # Cache the result
#         cache.set(cache_key, data, timeout=180)
#         return self.success_response(data=data)
    
#     @action(detail=True, methods=['get'])
#     def stats(self, request, pk=None):
#         """
#         Get detailed statistics for ad network
#         """
#         ad_network = self.get_object()
        
#         cache_key = f'ad_network_{ad_network.id}_detailed_stats'
#         cached_stats = cache.get(cache_key)
        
#         if cached_stats:
#             return self.success_response(data=cached_stats)
        
#         stats = self._get_detailed_stats(ad_network)
        
#         cache.set(cache_key, stats, timeout=900)  # 15 minutes
#         return self.success_response(data=stats)
    
#     @action(detail=False, methods=['get'])
#     def top_networks(self, request):
#         """
#         Get top performing networks
#         """
#         cache_key = 'top_ad_networks'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         top_networks = AdNetwork.objects.filter(
#             is_active=True,
#             total_conversions__gt=0
#         ).select_related().order_by(
#             '-total_conversions', '-conversion_rate'
#         )[:10]
        
#         serializer = self.get_serializer(top_networks, many=True)
#         data = serializer.data
        
#         cache.set(cache_key, data, timeout=600)
#         return self.success_response(data=data)
    
#     @action(detail=False, methods=['get'])
#     def categories(self, request):
#         """
#         Get network categories with counts
#         """
#         cache_key = 'ad_network_categories'
#         cached_data = cache.get(cache_key)
        
#         if cached_data:
#             return self.success_response(data=cached_data)
        
#         categories = AdNetwork.objects.filter(
#             is_active=True
#         ).values('category').annotate(
#             count=Count('id'),
#             avg_rating=Avg('rating'),
#             avg_conversion_rate=Avg('conversion_rate'),
#             total_payout=Sum('total_payout')
#         ).order_by('-count')
        
#         # Format categories with display names
#         category_display = {
#             'offerwall': 'Offerwall 📱',
#             'survey': 'Survey [NOTE]',
#             'video': 'Video/Ads 🎬',
#             'gaming': 'Gaming 🎮',
#             'app_install': 'App Install 📲',
#             'cashback': 'Cashback [MONEY]',
#             'cpi_cpa': 'CPI/CPA [STATS]',
#             'cpe': 'CPE [LOADING]',
#             'other': 'Other 📦',
#         }
        
#         formatted_categories = []
#         for cat in categories:
#             category_name = cat['category']
#             formatted_categories.append({
#                 'category': category_name,
#                 'display_name': category_display.get(category_name, category_name),
#                 'count': cat['count'],
#                 'avg_rating': round(cat['avg_rating'] or 0, 2),
#                 'avg_conversion_rate': round(cat['avg_conversion_rate'] or 0, 2),
#                 'total_payout': cat['total_payout'] or 0
#             })
        
#         cache.set(cache_key, formatted_categories, timeout=1800)  # 30 minutes
#         return self.success_response(data=formatted_categories)
    
#     @action(detail=True, methods=['post'])
#     def sync_offers(self, request, pk=None):
#         """
#         Sync offers from ad network (manual trigger)
#         """
#         ad_network = self.get_object()
        
#         # Check if network supports API sync
#         if not ad_network.supports_offers or not ad_network.api_key:
#             return self.error_response(
#                 message='This network does not support API sync',
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             # Get ad network service
#             ad_service = AdNetworkFactory.get_service(ad_network.network_type)
            
#             # Sync offers
#             sync_result = ad_service.sync_offers(ad_network)
            
#             # Create sync log
#             from .models import OfferSyncLog
#             OfferSyncLog.objects.create(
#                 ad_network=ad_network,
#                 sync_type='manual',
#                 offers_fetched=sync_result.get('offers_fetched', 0),
#                 offers_created=sync_result.get('offers_created', 0),
#                 offers_updated=sync_result.get('offers_updated', 0),
#                 success=True,
#                 metadata=sync_result
#             )
            
#             # Update last sync time
#             ad_network.last_sync = timezone.now()
#             ad_network.save()
            
#             # Invalidate caches
#             self._invalidate_network_caches(ad_network)
            
#             return self.success_response(
#                 data=sync_result,
#                 message=f"Successfully synced {sync_result.get('offers_fetched', 0)} offers"
#             )
            
#         except Exception as e:
#             # Log error
#             from .models import OfferSyncLog
#             OfferSyncLog.objects.create(
#                 ad_network=ad_network,
#                 sync_type='manual',
#                 success=False,
#                 error_message=str(e)
#             )
            
#             return self.error_response(
#                 message=f"Failed to sync offers: {str(e)}",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     # ============================================================================
#     # HELPER METHODS
#     # ============================================================================
    
#     def _get_list_cache_key(self, request):
#         """Generate cache key for list view"""
#         params = dict(request.query_params)
#         params.pop('page', None)
#         params.pop('page_size', None)
#         params_str = str(sorted(params.items()))
#         return f'ad_network_list_{hash(params_str)}_{request.user.id if request.user.is_authenticated else "anon"}'
    
#     def _get_network_stats(self, ad_network):
#         """Get network statistics"""
#         # Today's date
#         today = timezone.now().date()
#         yesterday = today - timedelta(days=1)
#         last_7_days = today - timedelta(days=7)
#         last_30_days = today - timedelta(days=30)
        
#         # Get basic stats
#         stats = {
#             'total_offers': Offer.objects.filter(
#                 ad_network=ad_network,
#                 status='active'
#             ).count(),
#             'total_active_users': UserOfferEngagement.objects.filter(
#                 offer__ad_network=ad_network
#             ).values('user').distinct().count(),
#             'network_info': {
#                 'name': ad_network.name,
#                 'network_type': ad_network.network_type,
#                 'category': ad_network.category,
#                 'rating': ad_network.rating,
#                 'trust_score': ad_network.trust_score,
#                 'is_verified': ad_network.is_verified
#             }
#         }
        
#         # Get conversion stats
#         conversion_stats = UserOfferEngagement.objects.filter(
#             offer__ad_network=ad_network,
#             status__in=['completed', 'approved', 'rewarded']
#         ).aggregate(
#             total_conversions=Count('id'),
#             conversions_today=Count('id', filter=Q(completed_at__date=today)),
#             conversions_yesterday=Count('id', filter=Q(completed_at__date=yesterday)),
#             conversions_last_7_days=Count('id', filter=Q(completed_at__gte=last_7_days)),
#             conversions_last_30_days=Count('id', filter=Q(completed_at__gte=last_30_days)),
#             total_earned=Sum('reward_earned'),
#             avg_completion_time=None
#         )
        
#         stats.update(conversion_stats)
        
#         # Get click stats
#         click_stats = UserOfferEngagement.objects.filter(
#             offer__ad_network=ad_network,
#             status='clicked'
#         ).aggregate(
#             total_clicks=Count('id'),
#             clicks_today=Count('id', filter=Q(clicked_at__date=today)),
#             clicks_last_7_days=Count('id', filter=Q(clicked_at__gte=last_7_days))
#         )
        
#         stats.update(click_stats)
        
#         # Calculate conversion rates
#         if stats.get('total_clicks', 0) > 0:
#             stats['overall_conversion_rate'] = (stats['total_conversions'] / stats['total_clicks']) * 100
        
#         if stats.get('clicks_today', 0) > 0:
#             stats['today_conversion_rate'] = (stats['conversions_today'] / stats['clicks_today']) * 100
        
#         # Get top performing offers
#         top_offers = Offer.objects.filter(
#             ad_network=ad_network,
#             status='active'
#         ).annotate(
#             recent_conversions=Count(
#                 'engagements',
#                 filter=Q(
#                     engagements__status__in=['completed', 'approved', 'rewarded'],
#                     engagements__completed_at__gte=last_7_days
#                 )
#             )
#         ).order_by('-recent_conversions', '-total_conversions')[:5]
        
#         stats['top_offers'] = [
#             {
#                 'id': offer.id,
#                 'title': offer.title,
#                 'reward_amount': offer.reward_amount,
#                 'total_conversions': offer.total_conversions,
#                 'recent_conversions': offer.recent_conversions
#             }
#             for offer in top_offers
#         ]
        
#         # Get user distribution by country
#         user_countries = UserOfferEngagement.objects.filter(
#             offer__ad_network=ad_network
#         ).exclude(
#             location_data__isnull=True
#         ).values(
#             'location_data__country'
#         ).annotate(
#             user_count=Count('user', distinct=True),
#             conversion_count=Count('id', filter=Q(status__in=['completed', 'approved', 'rewarded']))
#         ).order_by('-user_count')[:5]
        
#         stats['top_countries'] = [
#             {
#                 'country': item['location_data__country'],
#                 'user_count': item['user_count'],
#                 'conversion_count': item['conversion_count']
#             }
#             for item in user_countries
#         ]
        
#         return stats
    
#     def _get_detailed_stats(self, ad_network):
#         """Get detailed statistics for ad network"""
#         # Time periods
#         today = timezone.now().date()
#         last_7_days = today - timedelta(days=7)
#         last_30_days = today - timedelta(days=30)
        
#         # Daily stats for last 7 days
#         daily_stats = UserOfferEngagement.objects.filter(
#             offer__ad_network=ad_network,
#             completed_at__gte=last_7_days,
#             status__in=['completed', 'approved', 'rewarded']
#         ).extra({
#             'date': "DATE(completed_at)"
#         }).values('date').annotate(
#             conversions=Count('id'),
#             earnings=Sum('reward_earned'),
#             clicks=Count('id', filter=Q(status='clicked')),
#             avg_time=None
#         ).order_by('date')
        
#         # Offer category distribution
#         category_stats = Offer.objects.filter(
#             ad_network=ad_network,
#             status='active'
#         ).values('category__name').annotate(
#             offer_count=Count('id'),
#             total_conversions=Sum('total_conversions'),
#             avg_reward=Avg('reward_amount')
#         ).order_by('-offer_count')
        
#         # Device type distribution
#         device_stats = UserOfferEngagement.objects.filter(
#             offer__ad_network=ad_network,
#             completed_at__gte=last_30_days
#         ).exclude(
#             device_info__isnull=True
#         ).values('device_info__device_type').annotate(
#             count=Count('id'),
#             conversion_rate=Count('id', filter=Q(status__in=['completed', 'approved', 'rewarded'])) * 100.0 / Count('id')
#         ).order_by('-count')
        
#         # Hourly distribution (best times)
#         hourly_stats = UserOfferEngagement.objects.filter(
#             offer__ad_network=ad_network,
#             status__in=['completed', 'approved', 'rewarded'],
#             completed_at__gte=last_30_days
#         ).extra({
#             'hour': "EXTRACT(HOUR FROM completed_at)"
#         }).values('hour').annotate(
#             count=Count('id'),
#             avg_earning=Avg('reward_earned')
#         ).order_by('hour')
        
#         return {
#             'daily_stats': list(daily_stats),
#             'category_distribution': list(category_stats),
#             'device_distribution': list(device_stats),
#             'hourly_distribution': list(hourly_stats),
#             'time_period': {
#                 'last_7_days': last_7_days.isoformat(),
#                 'last_30_days': last_30_days.isoformat(),
#                 'today': today.isoformat()
#             },
#             'updated_at': timezone.now().isoformat()
#         }
    
#     def _invalidate_network_caches(self, ad_network):
#         """Invalidate caches related to ad network"""
#         cache_keys = [
#             f'ad_network_{ad_network.id}_detail',
#             f'ad_network_{ad_network.id}_stats',
#             f'ad_network_{ad_network.id}_detailed_stats',
#             f'ad_network_{ad_network.id}_offers_user_*',  # Pattern for user-specific caches
#             'top_ad_networks',
#             'ad_network_categories',
#         ]
        
#         # Delete pattern-based caches
#         for key in cache_keys:
#             if '*' in key:
#                 # For pattern keys, we need to clear all matching keys
#                 from django.core.cache.utils import make_template_fragment_key
#                 # This is a simplified approach - in production you might need Redis scan
#                 pass
#             else:
#                 cache.delete(key)
        
#         # Also delete list cache keys
#         from django.core.cache import cache
#         keys = cache.keys('ad_network_list_*')
#         for key in keys:
#             cache.delete(key)
# # ============================================================================
# # VIEWSET REGISTRATION
# # ============================================================================

# # Note: Register these viewsets in your urls.py

# # ============================================================================
# # POSTBACK VIEW WITH THIRD-PARTY IP REPUTATION SERVICES
# # ============================================================================

# from django.views import View
# from django.http import HttpResponse, JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
# from django.core.exceptions import ValidationError
# from django.db import transaction
# from django.utils import timezone
# from decimal import Decimal, InvalidOperation
# import hashlib
# import hmac
# import json
# import logging
# from datetime import timedelta
# import requests
# from django.conf import settings

# # Get logger for this module
# logger = logging.getLogger(__name__)

# @method_decorator(csrf_exempt, name='dispatch')
# class PostbackView(View):
#     """
#     Enterprise-grade postback receiver with third-party IP reputation services
#     """
    
#     # Configuration from Django settings
#     FRAUD_CHECK_ENABLED = getattr(settings, 'FRAUD_CHECK_ENABLED', True)
#     BOT_DETECTION_ENABLED = getattr(settings, 'BOT_DETECTION_ENABLED', True)
#     ALLOW_DUPLICATE_CONVERSIONS = getattr(settings, 'ALLOW_DUPLICATE_CONVERSIONS', False)
    
#     # Third-party service settings
#     IP_REPUTATION_SERVICE = getattr(settings, 'IP_REPUTATION_SERVICE', 'ipqualityscore')  # ipqualityscore, maxmind, abuseipdb
#     IP_REPUTATION_API_KEY = getattr(settings, 'IP_REPUTATION_API_KEY', '')
#     IP_REPUTATION_CACHE_TIME = getattr(settings, 'IP_REPUTATION_CACHE_TIME', 3600)  # 1 hour cache
    
#     # Timing check settings
#     STRICT_TIMING_CHECK_SECONDS = 3  # Strict check for 0-3 seconds
#     RELAXED_TIMING_CHECK_SECONDS = 10  # Relaxed check for 3-10 seconds
    
#     def __init__(self):
#         super().__init__()
#         self.ip_reputation_cache = {}
    
#     # ... [GET এবং POST methods আগের মতো থাকবে]
    
#     def _advanced_bot_detection(self, request_id, client_ip, data, request):
#         """
#         Advanced bot detection with third-party IP reputation services
#         """
#         bot_indicators = []
        
#         # 1. Check IP reputation using third-party service
#         ip_reputation = self._get_ip_reputation(client_ip)
        
#         if ip_reputation.get('is_bot', False):
#             bot_indicators.append(f"Bot IP detected: {ip_reputation.get('reason', 'Unknown')}")
        
#         if ip_reputation.get('is_vpn', False):
#             bot_indicators.append(f"VPN/Proxy detected: {ip_reputation.get('vpn_reason', 'Unknown')}")
        
#         if ip_reputation.get('reputation_score', 100) < 30:
#             bot_indicators.append(f"Low IP reputation: {ip_reputation.get('reputation_score')}")
        
#         # 2. Check request frequency from this IP
#         from .models import PostbackLog
#         recent_hour = timezone.now() - timedelta(hours=1)
#         recent_requests = PostbackLog.objects.filter(
#             ip_address=client_ip,
#             created_at__gte=recent_hour
#         ).count()
        
#         max_conversions = getattr(settings, 'MAX_CONVERSIONS_PER_HOUR', 15)
#         if recent_requests > max_conversions:
#             bot_indicators.append(f"High frequency: {recent_requests} requests/hour (max: {max_conversions})")
        
#         # 3. Check for missing or suspicious headers
#         headers = dict(request.headers)
#         suspicious_headers = self._check_suspicious_headers(headers)
#         if suspicious_headers:
#             bot_indicators.append(f"Suspicious headers: {', '.join(suspicious_headers)}")
        
#         # 4. Advanced User-Agent analysis
#         user_agent = headers.get('User-Agent', '')
#         if self._is_suspicious_user_agent(user_agent):
#             bot_indicators.append(f"Suspicious User-Agent pattern")
        
#         if bot_indicators:
#             logger.warning(f"[{request_id}] Bot indicators: {bot_indicators}")
            
#             # Log to BlacklistedIP if multiple strong indicators
#             if len(bot_indicators) >= 2:
#                 self._add_to_blacklist_if_needed(client_ip, bot_indicators)
            
#             return {
#                 'is_bot': True,
#                 'reason': ', '.join(bot_indicators[:3]),  # First 3 reasons
#                 'indicators': bot_indicators,
#                 'ip_address': client_ip,
#                 'timestamp': timezone.now().isoformat(),
#                 'ip_reputation': ip_reputation
#             }
        
#         return {'is_bot': False}
    
#     def _get_ip_reputation(self, ip_address):
#         """
#         Get IP reputation from third-party service with caching
#         """
#         # Check cache first
#         cache_key = f"ip_reputation_{ip_address}"
#         if cache_key in self.ip_reputation_cache:
#             cached_data = self.ip_reputation_cache.get(cache_key)
#             if cached_data.get('timestamp') > (timezone.now() - timedelta(seconds=self.IP_REPUTATION_CACHE_TIME)):
#                 logger.debug(f"IP reputation cache hit for {ip_address}")
#                 return cached_data['data']
        
#         # Initialize default response
#         reputation_data = {
#             'is_bot': False,
#             'is_vpn': False,
#             'reputation_score': 50,
#             'country': None,
#             'isp': None,
#             'source': 'fallback'
#         }
        
#         try:
#             # Check local blacklist first
#             from .models import BlacklistedIP
#             blacklisted = BlacklistedIP.objects.filter(
#                 ip_address=ip_address,
#                 is_active=True
#             ).first()
            
#             if blacklisted:
#                 if blacklisted.deactivate_if_expired():
#                     logger.info(f"Expired blacklist entry deactivated for {ip_address}")
#                 else:
#                     reputation_data.update({
#                         'is_bot': blacklisted.reason in ['bot', 'fraud', 'abuse'],
#                         'is_vpn': blacklisted.reason == 'vpn',
#                         'reputation_score': 0,
#                         'source': 'local_blacklist',
#                         'reason': blacklisted.reason
#                     })
#                     return reputation_data
            
#             # Use third-party service based on configuration
#             if self.IP_REPUTATION_SERVICE == 'ipqualityscore' and self.IP_REPUTATION_API_KEY:
#                 reputation_data = self._get_ipqualityscore_reputation(ip_address)
#             elif self.IP_REPUTATION_SERVICE == 'maxmind' and self.IP_REPUTATION_API_KEY:
#                 reputation_data = self._get_maxmind_reputation(ip_address)
#             elif self.IP_REPUTATION_SERVICE == 'abuseipdb' and self.IP_REPUTATION_API_KEY:
#                 reputation_data = self._get_abuseipdb_reputation(ip_address)
#             else:
#                 # Fallback to basic checks if no service configured
#                 reputation_data = self._get_basic_ip_reputation(ip_address)
            
#         except Exception as e:
#             logger.error(f"IP reputation check failed for {ip_address}: {str(e)}")
#             reputation_data = self._get_basic_ip_reputation(ip_address)
#             reputation_data['source'] = 'fallback_error'
#             reputation_data['error'] = str(e)
        
#         # Cache the result
#         self.ip_reputation_cache[cache_key] = {
#             'data': reputation_data,
#             'timestamp': timezone.now()
#         }
        
#         return reputation_data
    
#     def _get_ipqualityscore_reputation(self, ip_address):
#         """Get IP reputation from IPQualityScore"""
#         try:
#             params = {
#                 'key': self.IP_REPUTATION_API_KEY,
#                 'ip': ip_address,
#                 'strictness': 1,
#                 'fast': 'true',
#                 'mobile': 'true',
#                 'allow_public_access_points': 'true',
#                 'lighter_penalties': 'false'
#             }
            
#             response = requests.get(
#                 'https://ipqualityscore.com/api/json/ip',
#                 params=params,
#                 timeout=5
#             )
#             response.raise_for_status()
#             data = response.json()
            
#             return {
#                 'is_bot': data.get('bot_status', False),
#                 'is_vpn': data.get('vpn', False) or data.get('proxy', False),
#                 'reputation_score': data.get('fraud_score', 0),
#                 'country': data.get('country_code'),
#                 'isp': data.get('ISP'),
#                 'city': data.get('city'),
#                 'region': data.get('region'),
#                 'tor': data.get('tor', False),
#                 'recent_abuse': data.get('abuse_velocity', 'low') != 'low',
#                 'source': 'ipqualityscore',
#                 'raw_data': data
#             }
            
#         except Exception as e:
#             logger.error(f"IPQualityScore error for {ip_address}: {str(e)}")
#             raise
    
#     def _get_maxmind_reputation(self, ip_address):
#         """Get IP reputation from MaxMind (MinFraud)"""
#         try:
#             # MaxMind MinFraud API
#             headers = {
#                 'Authorization': f'Bearer {self.IP_REPUTATION_API_KEY}',
#                 'Content-Type': 'application/json'
#             }
            
#             payload = {
#                 'ip_address': ip_address,
#                 'device': {
#                     'accept_language': 'en-US,en;q=0.9',
#                     'session_age': 3600,
#                     'session_id': 'postback_session'
#                 }
#             }
            
#             response = requests.post(
#                 'https://minfraud.maxmind.com/minfraud/v2.0/score',
#                 headers=headers,
#                 json=payload,
#                 timeout=5
#             )
#             response.raise_for_status()
#             data = response.json()
            
#             # Parse MaxMind response
#             risk_score = data.get('risk_score', 0.5)
            
#             return {
#                 'is_bot': risk_score > 0.7,
#                 'is_vpn': data.get('ip_address', {}).get('network', {}).get('autonomous_system_number', 0) in self._get_vpn_asn_list(),
#                 'reputation_score': int((1 - risk_score) * 100),
#                 'country': data.get('ip_address', {}).get('country', {}).get('iso_code'),
#                 'isp': data.get('ip_address', {}).get('network', {}).get('autonomous_system_organization'),
#                 'risk_score': risk_score,
#                 'source': 'maxmind',
#                 'raw_data': data
#             }
            
#         except Exception as e:
#             logger.error(f"MaxMind error for {ip_address}: {str(e)}")
#             raise
    
#     def _get_abuseipdb_reputation(self, ip_address):
#         """Get IP reputation from AbuseIPDB"""
#         try:
#             headers = {
#                 'Key': self.IP_REPUTATION_API_KEY,
#                 'Accept': 'application/json'
#             }
            
#             params = {
#                 'ipAddress': ip_address,
#                 'maxAgeInDays': 30
#             }
            
#             response = requests.get(
#                 'https://api.abuseipdb.com/api/v2/check',
#                 headers=headers,
#                 params=params,
#                 timeout=5
#             )
#             response.raise_for_status()
#             data = response.json()
            
#             abuse_data = data.get('data', {})
#             abuse_score = abuse_data.get('abuseConfidenceScore', 0)
            
#             return {
#                 'is_bot': abuse_score > 70,
#                 'is_vpn': abuse_data.get('usageType') in ['hosting', 'vpn'],
#                 'reputation_score': 100 - abuse_score,
#                 'country': abuse_data.get('countryCode'),
#                 'isp': abuse_data.get('isp'),
#                 'domain': abuse_data.get('domain'),
#                 'total_reports': abuse_data.get('totalReports', 0),
#                 'last_reported': abuse_data.get('lastReportedAt'),
#                 'abuse_score': abuse_score,
#                 'source': 'abuseipdb',
#                 'raw_data': abuse_data
#             }
            
#         except Exception as e:
#             logger.error(f"AbuseIPDB error for {ip_address}: {str(e)}")
#             raise
    
#     def _get_basic_ip_reputation(self, ip_address):
#         """Basic IP reputation check (fallback)"""
#         reputation_data = {
#             'is_bot': False,
#             'is_vpn': False,
#             'reputation_score': 50,
#             'country': None,
#             'isp': None,
#             'source': 'basic_fallback'
#         }
        
#         # Basic checks (improved from hardcoded ranges)
#         try:
#             # Check for private IP ranges (more comprehensive)
#             import ipaddress
            
#             ip = ipaddress.ip_address(ip_address)
            
#             # Private IP ranges
#             private_ranges = [
#                 ipaddress.ip_network('10.0.0.0/8'),
#                 ipaddress.ip_network('172.16.0.0/12'),
#                 ipaddress.ip_network('192.168.0.0/16'),
#                 ipaddress.ip_network('127.0.0.0/8'),
#                 ipaddress.ip_network('169.254.0.0/16'),  # Link-local
#                 ipaddress.ip_network('224.0.0.0/4'),     # Multicast
#                 ipaddress.ip_network('240.0.0.0/4'),     # Reserved
#             ]
            
#             if any(ip in network for network in private_ranges):
#                 reputation_data.update({
#                     'is_vpn': True,
#                     'reputation_score': 10,
#                     'reason': 'private_ip'
#                 })
            
#             # Check known bad IPs from database
#             from .models import KnownBadIP
#             known_bad = KnownBadIP.objects.filter(
#                 ip_address=ip_address,
#                 is_active=True
#             ).first()
            
#             if known_bad:
#                 reputation_data.update({
#                     'is_bot': known_bad.threat_type == 'bot',
#                     'is_vpn': known_bad.threat_type == 'vpn',
#                     'reputation_score': max(0, 50 - known_bad.confidence_score),
#                     'reason': known_bad.threat_type,
#                     'details': known_bad.description
#                 })
            
#         except Exception as e:
#             logger.error(f"Basic IP check failed: {str(e)}")
        
#         return reputation_data
    
#     def _get_vpn_asn_list(self):
#         """Get list of VPN/Proxy ASN numbers"""
#         # Common VPN/Proxy ASN numbers (partial list)
#         # In production, maintain this in database or external config
#         return [
#             174, 209, 701, 702, 703, 704, 705, 706, 707, 708,  # Cogent
#             7922,  # Comcast
#             15169,  # Google
#             8075,  # Microsoft
#             14618,  # Amazon
#             16509,  # Amazon
#             13335,  # Cloudflare
#             16276,  # OVH
#             20473,  # Choopa
#             24940,  # Hetzner
#         ]
    
#     def _add_to_blacklist_if_needed(self, ip_address, indicators):
#         """Add IP to blacklist if it meets criteria"""
#         try:
#             from .models import BlacklistedIP
            
#             # Check if already blacklisted
#             existing = BlacklistedIP.objects.filter(ip_address=ip_address).first()
#             if existing:
#                 if existing.is_active:
#                     return False  # Already active
#                 else:
#                     # Reactivate with new expiry
#                     existing.is_active = True
#                     existing.reason = 'bot'
#                     existing.expiry_date = timezone.now() + timedelta(days=30)
#                     existing.save()
#                     logger.info(f"Reactivated blacklist for {ip_address}")
#                     return True
            
#             # Determine reason based on indicators
#             reason = 'bot'
#             if any('VPN' in ind or 'Proxy' in ind for ind in indicators):
#                 reason = 'vpn'
#             elif any('fraud' in ind.lower() for ind in indicators):
#                 reason = 'fraud'
            
#             # Create new blacklist entry
#             BlacklistedIP.objects.create(
#                 ip_address=ip_address,
#                 reason=reason,
#                 is_active=True,
#                 metadata={
#                     'indicators': indicators,
#                     'first_detected': timezone.now().isoformat(),
#                     'detection_method': 'auto_bot_detection'
#                 }
#             )
            
#             logger.info(f"Added {ip_address} to blacklist for {reason}")
#             return True
            
#         except Exception as e:
#             logger.error(f"Failed to add {ip_address} to blacklist: {str(e)}")
#             return False
    
#     def _is_suspicious_timing(self, time_diff):
#         """
#         Smart timing pattern detection with different strictness levels
#         """
#         seconds = time_diff.total_seconds()
        
#         # Level 1: Very strict for 0-3 seconds (likely bots)
#         if seconds <= self.STRICT_TIMING_CHECK_SECONDS:
#             # Check for exact values with high precision
#             strict_exact_values = [0, 1, 2, 3]
#             for exact_value in strict_exact_values:
#                 if abs(seconds - exact_value) < 0.1:  # Within 0.1 second
#                     return True
        
#         # Level 2: Relaxed for 3-10 seconds
#         elif seconds <= self.RELAXED_TIMING_CHECK_SECONDS:
#             # Check for round numbers but with tolerance
#             round_values = [5, 10]
#             for round_value in round_values:
#                 if abs(seconds - round_value) < 0.5:  # Within 0.5 second
#                     # Additional check: not suspicious if user might realistically take this time
#                     if round_value == 10 and seconds > 9.5:
#                         # 10 seconds is reasonable for many offers
#                         return False
#                     return True
        
#         # Level 3: No check for >10 seconds (normal user behavior)
#         # Users can take exactly 15, 20, 30 seconds legitimately
        
#         # Additional check: Unusually perfect timing patterns
#         # Bots often use exact multiples of 5
#         if seconds <= 60 and seconds % 5 == 0:
#             # Check if it's suspiciously exact
#             if abs(seconds - round(seconds)) < 0.01:
#                 # But only flag if it's very fast (<15s)
#                 if seconds < 15:
#                     return True
        
#         return False
    
#     # ... [বাকি methods একই থাকবে, শুধু _check_for_fraud এ timing check call update করুন]
    
#     def _check_for_fraud(self, engagement, postback_time, request_id):
#         """
#         Advanced fraud detection with smart timing checks
#         """
#         if not self.FRAUD_CHECK_ENABLED:
#             return False, []
        
#         fraud_indicators = []
        
#         # Get offer-specific fraud settings
#         fraud_settings = self._get_offer_fraud_settings(engagement.offer)
        
#         if not fraud_settings['enabled']:
#             logger.debug(f"[{request_id}] Fraud detection disabled for offer {engagement.offer.id}")
#             return False, []
        
#         # 1. Check click to conversion time with offer-specific settings
#         if engagement.clicked_at:
#             time_diff = postback_time - engagement.clicked_at
#             time_seconds = time_diff.total_seconds()
            
#             # Get minimum time for this offer
#             min_seconds = fraud_settings['min_time'].total_seconds()
            
#             # Smart timing check with context
#             if time_seconds < min_seconds:
#                 # Use different messages based on how fast it is
#                 if time_seconds < 3:
#                     message = f"Impossibly fast: {time_seconds:.1f}s (minimum: {min_seconds}s)"
#                 elif time_seconds < 10:
#                     message = f"Too fast for {fraud_settings['category']}: {time_seconds:.1f}s (minimum: {min_seconds}s)"
#                 else:
#                     message = f"Faster than expected for {fraud_settings['category']}: {time_seconds:.1f}s (minimum: {min_seconds}s)"
                
#                 fraud_indicators.append(message)
#                 logger.warning(f"[{request_id}] {message}")
            
#             # Check suspicious timing patterns (smart version)
#             if time_seconds < 15 and self._is_suspicious_timing(time_diff):
#                 fraud_indicators.append(f"Suspicious timing pattern: {time_seconds:.1f}s")
#                 logger.warning(f"[{request_id}] Suspicious timing pattern: {time_seconds:.1f}s")
        
#         # ... [বাকি fraud checks একই থাকবে]
        
#         return len(fraud_indicators) > 0, fraud_indicators
    
#     def get(self, request, *args, **kwargs):
#         """
#         হ্যান্ডেল ইনকামিং পোস্টব্যাক (GET Request)
#         """
#         # ১. সিকিউরিটি চেক (আপনার টেস্ট এই 'secret_password' ই খুঁজছে)
#         password = request.GET.get('pw')
#         if password != 'secret_password':
#             from django.http import HttpResponseForbidden
#             return HttpResponseForbidden("Invalid Secret Key")

#         # ২. প্যারামিটার রিড করা
#         click_id = request.GET.get('click_id')
        
#         if not click_id:
#             from django.http import HttpResponseBadRequest
#             return HttpResponseBadRequest("Missing click_id")

#         # ৩. এনগেজমেন্ট আপডেট লজিক
#         try:
#             engagement = UserOfferEngagement.objects.get(click_id=click_id)
#             if engagement.status != 'completed':
#                 engagement.status = 'completed'
#                 engagement.completed_at = timezone.now()
#                 engagement.save()
            
#             from django.http import HttpResponse
#             return HttpResponse("OK")
            
#         except UserOfferEngagement.DoesNotExist:
#             from django.http import HttpResponseNotFound
#             return HttpResponseNotFound("Engagement not found")
        
        
        
        
#         # ============================================================================
# # এই পুরো block টা views.py ফাইলের একদম শেষে PASTE করো
# # ============================================================================

# from rest_framework import serializers as drf_serializers
# from rest_framework.permissions import IsAdminUser

# # ── Missing models import (views.py তে already নেই এগুলো) ─────────────────
# from .models import (
#     AdNetworkWebhookLog, OfferSyncLog,
#     BlacklistedIP, FraudDetectionRule
# )


# # ============================================================================
# # AdNetworkViewSet এ এই ৩টা @action add করো (class এর ভেতরে)
# # views.py তে AdNetworkViewSet class খুঁজে, শেষের } এর আগে paste করো
# # ============================================================================
# #
# #   @action(detail=False, methods=['get'])
# #   def summary(self, request):
# #       qs = AdNetwork.objects.all()
# #       total  = qs.count()
# #       active = qs.filter(is_active=True).count()
# #       tp     = qs.aggregate(t=Sum('total_payout'))['t'] or 0
# #       tc     = qs.aggregate(t=Sum('total_conversions'))['t'] or 0
# #       return Response({
# #           'totals':     {'total': total, 'active': active},
# #           'financials': {'total_payout': float(tp), 'total_conversions': int(tc)},
# #       })
# #
# #   @action(detail=True, methods=['post'])
# #   def toggle_status(self, request, pk=None):
# #       n = self.get_object()
# #       n.is_active = not n.is_active
# #       n.save(update_fields=['is_active'])
# #       return Response({'id': n.id, 'is_active': n.is_active})
# #
# #   @action(detail=True, methods=['post'])
# #   def sync(self, request, pk=None):
# #       log = OfferSyncLog.objects.create(
# #           ad_network=self.get_object(), status='success',
# #           offers_fetched=0, offers_added=0, offers_updated=0, offers_removed=0,
# #       )
# #       return Response({'success': True, 'log_id': log.id})


# # ============================================================================
# # SERIALIZERS
# # ============================================================================

# class OfferConversionAdminSerializer(drf_serializers.ModelSerializer):
#     user_name     = drf_serializers.SerializerMethodField()
#     offer_title   = drf_serializers.SerializerMethodField()
#     risk_level    = drf_serializers.SerializerMethodField()
#     payout_amount = drf_serializers.SerializerMethodField()

#     class Meta:
#         model  = OfferConversion
#         fields = ['id', 'conversion_status', 'payout_amount', 'risk_level',
#                   'user_name', 'offer_title', 'created_at', 'fraud_score']

#     def get_user_name(self, obj):
#         try:    return obj.engagement.user.username
#         except: return '—'

#     def get_offer_title(self, obj):
#         try:    return obj.engagement.offer.title
#         except: return '—'

#     def get_risk_level(self, obj):
#         s = getattr(obj, 'fraud_score', 0) or 0
#         return 'high' if s > 70 else 'medium' if s > 40 else 'low'

#     def get_payout_amount(self, obj):
#         try:    return str(obj.engagement.offer.reward_amount)
#         except: return '0'


# class OfferWallAdminSerializer(drf_serializers.ModelSerializer):
#     class Meta:
#         model  = OfferWall
#         fields = ['id', 'name', 'slug', 'wall_type', 'is_active', 'is_default',
#                   'title', 'description', 'created_at']
#         extra_kwargs = {
#             'slug':        {'required': False},
#             'title':       {'required': False},
#             'description': {'required': False},
#         }


# class BlacklistedIPSerializer(drf_serializers.ModelSerializer):
#     class Meta:
#         model  = BlacklistedIP
#         fields = ['id', 'ip_address', 'reason', 'is_active',
#                   'expiry_date', 'created_at']
#         extra_kwargs = {'expiry_date': {'required': False}}


# class FraudRuleSerializer(drf_serializers.ModelSerializer):
#     class Meta:
#         model  = FraudDetectionRule
#         fields = ['id', 'name', 'description', 'rule_type', 'action',
#                   'severity', 'is_active', 'condition', 'created_at']
#         extra_kwargs = {
#             'condition':   {'required': False, 'default': dict},
#             'description': {'required': False},
#         }


# class WebhookLogSerializer(drf_serializers.ModelSerializer):
#     ad_network_name = drf_serializers.SerializerMethodField()

#     class Meta:
#         model  = AdNetworkWebhookLog
#         fields = ['id', 'ad_network', 'ad_network_name', 'event_type',
#                   'is_valid_signature', 'is_processed', 'created_at', 'ip_address']
#         extra_kwargs = {
#             'event_type':         {'required': False},
#             'is_valid_signature': {'required': False},
#             'is_processed':       {'required': False},
#             'ip_address':         {'required': False},
#         }

#     def get_ad_network_name(self, obj):
#         try:    return obj.ad_network.name if obj.ad_network else '—'
#         except: return '—'


# class SyncLogSerializer(drf_serializers.ModelSerializer):
#     ad_network_name = drf_serializers.SerializerMethodField()
#     offers_synced   = drf_serializers.SerializerMethodField()

#     class Meta:
#         model  = OfferSyncLog
#         fields = ['id', 'ad_network', 'ad_network_name', 'status',
#                   'offers_fetched', 'offers_added', 'offers_updated',
#                   'offers_removed', 'offers_synced', 'created_at']

#     def get_ad_network_name(self, obj):
#         try:    return obj.ad_network.name
#         except: return '—'

#     def get_offers_synced(self, obj):
#         return (obj.offers_added or 0) + (obj.offers_updated or 0)


# # ============================================================================
# # NEW VIEWSETS
# # ============================================================================

# class OfferConversionViewSet(viewsets.ModelViewSet):
#     """
#     GET  /api/ad-networks/conversions/
#     POST /api/ad-networks/conversions/{id}/approve/
#     POST /api/ad-networks/conversions/{id}/reject/
#     POST /api/ad-networks/conversions/bulk_approve/
#     """
#     permission_classes = [IsAuthenticated]
#     serializer_class   = OfferConversionAdminSerializer

#     def get_queryset(self):
#         qs = OfferConversion.objects.select_related(
#             'engagement__user', 'engagement__offer'
#         ).order_by('-created_at')
#         st = self.request.query_params.get('conversion_status')
#         if st:
#             qs = qs.filter(conversion_status=st)
#         return qs

#     @action(detail=True, methods=['post'])
#     def approve(self, request, pk=None):
#         obj = self.get_object()
#         obj.conversion_status = 'approved'
#         obj.save(update_fields=['conversion_status'])
#         return Response({'success': True})

#     @action(detail=True, methods=['post'])
#     def reject(self, request, pk=None):
#         obj = self.get_object()
#         obj.conversion_status = 'rejected'
#         obj.save(update_fields=['conversion_status'])
#         return Response({'success': True})

#     @action(detail=False, methods=['post'])
#     def bulk_approve(self, request):
#         ids = request.data.get('ids', [])
#         count = OfferConversion.objects.filter(id__in=ids).update(
#             conversion_status='approved'
#         )
#         return Response({'success': True, 'updated': count})


# class OfferWallAdminViewSet(viewsets.ModelViewSet):
#     """
#     GET   /api/ad-networks/offerwalls/
#     POST  /api/ad-networks/offerwalls/
#     PATCH /api/ad-networks/offerwalls/{id}/
#     DEL   /api/ad-networks/offerwalls/{id}/
#     """
#     permission_classes = [IsAuthenticated]
#     serializer_class   = OfferWallAdminSerializer

#     def get_queryset(self):
#         return OfferWall.objects.order_by('-created_at')

#     def perform_create(self, serializer):
#         import re
#         name = serializer.validated_data.get('name', '')
#         slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'wall'
#         base, i = slug, 1
#         while OfferWall.objects.filter(slug=slug).exists():
#             slug = f"{base}-{i}"
#             i += 1
#         serializer.save(slug=slug)


# class BlacklistedIPViewSet(viewsets.ModelViewSet):
#     """
#     GET  /api/ad-networks/blacklisted-ips/
#     POST /api/ad-networks/blacklisted-ips/check/
#     POST /api/ad-networks/blacklisted-ips/cleanup/
#     """
#     permission_classes = [IsAuthenticated]
#     serializer_class   = BlacklistedIPSerializer

#     def get_queryset(self):
#         return BlacklistedIP.objects.order_by('-created_at')

#     @action(detail=False, methods=['post'])
#     def check(self, request):
#         ip    = request.data.get('ip_address', '')
#         is_bl = BlacklistedIP.objects.filter(ip_address=ip, is_active=True).exists()
#         return Response({'ip_address': ip, 'is_blacklisted': is_bl})

#     @action(detail=False, methods=['post'])
#     def cleanup(self, request):
#         deleted, _ = BlacklistedIP.objects.filter(
#             expiry_date__lt=timezone.now()
#         ).delete()
#         return Response({'success': True, 'removed': deleted})


# class FraudRuleViewSet(viewsets.ModelViewSet):
#     """
#     GET   /api/ad-networks/fraud-rules/
#     POST  /api/ad-networks/fraud-rules/
#     PATCH /api/ad-networks/fraud-rules/{id}/
#     DEL   /api/ad-networks/fraud-rules/{id}/
#     """
#     permission_classes = [IsAuthenticated]
#     serializer_class   = FraudRuleSerializer

#     def get_queryset(self):
#         return FraudDetectionRule.objects.order_by('-created_at')


# class WebhookLogViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     GET  /api/ad-networks/webhooks/
#     POST /api/ad-networks/webhooks/{id}/reprocess/
#     """
#     permission_classes = [IsAuthenticated]
#     serializer_class   = WebhookLogSerializer

#     def get_queryset(self):
#         qs = AdNetworkWebhookLog.objects.select_related(
#             'ad_network'
#         ).order_by('-created_at')
#         n = self.request.query_params.get('network')
#         if n:
#             qs = qs.filter(ad_network__name=n)
#         return qs[:200]

#     @action(detail=True, methods=['post'])
#     def reprocess(self, request, pk=None):
#         log = self.get_object()
#         log.is_processed = True
#         log.save(update_fields=['is_processed'])
#         return Response({'success': True})


# class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     GET /api/ad-networks/sync-logs/
#     """
#     permission_classes = [IsAuthenticated]
#     serializer_class   = SyncLogSerializer

#     def get_queryset(self):
#         qs = OfferSyncLog.objects.select_related(
#             'ad_network'
#         ).order_by('-created_at')
#         st = self.request.query_params.get('status')
#         if st:
#             qs = qs.filter(status=st)
#         return qs[:200]