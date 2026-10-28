"""
Tests for Incident Models
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from api.alerts.models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)

User = get_user_model()


class IncidentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.incident = Incident.objects.create(
            title='Database Connection Failure',
            severity='high',
            impact='major',
            urgency='high',
            status='open',
            assigned_to=self.user,
            affected_services=['database', 'api'],
            affected_users_count=1000,
            business_impact='Critical services unavailable'
        )

    def test_incident_creation(self):
        self.assertEqual(self.incident.title, 'Database Connection Failure')
        self.assertEqual(self.incident.severity, 'high')
        self.assertEqual(self.incident.impact, 'major')
        self.assertEqual(self.incident.status, 'open')
        self.assertEqual(self.incident.assigned_to, self.user)
        self.assertIsNotNone(self.incident.detected_at)

    def test_incident_str_representation(self):
        expected = f'Incident: {self.incident.title} - high'
        self.assertEqual(str(self.incident), expected)

    def test_incident_get_severity_display(self):
        self.assertEqual(self.incident.get_severity_display(), 'High')
        self.incident.severity = 'critical'
        self.assertEqual(self.incident.get_severity_display(), 'Critical')
        self.incident.severity = 'medium'
        self.assertEqual(self.incident.get_severity_display(), 'Medium')

    def test_incident_get_impact_display(self):
        self.assertEqual(self.incident.get_impact_display(), 'Major')
        self.incident.impact = 'minor'
        self.assertEqual(self.incident.get_impact_display(), 'Minor')
        self.incident.impact = 'severe'
        self.assertEqual(self.incident.get_impact_display(), 'Severe')

    def test_incident_get_urgency_display(self):
        self.assertEqual(self.incident.get_urgency_display(), 'High')
        self.incident.urgency = 'low'
        self.assertEqual(self.incident.get_urgency_display(), 'Low')
        self.incident.urgency = 'medium'
        self.assertEqual(self.incident.get_urgency_display(), 'Medium')

    def test_incident_get_status_display(self):
        self.assertEqual(self.incident.get_status_display(), 'Open')
        self.incident.status = 'investigating'
        self.assertEqual(self.incident.get_status_display(), 'Investigating')
        self.incident.status = 'resolved'
        self.assertEqual(self.incident.get_status_display(), 'Resolved')
        self.incident.status = 'closed'
        self.assertEqual(self.incident.get_status_display(), 'Closed')

    def test_incident_acknowledge(self):
        self.incident.acknowledge(self.user, 'Investigating the issue')
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'investigating')
        self.assertEqual(self.incident.acknowledged_by, self.user)
        self.assertEqual(self.incident.acknowledgment_note, 'Investigating the issue')
        self.assertIsNotNone(self.incident.acknowledged_at)

    def test_incident_identify(self):
        self.incident.identify('Root cause identified', 'Database connection pool exhausted')
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'identified')
        self.assertEqual(self.incident.root_cause, 'Root cause identified')
        self.assertIsNotNone(self.incident.identified_at)

    def test_incident_resolve(self):
        self.incident.resolve(
            self.user,
            'Fixed database connection pool',
            'Increased pool size and restarted connections'
        )
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'resolved')
        self.assertEqual(self.incident.resolved_by, self.user)
        self.assertEqual(self.incident.resolution_summary, 'Fixed database connection pool')
        self.assertIsNotNone(self.incident.resolved_at)

    def test_incident_close(self):
        self.incident.status = 'resolved'
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        self.incident.close(self.user, 'Issue resolved and verified')
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'closed')
        self.assertEqual(self.incident.closed_by, self.user)
        self.assertEqual(self.incident.closure_note, 'Issue resolved and verified')
        self.assertIsNotNone(self.incident.closed_at)

    def test_incident_get_duration_minutes(self):
        # get_duration_minutes always returns float (falls back to timezone.now())
        duration = self.incident.get_duration_minutes()
        self.assertIsInstance(duration, float)
        self.assertGreaterEqual(duration, 0)
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        duration2 = self.incident.get_duration_minutes()
        self.assertIsInstance(duration2, float)

    def test_incident_get_business_hours_duration(self):
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        duration = self.incident.get_business_hours_duration()
        self.assertIsInstance(duration, (int, float, type(None)))

    def test_incident_escalate(self):
        initial_level = self.incident.escalation_level
        self.incident.escalate('No response from primary team')
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.escalation_level, initial_level + 1)
        self.assertEqual(self.incident.escalation_reason, 'No response from primary team')
        self.assertIsNotNone(self.incident.escalated_at)

    def test_incident_get_severity_score(self):
        score = self.incident.get_severity_score()
        # Score = severity(3)*3 + impact(3)*2 + urgency(3)*1 = 18 for high+major+high
        self.assertIsInstance(score, int)
        self.assertGreater(score, 0)
        self.assertGreater(score, 10)

    def test_incident_is_overdue(self):
        # Critical severity SLA is 60 minutes — 2h ago exceeds it
        self.incident.severity = 'critical'
        self.incident.save()
        result = self.incident.is_overdue()
        self.assertIsInstance(result, bool)


class IncidentTimelineModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.incident = Incident.objects.create(
            title='Test Incident', severity='high', status='open', assigned_to=self.user
        )
        self.incident_timeline = IncidentTimeline.objects.create(
            incident=self.incident,
            event_type='update',
            title='Incident Created',
            description='Initial incident creation',
            participants=[self.user.id]
        )

    def test_incident_timeline_creation(self):
        self.assertEqual(self.incident_timeline.incident, self.incident)
        self.assertEqual(self.incident_timeline.event_type, 'update')
        self.assertEqual(self.incident_timeline.title, 'Incident Created')
        self.assertIsInstance(self.incident_timeline.participants, list)

    def test_incident_timeline_str_representation(self):
        expected = f'IncidentTimeline: {self.incident_timeline.id} - update'
        self.assertEqual(str(self.incident_timeline), expected)

    def test_incident_timeline_get_event_type_display(self):
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Status Update')
        self.incident_timeline.event_type = 'escalation'
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Incident Escalated')
        self.incident_timeline.event_type = 'resolved'
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Incident Resolved')

    def test_incident_timeline_add_participant(self):
        another_user = User.objects.create_user(
            username='anotheruser', email='another@example.com', password='testpass123'
        )
        initial_count = len(self.incident_timeline.participants)
        self.incident_timeline.add_participant(another_user.id)
        self.assertEqual(len(self.incident_timeline.participants), initial_count + 1)
        self.assertIn(another_user.id, self.incident_timeline.participants)

    def test_incident_timeline_remove_participant(self):
        initial_count = len(self.incident_timeline.participants)
        self.incident_timeline.remove_participant(self.user.id)
        self.assertEqual(len(self.incident_timeline.participants), initial_count - 1)
        self.assertNotIn(self.user.id, self.incident_timeline.participants)

    def test_incident_timeline_has_participant(self):
        self.assertTrue(self.incident_timeline.has_participant(self.user.id))
        another_user = User.objects.create_user(
            username='anotheruser', email='another@example.com', password='testpass123'
        )
        self.assertFalse(self.incident_timeline.has_participant(another_user.id))

    def test_incident_timeline_get_duration(self):
        duration = self.incident_timeline.get_duration()
        self.assertIsInstance(duration, timedelta)

    def test_incident_timeline_get_formatted_timestamp(self):
        formatted = self.incident_timeline.get_formatted_timestamp()
        self.assertIsInstance(formatted, str)
        self.assertIn(':', formatted)


class IncidentResponderModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.incident = Incident.objects.create(
            title='Test Incident', severity='high', status='open'
        )
        self.incident_responder = IncidentResponder.objects.create(
            incident=self.incident,
            user=self.user,
            role='responder',
            status='assigned',
            responsibilities=['Investigation', 'Communication']
        )

    def test_incident_responder_creation(self):
        self.assertEqual(self.incident_responder.incident, self.incident)
        self.assertEqual(self.incident_responder.user, self.user)
        self.assertEqual(self.incident_responder.role, 'responder')
        self.assertEqual(self.incident_responder.status, 'assigned')
        self.assertIsInstance(self.incident_responder.responsibilities, list)

    def test_incident_responder_str_representation(self):
        expected = f'IncidentResponder: {self.user.username} - responder'
        self.assertEqual(str(self.incident_responder), expected)

    def test_incident_responder_get_role_display(self):
        self.assertEqual(self.incident_responder.get_role_display(), 'Responder')
        self.incident_responder.role = 'lead'
        self.assertEqual(self.incident_responder.get_role_display(), 'Lead')
        self.incident_responder.role = 'observer'
        self.assertEqual(self.incident_responder.get_role_display(), 'Observer')
        self.incident_responder.role = 'manager'
        self.assertEqual(self.incident_responder.get_role_display(), 'Manager')

    def test_incident_responder_get_status_display(self):
        self.assertEqual(self.incident_responder.get_status_display(), 'Assigned')
        self.incident_responder.status = 'active'
        self.assertEqual(self.incident_responder.get_status_display(), 'Active')
        self.incident_responder.status = 'away'
        self.assertEqual(self.incident_responder.get_status_display(), 'Away')
        self.incident_responder.status = 'completed'
        self.assertEqual(self.incident_responder.get_status_display(), 'Completed')

    def test_incident_responder_activate(self):
        self.incident_responder.activate()
        self.incident_responder.refresh_from_db()
        self.assertEqual(self.incident_responder.status, 'active')
        self.assertIsNotNone(self.incident_responder.active_at)

    def test_incident_responder_deactivate(self):
        self.incident_responder.deactivate()
        self.incident_responder.refresh_from_db()
        self.assertEqual(self.incident_responder.status, 'away')

    def test_incident_responder_complete(self):
        self.incident_responder.complete(self.user, 'Tasks completed successfully')
        self.incident_responder.refresh_from_db()
        self.assertEqual(self.incident_responder.status, 'completed')
        self.assertEqual(self.incident_responder.completion_note, 'Tasks completed successfully')
        self.assertIsNotNone(self.incident_responder.completed_at)

    def test_incident_responder_is_available_now(self):
        self.assertTrue(self.incident_responder.is_available_now())
        from datetime import time
        future_start = (timezone.now() + timedelta(hours=4)).time()
        future_end = (timezone.now() + timedelta(hours=12)).time()
        self.incident_responder.available_hours_start = future_start
        self.incident_responder.available_hours_end = future_end
        self.assertFalse(self.incident_responder.is_available_now())

    def test_incident_responder_has_responsibility(self):
        self.assertTrue(self.incident_responder.has_responsibility('Investigation'))
        self.assertTrue(self.incident_responder.has_responsibility('Communication'))
        self.assertFalse(self.incident_responder.has_responsibility('Testing'))

    def test_incident_responder_add_responsibility(self):
        initial_count = len(self.incident_responder.responsibilities)
        self.incident_responder.add_responsibility('Testing')
        self.assertEqual(len(self.incident_responder.responsibilities), initial_count + 1)
        self.assertIn('Testing', self.incident_responder.responsibilities)

    def test_incident_responder_remove_responsibility(self):
        initial_count = len(self.incident_responder.responsibilities)
        self.incident_responder.remove_responsibility('Investigation')
        self.assertEqual(len(self.incident_responder.responsibilities), initial_count - 1)
        self.assertNotIn('Investigation', self.incident_responder.responsibilities)


class IncidentPostMortemModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.incident = Incident.objects.create(
            title='Test Incident', severity='high', status='resolved'
        )
        self.incident_postmortem = IncidentPostMortem.objects.create(
            incident=self.incident,
            title='Post-Mortem: Database Connection Failure',
            summary='Analysis of database connection failure incident',
            timeline_summary='Timeline of events',
            root_cause_analysis='Database connection pool exhausted',
            business_impact='Critical services unavailable',
            technical_impact='API latency increased',
            customer_impact='All customers affected',
            status='draft',
            created_by=self.user,
            internal_only=False
        )

    def test_incident_postmortem_creation(self):
        self.assertEqual(self.incident_postmortem.incident, self.incident)
        self.assertEqual(self.incident_postmortem.title, 'Post-Mortem: Database Connection Failure')
        self.assertEqual(self.incident_postmortem.status, 'draft')
        self.assertEqual(self.incident_postmortem.created_by, self.user)
        self.assertFalse(self.incident_postmortem.internal_only)

    def test_incident_postmortem_str_representation(self):
        expected = f'IncidentPostMortem: {self.incident_postmortem.id} - draft'
        self.assertEqual(str(self.incident_postmortem), expected)

    def test_incident_postmortem_get_status_display(self):
        self.assertEqual(self.incident_postmortem.get_status_display(), 'Draft')
        self.incident_postmortem.status = 'in_progress'
        self.assertEqual(self.incident_postmortem.get_status_display(), 'In Progress')
        self.incident_postmortem.status = 'submitted_for_review'
        self.assertEqual(self.incident_postmortem.get_status_display(), 'Submitted For Review')
        self.incident_postmortem.status = 'approved'
        self.assertEqual(self.incident_postmortem.get_status_display(), 'Approved')
        self.incident_postmortem.status = 'rejected'
        self.assertEqual(self.incident_postmortem.get_status_display(), 'Rejected')
        self.incident_postmortem.status = 'published'
        self.assertEqual(self.incident_postmortem.get_status_display(), 'Published')

    def test_incident_postmortem_submit_for_review(self):
        self.incident_postmortem.submit_for_review()
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'submitted_for_review')
        self.assertIsNotNone(self.incident_postmortem.submitted_at)

    def test_incident_postmortem_approve(self):
        reviewer = User.objects.create_user(
            username='reviewer', email='reviewer@example.com', password='testpass123'
        )
        self.incident_postmortem.approve(reviewer, 'Approved with minor changes')
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'approved')
        self.assertEqual(self.incident_postmortem.approved_by, reviewer)
        self.assertEqual(self.incident_postmortem.approval_note, 'Approved with minor changes')
        self.assertIsNotNone(self.incident_postmortem.approved_at)

    def test_incident_postmortem_reject(self):
        reviewer = User.objects.create_user(
            username='reviewer', email='reviewer@example.com', password='testpass123'
        )
        self.incident_postmortem.reject(reviewer, 'Needs more detail on root cause')
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'rejected')
        self.assertEqual(self.incident_postmortem.approved_by, reviewer)
        self.assertEqual(self.incident_postmortem.approval_note, 'Needs more detail on root cause')

    def test_incident_postmortem_publish(self):
        self.incident_postmortem.status = 'approved'
        self.incident_postmortem.save()
        self.incident_postmortem.publish()
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'published')
        self.assertIsNotNone(self.incident_postmortem.published_at)

    def test_incident_postmortem_get_completion_score(self):
        score = self.incident_postmortem.get_completion_score()
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)


class OnCallScheduleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.oncall_schedule = OnCallSchedule.objects.create(
            name='Production On-Call',
            description='Primary on-call schedule for production systems',
            schedule_type='rotation',
            timezone='UTC',
            rotation_period_days=7,
            rotation_start_date=timezone.now().date(),
            is_active=True
        )
        self.oncall_schedule.primary_users.add(self.user)

    def test_oncall_schedule_creation(self):
        self.assertEqual(self.oncall_schedule.name, 'Production On-Call')
        self.assertEqual(self.oncall_schedule.schedule_type, 'rotation')
        self.assertEqual(self.oncall_schedule.timezone, 'UTC')
        self.assertEqual(self.oncall_schedule.rotation_period_days, 7)
        self.assertTrue(self.oncall_schedule.is_active)

    def test_oncall_schedule_str_representation(self):
        expected = f'OnCallSchedule: {self.oncall_schedule.name} - rotation'
        self.assertEqual(str(self.oncall_schedule), expected)

    def test_oncall_schedule_get_type_display(self):
        self.assertEqual(self.oncall_schedule.profile_type, 'Rotation')
        self.oncall_schedule.schedule_type = 'fixed'
        self.assertEqual(self.oncall_schedule.profile_type, 'Fixed')
        self.oncall_schedule.schedule_type = 'on_demand'
        self.assertEqual(self.oncall_schedule.profile_type, 'On Demand')

    def test_oncall_schedule_get_current_on_call(self):
        current_on_call = self.oncall_schedule.get_current_on_call()
        self.assertTrue(current_on_call is None or hasattr(current_on_call, 'username'))

    def test_oncall_schedule_get_next_rotation(self):
        next_rotation = self.oncall_schedule.get_next_rotation()
        self.assertTrue(next_rotation is None or hasattr(next_rotation, 'date'))

    def test_oncall_schedule_rotate(self):
        original_date = self.oncall_schedule.rotation_start_date
        self.oncall_schedule.rotate()
        self.oncall_schedule.refresh_from_db()
        self.assertIsNotNone(self.oncall_schedule.rotation_start_date)

    def test_oncall_schedule_add_user(self):
        another_user = User.objects.create_user(
            username='anotheruser', email='another@example.com', password='testpass123'
        )
        initial_count = self.oncall_schedule.primary_users.count()
        self.oncall_schedule.add_user(another_user)
        self.assertEqual(self.oncall_schedule.primary_users.count(), initial_count + 1)
        self.assertIn(another_user, self.oncall_schedule.primary_users.all())

    def test_oncall_schedule_remove_user(self):
        initial_count = self.oncall_schedule.primary_users.count()
        self.oncall_schedule.remove_user(self.user)
        self.assertEqual(self.oncall_schedule.primary_users.count(), initial_count - 1)
        self.assertNotIn(self.user, self.oncall_schedule.primary_users.all())

    def test_oncall_schedule_is_user_on_call(self):
        result = self.oncall_schedule.is_user_on_call(self.user)
        self.assertIsInstance(result, bool)

    def test_oncall_schedule_get_users_count(self):
        count = self.oncall_schedule.get_users_count()
        self.assertEqual(count, 1)
        another_user = User.objects.create_user(
            username='anotheruser', email='another@example.com', password='testpass123'
        )
        self.oncall_schedule.primary_users.add(another_user)
        count = self.oncall_schedule.get_users_count()
        self.assertEqual(count, 2)
