# api/djoyalty/viewsets/advanced/AnalyticsViewSet.py
"""
AnalyticsViewSet -- Full business intelligence API।

FIXED (original): kpi_tracker.py, reports.py were orphaned।
Both now exposed via this viewset।

AUDIT FIX (2.4): Direct imports of kpi_tracker, ltv_calculator,
cohort_analysis, analytics, reports removed from every action method।
All analytics orchestration is now the sole responsibility of
AnalyticsService.  Per "এক কাজের জন্য একটাই মালিক" — viewset is a
thin HTTP adapter that calls AnalyticsService and returns results।

Before (removed):
    # from ...kpi_tracker import KPITracker  # direct import removed
    # tracker = KPITracker(tenant=tenant)
    # return Response({...tracker calls...})

After:
    from ...services.AnalyticsService import AnalyticsService
    result = AnalyticsService.get_kpi_dashboard(tenant=tenant, period=period)
    return self.from_service(result)

Endpoints:
  GET /analytics/overview/                      -- tenant KPI overview
  GET /analytics/kpi/                           -- live KPI dashboard
  GET /analytics/kpi/history/                   -- KPI trend over time
  GET /analytics/reports/summary/               -- summary report
  GET /analytics/reports/points/                -- points flow report
  GET /analytics/reports/tiers/                 -- tier distribution report
  GET /analytics/reports/campaigns/             -- campaign performance report
  GET /analytics/customer/{id}/ltv/             -- customer LTV breakdown
  GET /analytics/customer/{id}/full/            -- full customer analytics
  GET /analytics/cohort-table/                  -- cohort retention table
  GET /analytics/campaigns/{id}/               -- single campaign stats
  GET /analytics/points/                        -- points liability & flow
  GET /analytics/segments/                      -- segment distribution
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ...mixins import DjoyaltyBaseViewSet
from ...permissions import IsLoyaltyAdmin
from ...serializers.AnalyticsSerializer import (
    CustomerLTVSerializer, AnalyticsOverviewSerializer,
    CohortTableSerializer, CampaignAnalyticsSerializer,
)


class AnalyticsViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    Analytics ViewSet — thin HTTP adapter over AnalyticsService.

    DjoyaltyBaseViewSet provides: ok(), err(), from_service(), get_tenant().
    All business logic delegated to AnalyticsService (audit fix 2.4).
    """
    permission_classes = [IsLoyaltyAdmin]

    # ── Customer LTV ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/ltv')
    def customer_ltv(self, request, customer_id=None):
        """Full LTV breakdown for a customer — AnalyticsService.get_customer_ltv()."""
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...services.AnalyticsService import AnalyticsService

        customer = get_object_or_404(Customer, pk=customer_id)
        result   = AnalyticsService.get_customer_ltv(customer=customer)
        return self.from_service(result)

    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/full')
    def customer_full(self, request, customer_id=None):
        """LTV + avg order value + purchase frequency."""
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...services.AnalyticsService import AnalyticsService

        customer = get_object_or_404(Customer, pk=customer_id)
        result   = AnalyticsService.get_customer_full_analytics(customer=customer)
        return self.from_service(result)

    # ── Overview ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        """Tenant-level KPI overview — AnalyticsService.get_overview()."""
        from ...services.AnalyticsService import AnalyticsService

        tenant = self.get_tenant()
        result = AnalyticsService.get_overview(tenant=tenant)
        return self.from_service(result)

    # ── KPI Dashboard ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='kpi')
    def kpi_dashboard(self, request):
        """
        Live KPI dashboard — AnalyticsService.get_kpi_dashboard().

        FIXED (original): kpi_tracker.KPITracker was a complete orphan;
        now exposed here and proxied through AnalyticsService.

        AUDIT FIX (2.4): kpi_tracker import removed from this viewset;
        all orchestration delegated to AnalyticsService.
        """
        from ...services.AnalyticsService import AnalyticsService

        tenant = self.get_tenant()
        period = request.query_params.get('period', 'monthly')
        result = AnalyticsService.get_kpi_dashboard(tenant=tenant, period=period)
        return self.from_service(result)

    @action(detail=False, methods=['get'], url_path='kpi/history')
    def kpi_history(self, request):
        """KPI trend over time — AnalyticsService.get_kpi_history()."""
        from ...services.AnalyticsService import AnalyticsService

        tenant = self.get_tenant()
        metric = request.query_params.get('metric', 'redemption_rate')
        months = int(request.query_params.get('months', 6))
        result = AnalyticsService.get_kpi_history(tenant=tenant, metric=metric, months=months)
        return self.from_service(result)

    # ── Reports ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='reports/summary')
    def report_summary(self, request):
        """
        Loyalty program summary report.

        FIXED (original): reports.LoyaltyReports was a complete orphan.
        AUDIT FIX (2.4): reports import removed; delegated to AnalyticsService.
        """
        from ...services.AnalyticsService import AnalyticsService

        tenant    = self.get_tenant()
        date_from = request.query_params.get('from')
        date_to   = request.query_params.get('to')
        result    = AnalyticsService.get_report_summary(
            tenant=tenant, date_from=date_from, date_to=date_to
        )
        return self.from_service(result)

    @action(detail=False, methods=['get'], url_path='reports/points')
    def report_points(self, request):
        """Points issuance, redemption, expiry report."""
        from ...services.AnalyticsService import AnalyticsService

        tenant    = self.get_tenant()
        date_from = request.query_params.get('from')
        date_to   = request.query_params.get('to')
        result    = AnalyticsService.get_report_points(
            tenant=tenant, date_from=date_from, date_to=date_to
        )
        return self.from_service(result)

    @action(detail=False, methods=['get'], url_path='reports/tiers')
    def report_tiers(self, request):
        """Tier distribution and upgrade/downgrade report."""
        from ...services.AnalyticsService import AnalyticsService

        tenant = self.get_tenant()
        result = AnalyticsService.get_report_tiers(tenant=tenant)
        return self.from_service(result)

    @action(detail=False, methods=['get'], url_path='reports/campaigns')
    def report_campaigns(self, request):
        """Campaign ROI and participation report."""
        from ...services.AnalyticsService import AnalyticsService

        tenant    = self.get_tenant()
        date_from = request.query_params.get('from')
        date_to   = request.query_params.get('to')
        result    = AnalyticsService.get_report_campaigns(
            tenant=tenant, date_from=date_from, date_to=date_to
        )
        return self.from_service(result)

    # ── Cohort ─────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='cohort-table')
    def cohort_table(self, request):
        """
        Full cohort retention table.

        AUDIT FIX (2.4): cohort_analysis import removed; delegated to AnalyticsService.
        """
        from ...services.AnalyticsService import AnalyticsService

        tenant = self.get_tenant()
        months = int(request.query_params.get('months', 6))
        result = AnalyticsService.get_cohort_table(tenant=tenant, months=months)
        return self.from_service(result)

    # ── Campaign stats ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            url_path='campaigns/(?P<campaign_id>[0-9]+)')
    def campaign_stats(self, request, campaign_id=None):
        """Single campaign performance."""
        from django.shortcuts import get_object_or_404
        from ...models.campaigns import LoyaltyCampaign
        from ...services.AnalyticsService import AnalyticsService

        campaign = get_object_or_404(LoyaltyCampaign, pk=campaign_id)
        result   = AnalyticsService.get_campaign_stats(campaign=campaign)
        return self.from_service(result)

    # ── Points liability ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='points')
    def points_liability(self, request):
        """
        Points outstanding liability and flow.

        AUDIT FIX (2.4): analytics import removed; delegated to AnalyticsService.
        """
        from ...services.AnalyticsService import AnalyticsService

        tenant = self.get_tenant()
        days   = int(request.query_params.get('days', 30))
        result = AnalyticsService.get_points_analytics(tenant=tenant, days=days)
        return self.from_service(result)

    # ── Segments ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='segments')
    def segments(self, request):
        """Customer segment distribution (RFM)."""
        from ...services.AnalyticsService import AnalyticsService

        tenant = self.get_tenant()
        result = AnalyticsService.get_segment_analytics(tenant=tenant)
        return self.from_service(result)
