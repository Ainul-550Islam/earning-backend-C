# api/offer_inventory/misc_features/analytics_dashboard.py
"""
Analytics Dashboard Aggregator.
Single-call full dashboard: KPIs, live stats, funnel, trends, geo, devices.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class AnalyticsDashboard:
    """Full analytics dashboard data aggregator."""

    @classmethod
    def get_full_dashboard(cls, tenant=None, days: int = 7) -> dict:
        """Return complete dashboard data in one API call."""
        from api.offer_inventory.business.kpi_dashboard import KPIDashboard
        from api.offer_inventory.reporting_audit.admin_dashboard_stats import AdminDashboardStats
        from api.offer_inventory.analytics import OfferAnalytics

        return {
            'summary'         : KPIDashboard.get_platform_kpis(days=days, tenant=tenant),
            'live_stats'      : AdminDashboardStats.get_live_stats(tenant=tenant),
            'conversion_funnel': AdminDashboardStats.get_conversion_funnel(days=days),
            'revenue_trend'   : OfferAnalytics.get_revenue_trend(tenant=tenant, days=days),
            'geo_breakdown'   : OfferAnalytics.get_geo_breakdown(days=days),
            'device_breakdown': OfferAnalytics.get_device_breakdown(days=days),
            'top_offers'      : OfferAnalytics.get_top_performers(metric='revenue', days=days, limit=5),
            'network_roi'     : KPIDashboard.network_roi_report(days=days),
            'forecast'        : KPIDashboard.forecast_revenue(days_ahead=30),
            'generated_at'    : timezone.now().isoformat(),
        }

    @classmethod
    def get_user_dashboard(cls, user) -> dict:
        """Analytics dashboard for an individual user."""
        from api.offer_inventory.user_behavior_analysis.engagement_score import EngagementScoreCalculator
        from api.offer_inventory.user_behavior_analysis.activity_heatmap import ActivityHeatmapService
        from api.offer_inventory.marketing.referral_program import ReferralProgramManager
        from api.offer_inventory.finance_payment.wallet_integration import WalletIntegration

        return {
            'wallet'         : WalletIntegration.get_balance(user),
            'engagement'     : EngagementScoreCalculator.calculate(user),
            'heatmap'        : ActivityHeatmapService.get_user_heatmap(user),
            'best_send_time' : ActivityHeatmapService.get_best_send_time(user),
            'referral_stats' : ReferralProgramManager.get_stats(user),
        }

    @classmethod
    def get_fraud_dashboard(cls, days: int = 7) -> dict:
        """Fraud-specific dashboard."""
        from api.offer_inventory.models import FraudAttempt, BlacklistedIP, Click
        from django.db.models import Count
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        return {
            'fraud_clicks'       : Click.objects.filter(is_fraud=True, created_at__gte=since).count(),
            'total_clicks'       : Click.objects.filter(created_at__gte=since).count(),
            'fraud_attempts'     : FraudAttempt.objects.filter(created_at__gte=since).count(),
            'new_ip_blocks'      : BlacklistedIP.objects.filter(created_at__gte=since).count(),
            'top_fraud_countries': list(
                Click.objects.filter(is_fraud=True, created_at__gte=since)
                .exclude(country_code='')
                .values('country_code')
                .annotate(count=Count('id'))
                .order_by('-count')[:5]
            ),
            'days': days,
        }

    @classmethod
    def get_financial_dashboard(cls, days: int = 30) -> dict:
        """Financial overview dashboard."""
        from api.offer_inventory.business.kpi_dashboard import KPIDashboard
        from api.offer_inventory.reporting import ReportGenerator
        from api.offer_inventory.models import WithdrawalRequest
        from django.db.models import Count, Sum

        kpis    = KPIDashboard.get_platform_kpis(days=days)
        recon   = ReportGenerator.payout_reconciliation()
        pending = WithdrawalRequest.objects.filter(status='pending').aggregate(
            count=Count('id'), total=Sum('amount')
        )
        return {
            'kpis'                   : kpis,
            'monthly_reconciliation' : recon,
            'pending_withdrawals'    : {
                'count' : pending['count'] or 0,
                'amount': float(pending['total'] or 0),
            },
            'days': days,
        }

    @classmethod
    def get_network_dashboard(cls, days: int = 7) -> dict:
        """Network performance dashboard."""
        from api.offer_inventory.business.kpi_dashboard import KPIDashboard
        from api.offer_inventory.models import OfferNetwork

        networks = list(
            OfferNetwork.objects.filter(status='active')
            .values('id', 'name', 'slug', 'revenue_share_pct')
        )
        return {
            'networks'   : networks,
            'roi_report' : KPIDashboard.network_roi_report(days=days),
            'days'       : days,
        }
