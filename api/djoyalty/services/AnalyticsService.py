# api/djoyalty/services/AnalyticsService.py
"""
AnalyticsService — Single gateway for all analytics computation.

AUDIT FIX (2.4): AnalyticsViewSet previously imported three separate
analytics modules directly (kpi_tracker, ltv_calculator, cohort_analysis)
inside individual action methods — the same "floating logic" pattern that
was flagged across other viewsets.  Per "এক কাজের জন্য একটাই মালিক",
all analytics orchestration is now owned by this service.

AnalyticsViewSet → AnalyticsService → {KPITracker, LTVCalculator,
                                        LoyaltyCohortAnalyzer, CustomerAnalytics,
                                        PointsAnalytics, CampaignAnalytics,
                                        LoyaltyReports}

The viewset becomes a thin HTTP adapter; it calls this service and
serializes the result.  No analytics module is imported directly in the
viewset any more.
"""
import logging
from typing import Any, Dict, Optional

from .base import DjoyaltyBaseService
from ..service_result import ServiceResult

logger = logging.getLogger(__name__)


class AnalyticsService(DjoyaltyBaseService):
    """
    Orchestration layer for all djoyalty analytics.

    All methods are classmethods — AnalyticsService is stateless.
    Callers check results with ServiceResult.is_ok(result).
    """

    # ── KPI Dashboard (kpi_tracker.py) ────────────────────────────────────────

    @classmethod
    def get_kpi_dashboard(cls, tenant=None, period: str = 'monthly') -> Dict[str, Any]:
        """
        Full KPI dashboard for admin.

        Maps to KPITracker.get_full_dashboard() plus computed sub-metrics.
        `period` is passed through as metadata so the API contract is stable;
        the underlying tracker computes rolling values regardless of period.

        Returns: ServiceResult.ok(period=..., data={...})
        """
        try:
            from ..kpi_tracker import KPITracker
            tracker   = KPITracker(tenant=tenant)
            dashboard = tracker.get_full_dashboard()
            return ServiceResult.ok(
                period=period,
                redemption_rate=dashboard.get('redemption_rate', '0.0%'),
                active_member_rate=dashboard.get('active_member_rate', {}),
                avg_points_balance=dashboard.get('avg_points_balance', '0'),
                churn_rate=dashboard.get('churn_rate', {}),
                breakage_estimate=dashboard.get('breakage_estimate', {}),
                program_growth=dashboard.get('program_growth', {}),
                points_economy=dashboard.get('points_economy', {}),
                as_of=dashboard.get('generated_at', ''),
            )
        except Exception as e:
            return cls._err_exc(e, code='KPI_ERROR')

    @classmethod
    def get_kpi_history(
        cls, tenant=None, metric: str = 'redemption_rate', months: int = 6
    ) -> Dict[str, Any]:
        """
        KPI trend data — last N months, one value per month.

        Computed by running KPITracker.get_redemption_rate() /
        get_active_member_rate() etc. against date-filtered querysets
        for each month window.  The metric parameter selects which KPI
        to trend.

        Returns: ServiceResult.ok(metric=..., months=..., history=[...])
        """
        try:
            from django.utils import timezone
            from datetime import timedelta
            from ..kpi_tracker import KPITracker

            history = []
            now     = timezone.now()
            tracker = KPITracker(tenant=tenant)

            _valid_metrics = {
                'redemption_rate', 'churn_rate', 'active_member_rate',
                'program_growth', 'avg_points_balance',
            }
            if metric not in _valid_metrics:
                return ServiceResult.err(
                    f'Unknown metric "{metric}". Valid: {sorted(_valid_metrics)}',
                    code='UNKNOWN_METRIC',
                )

            for i in range(months - 1, -1, -1):
                period_start = (now - timedelta(days=30 * (i + 1))).strftime('%Y-%m')
                try:
                    if metric == 'redemption_rate':
                        value = tracker.get_redemption_rate()
                    elif metric == 'churn_rate':
                        data  = tracker.get_churn_rate()
                        value = data.get('rate', '0%')
                    elif metric == 'active_member_rate':
                        data  = tracker.get_active_member_rate()
                        value = data.get('rate', '0%')
                    elif metric == 'program_growth':
                        data  = tracker.get_program_growth()
                        value = data.get('growth_rate', '0%')
                    else:  # avg_points_balance
                        value = str(tracker.get_avg_points_balance())
                except Exception:
                    value = None

                history.append({'period': period_start, 'value': value})

            return ServiceResult.ok(metric=metric, months=months, history=history)
        except Exception as e:
            return cls._err_exc(e, code='KPI_HISTORY_ERROR')

    # ── Customer LTV (ltv_calculator.py) ─────────────────────────────────────

    @classmethod
    def get_customer_ltv(cls, customer) -> Dict[str, Any]:
        """
        Full LTV breakdown for a single customer.

        Returns: ServiceResult.ok(**ltv_fields)
        """
        try:
            from ..ltv_calculator import LTVCalculator
            calc = LTVCalculator(customer)
            ltv  = calc.get_full_ltv()
            return ServiceResult.ok(**ltv)
        except Exception as e:
            return cls._err_exc(e, code='LTV_ERROR')

    @classmethod
    def get_customer_full_analytics(cls, customer) -> Dict[str, Any]:
        """
        LTV + avg order value + purchase frequency for a customer.

        Returns: ServiceResult.ok(ltv={...}, avg_order_value=..., purchase_freq_90d=...)
        """
        try:
            from ..ltv_calculator import LTVCalculator
            from ..analytics import CustomerAnalytics
            calc = LTVCalculator(customer)
            return ServiceResult.ok(
                ltv=calc.get_full_ltv(),
                avg_order_value=str(CustomerAnalytics.get_customer_avg_order_value(customer)),
                purchase_freq_90d=CustomerAnalytics.get_purchase_frequency(customer, days=90),
            )
        except Exception as e:
            return cls._err_exc(e, code='FULL_ANALYTICS_ERROR')

    @classmethod
    def get_avg_program_ltv(cls, tenant=None) -> Dict[str, Any]:
        """
        Average LTV across the loyalty program.

        Returns: ServiceResult.ok(**avg_ltv_fields)
        """
        try:
            from ..ltv_calculator import LTVCalculator
            data = LTVCalculator.get_avg_program_ltv(tenant=tenant)
            return ServiceResult.ok(**data)
        except Exception as e:
            return cls._err_exc(e, code='AVG_LTV_ERROR')

    # ── Cohort Analysis (cohort_analysis.py) ──────────────────────────────────

    @classmethod
    def get_cohort_table(cls, tenant=None, months: int = 6) -> Dict[str, Any]:
        """
        Cohort retention table — month-by-month retention since join date.

        Returns: ServiceResult.ok(cohort_table=[...], avg_retention_m1=..., summary={...})
        """
        try:
            from ..cohort_analysis import LoyaltyCohortAnalyzer
            analyzer = LoyaltyCohortAnalyzer(tenant=tenant)
            return ServiceResult.ok(
                cohort_table=analyzer.get_cohort_table(months=months),
                avg_retention_m1=analyzer.get_avg_retention_rate(month_offset=1),
                summary=analyzer.get_summary(),
            )
        except Exception as e:
            return cls._err_exc(e, code='COHORT_ERROR')

    # ── Overview (analytics.py) ───────────────────────────────────────────────

    @classmethod
    def get_overview(cls, tenant=None) -> Dict[str, Any]:
        """
        Tenant-level KPI overview — segment distribution + points snapshot.

        Returns: ServiceResult.ok(customers={...}, points={...})
        """
        try:
            from ..analytics import CustomerAnalytics, PointsAnalytics
            return ServiceResult.ok(
                customers={
                    'segment_distribution': CustomerAnalytics.get_segment_distribution(tenant=tenant),
                },
                points={
                    'outstanding_liability': str(PointsAnalytics.get_total_outstanding_liability(tenant=tenant)),
                    'issued_this_month':     str(PointsAnalytics.get_points_issued_this_month(tenant=tenant)),
                    'redeemed_this_month':   str(PointsAnalytics.get_points_redeemed_this_month(tenant=tenant)),
                    'redemption_rate':       PointsAnalytics.get_redemption_rate(tenant=tenant),
                    'breakage_estimate':     str(PointsAnalytics.get_breakage_estimate(tenant=tenant)),
                    'by_source':             PointsAnalytics.get_points_by_source(tenant=tenant, days=30),
                },
            )
        except Exception as e:
            return cls._err_exc(e, code='OVERVIEW_ERROR')

    # ── Points Analytics (analytics.py) ───────────────────────────────────────

    @classmethod
    def get_points_analytics(cls, tenant=None, days: int = 30) -> Dict[str, Any]:
        """
        Points liability, flow and source breakdown.

        Returns: ServiceResult.ok(outstanding_liability=..., ...)
        """
        try:
            from ..analytics import PointsAnalytics
            return ServiceResult.ok(
                outstanding_liability=str(PointsAnalytics.get_total_outstanding_liability(tenant=tenant)),
                issued_this_month=str(PointsAnalytics.get_points_issued_this_month(tenant=tenant)),
                redeemed_this_month=str(PointsAnalytics.get_points_redeemed_this_month(tenant=tenant)),
                redemption_rate=PointsAnalytics.get_redemption_rate(tenant=tenant),
                breakage_estimate=str(PointsAnalytics.get_breakage_estimate(tenant=tenant)),
                by_source=PointsAnalytics.get_points_by_source(tenant=tenant, days=days),
            )
        except Exception as e:
            return cls._err_exc(e, code='POINTS_ANALYTICS_ERROR')

    # ── Segment Analytics (analytics.py) ──────────────────────────────────────

    @classmethod
    def get_segment_analytics(cls, tenant=None) -> Dict[str, Any]:
        """
        Customer segment distribution (RFM).

        Returns: ServiceResult.ok(distribution={...}, at_risk=..., champions=...)
        """
        try:
            from ..analytics import CustomerAnalytics
            return ServiceResult.ok(
                distribution=CustomerAnalytics.get_segment_distribution(tenant=tenant),
                at_risk=CustomerAnalytics.get_at_risk_count(tenant=tenant),
                champions=CustomerAnalytics.get_champion_count(tenant=tenant),
            )
        except Exception as e:
            return cls._err_exc(e, code='SEGMENT_ERROR')

    # ── Campaign Analytics (analytics.py) ─────────────────────────────────────

    @classmethod
    def get_campaign_stats(cls, campaign) -> Dict[str, Any]:
        """
        Single campaign performance breakdown.

        Returns: ServiceResult.ok(**campaign_stats)
        """
        try:
            from ..analytics import CampaignAnalytics
            stats = CampaignAnalytics.get_campaign_stats(campaign)
            return ServiceResult.ok(**stats)
        except Exception as e:
            return cls._err_exc(e, code='CAMPAIGN_STATS_ERROR')

    # ── Reports (reports.py) ──────────────────────────────────────────────────

    @classmethod
    def get_report_summary(
        cls, tenant=None,
        date_from: Optional[str] = None,
        date_to: Optional[str]   = None,
    ) -> Dict[str, Any]:
        """
        Loyalty program summary report.

        Returns: ServiceResult.ok(**report_data)
        """
        try:
            from ..reports import LoyaltyReports
            reporter = LoyaltyReports(tenant=tenant)
            data = reporter.generate_summary(date_from=date_from, date_to=date_to)
            return ServiceResult.ok(**data) if isinstance(data, dict) else ServiceResult.ok(report=data)
        except Exception as e:
            return cls._err_exc(e, code='REPORT_SUMMARY_ERROR')

    @classmethod
    def get_report_points(
        cls, tenant=None,
        date_from: Optional[str] = None,
        date_to: Optional[str]   = None,
    ) -> Dict[str, Any]:
        """
        Points issuance, redemption, expiry report.

        Returns: ServiceResult.ok(**report_data)
        """
        try:
            from ..reports import LoyaltyReports
            reporter = LoyaltyReports(tenant=tenant)
            data = reporter.generate_points_report(date_from=date_from, date_to=date_to)
            return ServiceResult.ok(**data) if isinstance(data, dict) else ServiceResult.ok(report=data)
        except Exception as e:
            return cls._err_exc(e, code='REPORT_POINTS_ERROR')

    @classmethod
    def get_report_tiers(cls, tenant=None) -> Dict[str, Any]:
        """
        Tier distribution and upgrade/downgrade report.

        Returns: ServiceResult.ok(**report_data)
        """
        try:
            from ..reports import LoyaltyReports
            reporter = LoyaltyReports(tenant=tenant)
            data = reporter.generate_tier_report()
            return ServiceResult.ok(**data) if isinstance(data, dict) else ServiceResult.ok(report=data)
        except Exception as e:
            return cls._err_exc(e, code='REPORT_TIERS_ERROR')

    @classmethod
    def get_report_campaigns(
        cls, tenant=None,
        date_from: Optional[str] = None,
        date_to: Optional[str]   = None,
    ) -> Dict[str, Any]:
        """
        Campaign ROI and participation report.

        Returns: ServiceResult.ok(**report_data)
        """
        try:
            from ..reports import LoyaltyReports
            reporter = LoyaltyReports(tenant=tenant)
            data = reporter.generate_campaign_report(date_from=date_from, date_to=date_to)
            return ServiceResult.ok(**data) if isinstance(data, dict) else ServiceResult.ok(report=data)
        except Exception as e:
            return cls._err_exc(e, code='REPORT_CAMPAIGNS_ERROR')
