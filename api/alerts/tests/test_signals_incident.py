"""
Tests for Incident Signals — FIXED
Covers: incident_created, incident_updated, incident_resolved, incident_escalated,
        timeline_created, responder_assigned signals.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from api.alerts.models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule,
)
from api.alerts.signals.incident import (
    incident_created, incident_updated, incident_acknowledged,
    incident_escalated, incident_resolved, incident_closed, timeline_created,
    timeline_event_added, responder_assigned, responder_created, responder_updated,
    post_mortem_created, post_mortem_updated,
    oncall_schedule_created, oncall_updated, oncall_rotation_changed,
    auto_resolution_triggered,
)

User = get_user_model()


class IncidentSignalsTest(TestCase):
    """Tests for Incident lifecycle signals"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='incsig', email='incsig@example.com', password='testpass')
        self.signal_received = False
        self.signal_data = {}

    def _handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_incident_created_signal(self):
        incident_created.connect(self._handler)
        incident = Incident.objects.create(
            title='Signal Test Incident', description='Testing signals',
            severity='high', status='open', created_by=self.user)
        self.assertTrue(self.signal_received)
        self.assertIn('instance', self.signal_data)
        incident_created.disconnect(self._handler)

    def test_incident_updated_signal(self):
        incident = Incident.objects.create(
            title='Update Signal Incident', description='Will be updated',
            severity='medium', status='open', created_by=self.user)
        incident_updated.connect(self._handler)
        self.signal_received = False
        incident.description = 'Updated description'
        incident.save()
        self.assertTrue(self.signal_received)
        incident_updated.disconnect(self._handler)

    def test_incident_resolved_signal_fires_on_resolve(self):
        incident = Incident.objects.create(
            title='Resolve Signal Incident', description='Will be resolved',
            severity='high', status='open', created_by=self.user)
        incident_resolved.connect(self._handler)
        incident.resolve(self.user, resolution_summary='Fixed it')
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data.get('instance'), incident)
        incident_resolved.disconnect(self._handler)

    def test_incident_escalated_signal_fires_on_escalate(self):
        incident = Incident.objects.create(
            title='Escalate Signal Incident', description='Will be escalated',
            severity='high', status='open', created_by=self.user)
        incident_escalated.connect(self._handler)
        incident.escalate(reason='SLA breach', user=self.user)
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data.get('reason'), 'SLA breach')
        incident_escalated.disconnect(self._handler)

    def test_incident_acknowledged_signal_fires_on_acknowledge(self):
        incident = Incident.objects.create(
            title='Ack Signal Incident', description='Will be acknowledged',
            severity='high', status='open', created_by=self.user)
        incident_acknowledged.connect(self._handler)
        incident.acknowledge(self.user, notes='On it')
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data.get('user'), self.user)
        incident_acknowledged.disconnect(self._handler)

    def test_multiple_incidents_multiple_signals(self):
        count = []
        def counter(sender, **kwargs):
            count.append(1)
        incident_created.connect(counter)
        for i in range(3):
            Incident.objects.create(
                title=f'Multi Signal Incident {i}',
                description='Testing', severity='low',
                status='open', created_by=self.user)
        self.assertEqual(len(count), 3)
        incident_created.disconnect(counter)


