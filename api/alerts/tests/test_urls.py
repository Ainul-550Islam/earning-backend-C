"""
Tests for URL patterns — FIXED
In the pytest-django context ROOT_URLCONF='api.alerts.urls' (no api/v1/ prefix).
All paths use the correct no-prefix form: /rules/, /channel/, /threshold/, etc.
"""
from django.test import TestCase
from django.urls import resolve, NoReverseMatch
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


def _ok(tc, path):
    try:
        resolve(path)
    except Exception as e:
        tc.fail(f"Could not resolve '{path}': {e}")


# ─── Resolve tests ────────────────────────────────────────────────────────────

class CoreURLResolveTest(TestCase):
    def test_rules_urls(self):
        for p in ['/rules/', '/rules/1/',
                  '/rules/1/activate/', '/rules/1/deactivate/',
                  '/rules/1/test/', '/rules/1/statistics/']:
            _ok(self, p)

    def test_logs_urls(self):
        for p in ['/logs/', '/logs/1/',
                  '/logs/1/resolve/', '/logs/1/acknowledge/',
                  '/logs/by_rule/1/', '/logs/pending/',
                  '/logs/resolved/', '/logs/by_severity/high/']:
            _ok(self, p)

    def test_notification_urls(self):
        for p in ['/notifications/', '/notifications/1/',
                  '/notifications/1/mark_sent/',
                  '/notifications/1/mark_failed/',
                  '/notifications/1/retry/',
                  '/notifications/by_status/pending/',
                  '/notifications/by_type/email/',
                  '/notifications/failed/']:
            _ok(self, p)

    def test_health_urls(self):
        for p in ['/health/', '/health/metrics/', '/health/history/',
                  '/health/check/', '/health/rules/', '/health/channels/',
                  '/health/incidents/']:
            _ok(self, p)

    def test_overview_urls(self):
        for p in ['/overview/', '/overview/summary/',
                  '/overview/recent_alerts/', '/overview/trends/',
                  '/overview/top_rules/', '/overview/metrics/',
                  '/overview/statistics/']:
            _ok(self, p)

    def test_maintenance_urls(self):
        for p in ['/maintenance/', '/maintenance/1/',
                  '/maintenance/suppress_alerts/',
                  '/maintenance/impact/',
                  '/maintenance/1/extend/', '/maintenance/1/complete/',
                  '/maintenance/history/', '/maintenance/upcoming/']:
            _ok(self, p)


class ThresholdURLResolveTest(TestCase):
    def test_configs(self):
        for p in ['/threshold/configs/', '/threshold/configs/1/',
                  '/threshold/configs/1/evaluate/',
                  '/threshold/configs/1/effectiveness/']:
            _ok(self, p)

    def test_breaches(self):
        for p in ['/threshold/breaches/', '/threshold/breaches/1/',
                  '/threshold/breaches/1/resolve/',
                  '/threshold/breaches/by_severity/high/',
                  '/threshold/breaches/active/',
                  '/threshold/breaches/statistics/']:
            _ok(self, p)

    def test_adaptive(self):
        for p in ['/threshold/adaptive/', '/threshold/adaptive/1/',
                  '/threshold/adaptive/1/train/',
                  '/threshold/adaptive/1/adapt/',
                  '/threshold/adaptive/1/history/']:
            _ok(self, p)

    def test_profiles(self):
        for p in ['/threshold/profiles/', '/threshold/profiles/1/',
                  '/threshold/profiles/1/apply/',
                  '/threshold/profiles/1/clone/']:
            _ok(self, p)


class ChannelURLResolveTest(TestCase):
    def test_channels(self):
        for p in ['/channel/', '/channel/1/',
                  '/channel/1/enable/', '/channel/1/disable/',
                  '/channel/1/test/', '/channel/1/health/',
                  '/channel/1/statistics/']:
            _ok(self, p)

    def test_routes(self):
        for p in ['/channel/routes/', '/channel/routes/1/',
                  '/channel/routes/1/activate/',
                  '/channel/routes/1/deactivate/']:
            _ok(self, p)

    def test_recipients(self):
        for p in ['/channel/recipients/', '/channel/recipients/1/',
                  '/channel/recipients/1/activate/',
                  '/channel/recipients/1/deactivate/']:
            _ok(self, p)


class IncidentURLResolveTest(TestCase):
    def test_incidents(self):
        for p in ['/incident/', '/incident/1/',
                  '/incident/1/acknowledge/',
                  '/incident/1/resolve/', '/incident/1/close/',
                  '/incident/1/escalate/',
                  '/incident/by_severity/high/',
                  '/incident/by_status/open/',
                  '/incident/active/']:
            _ok(self, p)

    def test_timelines(self):
        for p in ['/incident/timelines/', '/incident/timelines/1/',
                  '/incident/timelines/by_incident/1/']:
            _ok(self, p)

    def test_oncall(self):
        for p in ['/incident/oncall_schedules/',
                  '/incident/oncall_schedules/1/',
                  '/incident/oncall_schedules/1/rotate/',
                  '/incident/oncall_schedules/active/']:
            _ok(self, p)


