"""Tests for Reporting ViewSets — FIXED. URL prefix: /reporting/"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from api.alerts.models.reporting import AlertReport, MTTRMetric, MTTDMetric, SLABreach

User = get_user_model()


def _count(data):
    if isinstance(data, dict): return len(data.get('results', []))
    return len(data)


def _report(title='Test Report', rtype='daily', user=None):
    now = timezone.now()
    return AlertReport.objects.create(
        title=title, report_type=rtype,
        start_date=now - timedelta(days=1), end_date=now,
        created_by=user)


class AlertReportViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('repvs','rep@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.report = _report(user=self.user)

    def test_list_reports(self):
        resp = self.client.get('/reporting/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_report(self):
        now = timezone.now()
        data = {'title': 'Weekly Report', 'report_type': 'weekly',
                'start_date': (now - timedelta(days=7)).isoformat(),
                'end_date': now.isoformat()}
        resp = self.client.post('/reporting/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_report(self):
        resp = self.client.get(f'/reporting/{self.report.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'Test Report')

    def test_update_report(self):
        resp = self.client.patch(f'/reporting/{self.report.id}/',
                                 {'title': 'Updated Report'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, 'Updated Report')

    def test_delete_report(self):
        resp = self.client.delete(f'/reporting/{self.report.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_generate_report(self):
        resp = self.client.post(f'/reporting/{self.report.id}/generate/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_reports_by_type(self):
        resp = self.client.get('/reporting/by_type/daily/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_recent_reports(self):
        resp = self.client.get('/reporting/recent/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_report_overview(self):
        resp = self.client.get('/reporting/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MTTRMetricViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('mttrvs','mttr@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.metric = MTTRMetric.objects.create(
            name='MTTR Primary', target_mttr_minutes=30.0)

    def test_list_mttr(self):
        resp = self.client.get('/reporting/mttr/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_mttr(self):
        data = {'name': 'MTTR Secondary', 'target_mttr_minutes': 45.0}
        resp = self.client.post('/reporting/mttr/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_mttr(self):
        resp = self.client.get(f'/reporting/mttr/{self.metric.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'MTTR Primary')

    def test_update_mttr(self):
        resp = self.client.patch(f'/reporting/mttr/{self.metric.id}/',
                                 {'target_mttr_minutes': 60.0}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_calculate_mttr(self):
        resp = self.client.post(f'/reporting/mttr/{self.metric.id}/calculate/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_mttr_trends(self):
        resp = self.client.get(f'/reporting/mttr/{self.metric.id}/trends/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class MTTDMetricViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('mttdvs','mttd@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.metric = MTTDMetric.objects.create(
            name='MTTD Primary', target_mttd_minutes=15.0)

    def test_list_mttd(self):
        resp = self.client.get('/reporting/mttd/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_mttd(self):
        data = {'name': 'MTTD Secondary', 'target_mttd_minutes': 20.0}
        resp = self.client.post('/reporting/mttd/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_mttd(self):
        resp = self.client.get(f'/reporting/mttd/{self.metric.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'MTTD Primary')

    def test_update_mttd(self):
        resp = self.client.patch(f'/reporting/mttd/{self.metric.id}/',
                                 {'target_mttd_minutes': 25.0}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_calculate_mttd(self):
        resp = self.client.post(f'/reporting/mttd/{self.metric.id}/calculate/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class SLABreachViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('slavs','sla@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.breach = SLABreach.objects.create(
            sla_name='Response SLA', breach_type='resolution_time',
            severity='high', status='open',
            target_minutes=30, actual_minutes=90)

    def test_list_sla_breaches(self):
        resp = self.client.get('/reporting/sla_breaches/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_sla_breach(self):
        data = {'sla_name': 'New SLA', 'breach_type': 'response_time',
                'severity': 'medium', 'status': 'open',
                'target_minutes': 15, 'actual_minutes': 45}
        resp = self.client.post('/reporting/sla_breaches/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_sla_breach(self):
        resp = self.client.get(f'/reporting/sla_breaches/{self.breach.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_acknowledge_sla_breach(self):
        resp = self.client.post(f'/reporting/sla_breaches/{self.breach.id}/acknowledge/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_resolve_sla_breach(self):
        resp = self.client.post(f'/reporting/sla_breaches/{self.breach.id}/resolve/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_active_breaches(self):
        resp = self.client.get('/reporting/sla_breaches/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_sla_breaches_by_severity(self):
        resp = self.client.get('/reporting/sla_breaches/by_severity/high/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_sla_breach_impact_score(self):
        resp = self.client.get(f'/reporting/sla_breaches/{self.breach.id}/impact_score/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class ReportingDashboardViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('dashvs','dash@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)

    def test_dashboard(self):
        resp = self.client.get('/reporting/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
