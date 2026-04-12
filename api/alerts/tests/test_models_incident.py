"""
Tests for Incident Models
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import json

from alerts.models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)

User = get_user_model()


class IncidentModelTest(TestCase):
    """Test cases for Incident model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.incident = Incident.objects.create(
            title='Database Connection Failure',
            description='Primary database connection is failing',
            severity='high',
            impact='major',
            urgency='high',
            status='open',
            assigned_to=self.user,
            detected_at=timezone.now(),
            affected_services=['database', 'api'],
            affected_users_count=1000,
            business_impact='Critical services unavailable'
        )
    
    def test_incident_creation(self):
        """Test Incident creation"""
        self.assertEqual(self.incident.title, 'Database Connection Failure')
        self.assertEqual(self.incident.severity, 'high')
        self.assertEqual(self.incident.impact, 'major')
        self.assertEqual(self.incident.urgency, 'high')
        self.assertEqual(self.incident.status, 'open')
        self.assertEqual(self.incident.assigned_to, self.user)
        self.assertIsNotNone(self.incident.detected_at)
    
    def test_incident_str_representation(self):
        """Test Incident string representation"""
        expected = f'Incident: {self.incident.title} - high'
        self.assertEqual(str(self.incident), expected)
    
    def test_incident_get_severity_display(self):
        """Test Incident severity display"""
        self.assertEqual(self.incident.get_severity_display(), 'High')
        
        self.incident.severity = 'critical'
        self.assertEqual(self.incident.get_severity_display(), 'Critical')
        
        self.incident.severity = 'medium'
        self.assertEqual(self.incident.get_severity_display(), 'Medium')
        
        self.incident.severity = 'low'
        self.assertEqual(self.incident.get_severity_display(), 'Low')
    
    def test_incident_get_impact_display(self):
        """Test Incident impact display"""
        self.assertEqual(self.incident.get_impact_display(), 'Major')
        
        self.incident.impact = 'none'
        self.assertEqual(self.incident.get_impact_display(), 'None')
        
        self.incident.impact = 'minimal'
        self.assertEqual(self.incident.get_impact_display(), 'Minimal')
        
        self.incident.impact = 'minor'
        self.assertEqual(self.incident.get_impact_display(), 'Minor')
        
        self.incident.impact = 'severe'
        self.assertEqual(self.incident.get_impact_display(), 'Severe')
        
        self.incident.impact = 'critical'
        self.assertEqual(self.incident.get_impact_display(), 'Critical')
    
    def test_incident_get_urgency_display(self):
        """Test Incident urgency display"""
        self.assertEqual(self.incident.get_urgency_display(), 'High')
        
        self.incident.urgency = 'low'
        self.assertEqual(self.incident.get_urgency_display(), 'Low')
        
        self.incident.urgency = 'medium'
        self.assertEqual(self.incident.get_urgency_display(), 'Medium')
        
        self.incident.urgency = 'critical'
        self.assertEqual(self.incident.get_urgency_display(), 'Critical')
    
    def test_incident_get_status_display(self):
        """Test Incident status display"""
        self.assertEqual(self.incident.get_status_display(), 'Open')
        
        self.incident.status = 'investigating'
        self.assertEqual(self.incident.get_status_display(), 'Investigating')
        
        self.incident.status = 'identified'
        self.assertEqual(self.incident.get_status_display(), 'Identified')
        
        self.incident.status = 'monitoring'
        self.assertEqual(self.incident.get_status_display(), 'Monitoring')
        
        self.incident.status = 'resolved'
        self.assertEqual(self.incident.get_status_display(), 'Resolved')
        
        self.incident.status = 'closed'
        self.assertEqual(self.incident.get_status_display(), 'Closed')
        
        self.incident.status = 'false_positive'
        self.assertEqual(self.incident.get_status_display(), 'False Positive')
    
    def test_incident_acknowledge(self):
        """Test Incident acknowledge method"""
        self.incident.acknowledge(self.user, 'Investigating the issue')
        
        self.assertEqual(self.incident.status, 'investigating')
        self.assertEqual(self.incident.acknowledged_by, self.user)
        self.assertEqual(self.incident.acknowledgment_note, 'Investigating the issue')
        self.assertIsNotNone(self.incident.acknowledged_at)
    
    def test_incident_identify(self):
        """Test Incident identify method"""
        self.incident.identify('Root cause identified', 'Database connection pool exhausted')
        
        self.assertEqual(self.incident.status, 'identified')
        self.assertEqual(self.incident.root_cause, 'Root cause identified')
        self.assertEqual(self.incident.contributing_factors, 'Database connection pool exhausted')
        self.assertIsNotNone(self.incident.identified_at)
    
    def test_incident_resolve(self):
        """Test Incident resolve method"""
        self.incident.resolve(
            self.user,
            'Fixed database connection pool',
            'Increased pool size and restarted connections'
        )
        
        self.assertEqual(self.incident.status, 'resolved')
        self.assertEqual(self.incident.resolved_by, self.user)
        self.assertEqual(self.incident.resolution_summary, 'Fixed database connection pool')
        self.assertEqual(self.incident.resolution_actions, 'Increased pool size and restarted connections')
        self.assertIsNotNone(self.incident.resolved_at)
    
    def test_incident_close(self):
        """Test Incident close method"""
        self.incident.status = 'resolved'
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        
        self.incident.close(self.user, 'Issue resolved and verified')
        
        self.assertEqual(self.incident.status, 'closed')
        self.assertEqual(self.incident.closed_by, self.user)
        self.assertEqual(self.incident.closure_note, 'Issue resolved and verified')
        self.assertIsNotNone(self.incident.closed_at)
    
    def test_incident_get_duration_minutes(self):
        """Test Incident duration calculation"""
        # Unresolved incident
        self.assertIsNone(self.incident.get_duration_minutes())
        
        # Resolved incident
        self.incident.detected_at = timezone.now() - timedelta(hours=2)
        self.incident.resolved_at = timezone.now() - timedelta(minutes=30)
        self.incident.save()
        
        duration = self.incident.get_duration_minutes()
        self.assertEqual(duration, 90)  # 2 hours - 30 minutes = 90 minutes
    
    def test_incident_get_business_hours_duration(self):
        """Test Incident business hours duration calculation"""
        # This would calculate duration only during business hours
        # For testing, we'll assume business hours are 9-5
        self.incident.detected_at = timezone.now() - timedelta(hours=4)
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        
        duration = self.incident.get_business_hours_duration()
        self.assertIsInstance(duration, float)
    
    def test_incident_escalate(self):
        """Test Incident escalation method"""
        initial_level = self.incident.escalation_level
        
        self.incident.escalate('No response from primary team')
        
        self.assertEqual(self.incident.escalation_level, initial_level + 1)
        self.assertEqual(self.incident.escalation_reason, 'No response from primary team')
        self.assertIsNotNone(self.incident.escalated_at)
    
    def test_incident_get_severity_score(self):
        """Test Incident severity score calculation"""
        score = self.incident.get_severity_score()
        
        # High severity should have a high score
        self.assertGreater(score, 50)
        self.assertLessEqual(score, 100)
    
    def test_incident_is_overdue(self):
        """Test Incident overdue check"""
        # Open incident with high urgency
        self.incident.detected_at = timezone.now() - timedelta(hours=2)
        self.incident.urgency = 'high'
        self.incident.save()
        
        is_overdue = self.incident.is_overdue()
        self.assertTrue(is_overdue)
        
        # Low urgency incident
        self.incident.urgency = 'low'
        self.incident.save()
        
        is_overdue = self.incident.is_overdue()
        self.assertFalse(is_overdue)


