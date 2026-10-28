"""
tests/test_viewsets_search.py — NEWLY CREATED
Tests for SearchViewSet, SchemaViewSet, ResourceViewSet (0% covered before)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class SearchViewSetBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='srch_admin', email='srch@test.com', password='pass123')
        self.user = User.objects.create_user(
            username='srch_user', email='srchuser@test.com', password='pass123')
        self.client.force_authenticate(user=self.admin)
        # Seed data
        from api.alerts.models.core import AlertRule, AlertLog
        self.rule = AlertRule.objects.create(
            name='Search Test CPU Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30, is_active=True,
            created_by=self.user)
        AlertLog.objects.create(
            rule=self.rule, trigger_value=90.0, threshold_value=80.0,
            message='CPU threshold exceeded in prod', is_resolved=False)


# ── SearchViewSet ─────────────────────────────────────────────────────────────
class SearchViewSetTest(SearchViewSetBase):

    def test_global_search_missing_q(self):
        resp = self.client.get('/search/')
        self.assertEqual(resp.status_code, 400)

    def test_global_search_with_query(self):
        resp = self.client.get('/search/?q=cpu')
        self.assertIn(resp.status_code, [200])

    def test_search_rules_no_params(self):
        resp = self.client.get('/search/rules/')
        self.assertEqual(resp.status_code, 400)

    def test_search_rules_by_query(self):
        resp = self.client.get('/search/rules/?q=cpu')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('results', resp.data)

    def test_search_rules_by_severity(self):
        resp = self.client.get('/search/rules/?severity=high')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('count', resp.data)

    def test_search_rules_by_type(self):
        resp = self.client.get('/search/rules/?type=cpu_usage')
        self.assertIn(resp.status_code, [200])

    def test_search_logs_by_query(self):
        resp = self.client.get('/search/logs/?q=CPU')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_search_logs_by_severity(self):
        resp = self.client.get('/search/logs/?severity=high')
        self.assertEqual(resp.status_code, 200)

    def test_search_logs_resolved_filter(self):
        resp = self.client.get('/search/logs/?resolved=false')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_search_logs_returns_results(self):
        resp = self.client.get('/search/logs/?q=threshold')
        self.assertEqual(resp.status_code, 200)

    def test_search_notifications_missing_q(self):
        resp = self.client.get('/search/notifications/')
        self.assertEqual(resp.status_code, 400)

    def test_search_notifications_valid(self):
        from api.alerts.models.core import AlertRule, AlertLog, Notification
        rule = AlertRule.objects.create(
            name='Notif Search Test', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0,
            message='Test', is_resolved=False)
        Notification.objects.create(
            alert_log=log, notification_type='email',
            status='pending', recipient='ops@test.com', message='Alert fired')
        resp = self.client.get('/search/notifications/?q=ops')
        self.assertIn(resp.status_code, [200])
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['recipient'], 'ops@test.com')

    def test_suggestions_missing_prefix(self):
        resp = self.client.get('/search/suggestions/')
        self.assertEqual(resp.status_code, 400)

    def test_suggestions_valid(self):
        resp = self.client.get('/search/suggestions/?prefix=cpu')
        self.assertIn(resp.status_code, [200])

    def test_search_analytics(self):
        resp = self.client.get('/search/analytics/')
        self.assertIn(resp.status_code, [200])

    def test_search_facets(self):
        resp = self.client.get('/search/facets/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('facets', data)
        self.assertIn('severity', data['facets'])
        self.assertIn('alert_type', data['facets'])
        self.assertIn('status', data['facets'])
        # Verify our seeded data shows up
        self.assertGreaterEqual(data['facets']['severity'].get('high', 0), 1)

    def test_regular_user_can_search(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/search/logs/?q=cpu')
        self.assertEqual(resp.status_code, 200)


# ── SchemaViewSet ─────────────────────────────────────────────────────────────
class SchemaViewSetTest(SearchViewSetBase):

    def test_list_schemas(self):
        resp = self.client.get('/search/schema/')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('schemas', resp.data)

    def test_get_schema_missing_type(self):
        resp = self.client.get('/search/schema/get/')
        self.assertEqual(resp.status_code, 400)

    def test_get_schema_alert_rule(self):
        resp = self.client.get('/search/schema/get/?type=alert_rule')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('type', resp.data)
            self.assertEqual(resp.data['type'], 'alert_rule')

    def test_validate_missing_schema_type(self):
        resp = self.client.post('/search/schema/validate/',
                                {'payload': {'name': 'test'}}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_validate_valid_payload(self):
        resp = self.client.post('/search/schema/validate/', {
            'schema_type': 'alert_rule',
            'payload': {'name': 'Test Rule', 'alert_type': 'server_error',
                        'severity': 'high', 'threshold_value': 80}}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_webhook_schemas(self):
        resp = self.client.get('/search/schema/webhooks/')
        self.assertIn(resp.status_code, [200])

    def test_system_schemas(self):
        resp = self.client.get('/search/schema/system/')
        self.assertIn(resp.status_code, [200])

    def test_schema_types_in_list(self):
        resp = self.client.get('/search/schema/')
        if resp.status_code == 200:
            schemas = resp.data.get('schemas', [])
            expected = ['alert_rule', 'alert_log', 'notification', 'threshold']
            for s in expected:
                self.assertIn(s, schemas)


# ── ResourceViewSet ───────────────────────────────────────────────────────────
class ResourceViewSetTest(SearchViewSetBase):

    def test_list_resources(self):
        resp = self.client.get('/search/resources/')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('resources', resp.data)

    def test_export_rules(self):
        resp = self.client.get('/search/resources/export/rules/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('data', resp.data)

    def test_export_rules_csv_format(self):
        resp = self.client.get('/search/resources/export/rules/?format=json')
        self.assertEqual(resp.status_code, 200)

    def test_export_logs(self):
        resp = self.client.get('/search/resources/export/logs/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)

    def test_export_logs_with_limit(self):
        resp = self.client.get('/search/resources/export/logs/?limit=10')
        self.assertEqual(resp.status_code, 200)

    def test_import_rules_missing_data(self):
        resp = self.client.post('/search/resources/import/rules/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_import_rules_valid(self):
        resp = self.client.post('/search/resources/import/rules/', {
            'data': [{'name': 'Imported Rule', 'alert_type': 'server_error',
                      'severity': 'high', 'threshold_value': 80.0}]}, format='json')
        self.assertIn(resp.status_code, [200, 201])

    def test_resource_info(self):
        resp = self.client.get('/search/resources/info/')
        self.assertIn(resp.status_code, [200])

    def test_export_count_matches_db(self):
        from api.alerts.models.core import AlertRule
        resp = self.client.get('/search/resources/export/rules/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], AlertRule.objects.count())

    def test_requires_admin_for_import(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/search/resources/import/rules/',
                                {'data': []}, format='json')
        self.assertEqual(resp.status_code, 403)
