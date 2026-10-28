# djoyalty/viewsets/advanced/SDKViewSet.py
"""
SDK / Public API / Export ViewSet
sdk.py: SDK helper endpoints for client-side JS/mobile SDKs
viewset_cap.py: ExportCapabilityMixin, BulkOperationsMixin -- expose via API
Previously: all logic built, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
# FIXED: LoyaltyAPIService was floating -- white-label API facade now imported
try:
    from ...services.LoyaltyAPIService import LoyaltyAPIService
    _api_service = LoyaltyAPIService()
except ImportError:
    _api_service = None
from ...serializers.AnalyticsSerializer import (
    SDKInitSerializer, SDKEventInputSerializer, CustomerSearchResultSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


# ─── SDK ViewSet ───────────────────────────────────────────────────────────────

class SDKViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /sdk/init/                -- SDK initialization payload (tenant config + customer)
    GET  /sdk/customer/status/     -- real-time customer status for SDK polling
    POST /sdk/event/               -- track a custom event from SDK
    GET  /sdk/config/              -- public SDK config (no secrets)
    GET  /sdk/health/              -- SDK connectivity health
    """
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        c = getattr(request, 'loyalty_customer', None)
        if c:
            return c
        cid = request.query_params.get('customer_id') or request.data.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    @action(detail=False, methods=['get'], url_path='init')
    def sdk_init(self, request):
        """Single endpoint SDK calls on app load -- returns all needed state."""
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found')
        try:
            from ...sdk import DjoyaltySDK
            return Response(DjoyaltySDK.get_init_payload(customer=customer))
        except Exception as e:
            # Fallback: return basic info
            from ...models.points import LoyaltyPoints
            lp = LoyaltyPoints.objects.filter(customer=customer).first()
            return Response({
                'customer': {
                    'code': customer.code,
                    'name': getattr(customer, 'full_name', ''),
                },
                'points': {
                    'balance': str(lp.balance) if lp else '0',
                    'lifetime_earned': str(lp.lifetime_earned) if lp else '0',
                },
            })

    @action(detail=False, methods=['get'], url_path='customer/status')
    def customer_status(self, request):
        """Lightweight polling endpoint for SDK (balance, tier, unread)."""
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found')
        try:
            from ...sdk import DjoyaltySDK
            return Response(DjoyaltySDK.get_customer_status(customer=customer))
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='event')
    def track_event(self, request):
        """Track a custom SDK event (page view, feature use, etc.)."""
        customer    = self._get_customer(request)
        event_name  = request.data.get('event', '')
        properties  = request.data.get('properties', {})
        if not event_name:
            return self.err('event required')
        try:
            from ...sdk import DjoyaltySDK
            DjoyaltySDK.track_event(
                customer=customer, event_name=event_name, properties=properties
            )
            return Response({'tracked': True})
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='config')
    def sdk_config(self, request):
        """Public SDK config -- no secrets, safe for client-side."""
        try:
            from ...sdk import DjoyaltySDK
            return Response(DjoyaltySDK.get_public_config())
        except Exception as e:
            return Response({'sdk_version': '2.0', 'features': []})

    @action(detail=False, methods=['get'], url_path='health')
    def sdk_health(self, request):
        return Response({'status': 'ok', 'sdk': 'djoyalty-v2'})


# ─── Export ViewSet ────────────────────────────────────────────────────────────

class ExportViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    POST /export/customers/        -- export customer list (CSV/JSON)
    POST /export/points/           -- export points ledger
    POST /export/transactions/     -- export transaction history
    POST /export/campaigns/        -- export campaign report
    GET  /export/status/{job_id}/  -- check export job status
    GET  /export/download/{job_id}/ -- download completed export
    """
    permission_classes = [IsLoyaltyAdmin]

    @action(detail=False, methods=['post'], url_path='customers')
    def export_customers(self, request):
        fmt       = request.data.get('format', 'csv')
        tenant_id = request.data.get('tenant_id')
        filters   = request.data.get('filters', {})
        try:
            from ...viewset_cap import ExportCapabilityMixin
            job_id = ExportCapabilityMixin.schedule_export(
                export_type='customers', fmt=fmt,
                tenant_id=tenant_id, filters=filters,
                requested_by=str(request.user),
            )
            return Response({'job_id': job_id, 'status': 'queued'}, status=202)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='points')
    def export_points(self, request):
        fmt       = request.data.get('format', 'csv')
        tenant_id = request.data.get('tenant_id')
        date_from = request.data.get('date_from', '')
        date_to   = request.data.get('date_to', '')
        try:
            from ...viewset_cap import ExportCapabilityMixin
            job_id = ExportCapabilityMixin.schedule_export(
                export_type='points_ledger', fmt=fmt,
                tenant_id=tenant_id,
                filters={'date_from': date_from, 'date_to': date_to},
                requested_by=str(request.user),
            )
            return Response({'job_id': job_id, 'status': 'queued'}, status=202)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='transactions')
    def export_transactions(self, request):
        fmt       = request.data.get('format', 'csv')
        tenant_id = request.data.get('tenant_id')
        date_from = request.data.get('date_from', '')
        date_to   = request.data.get('date_to', '')
        try:
            from ...viewset_cap import ExportCapabilityMixin
            job_id = ExportCapabilityMixin.schedule_export(
                export_type='transactions', fmt=fmt,
                tenant_id=tenant_id,
                filters={'date_from': date_from, 'date_to': date_to},
                requested_by=str(request.user),
            )
            return Response({'job_id': job_id, 'status': 'queued'}, status=202)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            url_path='status/(?P<job_id>[a-zA-Z0-9_-]+)')
    def export_status(self, request, job_id=None):
        try:
            from ...viewset_cap import ExportCapabilityMixin
            result = ExportCapabilityMixin.get_export_status(job_id=job_id)
            return Response(result)
        except Exception as e:
            return self.not_found(str(e))

    @action(detail=False, methods=['get'],
            url_path='download/(?P<job_id>[a-zA-Z0-9_-]+)')
    def export_download(self, request, job_id=None):
        try:
            from ...viewset_cap import ExportCapabilityMixin
            file_url = ExportCapabilityMixin.get_download_url(job_id=job_id)
            if not file_url:
                return self.not_found('Export not ready')
            return Response({'download_url': file_url, 'job_id': job_id})
        except Exception as e:
            return self.not_found(str(e))