class TimelineSignalsTest(TestCase):
    """Tests for IncidentTimeline signals"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tlsig', email='tlsig@example.com', password='testpass')
        self.incident = Incident.objects.create(
            title='TL Signal Incident', description='Timeline signals',
            severity='medium', status='open', created_by=self.user)
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_timeline_created_signal_fires_on_create(self):
        """timeline_created fires when a new IncidentTimeline is saved"""
        timeline_created.connect(self._handler)
        IncidentTimeline.objects.create(
            incident=self.incident,
            event_type='update',
            title='A note',
            description='Added a note',
            created_by=self.user)
        self.assertTrue(self.signal_received)
        timeline_created.disconnect(self._handler)

    def test_timeline_event_added_signal_fires_on_add_event(self):
        timeline_event_added.connect(self._handler)
        IncidentTimeline.add_event(self.incident, 'update', 'Manual Note', 'Investigating', self.user)
        self.assertTrue(self.signal_received)
        timeline_event_added.disconnect(self._handler)

    def test_responder_assigned_signal_fires_on_create(self):
        responder_assigned.connect(self._handler)
        IncidentResponder.objects.create(
            incident=self.incident, user=self.user, role='responder', status='assigned')
        self.assertTrue(self.signal_received)
        responder_assigned.disconnect(self._handler)

    def test_timeline_event_types_valid(self):
        """All common event_type choices can be stored"""
        for event_type in ('detected', 'update', 'resolved', 'escalation'):
            tl = IncidentTimeline.objects.create(
                incident=self.incident,
                event_type=event_type,
                title=f'Event {event_type}',
                description='Test',
                created_by=self.user)
            self.assertEqual(tl.event_type, event_type)


class NewlyWiredIncidentAreaSignalsTest(TestCase):
    """Real behavioral tests for 8 more signals confirmed never fired anywhere
    before this session, across Incident/IncidentResponder/IncidentPostMortem/
    OnCallSchedule."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='newincsig', email='newincsig@example.com', password='testpass')
        self.incident = Incident.objects.create(
            title='New Signals Incident', severity='high', status='open',
            created_by=self.user)
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_incident_closed_signal_fires_on_close(self):
        incident_closed.connect(self._handler)
        self.incident.close(self.user, notes='Done')
        self.assertTrue(self.signal_received)
        incident_closed.disconnect(self._handler)

    def test_responder_created_signal_fires_on_create(self):
        responder_created.connect(self._handler)
        IncidentResponder.objects.create(
            incident=self.incident, user=self.user, role='responder', status='assigned')
        self.assertTrue(self.signal_received)
        responder_created.disconnect(self._handler)

    def test_responder_updated_signal_fires_on_update(self):
        responder = IncidentResponder.objects.create(
            incident=self.incident, user=self.user, role='responder', status='assigned')
        self.signal_received = False
        responder_updated.connect(self._handler)
        responder.status = 'active'
        responder.save()
        self.assertTrue(self.signal_received)
        responder_updated.disconnect(self._handler)

    def test_post_mortem_created_signal_fires_on_create(self):
        post_mortem_created.connect(self._handler)
        IncidentPostMortem.objects.create(
            incident=self.incident, title='PM Signal Test', summary='s',
            timeline_summary='t', root_cause_analysis='r', business_impact='b',
            technical_impact='ti', customer_impact='c', created_by=self.user)
        self.assertTrue(self.signal_received)
        post_mortem_created.disconnect(self._handler)

    def test_post_mortem_updated_signal_fires_on_update(self):
        pm = IncidentPostMortem.objects.create(
            incident=self.incident, title='PM Update Signal Test', summary='s',
            timeline_summary='t', root_cause_analysis='r', business_impact='b',
            technical_impact='ti', customer_impact='c', created_by=self.user)
        self.signal_received = False
        post_mortem_updated.connect(self._handler)
        pm.summary = 'updated summary'
        pm.save()
        self.assertTrue(self.signal_received)
        post_mortem_updated.disconnect(self._handler)

    def test_oncall_schedule_created_signal_fires_on_create(self):
        oncall_schedule_created.connect(self._handler)
        OnCallSchedule.objects.create(name='OnCall Signal Test', schedule_type='rotation')
        self.assertTrue(self.signal_received)
        oncall_schedule_created.disconnect(self._handler)

    def test_oncall_updated_and_rotation_changed_signals_fire_on_update(self):
        schedule = OnCallSchedule.objects.create(name='OnCall Update Signal Test', schedule_type='rotation')
        self.signal_received = False
        rotation_received = {'v': False}
        def _rotation_handler(sender, **kwargs):
            rotation_received['v'] = True
        oncall_updated.connect(self._handler)
        oncall_rotation_changed.connect(_rotation_handler)
        schedule.name = 'Renamed OnCall Schedule'
        schedule.save()
        self.assertTrue(self.signal_received)
        self.assertTrue(rotation_received['v'])
        oncall_updated.disconnect(self._handler)
        oncall_rotation_changed.disconnect(_rotation_handler)

    def test_auto_resolution_triggered_signal_fires_on_timeout(self):
        from datetime import timedelta
        from api.alerts.tasks.incident import auto_resolve_low_priority_incidents
        old_incident = Incident.objects.create(
            title='Timed Out Low Priority Incident', severity='low', status='open',
            created_by=self.user)
        Incident.objects.filter(pk=old_incident.pk).update(
            detected_at=timezone.now() - timedelta(hours=100))
        auto_resolution_triggered.connect(self._handler)
        auto_resolve_low_priority_incidents()
        self.assertTrue(self.signal_received)
        auto_resolution_triggered.disconnect(self._handler)
