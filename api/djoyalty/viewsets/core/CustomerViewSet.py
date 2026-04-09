# api/djoyalty/viewsets/core/CustomerViewSet.py
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from ...models.core import Customer
from ...serializers.CustomerSerializer import CustomerSerializer, CustomerDetailSerializer
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsAuthenticatedAndActive, IsLoyaltyAdmin
from ...throttles import DjoyaltyUserThrottle, DjoyaltyBurstThrottle
from ...mixins import DjoyaltyTenantMixin, DjoyaltyAuditMixin
from ...cache_backends import DjoyaltyCache


class CustomerViewSet(DjoyaltyTenantMixin, DjoyaltyAuditMixin, viewsets.ModelViewSet):
    """
    Customer CRUD — Tenant isolated, cached, throttled।
    """
    permission_classes = [IsAuthenticatedAndActive]
    throttle_classes = [DjoyaltyUserThrottle]
    queryset = Customer.objects.all().order_by('-created_at')
    serializer_class = CustomerSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'firstname', 'lastname', 'email', 'phone']
    ordering_fields = ['created_at', 'code', 'city']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CustomerDetailSerializer
        return CustomerSerializer

    def get_queryset(self):
        # DjoyaltyTenantMixin handles tenant filter
        qs = super().get_queryset()
        newsletter = self.request.query_params.get('newsletter')
        city = self.request.query_params.get('city')
        is_active = self.request.query_params.get('is_active')
        if newsletter is not None:
            qs = qs.filter(newsletter=newsletter.lower() == 'true')
        if city:
            qs = qs.filter(city__icontains=city)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs.prefetch_related('transactions', 'events', 'loyalty_points', 'user_tiers__tier')

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Customer এর complete stats — cached।"""
        customer = get_object_or_404(Customer, pk=pk)
        txns = customer.transactions.all()
        lp = customer.loyalty_points.first()
        ut = customer.user_tiers.filter(is_current=True).first()
        data = {
            'total_transactions': txns.count(),
            'total_spent': float(txns.filter(value__gt=0).aggregate(s=Sum('value'))['s'] or 0),
            'full_price_count': txns.filter(is_discount=False).count(),
            'discount_count': txns.filter(is_discount=True).count(),
            'spending_count': txns.filter(value__lt=0).count(),
            'event_count': customer.events.count(),
            'points_balance': str(lp.balance if lp else 0),
            'lifetime_earned': str(lp.lifetime_earned if lp else 0),
            'lifetime_redeemed': str(lp.lifetime_redeemed if lp else 0),
            'current_tier': ut.tier.name if ut and ut.tier else 'bronze',
            'badge_count': customer.user_badges.count(),
        }
        return Response(data)

    @action(detail=False, methods=['get'])
    def newsletter_subscribers(self, request):
        """Newsletter subscribers list।"""
        qs = self.get_queryset().filter(newsletter=True)
        serializer = self.get_serializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        """Customer এর points ledger history।"""
        from ...services.points.PointsLedgerService import PointsLedgerService
        from ...serializers.LedgerSerializer import LedgerSerializer
        customer = get_object_or_404(Customer, pk=pk)
        history = PointsLedgerService.get_ledger_history(customer)
        return Response({'results': LedgerSerializer(history, many=True).data})

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def deactivate(self, request, pk=None):
        """Customer deactivate করো (soft delete)।"""
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_active = False
        customer.save(update_fields=['is_active'])
        DjoyaltyCache.flush_customer_cache(customer.id)
        return Response({'message': f'Customer {customer.code} deactivated.'})

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def reactivate(self, request, pk=None):
        """Customer reactivate করো।"""
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_active = True
        customer.save(update_fields=['is_active'])
        return Response({'message': f'Customer {customer.code} reactivated.'})
