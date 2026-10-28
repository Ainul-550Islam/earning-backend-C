# api/djoyalty/viewsets/advanced/SmartLinkViewSet.py
"""
SmartLinkViewSet -- geo-targeted short URL API.

Exposes SmartLinkService which was fully built but had ZERO API endpoints.

Endpoints:
  GET  /smart-links/               -- admin: list all links
  GET  /smart-links/{id}/          -- detail
  POST /smart-links/create/        -- admin: create a smart link
  GET  /smart-links/{slug}/resolve/ -- public: resolve URL (geo/device routing)
  POST /smart-links/{slug}/click/  -- public: record a click
  GET  /smart-links/{slug}/stats/  -- admin: click statistics
  GET  /smart-links/my-links/      -- customer: own smart links
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...throttles import DjoyaltyUserThrottle, DjoyaltyBurstThrottle
from ...services.SmartLinkService import SmartLinkService
from ...mixins import DjoyaltyBaseViewSet


class SmartLinkViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = DjoyaltyPagePagination
    throttle_classes = [DjoyaltyUserThrottle]

    def get_queryset(self):
        from ...models.catalog import SmartLink
        qs = SmartLink.objects.all().select_related('customer', 'tenant')
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            # Customers see only their own links
            qs = qs.filter(customer__user=self.request.user)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        # Use a basic serializer; project may have SmartLinkSerializer
        try:
            from ...serializers.CatalogSerializer import SmartLinkSerializer
            return SmartLinkSerializer
        except ImportError:
            from rest_framework import serializers
            from ...models.catalog import SmartLink

            class _SmartLinkSerializer(serializers.ModelSerializer):
                class Meta:
                    model = SmartLink
                    fields = [
                        'id', 'slug', 'name', 'default_url',
                        'is_active', 'total_clicks', 'unique_clicks',
                        'total_conversions', 'valid_from', 'valid_until',
                        'created_at',
                    ]
            return _SmartLinkSerializer

    @action(
        detail=False,
        methods=['post'],
        url_path='create',
        permission_classes=[IsLoyaltyAdmin],
    )
    def create_link(self, request):
        """Admin or customer: create a new SmartLink."""
        customer_id = request.data.get('customer_id')
        customer = None
        if customer_id:
            from ...models.core import Customer
            customer = get_object_or_404(Customer, pk=customer_id)

        link = SmartLinkService.create(
            customer=customer,
            tenant=getattr(request, 'tenant', None),
            name=request.data.get('name', ''),
            default_url=request.data.get('default_url', ''),
            geo_rules=request.data.get('geo_rules', []),
            linked_offer_id=request.data.get('linked_offer_id'),
            linked_campaign_id=request.data.get('linked_campaign_id'),
            slug=request.data.get('slug', ''),
        )
        serializer_class = self.get_serializer_class()
        return Response(
            serializer_class(link).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=['get'],
        url_path=r'resolve/(?P<slug>[A-Z0-9]+)',
        permission_classes=[AllowAny],
        throttle_classes=[DjoyaltyBurstThrottle],
    )
    def resolve(self, request, slug=None):
        """
        Public: resolve a SmartLink slug to its destination URL.
        Applies geo and device routing rules.
        """
        country = request.query_params.get('country', '')
        device = request.query_params.get('device', '')
        url = SmartLinkService.resolve(
            slug=slug.upper(),
            country=country,
            device=device,
        )
        if not url:
            return Response(
                {'error': 'SmartLink not found or expired.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'slug': slug.upper(), 'destination_url': url})

    @action(
        detail=False,
        methods=['post'],
        url_path=r'click/(?P<slug>[A-Z0-9]+)',
        permission_classes=[AllowAny],
        throttle_classes=[DjoyaltyBurstThrottle],
    )
    def record_click(self, request, slug=None):
        """
        Public: record a click on a SmartLink.
        Called by redirect middleware or client SDK.
        """
        ip = request.META.get('REMOTE_ADDR', '')
        country = request.data.get('country_code', '')
        device = request.data.get('device_type', '')
        ua = request.META.get('HTTP_USER_AGENT', '')

        recorded = SmartLinkService.record_click(
            slug=slug.upper(),
            ip_address=ip,
            country_code=country,
            device_type=device,
            user_agent=ua,
        )
        if not recorded:
            return Response(
                {'error': 'SmartLink not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'recorded': True})

    @action(
        detail=False,
        methods=['get'],
        url_path=r'stats/(?P<slug>[A-Z0-9]+)',
        permission_classes=[IsLoyaltyAdmin],
    )
    def stats(self, request, slug=None):
        """Admin: click statistics for a SmartLink."""
        data = SmartLinkService.get_stats(slug.upper())
        if not data:
            return Response(
                {'error': 'SmartLink not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)

    @action(
        detail=False,
        methods=['get'],
        url_path='my-links',
    )
    def my_links(self, request):
        """Customer: list own SmartLinks."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            # Fallback: look up by user
            from ...models.core import Customer
            customer = Customer.objects.filter(user=request.user).first()
        if not customer:
            return Response({'links': []})
        from ...models.catalog import SmartLink
        qs = SmartLink.objects.filter(customer=customer).order_by('-created_at')
        serializer_class = self.get_serializer_class()
        return Response(serializer_class(qs, many=True).data)
    @action(detail=True, methods=['get'], url_path='clicks', permission_classes=[IsLoyaltyAdmin])
    def clicks(self, request, pk=None):
        """
        FIXED: SmartLinkClick had NO API endpoint -- click analytics
        only visible in DB directly. Now queryable via API.
        """
        from ...models.catalog import SmartLinkClick
        from django.shortcuts import get_object_or_404
        from ...models.catalog import SmartLink
        link = get_object_or_404(SmartLink, pk=pk)
        qs   = SmartLinkClick.objects.filter(smart_link=link).order_by('-clicked_at')[:200]
        return Response({
            'smart_link_id': link.pk,
            'total_clicks':  qs.count(),
            'clicks': [{
                'id': c.id, 'ip_address': c.ip_address,
                'customer_code': c.customer.code if c.customer else None,
                'clicked_at': str(c.clicked_at),
                'converted': getattr(c, 'converted', False),
            } for c in qs],
        })
