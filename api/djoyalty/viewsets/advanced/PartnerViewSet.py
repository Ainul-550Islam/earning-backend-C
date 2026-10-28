# api/djoyalty/viewsets/advanced/PartnerViewSet.py
"""
PartnerViewSet -- Partner Merchant CRUD + coalition earn API।
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal

from ...models.campaigns import PartnerMerchant
from ...models.advanced import CoalitionEarn
from ...serializers.PartnerSerializer import (
    PartnerMerchantSerializer, PartnerMerchantAdminSerializer, CoalitionEarnSerializer
)
from ...services.PartnerMerchantService import PartnerMerchantService
from ...services.CoalitionEarnService import CoalitionEarnService
from ...permissions import IsLoyaltyAdmin, IsPublicAPIClient
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyTenantMixin
from ...mixins import DjoyaltyBaseViewSet


class PartnerViewSet(DjoyaltyBaseViewSet, DjoyaltyTenantMixin, viewsets.ModelViewSet):
    """
    Partner Merchant CRUD + Coalition Earn API।
    GET  /partners/               -- list all active partners
    GET  /partners/{id}/          -- partner detail
    POST /partners/               -- create partner (admin)
    PUT  /partners/{id}/          -- update partner (admin)
    POST /partners/{id}/earn/     -- process earn at partner (public API key)
    POST /partners/{id}/sync/     -- sync partner (admin)
    GET  /partners/{id}/stats/    -- partner earn statistics (admin)
    GET  /partners/coalition_history/ -- customer coalition earn history
    POST /partners/reverse_earn/  -- reverse a coalition earn (admin)
    """
    permission_classes = [IsAuthenticated]
    queryset = PartnerMerchant.objects.all().order_by('name')
    serializer_class = PartnerMerchantSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'category', 'api_key']
    ordering_fields = ['name', 'earn_rate', 'created_at']

    def get_serializer_class(self):
        if self.request.user and self.request.user.is_staff:
            return PartnerMerchantAdminSerializer
        return PartnerMerchantSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        category = self.request.query_params.get('category')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        if category:
            qs = qs.filter(category__icontains=category)
        return qs

    @action(detail=True, methods=['post'])
    def earn(self, request, pk=None):
        """
        Process earn at partner।
        Body: { customer_code, spend_amount, reference, currency }
        Requires X-Loyalty-API-Key header or api_key in body।
        """
        partner = self.get_object()
        api_key = (
            request.META.get('HTTP_X_LOYALTY_API_KEY')
            or request.data.get('api_key', '')
        )
        if api_key != partner.api_key:
            return self.forbidden('Invalid API key for this partner.')

        customer_code = request.data.get('customer_code', '')
        spend_amount = request.data.get('spend_amount', 0)
        reference = request.data.get('reference', '')
        currency = request.data.get('currency', 'BDT')
        description = request.data.get('description', '')

        if not customer_code or not reference:
            return self.err('customer_code and reference are required.')

        try:
            from ...models.core import Customer
            customer = get_object_or_404(Customer, code=customer_code.strip().upper(), is_active=True)
            earn = PartnerMerchantService.process_partner_earn(
                customer=customer,
                partner=partner,
                spend_amount=Decimal(str(spend_amount)),
                reference=reference,
                currency=currency,
                description=description,
                tenant=getattr(request, 'tenant', None),
            )
            return Response({
                'success': True,
                'customer_code': customer.code,
                'points_earned': str(earn.points_earned),
                'reference': earn.reference,
                'status': earn.status,
                'partner': partner.name,
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))
        except Exception as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def sync(self, request, pk=None):
        """Sync partner last_sync_at।"""
        partner = self.get_object()
        ok = PartnerMerchantService.sync_partner(partner)
        if ok:
            return Response({'message': f'Partner {partner.name} synced.', 'last_sync_at': str(partner.last_sync_at)})
        return self.err('Sync failed.', http_status=500)

    @action(detail=True, methods=['get'], permission_classes=[IsLoyaltyAdmin])
    def stats(self, request, pk=None):
        """Partner earn statistics।"""
        partner = self.get_object()
        stats = PartnerMerchantService.get_partner_stats(partner)
        return Response(stats)

    @action(detail=False, methods=['get'])
    def coalition_history(self, request):
        """Customer এর coalition earn history।"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required.')
        from ...models.core import Customer
        customer = get_object_or_404(Customer, pk=customer_id)
        limit = int(request.query_params.get('limit', 50))
        history = CoalitionEarnService.get_customer_coalition_history(customer, limit=limit)
        summary = CoalitionEarnService.get_coalition_summary(customer)
        return Response({
            'summary': summary,
            'history': CoalitionEarnSerializer(history, many=True).data,
        })

    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def reverse_earn(self, request):
        """Admin: coalition earn reverse করো।"""
        reference = request.data.get('reference', '')
        if not reference:
            return self.err('reference required.')
        reversed_by = str(request.user)
        ok = CoalitionEarnService.reverse_earn(reference, reversed_by=reversed_by)
        if ok:
            return Response({'success': True, 'message': f'Earn {reference} reversed by {reversed_by}.'})
        return Response({'error': f'Could not reverse earn: {reference}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """All active partner merchants।"""
        qs = self.get_queryset().filter(is_active=True)
        return Response(self.get_serializer(qs, many=True).data)