class IntelligenceURLResolveTest(TestCase):
    def test_correlations(self):
        for p in ['/intelligence/correlations/',
                  '/intelligence/correlations/1/',
                  '/intelligence/correlations/1/analyze/',
                  '/intelligence/correlations/significant/']:
            _ok(self, p)

    def test_predictions(self):
        for p in ['/intelligence/predictions/',
                  '/intelligence/predictions/1/',
                  '/intelligence/predictions/1/train/',
                  '/intelligence/predictions/active/']:
            _ok(self, p)

    def test_rca(self):
        for p in ['/intelligence/rca/', '/intelligence/rca/1/',
                  '/intelligence/rca/1/analyze/',
                  '/intelligence/overview/']:
            _ok(self, p)


class ReportingURLResolveTest(TestCase):
    def test_reports(self):
        for p in ['/reporting/', '/reporting/1/',
                  '/reporting/1/generate/',
                  '/reporting/by_type/daily/']:
            _ok(self, p)

    def test_mttr(self):
        for p in ['/reporting/mttr/', '/reporting/mttr/1/',
                  '/reporting/mttr/1/calculate/']:
            _ok(self, p)

    def test_sla(self):
        for p in ['/reporting/sla_breaches/',
                  '/reporting/sla_breaches/1/',
                  '/reporting/sla_breaches/active/',
                  '/reporting/dashboard/']:
            _ok(self, p)


class URLNameTest(TestCase):
    """Resolve paths and verify their url_name strings"""
    def _check(self, path, expected_name):
        match = resolve(path)
        self.assertEqual(match.url_name, expected_name,
                         f"Path {path}: expected '{expected_name}', got '{match.url_name}'")

    def test_core_names(self):
        self._check('/rules/', 'alert-rule-list')
        self._check('/logs/', 'alert-log-list')
        self._check('/notifications/', 'notification-list')
        self._check('/health/', 'system-health-list')
        self._check('/overview/', 'alert-overview-list')
        self._check('/maintenance/', 'alert-maintenance-list')

    def test_threshold_names(self):
        self._check('/threshold/configs/', 'threshold-config-list')
        self._check('/threshold/breaches/', 'threshold-breach-list')
        self._check('/threshold/adaptive/', 'adaptive-threshold-list')

    def test_channel_names(self):
        self._check('/channel/', 'alert-channel-list')
        self._check('/channel/routes/', 'channel-route-list')
        self._check('/channel/recipients/', 'alert-recipient-list')

    def test_incident_names(self):
        self._check('/incident/', 'incident-list')

    def test_intelligence_names(self):
        self._check('/intelligence/correlations/', 'alert-correlation-list')
        self._check('/intelligence/predictions/', 'alert-prediction-list')

    def test_reporting_names(self):
        self._check('/reporting/', 'alert-report-list')
        self._check('/reporting/mttr/', 'mttr-metric-list')
        self._check('/reporting/sla_breaches/', 'sla-breach-list')


# ─── API smoke tests ──────────────────────────────────────────────────────────

class AlertURLsAPITest(APITestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='testurlapi', email='test@example.com', password='testpass123')
        self.client.force_authenticate(user=self.user)

    def _get_ok(self, path):
        response = self.client.get(path)
        self.assertIn(response.status_code,
                      [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT,
                       status.HTTP_403_FORBIDDEN],   # admin-only endpoints return 403 for regular users
                      f"GET {path} returned {response.status_code}")

    def test_alert_rules_list(self):
        self._get_ok('/rules/')

    def test_alert_logs_list(self):
        self._get_ok('/logs/')

    def test_notifications_list(self):
        self._get_ok('/notifications/')

    def test_system_health_list(self):
        self._get_ok('/health/')

    def test_overview_list(self):
        self._get_ok('/overview/')

    def test_maintenance_list(self):
        self._get_ok('/maintenance/')

    def test_threshold_config_list(self):
        self._get_ok('/threshold/configs/')

    def test_threshold_breach_list(self):
        self._get_ok('/threshold/breaches/')

    def test_adaptive_threshold_list(self):
        self._get_ok('/threshold/adaptive/')

    def test_channel_list(self):
        self._get_ok('/channel/')

    def test_incident_list(self):
        self._get_ok('/incident/')

    def test_correlation_list(self):
        self._get_ok('/intelligence/correlations/')

    def test_report_list(self):
        self._get_ok('/reporting/')

    def test_sla_breach_list(self):
        self._get_ok('/reporting/sla_breaches/')

    def test_unauthorized_returns_401(self):
        self.client.force_authenticate(user=None)
        for path in ['/rules/', '/logs/', '/notifications/']:
            resp = self.client.get(path)
            self.assertIn(
                resp.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                f"Expected 401/403 for {path}, got {resp.status_code}"
            )

    def test_filtering_params_accepted(self):
        resp = self.client.get('/rules/?severity=high&is_active=true')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_ordering_param_accepted(self):
        resp = self.client.get('/rules/?ordering=-created_at')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
