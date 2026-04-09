# api/djoyalty/viewsets/tiers/UserTierViewSet.py
"""
UserTierViewSet — Customer এর current ও historical tier management।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from ...models.tiers import UserTier, TierHistory
from ...models.core import Customer
from ...serializers.UserTierSerializer import (
    UserTierSerializer, UserTierHistorySerializer, MyTierSerializer
)
from ...services.tiers.TierEvaluationService import TierEvaluationService
from ...services.tiers.TierUpgradeService import TierUpgradeService
from ...services.tiers.TierDowngradeService import TierDowngradeService
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination


class UserTierViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Customer tier management endpoints।
    - list: সব current user tiers
    - retrieve: নির্দিষ্ট user tier detail
    - evaluate: Tier re-evaluate করো
    - my_tier: Customer নিজের tier info
    - history: Tier change history
    - force_upgrade: Admin — force upgrade
    - force_downgrade: Admin — force downgrade
    - progress: Upgrade progress detail
    """
    permission_classes = [IsAuthenticated]
    queryset = UserTier.objects.filter(is_current=True).select_related(
        'customer', 'tier', 'tier__benefits'
    ).prefetch_related('tier__benefits')
    serializer_class = UserTierSerializer
    pagination_class = DjoyaltyPagePagination

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        tier_name = self.request.query_params.get('tier')
        is_current = self.request.query_params.get('is_current', 'true')

        if is_current.lower() == 'false':
            qs = UserTier.objects.all().select_related('customer', 'tier')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if tier_name:
            qs = qs.filter(tier__name=tier_name)
        return qs.order_by('-assigned_at')

    @action(detail=False, methods=['post'])
    def evaluate(self, request):
        """Customer এর tier re-evaluate করো।"""
        customer_id = request.data.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)
        user_tier = TierEvaluationService.evaluate(customer, tenant=customer.tenant)
        if user_tier:
            return Response({
                'message': f'Tier evaluated: {user_tier.tier.name}',
                'tier': UserTierSerializer(user_tier).data,
            })
        return Response({'message': 'No tier change required.'})

    @action(detail=False, methods=['get'])
    def my_tier(self, request):
        """
        Customer নিজের tier summary দেখো।
        Query param: ?customer_id=<id>
        """
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': 'customer_id required'}, status=status.HTTP_400_BAD_REQUEST)

        customer = get_object_or_404(Customer, pk=customer_id)
        user_tier = customer.user_tiers.filter(is_current=True).select_related('tier').first()
        lp = customer.loyalty_points.first()

        from ...utils import get_next_tier, get_points_needed_for_next_tier
        from ...constants import TIER_THRESHOLDS
        from decimal import Decimal

        tier_name = user_tier.tier.name if user_tier and user_tier.tier else 'bronze'
        lifetime = lp.lifetime_earned if lp else Decimal('0')
        balance = lp.balance if lp else Decimal('0')
        next_tier_name = get_next_tier(tier_name)
        points_needed = get_points_needed_for_next_tier(lifetime, tier_name) if next_tier_name else None

        # Progress %
        if next_tier_name and points_needed is not None:
            current_thresh = TIER_THRESHOLDS.get(tier_name, Decimal('0'))
            next_thresh = TIER_THRESHOLDS.get(next_tier_name, Decimal('0'))
            tier_range = next_thresh - current_thresh
            progress_pct = float(min((lifetime - current_thresh) / tier_range * 100, 100)) if tier_range > 0 else 100.0
        else:
            progress_pct = 100.0

        # Benefits
        from ...models.tiers import TierBenefit
        from ...serializers.UserTierSerializer import TierBenefitInlineSerializer
        benefits = []
        if user_tier and user_tier.tier:
            benefits_qs = TierBenefit.objects.filter(tier=user_tier.tier, is_active=True)
            benefits = TierBenefitInlineSerializer(benefits_qs, many=True).data

        # Tier history (last 5)
        history_qs = TierHistory.objects.filter(customer=customer).order_by('-created_at')[:5]
        history_data = UserTierHistorySerializer(history_qs, many=True).data

        # Days in tier
        days_in_tier = 0
        if user_tier and user_tier.assigned_at:
            from django.utils import timezone
            days_in_tier = (timezone.now() - user_tier.assigned_at).days

        from ...models.tiers import LoyaltyTier
        tier_obj = user_tier.tier if user_tier else None
        data = {
            'current_tier': tier_name,
            'tier_label': tier_obj.label if tier_obj else tier_name.title(),
            'tier_icon': tier_obj.icon if tier_obj else '⭐',
            'tier_color': tier_obj.color if tier_obj else '#888888',
            'tier_rank': tier_obj.rank if tier_obj else 1,
            'earn_multiplier': str(tier_obj.earn_multiplier) if tier_obj else '1.00',
            'points_balance': str(balance),
            'lifetime_earned': str(lifetime),
            'next_tier': next_tier_name,
            'points_needed': str(points_needed) if points_needed is not None else None,
            'upgrade_progress_pct': round(max(progress_pct, 0.0), 1),
            'assigned_at': user_tier.assigned_at.isoformat() if user_tier and user_tier.assigned_at else None,
            'days_in_tier': days_in_tier,
            'benefits': benefits,
            'tier_history': history_data,
        }
        return Response(data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Customer এর tier change history।"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': 'customer_id required'}, status=status.HTTP_400_BAD_REQUEST)
        customer = get_object_or_404(Customer, pk=customer_id)
        history = TierHistory.objects.filter(customer=customer).order_by('-created_at')
        page = self.paginate_queryset(history)
        if page is not None:
            return self.get_paginated_response(UserTierHistorySerializer(page, many=True).data)
        return Response(UserTierHistorySerializer(history, many=True).data)

    @action(detail=False, methods=['get'])
    def progress(self, request):
        """Customer এর upgrade progress detail।"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': 'customer_id required'}, status=status.HTTP_400_BAD_REQUEST)
        customer = get_object_or_404(Customer, pk=customer_id)
        progress = TierUpgradeService.get_upgrade_progress(customer)
        return Response(progress)

    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def force_upgrade(self, request):
        """Admin: Customer কে নির্দিষ্ট tier এ force upgrade করো।"""
        customer_id = request.data.get('customer_id')
        target_tier = request.data.get('tier_name')
        reason = request.data.get('reason', 'Admin forced upgrade')
        if not customer_id or not target_tier:
            return Response(
                {'error': 'customer_id and tier_name required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        customer = get_object_or_404(Customer, pk=customer_id)
        user_tier = TierUpgradeService.force_upgrade(
            customer, target_tier, reason=reason, tenant=customer.tenant
        )
        if user_tier:
            return Response({
                'message': f'Customer upgraded to {target_tier}',
                'tier': UserTierSerializer(user_tier).data,
            })
        return Response({'error': 'Upgrade failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def force_downgrade(self, request):
        """Admin: Customer কে force downgrade করো।"""
        customer_id = request.data.get('customer_id')
        target_tier = request.data.get('tier_name')
        reason = request.data.get('reason', 'Admin forced downgrade')
        if not customer_id or not target_tier:
            return Response(
                {'error': 'customer_id and tier_name required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        customer = get_object_or_404(Customer, pk=customer_id)
        user_tier = TierDowngradeService.force_downgrade(
            customer, target_tier, reason=reason, tenant=customer.tenant
        )
        if user_tier:
            return Response({
                'message': f'Customer downgraded to {target_tier}',
                'tier': UserTierSerializer(user_tier).data,
            })
        return Response({'error': 'Downgrade failed'}, status=status.HTTP_400_BAD_REQUEST)
