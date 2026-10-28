"""Tests for Incident Serializers"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from api.alerts.models.incident import Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
from api.alerts.serializers.incident import (
    IncidentSerializer, IncidentTimelineSerializer, IncidentResponderSerializer,
    IncidentPostMortemSerializer, OnCallScheduleSerializer, IncidentListSerializer,
    IncidentAcknowledgeSerializer, IncidentResolveSerializer, IncidentCloseSerializer)
User = get_user_model()


class IncidentSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.incident = Incident.objects.create(
            title='DB Failure', severity='critical', impact='severe',
            urgency='critical', status='open', assigned_to=self.user)

    def test_serializer_read(self):
        data = IncidentSerializer(self.incident).data
        for f in ['id', 'title', 'severity', 'impact', 'status', 'detected_at',
                  'duration_minutes', 'severity_score']:
            self.assertIn(f, data)

    def test_list_serializer(self):
        data = IncidentListSerializer(self.incident).data
        for f in ['id', 'title', 'severity', 'status', 'detected_at']:
            self.assertIn(f, data)
        self.assertNotIn('root_cause', data)

    def test_acknowledge_serializer_valid(self):
        s = IncidentAcknowledgeSerializer(data={})
        self.assertTrue(s.is_valid(), s.errors)

    def test_resolve_serializer_valid(self):
        s = IncidentResolveSerializer(data={'resolution_summary': 'Fixed by restart'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_close_serializer_valid(self):
        s = IncidentCloseSerializer(data={})
        self.assertTrue(s.is_valid(), s.errors)

    def test_serializer_create(self):
        s = IncidentSerializer(data={
            'title': 'API Outage', 'severity': 'high', 'impact': 'major',
            'urgency': 'high', 'status': 'open', 'description': 'API is down'
        })
        self.assertTrue(s.is_valid(), s.errors)


class IncidentTimelineSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.incident = Incident.objects.create(
            title='DB Failure', severity='high', impact='major',
            urgency='high', status='open')
        self.timeline = IncidentTimeline.objects.create(
            incident=self.incident, event_type='update',
            title='Status Change', description='Changed to investigating',
            participants=[self.user.id])

    def test_serializer_read(self):
        data = IncidentTimelineSerializer(self.timeline).data
        for f in ['id', 'incident', 'event_type', 'title', 'description', 'timestamp']:
            self.assertIn(f, data)

    def test_serializer_create(self):
        s = IncidentTimelineSerializer(data={
            'incident': self.incident.id, 'event_type': 'update',
            'title': 'Root Cause Found', 'description': 'Database pool exhausted'
        })
        self.assertTrue(s.is_valid(), s.errors)


class IncidentResponderSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('responder', 'responder@example.com', 'testpass123')
        self.incident = Incident.objects.create(
            title='Test Incident', severity='high', impact='major',
            urgency='high', status='open')
        self.responder = IncidentResponder.objects.create(
            incident=self.incident, user=self.user,
            role='responder', status='assigned',
            responsibilities=['Investigation'])

    def test_serializer_read(self):
        data = IncidentResponderSerializer(self.responder).data
        for f in ['id', 'incident', 'user', 'role', 'status', 'is_available_now']:
            self.assertIn(f, data)

    def test_serializer_create(self):
        user2 = User.objects.create_user('u2', 'u2@e.com', 'pass')
        s = IncidentResponderSerializer(data={
            'incident': self.incident.id, 'user': user2.id,
            'role': 'observer', 'status': 'assigned'
        })
        self.assertTrue(s.is_valid(), s.errors)


class IncidentPostMortemSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.incident = Incident.objects.create(
            title='Resolved Incident', severity='high', impact='major',
            urgency='high', status='resolved')
        self.postmortem = IncidentPostMortem.objects.create(
            incident=self.incident, title='Post-Mortem Report',
            summary='Analysis of the incident', status='draft',
            created_by=self.user, internal_only=False)

    def test_serializer_read(self):
        data = IncidentPostMortemSerializer(self.postmortem).data
        for f in ['id', 'incident', 'title', 'summary', 'status', 'created_at']:
            self.assertIn(f, data)

    def test_serializer_completion_score(self):
        data = IncidentPostMortemSerializer(self.postmortem).data
        self.assertIn('completion_score', data)
        self.assertIsInstance(data['completion_score'], (int, float))


class OnCallScheduleSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('oncall', 'oncall@example.com', 'testpass123')
        self.schedule = OnCallSchedule.objects.create(
            name='Production On-Call', schedule_type='rotation',
            timezone='UTC', rotation_period_days=7,
            rotation_start_date=timezone.now().date(), is_active=True)
        self.schedule.primary_users.add(self.user)

    def test_serializer_read(self):
        data = OnCallScheduleSerializer(self.schedule).data
        for f in ['id', 'name', 'schedule_type', 'is_active', 'timezone', 'current_on_call']:
            self.assertIn(f, data)

    def test_serializer_create(self):
        s = OnCallScheduleSerializer(data={
            'name': 'Dev On-Call', 'schedule_type': 'fixed',
            'timezone': 'UTC', 'rotation_period_days': 14,
            'rotation_start_date': str(timezone.now().date()),
            'is_active': True
        })
        self.assertTrue(s.is_valid(), s.errors)
