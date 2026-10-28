# djoyalty/viewsets/advanced/SearchViewSet.py
"""
Search ViewSet -- exposes search.py CustomerSearch, TransactionSearch,
PointsLedgerSearch, OfferSearch। Previously: zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet
from ...serializers.AnalyticsSerializer import (
    CustomerSearchResultSerializer, TransactionSearchResultSerializer,
)


class SearchViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET /search/customers/           -- full-text customer search
    GET /search/customers/by-tier/   -- filter by tier
    GET /search/customers/by-points/ -- filter by points range
    GET /search/customers/inactive/  -- inactive customers
    GET /search/transactions/        -- transaction search
    GET /search/ledger/              -- points ledger search
    GET /search/offers/              -- offer search
    """
    permission_classes = [IsLoyaltyAdmin]

    @action(detail=False, methods=['get'], url_path='customers')
    def customers(self, request):
        from ...search import CustomerSearch
        q      = request.query_params.get('q', '')
        limit  = int(request.query_params.get('limit', 20))
        tenant_id = request.query_params.get('tenant_id')
        tenant = None
        if tenant_id:
            from ...models.core import Tenant
            tenant = Tenant.objects.filter(pk=tenant_id).first()
        if not q:
            return self.err('q parameter required')
        try:
            results = CustomerSearch.search(query=q, tenant=tenant, limit=limit)
            return Response({'count': len(results), 'results': results})
        except Exception as e:
            return self.err(str(e), http_status=500)

    @action(detail=False, methods=['get'], url_path='customers/by-tier')
    def by_tier(self, request):
        from ...search import CustomerSearch
        tier_name = request.query_params.get('tier')
        if not tier_name:
            return self.err('tier parameter required')
        try:
            results = CustomerSearch.search_by_tier(tier_name=tier_name)
            return Response({'count': len(results), 'results': results})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='customers/by-points')
    def by_points(self, request):
        from decimal import Decimal
        from ...search import CustomerSearch
        min_pts = Decimal(request.query_params.get('min', '0'))
        max_pts = Decimal(request.query_params.get('max', '999999999'))
        try:
            results = CustomerSearch.search_by_points_range(min_pts=min_pts, max_pts=max_pts)
            return Response({'count': len(results), 'results': results})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='customers/inactive')
    def inactive_customers(self, request):
        from ...search import CustomerSearch
        days = int(request.query_params.get('days', 30))
        try:
            results = CustomerSearch.search_inactive(days=days)
            return Response({'days': days, 'count': len(results), 'results': results})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='transactions')
    def transactions(self, request):
        from ...search import TransactionSearch
        customer_id = request.query_params.get('customer_id')
        source      = request.query_params.get('source', '')
        customer    = None
        if customer_id:
            from ...models.core import Customer
            customer = Customer.objects.filter(pk=customer_id).first()
        try:
            results = TransactionSearch.search(customer=customer, source=source)
            return Response({'count': len(results), 'results': results})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='ledger')
    def ledger(self, request):
        from ...search import PointsLedgerSearch
        customer_id = request.query_params.get('customer_id')
        txn_type    = request.query_params.get('txn_type', '')
        source      = request.query_params.get('source', '')
        customer    = None
        if customer_id:
            from ...models.core import Customer
            customer = Customer.objects.filter(pk=customer_id).first()
        try:
            results = PointsLedgerSearch.search(customer=customer, txn_type=txn_type, source=source)
            return Response({'count': len(results), 'results': results})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
