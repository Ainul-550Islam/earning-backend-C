# api/djoyalty/tests/test_analytics_extended.py
"""
Extended AnalyticsViewSet tests -- kpi_dashboard, kpi_history,
report_summary, report_points, report_tiers, report_campaigns,
cohort_table, customer_ltv, points_liability, segments。
Previously 0 of these 10 actions were tested。
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _admin():
    u = User.objects.create_user(username=f'ana_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c

def _customer_client():
    from djoyalty.models.core import Tenant, Customer
    t = Tenant.objects.create(name=f'AnaCo-{Tenant.objects.count()}',
                               slug=f'ana-{Tenant.objects.count()}', is_active=True)
    u = User.objects.create_user(username=f'anac_{User.objects.count()}', password='pw')
    c = Customer.objects.create(tenant=t, user=u, code=f'A{Customer.objects.count():04d}', is_active=True)
    cli = APIClient(); cli.force_authenticate(user=u)
    return cli


class KPIDashboardTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.KPITracker')
    def test_kpi_dashboard_returns_all_metrics(self, mock_kpi_cls):
        tracker = MagicMock()
        tracker.get_revenue_per_point.return_value  = 0.05
        tracker.get_redemption_rate.return_value    = 42.5
        tracker.get_retention_rate.return_value     = 78.3
        tracker.get_nps_score.return_value          = 55
        tracker.get_active_member_percentage.return_value = 61.2
        tracker.get_avg_ltv.return_value            = Decimal('15000')
        tracker.get_churn_rate.return_value         = 8.7
        tracker.get_program_roi.return_value        = 320.0
        tracker.get_as_of_date.return_value         = '2026-06-01'
        mock_kpi_cls.return_value = tracker
        resp = self.admin.get('/api/loyalty/analytics/kpi/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ('revenue_per_point', 'redemption_rate', 'retention_rate',
                      'nps_score', 'active_member_pct', 'avg_ltv', 'churn_rate',
                      'program_roi', 'as_of', 'period'):
            self.assertIn(field, resp.data, f"Missing KPI field: {field}")

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.KPITracker')
    def test_kpi_history(self, mock_kpi_cls):
        tracker = MagicMock()
        tracker.get_history.return_value = [
            {'month': '2026-01', 'value': 38.5},
            {'month': '2026-02', 'value': 41.2},
        ]
        mock_kpi_cls.return_value = tracker
        resp = self.admin.get('/api/loyalty/analytics/kpi/history/?metric=redemption_rate&months=6')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('history', resp.data)
        self.assertIn('metric', resp.data)
        self.assertIsInstance(resp.data['history'], list)

    def test_kpi_requires_admin(self):
        cli = _customer_client()
        resp = cli.get('/api/loyalty/analytics/kpi/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AnalyticsReportsTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.LoyaltyReports')
    def test_report_summary(self, mock_reporter_cls):
        reporter = MagicMock()
        reporter.generate_summary.return_value = {
            'total_customers': 1200, 'active_customers': 800,
            'total_points_issued': 500000, 'total_points_redeemed': 200000,
            'redemption_rate': 40.0, 'period': 'all_time',
        }
        mock_reporter_cls.return_value = reporter
        resp = self.admin.get('/api/loyalty/analytics/reports/summary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_customers', resp.data)
        reporter.generate_summary.assert_called_once()

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.LoyaltyReports')
    def test_report_points(self, mock_reporter_cls):
        reporter = MagicMock()
        reporter.generate_points_report.return_value = {
            'issued': 50000, 'redeemed': 20000, 'expired': 5000,
            'breakage': 5000, 'period': '30d',
        }
        mock_reporter_cls.return_value = reporter
        resp = self.admin.get('/api/loyalty/analytics/reports/points/?from=2026-01-01&to=2026-06-01')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('issued', resp.data)
        reporter.generate_points_report.assert_called_once()

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.LoyaltyReports')
    def test_report_tiers(self, mock_reporter_cls):
        reporter = MagicMock()
        reporter.generate_tier_report.return_value = {
            'distribution': [{'tier': 'Bronze', 'count': 500, 'pct': 50.0}],
            'upgrades_30d': 45, 'downgrades_30d': 12,
        }
        mock_reporter_cls.return_value = reporter
        resp = self.admin.get('/api/loyalty/analytics/reports/tiers/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('distribution', resp.data)

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.LoyaltyReports')
    def test_report_campaigns(self, mock_reporter_cls):
        reporter = MagicMock()
        reporter.generate_campaign_report.return_value = {
            'campaigns': [], 'total_spend': 0, 'total_conversions': 0,
        }
        mock_reporter_cls.return_value = reporter
        resp = self.admin.get('/api/loyalty/analytics/reports/campaigns/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        reporter.generate_campaign_report.assert_called_once()


class CohortAnalysisTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.LoyaltyCohortAnalyzer')
    def test_cohort_table(self, mock_cls):
        analyzer = MagicMock()
        analyzer.get_cohort_table.return_value = [
            {'cohort_month': '2026-01', 'cohort_size': 100,
             'retention_m1': 72.0, 'retention_m3': 55.0},
        ]
        analyzer.get_avg_retention_rate.return_value = 65.0
        analyzer.get_summary.return_value = {'avg_cohort_size': 100}
        mock_cls.return_value = analyzer
        resp = self.admin.get('/api/loyalty/analytics/cohort-table/?months=6')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('cohort_table', resp.data)
        self.assertIn('avg_retention_m1', resp.data)
        self.assertIn('summary', resp.data)


class CustomerLTVTest(TestCase):
    def setUp(self):
        self.admin    = _admin()
        from djoyalty.models.core import Tenant, Customer
        t = Tenant.objects.create(name='LTVCo', slug=f'ltv-{Tenant.objects.count()}', is_active=True)
        u = User.objects.create_user(username=f'ltv_{User.objects.count()}', password='pw')
        self.customer = Customer.objects.create(tenant=t, user=u,
                                                code=f'L{Customer.objects.count():04d}', is_active=True)

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.LTVCalculator')
    def test_customer_ltv(self, mock_ltv_cls):
        calc = MagicMock()
        calc.get_full_ltv.return_value = {
            'customer_id': self.customer.pk, 'customer_code': self.customer.code,
            'predicted_ltv_12m': Decimal('12000'), 'predicted_ltv_24m': Decimal('22000'),
            'historical_spend': Decimal('8000'), 'avg_order_value': Decimal('800'),
            'purchase_frequency': 2.5, 'churn_probability': 0.12,
            'rfm_segment': 'Champions', 'rfm_score': 4.8, 'tier': 'Gold',
        }
        mock_ltv_cls.return_value = calc
        resp = self.admin.get(f'/api/loyalty/analytics/customer/{self.customer.pk}/ltv/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ('predicted_ltv_12m', 'predicted_ltv_24m', 'rfm_segment', 'churn_probability'):
            self.assertIn(field, resp.data)

    def test_customer_ltv_not_found(self):
        resp = self.admin.get('/api/loyalty/analytics/customer/99999/ltv/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class PointsLiabilityTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.AnalyticsViewSet.PointsAnalytics')
    def test_points_liability(self, mock_pa):
        mock_pa.get_total_outstanding_liability.return_value = Decimal('500000')
        mock_pa.get_points_issued_this_month.return_value   = Decimal('50000')
        mock_pa.get_points_redeemed_this_month.return_value = Decimal('20000')
        mock_pa.get_redemption_rate.return_value            = 40.0
        mock_pa.get_breakage_estimate.return_value          = Decimal('15000')
        mock_pa.get_points_by_source.return_value           = {'purchase': 80.0, 'bonus': 20.0}
        resp = self.admin.get('/api/loyalty/analytics/points/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ('outstanding_liability', 'issued_this_month', 'redeemed_this_month',
                      'redemption_rate', 'breakage_estimate', 'by_source'):
            self.assertIn(field, resp.data)
