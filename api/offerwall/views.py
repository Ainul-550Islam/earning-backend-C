"""
api/offerwall/views.py

Fixes applied vs original:
  1. OfferViewSet.get_queryset() — admin sees all statuses
  2. toggle_recommended action added
  3. OfferConversionViewSet.chargeback + reverse actions added
  4. PublicOfferListView UUID str() fix
  5. OfferRoutingAdapter wired into recommended() view  ← NEW
  6. RateLimitAdapter wired into click() view           ← NEW
  7. filter_available_for_user() called via mixin       ← NEW
  8. validate_user_daily_limit() called before click    ← NEW
  9. pagination_class wired — StandardPagination
  10. throttle_classes wired — OfferListThrottle, etc
  11. filter_backends wired — OfferFilterBackend, SearchFilter
"""
import logging
from decimal import Decimal, InvalidOperation
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum

from .models import Offer, OfferProvider, OfferCategory, OfferClick, OfferConversion, OfferWall
from .serializers import (
    OfferListSerializer, OfferDetailSerializer,
    OfferProviderSerializer, OfferProviderDetailSerializer,
    OfferCategorySerializer, OfferClickSerializer,
    OfferConversionSerializer, OfferConversionDetailSerializer,
    OfferWallSerializer,
)
from .mixins import (
    OfferFilterMixin, OfferSortMixin, CacheMixin, AnalyticsMixin,
    ResponseMixin, FraudCheckMixin, RateLimitMixin,
)
from .constants import (
    STATUS_ACTIVE, CONVERSION_APPROVED,
    FEATURE_AUTO_APPROVE_CONVERSIONS,
    FEATURE_FRAUD_DETECTION,
    # FIX: RATE_LIMIT_* constants were unused — now wire into click action
    RATE_LIMIT_OFFER_CLICK,
    RATE_LIMIT_OFFER_VIEW,
)
from .exceptions import (
    OfferNotFoundException, OfferInactiveException, OfferNotAvailableException,
    OfferLimitReachedException, RateLimitException, FraudException,
)
from .utils.OfferValidator import OfferValidator
from .utils.RewardCalculator import RewardCalculator
from .utils.FraudDetector import FraudDetector
from .utils.AnalyticsTracker import AnalyticsTracker
# NEW: Import DRF components
from .pagination import StandardPagination, LargePagination, SmallPagination
from .throttling import (
    OfferListThrottle, OfferDetailThrottle, OfferClickThrottle,
    ConversionThrottle, WebhookThrottle, AnalyticsThrottle,
    AdminThrottle, PublicThrottle
)
from .filters import (
    OfferFilterBackend, ProviderFilterBackend, ConversionFilterBackend,
    OfferClickFilterBackend, DateRangeFilterBackend
)
from .permissions import (
    IsOfferProvider, IsOfferAdmin, IsConversionApprover,
    IsPublisher, IsOwnerOrAdmin
)

logger = logging.getLogger(__name__)