class IncidentTimelineModelTest(TestCase):
    """Test cases for IncidentTimeline model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.incident = Incident.objects.create(
            title='Test Incident',
            severity='high',
            status='open',
            assigned_to=self.user
        )
        
        self.incident_timeline = IncidentTimeline.objects.create(
            incident=self.incident,
            event_type='status_change',
            title='Incident Created',
            description='Initial incident creation',
            timestamp=timezone.now(),
            participants=[self.user.id]
        )
    
    def test_incident_timeline_creation(self):
        """Test IncidentTimeline creation"""
        self.assertEqual(self.incident_timeline.incident, self.incident)
        self.assertEqual(self.incident_timeline.event_type, 'status_change')
        self.assertEqual(self.incident_timeline.title, 'Incident Created')
        self.assertEqual(self.incident_timeline.description, 'Initial incident creation')
        self.assertIsInstance(self.incident_timeline.participants, list)
    
    def test_incident_timeline_str_representation(self):
        """Test IncidentTimeline string representation"""
        expected = f'IncidentTimeline: {self.incident_timeline.id} - status_change'
        self.assertEqual(str(self.incident_timeline), expected)
    
    def test_incident_timeline_get_event_type_display(self):
        """Test IncidentTimeline event type display"""
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Status Change')
        
        self.incident_timeline.event_type = 'action'
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Action')
        
        self.incident_timeline.event_type = 'note'
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Note')
        
        self.incident_timeline.event_type = 'escalation'
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Escalation')
        
        self.incident_timeline.event_type = 'communication'
        self.assertEqual(self.incident_timeline.get_event_type_display(), 'Communication')
    
    def test_incident_timeline_add_participant(self):
        """Test IncidentTimeline add participant method"""
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='testpass123'
        )
        
        initial_count = len(self.incident_timeline.participants)
        
        self.incident_timeline.add_participant(another_user.id)
        
        self.assertEqual(len(self.incident_timeline.participants), initial_count + 1)
        self.assertIn(another_user.id, self.incident_timeline.participants)
    
    def test_incident_timeline_remove_participant(self):
        """Test IncidentTimeline remove participant method"""
        initial_count = len(self.incident_timeline.participants)
        
        self.incident_timeline.remove_participant(self.user.id)
        
        self.assertEqual(len(self.incident_timeline.participants), initial_count - 1)
        self.assertNotIn(self.user.id, self.incident_timeline.participants)
    
    def test_incident_timeline_has_participant(self):
        """Test IncidentTimeline has participant check"""
        self.assertTrue(self.incident_timeline.has_participant(self.user.id))
        
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='testpass123'
        )
        
        self.assertFalse(self.incident_timeline.has_participant(another_user.id))
    
    def test_incident_timeline_get_duration(self):
        """Test IncidentTimeline duration calculation"""
        # Timeline event with no duration
        self.assertIsNone(self.incident_timeline.get_duration())
        
        # Timeline event with duration
        self.incident_timeline.timestamp = timezone.now() - timedelta(minutes=30)
        self.incident_timeline.save()
        
        duration = self.incident_timeline.get_duration()
        self.assertIsInstance(duration, timedelta)
    
    def test_incident_timeline_get_formatted_timestamp(self):
        """Test IncidentTimeline formatted timestamp"""
        formatted = self.incident_timeline.get_formatted_timestamp()
        self.assertIsInstance(formatted, str)
        
        # Should be in a readable format
        self.assertIn(':', formatted)


class IncidentResponderModelTest(TestCase):
    """Test cases for IncidentResponder model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.incident = Incident.objects.create(
            title='Test Incident',
            severity='high',
            status='open'
        )
        
        self.incident_responder = IncidentResponder.objects.create(
            incident=self.incident,
            user=self.user,
            role='responder',
            status='assigned',
            responsibilities=['Investigation', 'Communication']
        )
    
    def test_incident_responder_creation(self):
        """Test IncidentResponder creation"""
        self.assertEqual(self.incident_responder.incident, self.incident)
        self.assertEqual(self.incident_responder.user, self.user)
        self.assertEqual(self.incident_responder.role, 'responder')
        self.assertEqual(self.incident_responder.status, 'assigned')
        self.assertIsInstance(self.incident_responder.responsibilities, list)
    
    def test_incident_responder_str_representation(self):
        """Test IncidentResponder string representation"""
        expected = f'IncidentResponder: {self.user.username} - responder'
        self.assertEqual(str(self.incident_responder), expected)
    
    def test_incident_responder_get_role_display(self):
        """Test IncidentResponder role display"""
        self.assertEqual(self.incident_responder.get_role_display(), 'Responder')
        
        self.incident_responder.role = 'lead'
        self.assertEqual(self.incident_responder.get_role_display(), 'Lead')
        
        self.incident_responder.role = 'observer'
        self.assertEqual(self.incident_responder.get_role_display(), 'Observer')
        
        self.incident_responder.role = 'escalation'
        self.assertEqual(self.incident_responder.get_role_display(), 'Escalation')
        
        self.incident_responder.role = 'manager'
        self.assertEqual(self.incident_responder.get_role_display(), 'Manager')
    
    def test_incident_responder_get_status_display(self):
        """Test IncidentResponder status display"""
        self.assertEqual(self.incident_responder.get_status_display(), 'Assigned')
        
        self.incident_responder.status = 'active'
        self.assertEqual(self.incident_responder.get_status_display(), 'Active')
        
        self.incident_responder.status = 'away'
        self.assertEqual(self.incident_responder.get_status_display(), 'Away')
        
        self.incident_responder.status = 'completed'
        self.assertEqual(self.incident_responder.get_status_display(), 'Completed')
        
        self.incident_responder.status = 'escalated'
        self.assertEqual(self.incident_responder.get_status_display(), 'Escalated')
    
    def test_incident_responder_activate(self):
        """Test IncidentResponder activate method"""
        self.incident_responder.activate()
        
        self.assertEqual(self.incident_responder.status, 'active')
        self.assertIsNotNone(self.incident_responder.active_at)
    
    def test_incident_responder_deactivate(self):
        """Test IncidentResponder deactivate method"""
        self.incident_responder.deactivate()
        
        self.assertEqual(self.incident_responder.status, 'away')
    
    def test_incident_responder_complete(self):
        """Test IncidentResponder complete method"""
        self.incident_responder.complete(self.user, 'Tasks completed successfully')
        
        self.assertEqual(self.incident_responder.status, 'completed')
        self.assertEqual(self.incident_responder.completion_note, 'Tasks completed successfully')
        self.assertIsNotNone(self.incident_responder.completed_at)
    
    def test_incident_responder_is_available_now(self):
        """Test IncidentResponder availability check"""
        # By default, should be available
        self.assertTrue(self.incident_responder.is_available_now())
        
        # With time restrictions
        self.incident_responder.available_hours_start = (timezone.now() + timezone.timedelta(hours=4)).time()
        self.incident_responder.available_hours_end = (timezone.now() + timezone.timedelta(hours=12)).time()
        self.incident_responder.save()
        
        self.assertFalse(self.incident_responder.is_available_now())
    
    def test_incident_responder_has_responsibility(self):
        """Test IncidentResponder responsibility check"""
        self.assertTrue(self.incident_responder.has_responsibility('Investigation'))
        self.assertTrue(self.incident_responder.has_responsibility('Communication'))
        self.assertFalse(self.incident_responder.has_responsibility('Testing'))
    
    def test_incident_responder_add_responsibility(self):
        """Test IncidentResponder add responsibility method"""
        initial_count = len(self.incident_responder.responsibilities)
        
        self.incident_responder.add_responsibility('Testing')
        
        self.assertEqual(len(self.incident_responder.responsibilities), initial_count + 1)
        self.assertIn('Testing', self.incident_responder.responsibilities)
    
    def test_incident_responder_remove_responsibility(self):
        """Test IncidentResponder remove responsibility method"""
        initial_count = len(self.incident_responder.responsibilities)
        
        self.incident_responder.remove_responsibility('Investigation')
        
        self.assertEqual(len(self.incident_responder.responsibilities), initial_count - 1)
        self.assertNotIn('Investigation', self.incident_responder.responsibilities)


