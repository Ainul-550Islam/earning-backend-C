"""
Tests for Core ViewSets — FIXED
URL prefix: /rules/, /logs/, /notifications/, /health/, /overview/, /maintenance/
(ROOT_URLCONF=alerts.urls in test context — no /api/v1/ prefix)
Pagination disabled in test_settings → response.data is a plain list.
"""
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from api.alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics

User = get_user_model()


def _count(data):
    if isinstance(data, dict):
        return len(data.get('results', []))
    return len(data)


def _make_rule(name='VS Rule', user=None, **kwargs):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high',
        threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
        created_by=user, **kwargs)


def _make_log(rule, msg='CPU high', trigger=85.0):
    return AlertLog.objects.create(
        rule=rule, trigger_value=trigger, threshold_value=80.0, message=msg)


# ─── AlertRuleViewSet ─────────────────────────────────────────────────────────

class AlertRuleViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='rulevstest', email='rvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.rule = _make_rule('Test Alert Rule', user=self.user)

    def test_list_alert_rules(self):
        resp = self.client.get('/rules/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_alert_rule(self):
        data = {'name': 'New Alert Rule', 'alert_type': 'server_error',
                'severity': 'medium', 'threshold_value': 85.0,
                'time_window_minutes': 60, 'cooldown_minutes': 15}
        resp = self.client.post('/rules/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AlertRule.objects.filter(name='New Alert Rule').exists())

    def test_retrieve_alert_rule(self):
        resp = self.client.get(f'/rules/{self.rule.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Test Alert Rule')

    def test_update_alert_rule(self):
        resp = self.client.patch(f'/rules/{self.rule.id}/',
                                 {'severity': 'critical'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.severity, 'critical')

    def test_delete_alert_rule(self):
        resp = self.client.delete(f'/rules/{self.rule.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AlertRule.objects.filter(id=self.rule.id).exists())

    def test_activate_rule(self):
        self.rule.is_active = False
        self.rule.save()
        resp = self.client.post(f'/rules/{self.rule.id}/activate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.rule.refresh_from_db()
        self.assertTrue(self.rule.is_active)

    def test_deactivate_rule(self):
        resp = self.client.post(f'/rules/{self.rule.id}/deactivate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.rule.refresh_from_db()
        self.assertFalse(self.rule.is_active)

    def test_test_rule(self):
        resp = self.client.post(f'/rules/{self.rule.id}/test/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_rule_statistics(self):
        resp = self.client.get(f'/rules/{self.rule.id}/statistics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_filter_by_severity(self):
        resp = self.client.get('/rules/?severity=high')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_filter_by_active(self):
        resp = self.client.get('/rules/?is_active=true')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthorized_rejected(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/rules/')
        self.assertIn(resp.status_code,
                      [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ─── AlertLogViewSet ──────────────────────────────────────────────────────────

class AlertLogViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='logvstest', email='lvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.rule = _make_rule('Log VS Rule', user=self.user)
        self.log = _make_log(self.rule)

    def test_list_logs(self):
        resp = self.client.get('/logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_retrieve_log(self):
        resp = self.client.get(f'/logs/{self.log.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['message'], 'CPU high')

    def test_resolve_log(self):
        resp = self.client.post(f'/logs/{self.log.id}/resolve/',
                                {'resolution_note': 'Fixed'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.log.refresh_from_db()
        self.assertTrue(self.log.is_resolved)

    def test_acknowledge_log(self):
        resp = self.client.post(f'/logs/{self.log.id}/acknowledge/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_logs_by_rule(self):
        resp = self.client.get(f'/logs/by_rule/{self.rule.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_pending_logs(self):
        resp = self.client.get('/logs/pending/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_resolved_logs(self):
        self.log.is_resolved = True
        self.log.save()
        resp = self.client.get('/logs/resolved/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_logs_by_severity(self):
        resp = self.client.get('/logs/by_severity/high/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_filter_by_resolved(self):
        resp = self.client.get('/logs/?is_resolved=false')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─── NotificationViewSet ──────────────────────────────────────────────────────

class NotificationViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='notifvstest', email='nvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.rule = _make_rule('Notif VS Rule', user=self.user)
        self.log = _make_log(self.rule)
        self.notif = Notification.objects.create(
            alert_log=self.log, notification_type='email',
            recipient='nvs@example.com', status='pending')

    def test_list_notifications(self):
        resp = self.client.get('/notifications/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_retrieve_notification(self):
        resp = self.client.get(f'/notifications/{self.notif.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['recipient'], 'nvs@example.com')

    def test_mark_sent(self):
        resp = self.client.post(f'/notifications/{self.notif.id}/mark_sent/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.notif.refresh_from_db()
        self.assertEqual(self.notif.status, 'sent')

    def test_mark_failed(self):
        resp = self.client.post(f'/notifications/{self.notif.id}/mark_failed/',
                                {'error': 'SMTP error'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.notif.refresh_from_db()
        self.assertEqual(self.notif.status, 'failed')

    def test_retry_notification(self):
        self.notif.status = 'failed'
        self.notif.save()
        resp = self.client.post(f'/notifications/{self.notif.id}/retry/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_notifications_by_status(self):
        resp = self.client.get('/notifications/by_status/pending/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_notifications_by_type(self):
        resp = self.client.get('/notifications/by_type/email/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_failed_notifications(self):
        resp = self.client.get('/notifications/failed/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_notification(self):
        data = {'alert_log': self.log.id, 'notification_type': 'sms',
                'recipient': '+1234567890', 'status': 'pending',
                'message': 'Test SMS notification'}
        resp = self.client.post('/notifications/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


# ─── SystemHealthViewSet ──────────────────────────────────────────────────────

class SystemHealthViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='healthvstest', email='hvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)

    def test_health_list(self):
        resp = self.client.get('/health/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_metrics(self):
        resp = self.client.get('/health/metrics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_history(self):
        resp = self.client.get('/health/history/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_check(self):
        resp = self.client.get('/health/check/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_rules(self):
        resp = self.client.get('/health/rules/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_channels(self):
        resp = self.client.get('/health/channels/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_incidents(self):
        resp = self.client.get('/health/incidents/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─── AlertOverviewViewSet ─────────────────────────────────────────────────────

class AlertOverviewViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='overviewvstest', email='ovs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.rule = _make_rule('Overview Rule', user=self.user)
        for i in range(3):
            _make_log(self.rule, msg=f'Alert {i}', trigger=82.0 + i)

    def test_overview_list(self):
        resp = self.client.get('/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_overview_summary(self):
        resp = self.client.get('/overview/summary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_recent_alerts(self):
        resp = self.client.get('/overview/recent_alerts/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_overview_trends(self):
        resp = self.client.get('/overview/trends/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_top_rules(self):
        resp = self.client.get('/overview/top_rules/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_overview_metrics(self):
        resp = self.client.get('/overview/metrics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_overview_statistics(self):
        resp = self.client.get('/overview/statistics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─── AlertMaintenanceViewSet ──────────────────────────────────────────────────

class AlertMaintenanceViewSetTest(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='adminmaint', email='adm@example.com', password='adminpass')
        self.client.force_authenticate(user=self.admin)

    def test_maintenance_list(self):
        resp = self.client.get('/maintenance/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_maintenance_impact(self):
        resp = self.client.get('/maintenance/impact/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_maintenance_history(self):
        resp = self.client.get('/maintenance/history/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_maintenance_upcoming(self):
        resp = self.client.get('/maintenance/upcoming/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_suppress_alerts(self):
        resp = self.client.post('/maintenance/suppress_alerts/',
                                {'duration_minutes': 30}, format='json')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_maintenance_forbidden_for_regular_user(self):
        regular = User.objects.create_user(
            username='regularmaint', email='reg@example.com', password='pass')
        self.client.force_authenticate(user=regular)
        resp = self.client.get('/maintenance/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
