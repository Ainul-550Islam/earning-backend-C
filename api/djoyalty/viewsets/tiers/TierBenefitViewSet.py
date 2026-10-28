# api/djoyalty/viewsets/tiers/TierBenefitViewSet.py
"""
TierBenefitViewSet -- Tier benefits API।

FIXED: TierBenefitService (services/tiers/TierBenefitService.py) was
fully built but had NO viewset, NO router entry।
Added to routers.py: router.register(r'tier-benefits', TierBenefitViewSet, ...)

Endpoints:
  GET  /tier-benefits/                            -- all benefit definitions
  GET  /tier-benefits/{id}/                       -- single benefit detail
  GET  /tier-benefits/by-tier/{tier_id}/          -- benefits for a specific tier
  GET  /tier-benefits/my-benefits/                -- current customer's active benefits
  GET  /tier-benefits/customer/{id}/benefits/     -- specific customer's benefits
  POST /tier-benefits/check-access/               -- check if customer has benefit
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ...models.tiers import LoyaltyTier, TierBenefit
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...services.tiers.TierBenefitService import TierBenefitService
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class TierBenefitSerializer:
    """Inline serializer -- avoids circular import with serializers package."""
    @staticmethod
    def to_dict(benefit) -> dict:
        return {
            'id':           benefit.id,
            'tier_id':      benefit.tier_id,
            'tier_name':    benefit.tier.name if benefit.tier else '',
            'benefit_type': benefit.benefit_type,
            'name':         benefit.name,
            'description':  getattr(benefit, 'description', ''),
            'value':        str(getattr(benefit, 'value', '')),
            'icon':         getattr(benefit, 'icon', ''),
            'is_active':    benefit.is_active,
            'sort_order':   getattr(benefit, 'sort_order', 0),
        }


class TierBenefitViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class   = DjoyaltyPagePagination

    # ── All benefits (admin catalog) ──────────────────────────────────────────
    def list(self, request):
        """All TierBenefit definitions -- admin view।"""
        qs = TierBenefit.objects.filter(is_active=True).select_related('tier').order_by(
            'tier__rank', 'sort_order', 'benefit_type'
        )
        tier_id = request.query_params.get('tier_id')
        if tier_id:
            qs = qs.filter(tier_id=tier_id)
        return Response({
            'count':   qs.count(),
            'results': [TierBenefitSerializer.to_dict(b) for b in qs],
        })

    def retrieve(self, request, pk=None):
        """Single benefit detail।"""
        from django.shortcuts import get_object_or_404
        b = get_object_or_404(TierBenefit, pk=pk)
        return Response(TierBenefitSerializer.to_dict(b))

    # ── By tier ────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='by-tier/(?P<tier_id>[0-9]+)')
    def by_tier(self, request, tier_id=None):
        """
        All benefits for a specific tier।
        FIXED: TierBenefitService.get_benefits_for_tier() was defined
        but no API called it。
        """
        from django.shortcuts import get_object_or_404
        tier = get_object_or_404(LoyaltyTier, pk=tier_id)
        benefits = TierBenefitService.get_benefits_for_tier(tier_id=tier_id)
        return Response({
            'tier_id':   tier_id,
            'tier_name': tier.name,
            'benefits':  [TierBenefitSerializer.to_dict(b) for b in benefits],
        })

    # ── Customer's current benefits ───────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='my-benefits')
    def my_benefits(self, request):
        """
        Current customer's active tier benefits।
        FIXED: TierBenefitService.get_benefits_for_customer() was defined
        but no API called it。 Customers had no way to see their benefits。
        """
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        customer = get_object_or_404(Customer, pk=customer_id)

        benefits  = TierBenefitService.get_benefits_for_customer(customer)
        user_tier = None
        try:
            ut = customer.user_tiers.filter(is_current=True).first()
            if ut:
                user_tier = {'id': ut.tier.id, 'name': ut.tier.name, 'rank': ut.tier.rank}
        except Exception:
            pass

        return Response({
            'customer_id': customer_id,
            'current_tier': user_tier,
            'benefits': [TierBenefitSerializer.to_dict(b) for b in benefits],
            'benefit_count': len(benefits),
        })

    # ── Specific customer's benefits ─────────────────────────────────────────
    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/benefits',
            permission_classes=[IsLoyaltyAdmin])
    def customer_benefits(self, request, customer_id=None):
        """Admin: get benefits for any customer।"""
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        customer = get_object_or_404(Customer, pk=customer_id)
        benefits = TierBenefitService.get_benefits_for_customer(customer)
        return Response({
            'customer_code': customer.code,
            'benefits': [TierBenefitSerializer.to_dict(b) for b in benefits],
        })

    # ── Check access ──────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='check-access')
    def check_access(self, request):
        """
        Check if a customer has access to a specific benefit type。
        Useful for gating premium features in the app。
        Body: { "customer_id": 1, "benefit_type": "free_shipping" }
        """
        customer_id  = request.data.get('customer_id')
        benefit_type = request.data.get('benefit_type')
        if not customer_id or not benefit_type:
            return Response(
                {'error': 'customer_id and benefit_type required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        customer = get_object_or_404(Customer, pk=customer_id)
        benefits = TierBenefitService.get_benefits_for_customer(customer)
        has_benefit = any(
            getattr(b, 'benefit_type', '') == benefit_type for b in benefits
        )
        matching = [
            TierBenefitSerializer.to_dict(b) for b in benefits
            if getattr(b, 'benefit_type', '') == benefit_type
        ]
        return Response({
            'customer_id':  customer_id,
            'benefit_type': benefit_type,
            'has_access':   has_benefit,
            'benefits':     matching,
        })

    # ── Admin: create benefit ──────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='create',
            permission_classes=[IsLoyaltyAdmin])
    def create_benefit(self, request):
        """Admin: add a new benefit to a tier।"""
        from django.shortcuts import get_object_or_404
        tier_id      = request.data.get('tier_id')
        benefit_type = request.data.get('benefit_type')
        name         = request.data.get('name', '')
        description  = request.data.get('description', '')
        value        = request.data.get('value', '')

        if not tier_id or not benefit_type:
            return Response(
                {'error': 'tier_id and benefit_type required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tier = get_object_or_404(LoyaltyTier, pk=tier_id)
        try:
            benefit = TierBenefit.objects.create(
                tier=tier, benefit_type=benefit_type,
                name=name, description=description, value=value,
                is_active=True,
            )
            return Response(TierBenefitSerializer.to_dict(benefit), status=status.HTTP_201_CREATED)
        except Exception as e:
            return self.err(str(e))
