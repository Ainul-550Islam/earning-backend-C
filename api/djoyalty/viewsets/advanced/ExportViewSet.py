# api/djoyalty/viewsets/advanced/ExportViewSet.py
"""
ExportViewSet -- Data export API endpoints।

FIXED: LoyaltyExportService (services/LoyaltyExportService.py) was
fully built (CSV customer export, points export, transaction export,
GDPR export, JSON/CSV format) but had NO viewset, NO router entry।
Connected here।

Already in routers.py:
  from .viewsets.advanced.SDKViewSet import SDKViewSet, ExportViewSet
  router.register(r'export', ExportViewSet, basename='export')

Endpoints:
  GET /export/customers/        -- CSV of all customers
  GET /export/points/           -- CSV of points ledger
  GET /export/transactions/     -- CSV of transactions
  GET /export/redemptions/      -- CSV of redemptions
  GET /export/tiers/            -- CSV of tier distribution
  POST /export/customer-gdpr/   -- GDPR full data export for one customer
"""
import logging
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ...permissions import IsLoyaltyAdmin
from ...services.LoyaltyExportService import LoyaltyExportService
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class ExportViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """Data export endpoints -- all require admin permission।"""
    permission_classes = [IsLoyaltyAdmin]

    def _get_tenant(self, request):
        tid = request.query_params.get('tenant_id')
        if tid:
            from ...models.core import Tenant
            return Tenant.objects.filter(pk=tid).first()
        return None

    # ── Customer CSV ──────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='customers')
    def export_customers(self, request):
        """
        All customers CSV export।
        FIXED: LoyaltyExportService.export_customers_csv() was defined
        but no API exposed it -- admins had no way to download customer data।
        Query params: ?is_active=true|false, ?tenant_id=N
        """
        tenant    = self._get_tenant(request)
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
        try:
            csv_content = LoyaltyExportService.export_customers_csv(
                tenant=tenant, is_active=is_active
            )
            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="customers.csv"'
            return response
        except Exception as e:
            logger.error('export_customers error: %s', e)
            return self.err(str(e), http_status=500)

    # ── Points Ledger CSV ─────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='points')
    def export_points(self, request):
        """
        Points ledger CSV -- all earn/redeem/expire transactions।
        Query params: ?customer_id=N, ?days=30, ?tenant_id=N
        """
        tenant      = self._get_tenant(request)
        customer_id = request.query_params.get('customer_id')
        days        = int(request.query_params.get('days', 90))
        customer    = None
        if customer_id:
            from ...models.core import Customer
            customer = Customer.objects.filter(pk=customer_id).first()
        try:
            csv_content = LoyaltyExportService.export_points_csv(
                tenant=tenant, customer=customer, days=days
            )
            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="points_ledger.csv"'
            return response
        except Exception as e:
            logger.error('export_points error: %s', e)
            return self.err(str(e), http_status=500)

    # ── Transactions CSV ──────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='transactions')
    def export_transactions(self, request):
        """
        Transaction CSV export।
        Query params: ?customer_id=N, ?days=30, ?tenant_id=N
        """
        tenant      = self._get_tenant(request)
        customer_id = request.query_params.get('customer_id')
        days        = int(request.query_params.get('days', 90))
        customer    = None
        if customer_id:
            from ...models.core import Customer
            customer = Customer.objects.filter(pk=customer_id).first()
        try:
            csv_content = LoyaltyExportService.export_transactions_csv(
                tenant=tenant, customer=customer, days=days
            )
            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
            return response
        except Exception as e:
            logger.error('export_transactions error: %s', e)
            return self.err(str(e), http_status=500)

    # ── Redemptions CSV ────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='redemptions')
    def export_redemptions(self, request):
        """
        Redemption requests CSV export।
        Query params: ?status=pending|approved|completed, ?days=30, ?tenant_id=N
        """
        tenant      = self._get_tenant(request)
        filter_status = request.query_params.get('status')
        days        = int(request.query_params.get('days', 90))
        try:
            csv_content = LoyaltyExportService.export_redemptions_csv(
                tenant=tenant, filter_status=filter_status, days=days
            )
            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="redemptions.csv"'
            return response
        except Exception as e:
            logger.error('export_redemptions error: %s', e)
            return self.err(str(e), http_status=500)

    # ── Tier Distribution CSV ─────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='tiers')
    def export_tiers(self, request):
        """
        Tier distribution CSV -- how many customers per tier।
        """
        tenant = self._get_tenant(request)
        try:
            csv_content = LoyaltyExportService.export_tier_distribution_csv(tenant=tenant)
            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="tier_distribution.csv"'
            return response
        except Exception as e:
            logger.error('export_tiers error: %s', e)
            return self.err(str(e), http_status=500)

    # ── GDPR Customer Data Export ─────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='customer-gdpr')
    def export_customer_gdpr(self, request):
        """
        GDPR Article 20 -- data portability export for a specific customer।
        Returns JSON bundle: profile + transactions + points + consents।
        POST body: { "customer_id": 123 }
        """
        customer_id = request.data.get('customer_id')
        if not customer_id:
            return Response(
                {'error': 'customer_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from ...models.core import Customer
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return self.not_found('Customer not found.')
        try:
            export_data = LoyaltyExportService.export_customer_gdpr_json(customer)
            import json
            response = HttpResponse(
                json.dumps(export_data, indent=2, default=str),
                content_type='application/json',
            )
            response['Content-Disposition'] = (
                f'attachment; filename="customer_{customer.code}_gdpr.json"'
            )
            return response
        except Exception as e:
            logger.error('export_customer_gdpr error: %s', e)
            return self.err(str(e), http_status=500)

    # ── JSON export (alternative format) ─────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='customers/json')
    def export_customers_json(self, request):
        """
        Customers export in JSON format (for data pipeline integrations)।
        """
        tenant    = self._get_tenant(request)
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
        try:
            data = LoyaltyExportService.export_customers_json(
                tenant=tenant, is_active=is_active
            )
            import json
            response = HttpResponse(
                json.dumps(data, indent=2, default=str),
                content_type='application/json',
            )
            response['Content-Disposition'] = 'attachment; filename="customers.json"'
            return response
        except Exception as e:
            logger.error('export_customers_json error: %s', e)
            return self.err(str(e), http_status=500)