class IncidentPostMortemModelTest(TestCase):
    """Test cases for IncidentPostMortem model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.incident = Incident.objects.create(
            title='Test Incident',
            severity='high',
            status='resolved',
            resolved_by=self.user,
            resolved_at=timezone.now()
        )
        
        self.incident_postmortem = IncidentPostMortem.objects.create(
            incident=self.incident,
            title='Post-Mortem: Database Connection Failure',
            description='Analysis of database connection failure incident',
            status='draft',
            created_by=self.user,
            internal_only=False
        )
    
    def test_incident_postmortem_creation(self):
        """Test IncidentPostMortem creation"""
        self.assertEqual(self.incident_postmortem.incident, self.incident)
        self.assertEqual(self.incident_postmortem.title, 'Post-Mortem: Database Connection Failure')
        self.assertEqual(self.incident_postmortem.status, 'draft')
        self.assertEqual(self.incident_postmortem.created_by, self.user)
        self.assertFalse(self.incident_postmortem.internal_only)
    
    def test_incident_postmortem_str_representation(self):
        """Test IncidentPostMortem string representation"""
        expected = f'IncidentPostMortem: {self.incident_postmortem.id} - draft'
        self.assertEqual(str(self.incident_postmortem), expected)
    
    def test_incident_postmortem_get_status_display(self):
        """Test IncidentPostMortem status display"""
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
        """Test IncidentPostMortem submit for review method"""
        self.incident_postmortem.submit_for_review()
        
        self.assertEqual(self.incident_postmortem.status, 'submitted_for_review')
        self.assertIsNotNone(self.incident_postmortem.submitted_at)
    
    def test_incident_postmortem_approve(self):
        """Test IncidentPostMortem approve method"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        self.incident_postmortem.approve(reviewer, 'Approved with minor changes')
        
        self.assertEqual(self.incident_postmortem.status, 'approved')
        self.assertEqual(self.incident_postmortem.approved_by, reviewer)
        self.assertEqual(self.incident_postmortem.approval_note, 'Approved with minor changes')
        self.assertIsNotNone(self.incident_postmortem.approved_at)
    
    def test_incident_postmortem_reject(self):
        """Test IncidentPostMortem reject method"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        self.incident_postmortem.reject(reviewer, 'Needs more detail on root cause')
        
        self.assertEqual(self.incident_postmortem.status, 'rejected')
        self.assertEqual(self.incident_postmortem.approved_by, reviewer)
        self.assertEqual(self.incident_postmortem.approval_note, 'Needs more detail on root cause')
        self.assertIsNotNone(self.incident_postmortem.approved_at)
    
    def test_incident_postmortem_publish(self):
        """Test IncidentPostMortem publish method"""
        self.incident_postmortem.status = 'approved'
        self.incident_postmortem.save()
        
        self.incident_postmortem.publish()
        
        self.assertEqual(self.incident_postmortem.status, 'published')
        self.assertIsNotNone(self.incident_postmortem.published_at)
    
    def test_incident_postmortem_get_completion_score(self):
        """Test IncidentPostMortem completion score calculation"""
        # Empty post-mortem
        score = self.incident_postmortem.get_completion_score()
        self.assertEqual(score, 0)
        
        # With some content
        self.incident_postmortem.root_cause = 'Database connection pool exhausted'
        self.incident_postmortem.timeline = 'Timeline of events'
        self.incident_postmortem.lessons_learned = 'Need better monitoring'
        self.incident_postmortem.preventive_measures = 'Increase pool size monitoring'
        self.incident_postmortem.save()
        
        score = self.incident_postmortem.get_completion_score()
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)


class OnCallScheduleModelTest(TestCase):
    """Test cases for OnCallSchedule model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
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
        
        self.oncall_schedule.users.add(self.user)
    
    def test_oncall_schedule_creation(self):
        """Test OnCallSchedule creation"""
        self.assertEqual(self.oncall_schedule.name, 'Production On-Call')
        self.assertEqual(self.oncall_schedule.schedule_type, 'rotation')
        self.assertEqual(self.oncall_schedule.timezone, 'UTC')
        self.assertEqual(self.oncall_schedule.rotation_period_days, 7)
        self.assertTrue(self.oncall_schedule.is_active)
    
    def test_oncall_schedule_str_representation(self):
        """Test OnCallSchedule string representation"""
        expected = f'OnCallSchedule: {self.oncall_schedule.name} - rotation'
        self.assertEqual(str(self.oncall_schedule), expected)
    
    def test_oncall_schedule_get_type_display(self):
        """Test OnCallSchedule type display"""
        self.assertEqual(self.oncall_schedule.get_type_display(), 'Rotation')
        
        self.oncall_schedule.schedule_type = 'fixed'
        self.assertEqual(self.oncall_schedule.get_type_display(), 'Fixed')
        
        self.oncall_schedule.schedule_type = 'weekly'
        self.assertEqual(self.oncall_schedule.get_type_display(), 'Weekly')
        
        self.oncall_schedule.schedule_type = 'custom'
        self.assertEqual(self.oncall_schedule.get_type_display(), 'Custom')
    
    def test_oncall_schedule_get_current_on_call(self):
        """Test OnCallSchedule get current on-call person"""
        # This would return the current on-call person based on the schedule
        current_on_call = self.oncall_schedule.get_current_on_call()
        
        # For testing, we'll verify it returns a user or None
        self.assertTrue(current_on_call is None or isinstance(current_on_call, User))
    
    def test_oncall_schedule_get_next_rotation(self):
        """Test OnCallSchedule next rotation time"""
        next_rotation = self.oncall_schedule.get_next_rotation()
        
        # Should return a datetime or None
        self.assertTrue(next_rotation is None or isinstance(next_rotation, timezone.datetime))
    
    def test_oncall_schedule_rotate(self):
        """Test OnCallSchedule rotation method"""
        initial_users = list(self.oncall_schedule.users.all())
        
        self.oncall_schedule.rotate()
        
        # This would rotate the on-call assignment
        # For testing, we'll verify the method exists and can be called
        self.assertIsNotNone(self.oncall_schedule.rotation_start_date)
    
    def test_oncall_schedule_add_user(self):
        """Test OnCallSchedule add user method"""
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='testpass123'
        )
        
        initial_count = self.oncall_schedule.users.count()
        
        self.oncall_schedule.add_user(another_user)
        
        self.assertEqual(self.oncall_schedule.users.count(), initial_count + 1)
        self.assertIn(another_user, self.oncall_schedule.users.all())
    
    def test_oncall_schedule_remove_user(self):
        """Test OnCallSchedule remove user method"""
        initial_count = self.oncall_schedule.users.count()
        
        self.oncall_schedule.remove_user(self.user)
        
        self.assertEqual(self.oncall_schedule.users.count(), initial_count - 1)
        self.assertNotIn(self.user, self.oncall_schedule.users.all())
    
    def test_oncall_schedule_is_user_on_call(self):
        """Test OnCallSchedule is user on-call check"""
        # This would check if the specified user is currently on-call
        is_on_call = self.oncall_schedule.is_user_on_call(self.user)
        
        self.assertIsInstance(is_on_call, bool)
    
    def test_oncall_schedule_get_users_count(self):
        """Test OnCallSchedule users count"""
        count = self.oncall_schedule.get_users_count()
        self.assertEqual(count, 1)
        
        # Add another user
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='testpass123'
        )
        self.oncall_schedule.users.add(another_user)
        
        count = self.oncall_schedule.get_users_count()
        self.assertEqual(count, 2)
