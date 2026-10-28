# api/djoyalty/viewsets/advanced/RewardCatalogViewSet.py
"""
Reward Catalog ViewSet -- Browse and redeem from reward catalog।
"""
from rest_framework import viewsets, status, filters
from ...mixins import DjoyaltyBaseViewSet, DjoyaltyTenantMixin
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...serializers.AnalyticsSerializer import (
    RewardCatalogItemSerializer, RedeemCatalogItemInputSerializer,
    RewardCatalogCategorySerializer,
)


class RewardCatalogViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'supplier_name']
    ordering_fields = ['points_cost', 'sort_order', 'created_at']

    def get_queryset(self):
        from ...models.catalog import RewardCatalogItem
        from django.utils import timezone

        qs = RewardCatalogItem.objects.filter(is_active=True)
        now = timezone.now()
        qs = qs.filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now)
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        )

        # Filter by reward_type
        reward_type = self.request.query_params.get('reward_type')
        if reward_type:
            qs = qs.filter(reward_type=reward_type)

        # Filter by category
        category_id = self.request.query_params.get('category_id')
        if category_id:
            qs = qs.filter(category_id=category_id)

        # Filter by max points
        max_points = self.request.query_params.get('max_points')
        if max_points:
            try:
                qs = qs.filter(points_cost__lte=float(max_points))
            except ValueError:
                pass

        return qs.order_by('-is_featured', 'sort_order', 'points_cost')

    @action(detail=False, methods=['get'])
    def affordable(self, request):
        """Items affordable by customer's current points balance।"""
        from ...models.points import LoyaltyPoints

        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')

        lp = LoyaltyPoints.objects.filter(customer_id=customer_id).first()
        balance = lp.balance if lp else 0

        from ...models.catalog import RewardCatalogItem
        items = self.get_queryset().filter(points_cost__lte=balance)
        return Response({
            'customer_balance': str(balance),
            'count': items.count(),
            'items': [
                {
                    'id': item.id,
                    'name': item.name,
                    'reward_type': item.reward_type,
                    'points_cost': str(item.points_cost),
                    'cash_value': str(item.cash_value),
                    'image_url': item.image_url,
                    'is_featured': item.is_featured,
                }
                for item in items[:20]
            ],
        })

    @action(detail=True, methods=['post'])
    def redeem(self, request, pk=None):
        """Redeem a catalog item with points।"""
        from ...models.catalog import RewardCatalogItem
        from ...models.core import Customer
        from ...integration_system.auth_bridge import PermissionGuard

        try:
            item = RewardCatalogItem.objects.get(id=pk)
        except RewardCatalogItem.DoesNotExist:
            return self.not_found('Item not found')

        if not item.is_available():
            return self.err('Item not available')

        customer_id = request.data.get('customer_id')
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return self.not_found('Customer not found')

        can, reason = PermissionGuard.can_redeem(customer, float(item.points_cost))
        if not can:
            return Response({'error': reason}, status=400)

        # Create redemption request via existing service
        from ...services.redemption.RedemptionService import RedemptionService
        try:
            result = RedemptionService.redeem_points(
                customer=customer,
                points=item.points_cost,
                redemption_type=item.reward_type,
                note=f'Catalog: {item.name}',
            )
            item.redeemed_count += 1
            item.save(update_fields=['redeemed_count'])
            return Response({'success': True, 'redemption_id': result.id if result else None})
        except Exception as e:
            return self.err(str(e))


import django.db.models as models
from ...mixins import DjoyaltyBaseViewSet
