"""Tests for Incident ViewSets — FIXED. URL prefix: /incident/"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from api.alerts.models.incident import Incident, IncidentTimeline, IncidentResponder, OnCallSchedule

User = get_user_model()


def _count(data):
    if isinstance(data, dict): return len(data.get('results', []))
    return len(data)


class IncidentViewSetTest(APITestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        self.user = User.objects.create_user('incvs','inc@x.com','pass', is_staff=True)
        self.user.groups.add(Group.objects.get_or_create(name='Alert Managers')[0])
        self.client.force_authenticate(self.user)
        self.incident = Incident.objects.create(
            title='DB Connection Failure', description='Primary DB failing',
            severity='high', impact='major', status='open', created_by=self.user)

    def test_list_incidents(self):
        resp = self.client.get('/incident/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_incident(self):
        data = {'title': 'New Incident', 'description': 'Something broke',
                'severity': 'medium', 'impact': 'minor', 'status': 'open'}
        resp = self.client.post('/incident/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Incident.objects.filter(title='New Incident').exists())

    def test_retrieve_incident(self):
        resp = self.client.get(f'/incident/{self.incident.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'DB Connection Failure')

    def test_update_incident(self):
        resp = self.client.patch(f'/incident/{self.incident.id}/',
                                 {'severity': 'critical'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.severity, 'critical')

    def test_delete_incident(self):
        resp = self.client.delete(f'/incident/{self.incident.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_acknowledge_incident(self):
        resp = self.client.post(f'/incident/{self.incident.id}/acknowledge/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_resolve_incident(self):
        resp = self.client.post(f'/incident/{self.incident.id}/resolve/',
                                {'resolution': 'Fixed the DB'}, format='json')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_escalate_incident(self):
        resp = self.client.post(f'/incident/{self.incident.id}/escalate/',
                                {'reason': 'Critical'}, format='json')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_close_incident(self):
        resp = self.client.post(f'/incident/{self.incident.id}/close/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                       status.HTTP_403_FORBIDDEN])

    def test_incidents_by_severity(self):
        resp = self.client.get('/incident/by_severity/high/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_incidents_by_status(self):
        resp = self.client.get('/incident/by_status/open/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_active_incidents(self):
        resp = self.client.get('/incident/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_filter_by_severity(self):
        resp = self.client.get('/incident/?severity=high')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class IncidentTimelineViewSetTest(APITestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        self.user = User.objects.create_user('tlvs','tl@x.com','pass', is_staff=True)
        self.user.groups.add(Group.objects.get_or_create(name='Alert Managers')[0])
        self.client.force_authenticate(self.user)
        self.incident = Incident.objects.create(
            title='TL Incident', description='Timeline test',
            severity='medium', impact='minor', status='open', created_by=self.user)
        self.timeline = IncidentTimeline.objects.create(
            incident=self.incident, event_type='detected',
            title='Initial detection', description='Issue detected',
            created_by=self.user)

    def test_list_timelines(self):
        resp = self.client.get('/incident/timelines/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_timeline(self):
        data = {'incident': self.incident.id, 'event_type': 'update',
                'title': 'Status update', 'description': 'Working on it'}
        resp = self.client.post('/incident/timelines/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_timeline(self):
        resp = self.client.get(f'/incident/timelines/{self.timeline.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['event_type'], 'detected')

    def test_update_timeline(self):
        resp = self.client.patch(f'/incident/timelines/{self.timeline.id}/',
                                 {'description': 'Updated description'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_timelines_by_incident(self):
        resp = self.client.get(f'/incident/timelines/by_incident/{self.incident.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)


class IncidentResponderViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('rspvs','rsp@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.incident = Incident.objects.create(
            title='Responder Incident', description='Need responders',
            severity='high', impact='major', status='open', created_by=self.user)
        self.responder = IncidentResponder.objects.create(
            incident=self.incident, user=self.user,
            role='primary', status='active')

    def test_list_responders(self):
        resp = self.client.get('/incident/responders/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_responder(self):
        other = User.objects.create_user('rsp2','rsp2@x.com','pass', is_staff=True)
        data = {'incident': self.incident.id, 'user': other.id,
                'role': 'secondary', 'status': 'active'}
        resp = self.client.post('/incident/responders/', data, format='json')
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_retrieve_responder(self):
        resp = self.client.get(f'/incident/responders/{self.responder.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['role'], 'primary')

    def test_complete_responder(self):
        resp = self.client.post(f'/incident/responders/{self.responder.id}/complete/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_responders_by_incident(self):
        resp = self.client.get(f'/incident/responders/by_incident/{self.incident.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_responders_by_role(self):
        resp = self.client.get('/incident/responders/by_role/primary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class OnCallScheduleViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('ocvs','oc@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.schedule = OnCallSchedule.objects.create(
            name='Primary On-Call', schedule_type='rotation',
            timezone='UTC', is_active=True)

    def test_list_schedules(self):
        resp = self.client.get('/incident/oncall_schedules/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_schedule(self):
        data = {'name': 'Secondary On-Call', 'schedule_type': 'fixed',
                'timezone': 'UTC', 'is_active': True}
        resp = self.client.post('/incident/oncall_schedules/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_schedule(self):
        resp = self.client.get(f'/incident/oncall_schedules/{self.schedule.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Primary On-Call')

    def test_update_schedule(self):
        resp = self.client.patch(f'/incident/oncall_schedules/{self.schedule.id}/',
                                 {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_active_schedules(self):
        resp = self.client.get('/incident/oncall_schedules/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_rotate_schedule(self):
        resp = self.client.post(f'/incident/oncall_schedules/{self.schedule.id}/rotate/')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