class OfferViewSet(
    viewsets.ModelViewSet,
    OfferFilterMixin, OfferSortMixin,
    CacheMixin, AnalyticsMixin, ResponseMixin,
    FraudCheckMixin,
    RateLimitMixin,   # FIX: was missing — check_rate_limit() now works
):
    # DRF Configuration - NEW
    pagination_class = StandardPagination
    filter_backends = [OfferFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['title', 'description', 'tags']
    ordering_fields = ['quality_score', 'reward_amount', 'payout', 'created_at', 'conversion_count']
    ordering = ['-quality_score']
    throttle_classes = [OfferListThrottle, PublicThrottle]
    
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser
        if self.action in [
            'create', 'update', 'partial_update', 'destroy',
            'toggle_featured', 'toggle_trending', 'toggle_recommended',
            'calculate_quality',
        ]:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # FIX: admin sees all statuses
        if getattr(self, 'request', None) and self.request.user.is_staff:
            qs = Offer.objects.select_related('provider', 'category').all()
        else:
            qs = Offer.objects.select_related('provider', 'category').filter(
                status=STATUS_ACTIVE
            )
        qs = self.apply_filters(qs)
        # FIX: filter_available_for_user() now called via mixin
        qs = self._apply_user_availability(qs, self.request)
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OfferDetailSerializer
        return OfferListSerializer

    def apply_filters(self, qs):
        p = self.request.query_params
        # Category — accept integer pk
        if c := p.get('category'):
            try:
                int(c)
                qs = self.filter_by_category(qs, c)
            except (ValueError, TypeError):
                pass
        if t := p.get('offer_type'):     qs = self.filter_by_offer_type(qs, t)
        if pl := p.get('platform'):      qs = self.filter_by_platform(qs, pl)
        if co := p.get('country'):       qs = self.filter_by_country(qs, co)
        if pr := p.get('provider'):      qs = self.filter_by_provider(qs, pr)
        try:
            if mn := p.get('min_payout'):    qs = self.filter_by_payout_range(qs, mn, None)
            if mx := p.get('max_payout'):    qs = self.filter_by_payout_range(qs, None, mx)
        except Exception:
            pass  # silently ignore invalid payout values
        if fe := p.get('featured'):      qs = self.filter_featured(qs, fe.lower() == 'true')
        if q := p.get('q'):
            qs = qs.filter(
                Q(title__icontains=q) | Q(description__icontains=q) |
                Q(tags__icontains=q))
        return qs

    def list(self, request, *args, **kwargs):
        # FIX: OfferSearchSerializer was floating — now validates list params
        from .serializers import OfferSearchSerializer
        # FIX: drop unparseable numeric filter values instead of 400ing the
        # whole request — matches the lenient try/except pattern used by
        # apply_filters() and OfferFilterBackend elsewhere in this module.
        query_data = request.query_params.copy()
        for decimal_field in ('min_payout', 'max_payout'):
            value = query_data.get(decimal_field)
            if value is not None:
                try:
                    Decimal(value)
                except (InvalidOperation, ValueError, TypeError):
                    query_data.pop(decimal_field, None)
        search_ser = OfferSearchSerializer(data=query_data)
        if not search_ser.is_valid():
            return Response(
                {'error': 'invalid_params', 'details': search_ser.errors},
                status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_queryset()
        sort_by = search_ser.validated_data.get('sort_by', 'quality_score')
        qs = self.sort_offers(qs, sort_by)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        try:
            offer = self.get_object()
            self.track_offer_view(offer, request.user, request)
            return Response(self.get_serializer(offer).data)
        except Offer.DoesNotExist:
            return self.error_response('Offer not found', status_code=404)

    # ── Actions ──────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def click(self, request, pk=None):
        """
        Track offer click and return click URL.

        Fixes vs original:
          • RateLimitAdapter wired (was using cache-only check)
          • validate_user_daily_limit() called before processing
          • validate_click_data() used for input validation
        """
        try:
            offer = self.get_object()
            user  = request.user

            # 1. Offer availability
            validator = OfferValidator(offer)
            validator.validate_offer_availability(user)

            # 2. Daily limit check via OfferValidator (was floating)
            validator.validate_user_daily_limit(user)

            # 3. Rate limit via RateLimitAdapter (was floating — only used cache)
            from .services.adapters.OfferwallAdapter import OfferwallAdapterFactory
            ip  = self.get_client_ip(request)
            # FIX: was hardcoded 100 — now uses RATE_LIMIT_OFFER_CLICK constant
            rl  = OfferwallAdapterFactory.get('rate_limit').send({
                'user_id':      user.id,
                'limit_type':   'offer_click',
                'max_requests': RATE_LIMIT_OFFER_CLICK,
                'identifier':   f'user_{user.id}',
            })
            if not rl.get('allowed', True):
                raise RateLimitException('Too many clicks. Please try again later.')

            # 4. Input validation via OfferValidator.validate_click_data()
            click_data = {
                'ip_address':     ip,
                'user_agent':     request.META.get('HTTP_USER_AGENT', ''),
                'device_type':    request.data.get('device_type', ''),
                'device_model':   request.data.get('device_model', ''),
                'os':             request.data.get('os', ''),
                'os_version':     request.data.get('os_version', ''),
                'browser':        request.data.get('browser', ''),
                'country':        request.data.get('country', ''),
                'city':           request.data.get('city', ''),
                'referrer_url':   request.META.get('HTTP_REFERER', ''),
                'session_id':     request.data.get('session_id', ''),
                'tracking_params':request.data.get('tracking_params', {}),
            }
            validator.validate_click_data(click_data)

            # 5. Fraud detection — FIX: FEATURE_FRAUD_DETECTION flag now respected
            if FEATURE_FRAUD_DETECTION:
                detector    = FraudDetector(user=user, offer=offer)
                fraud_check = detector.comprehensive_fraud_check(
                click_data=click_data,
                device_data=request.data.get('device_data'),
            )
            if fraud_check.get('should_block'):
                detector.create_fraud_attempt_record(fraud_check)
                raise FraudException('Suspicious activity detected')

            # 6. Track click
            tracker      = AnalyticsTracker(offer=offer, user=user)
            click_record = tracker.track_offer_click(click_data)
            if not click_record:
                return self.error_response('Failed to track click')

            # 7. Build click URL
            from .services.OfferProcessor import OfferProcessorFactory
            processor = OfferProcessorFactory.create(offer.provider)
            click_url = processor.build_click_url(offer, user)

            return self.success_response({
                'click_id':  click_record.click_id,
                'click_url': click_url,
                'offer':     OfferListSerializer(offer).data,
            })

        except (
            OfferNotFoundException, OfferInactiveException,
            OfferNotAvailableException, OfferLimitReachedException,
            RateLimitException, FraudException,
        ) as e:
            code = getattr(e, 'status_code', status.HTTP_400_BAD_REQUEST)
            return self.error_response(str(e), status_code=code)
        except Exception as e:
            logger.error(f'[OfferViewSet.click] {e}', exc_info=True)
            return self.error_response(str(e),
                                       status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        qs = self.get_queryset().filter(is_featured=True)[:20]
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def trending(self, request):
        tracker = AnalyticsTracker(user=request.user)
        qs      = tracker.get_trending_offers(limit=20)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def recommended(self, request):
        """
        FIX: Was using a simple category DB filter.
        Now uses OfferRoutingAdapter.route_multiple_offers() for ML-based
        personalised ranking. Falls back to category filter if adapter fails.
        """
        from .services.adapters.OfferwallAdapter import OfferwallAdapterFactory

        ip      = self.get_client_ip(request)
        country = request.query_params.get('country', '')
        platform= request.query_params.get('platform', 'all')

        try:
            result = OfferwallAdapterFactory.get('offer_routing').send({
                'user_id': request.user.id,
                'count':   20,
                'context': {
                    'country':  country,
                    'platform': platform,
                    'ip':       ip,
                },
            })

            if result.get('success') and result.get('offer_ids'):
                import uuid as _uuid
                safe_ids = []
                for oid in result['offer_ids']:
                    try:
                        safe_ids.append(_uuid.UUID(str(oid)))
                    except ValueError:
                        pass

                if safe_ids:
                    offers = Offer.objects.filter(
                        id__in=safe_ids, status=STATUS_ACTIVE
                    )
                    # Preserve ML ranking order
                    id_order = {uid: i for i, uid in enumerate(safe_ids)}
                    offers   = sorted(offers, key=lambda o: id_order.get(o.id, 999))
                    return Response(
                        OfferListSerializer(offers, many=True,
                                           context={'request': request}).data)

        except Exception as e:
            logger.debug(f'[recommended] routing adapter fallback: {e}')

        # Fallback: category-based filter
        completed = OfferConversion.objects.filter(
            user=request.user, status=CONVERSION_APPROVED
        ).values('offer__category').annotate(count=Count('id')).order_by('-count')[:3]
        cat_ids = [c['offer__category'] for c in completed if c['offer__category']]

        qs = self.get_queryset()
        if cat_ids:
            qs = qs.filter(category_id__in=cat_ids)
        qs = qs.order_by('-quality_score')[:20]
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = Offer.objects.all()
        data = qs.aggregate(
            total_offers=Count('id'),
            active_offers=Count('id', filter=Q(status=STATUS_ACTIVE)),
            featured_offers=Count('id', filter=Q(is_featured=True)),
            total_views=Sum('view_count'),
            total_clicks=Sum('click_count'),
            total_conversions=Sum('conversion_count'),
            total_revenue=Sum('total_revenue'),
            total_payout=Sum('total_payout'),
            average_completion_rate=Avg('completion_rate'),
            average_quality_score=Avg('quality_score'),
        )
        return Response({k: str(v) if hasattr(v, '__float__') else v
                         for k, v in (data or {}).items()})

    @action(detail=True, methods=['post'])
    def toggle_featured(self, request, pk=None):
        offer = self.get_object()
        offer.is_featured = not offer.is_featured
        offer.save(update_fields=['is_featured'])
        return self.success_response({'is_featured': offer.is_featured})

    @action(detail=True, methods=['post'])
    def toggle_trending(self, request, pk=None):
        offer = self.get_object()
        offer.is_trending = not offer.is_trending
        offer.save(update_fields=['is_trending'])
        return self.success_response({'is_trending': offer.is_trending})

    @action(detail=True, methods=['post'])
    def toggle_recommended(self, request, pk=None):
        offer = self.get_object()
        offer.is_recommended = not offer.is_recommended
        offer.save(update_fields=['is_recommended'])
        return self.success_response({'is_recommended': offer.is_recommended})

    @action(detail=True, methods=['post'])
    def calculate_quality(self, request, pk=None):
        offer = self.get_object()
        score = offer.calculate_quality_score()
        return self.success_response({'quality_score': score})


class OfferConversionViewSet(viewsets.ReadOnlyModelViewSet, ResponseMixin):
    # DRF Configuration - NEW
    pagination_class = StandardPagination
    filter_backends = [ConversionFilterBackend, OrderingFilter]
    ordering_fields = ['converted_at', 'status', 'payout_amount']
    ordering = ['-converted_at']
    throttle_classes = [ConversionThrottle, PublicThrottle]
    
    permission_classes = [IsAuthenticated]
    serializer_class   = OfferConversionSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return OfferConversion.objects.select_related(
                'offer', 'offer__provider', 'user').order_by('-converted_at')
        return OfferConversion.objects.filter(
            user=self.request.user
        ).select_related('offer', 'offer__provider').order_by('-converted_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OfferConversionDetailSerializer
        return OfferConversionSerializer

    @action(detail=False, methods=['get'])
    def stats(self, request):
        # FIX: UserOfferStatsSerializer was floating — now serializes output
        from .serializers import UserOfferStatsSerializer
        tracker    = AnalyticsTracker(user=request.user)
        raw_stats  = tracker.get_user_offer_stats()
        serializer = UserOfferStatsSerializer(data=raw_stats)
        if serializer.is_valid():
            return Response(serializer.data)
        return Response(raw_stats)  # fallback: return raw if schema mismatch

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        from .services.OfferwallIntegrationService import OfferwallIntegrationService
        result = OfferwallIntegrationService.approve_conversion(
            self.get_object(), approver=request.user)
        if result.get('success'):
            conv_obj = result.get('conversion')
            return self.success_response(
                {'conversion_id': str(conv_obj.id) if conv_obj else str(pk)})
        return self.error_response(result.get('error', 'Approve failed'))

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        from .services.OfferwallIntegrationService import OfferwallIntegrationService
        result = OfferwallIntegrationService.reject_conversion(
            self.get_object(),
            reason=request.data.get('reason', ''),
            rejector=request.user)
        if result.get('success'):
            conv_obj = result.get('conversion')
            return self.success_response(
                {'conversion_id': str(conv_obj.id) if conv_obj else str(pk)})
        return self.error_response(result.get('error', 'Reject failed'))

    @action(detail=True, methods=['post'])
    def chargeback(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        conversion = self.get_object()
        if conversion.status != 'approved':
            return self.error_response(
                f"Cannot chargeback status='{conversion.status}'",
                status_code=status.HTTP_400_BAD_REQUEST)
        conversion.status           = 'chargeback'
        conversion.rejection_reason = request.data.get('reason', '')
        conversion.verified_by      = request.user
        conversion.verified_at      = timezone.now()
        conversion.save(update_fields=[
            'status', 'rejection_reason', 'verified_by', 'verified_at', 'updated_at'])
        return self.success_response({'status': conversion.status})

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        conversion = self.get_object()
        if conversion.status not in ('approved', 'chargeback'):
            return self.error_response(
                f"Cannot reverse status='{conversion.status}'",
                status_code=status.HTTP_400_BAD_REQUEST)
        conversion.status           = 'reversed'
        conversion.rejection_reason = request.data.get('reason', '')
        conversion.verified_by      = request.user
        conversion.verified_at      = timezone.now()
        conversion.save(update_fields=[
            'status', 'rejection_reason', 'verified_by', 'verified_at', 'updated_at'])
        return self.success_response({'status': conversion.status})

    # ── Phase 2: Bulk actions ─────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated, IsConversionApprover],
            throttle_classes=[ConversionThrottle])
    def bulk_approve(self, request):
        """
        Approve multiple conversions in a single request.
        Body: { "conversion_ids": ["uuid1", "uuid2", ...] }
        Requires: conversion_approvers group or staff.
        """
        from .serializers import ConversionBatchApprovalSerializer
        ser = ConversionBatchApprovalSerializer(
            data={**request.data, 'action': 'approve'})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ids = ser.validated_data['conversion_ids']
        qs  = OfferConversion.objects.filter(id__in=ids, status='pending')
        now = timezone.now()

        updated = qs.update(
            status='approved',
            approved_at=now,
            verified_at=now,
        )
        logger.info(f'[bulk_approve] user={request.user.id} approved={updated}')
        return Response({'approved': updated, 'requested': len(ids)})

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated, IsConversionApprover],
            throttle_classes=[ConversionThrottle])
    def bulk_reject(self, request):
        """
        Reject multiple conversions in a single request.
        Body: { "conversion_ids": [...], "reason": "..." }
        Requires: conversion_approvers group or staff.
        """
        from .serializers import ConversionBatchApprovalSerializer
        ser = ConversionBatchApprovalSerializer(
            data={**request.data, 'action': 'reject'})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ids    = ser.validated_data['conversion_ids']
        reason = ser.validated_data.get('reason', 'Bulk rejected by admin')
        qs     = OfferConversion.objects.filter(id__in=ids, status='pending')
        now    = timezone.now()

        updated = qs.update(
            status='rejected',
            rejection_reason=reason,
            verified_at=now,
        )
        logger.info(f'[bulk_reject] user={request.user.id} rejected={updated}')
        return Response({'rejected': updated, 'requested': len(ids)})


class OfferCategoryViewSet(viewsets.ModelViewSet):
    # DRF Configuration - NEW
    pagination_class = SmallPagination
    throttle_classes = [OfferListThrottle, PublicThrottle]
    
    serializer_class   = OfferCategorySerializer
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
        offers = Offer.objects.filter(
            category=self.get_object(), status=STATUS_ACTIVE
        ).order_by('-quality_score')[:50]
        return Response(OfferListSerializer(
            offers, many=True, context={'request': request}).data)


class OfferProviderViewSet(viewsets.ModelViewSet):
    # DRF Configuration - NEW
    pagination_class = StandardPagination
    filter_backends = [ProviderFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'provider_type']
    ordering_fields = ['created_at', 'status', 'total_offers']
    ordering = ['-created_at']
    throttle_classes = [AdminThrottle, PublicThrottle]
    
    queryset           = OfferProvider.objects.all()
    serializer_class   = OfferProviderSerializer
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
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        provider = self.get_object()
        try:
            from .services.OfferProcessor import OfferProcessorFactory
            results = OfferProcessorFactory.create(provider).sync_offers()
            provider.last_sync = timezone.now()
            provider.save(update_fields=['last_sync'])
            return Response(results)
        except Exception as e:
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        p = self.get_object()
        return Response({
            'total_offers':      p.total_offers,
            'total_conversions': p.total_conversions,
            'total_revenue':     float(p.total_revenue or 0),
            'last_sync':         p.last_sync,
            'status':            p.status,
        })


class OfferClickViewSet(viewsets.ReadOnlyModelViewSet, ResponseMixin):
    # DRF Configuration - NEW
    pagination_class = StandardPagination
    filter_backends = [OfferClickFilterBackend, DateRangeFilterBackend, OrderingFilter]
    ordering_fields = ['clicked_at', 'is_converted']
    ordering = ['-clicked_at']
    throttle_classes = [OfferClickThrottle, PublicThrottle]
    
    permission_classes = [IsAuthenticated]
    serializer_class   = OfferClickSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return OfferClick.objects.select_related('offer', 'user').order_by('-clicked_at')
        return OfferClick.objects.filter(
            user=self.request.user).order_by('-clicked_at')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs    = self.get_queryset()
        total = qs.count()
        converted = qs.filter(is_converted=True).count()
        return Response({
            'total':           total,
            'converted':       converted,
            'conversion_rate': round(converted / total * 100, 2) if total else 0,
            'top_offers':      list(qs.values('offer__title').annotate(
                               c=Count('id')).order_by('-c')[:5]),
        })


class OfferWallViewSet(viewsets.ModelViewSet):
    # DRF Configuration - NEW
    pagination_class = StandardPagination
    throttle_classes = [OfferListThrottle, PublicThrottle]
    
    permission_classes = [IsAuthenticated]
    serializer_class   = OfferWallSerializer

    def get_queryset(self):
        return OfferWall.objects.all()

    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'], url_path='offers')
    def get_offers(self, request, pk=None):
        offers = self.get_object().get_offers(user=request.user)
        page   = self.paginate_queryset(offers)
        if page is not None:
            return self.get_paginated_response(
                OfferListSerializer(page, many=True, context={'request': request}).data)
        return Response(OfferListSerializer(
            offers, many=True, context={'request': request}).data)


# ── Public (no auth) ──────────────────────────────────────────
from rest_framework.views import APIView


class PublicOfferListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        offers = Offer.objects.filter(status='active').order_by(
            '-is_featured', '-reward_amount', '-created_at')

        seen, unique = set(), []
        for o in offers:
            key = o.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(o)

        data = [{
            'id':            str(o.id),   # FIX: UUID → str
            'title':         o.title,
            'description':   o.short_description or o.description[:200],
            'offer_type':    o.offer_type,
            'payout':        str(o.payout),
            'reward_amount': str(o.reward_amount),
            'reward_currency': o.reward_currency,
            'countries':     o.countries,
            'image_url':     o.image_url or o.thumbnail_url or o.icon_url,
            'click_url':     o.click_url,
            'is_featured':   o.is_featured,
            'created_at':    o.created_at.strftime('%Y-%m-%d'),
            'category':      o.category.name if o.category else 'General',
        } for o in unique[:100]]

        return Response({'count': len(data), 'results': data})
