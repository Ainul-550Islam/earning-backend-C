"""
Tests for Incident ViewSets
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)
from alerts.viewsets.incident import (
    IncidentViewSet, IncidentTimelineViewSet, IncidentResponderViewSet,
    IncidentPostMortemViewSet, OnCallScheduleViewSet
)

User = get_user_model()


class IncidentViewSetTest(APITestCase):
    """Test cases for IncidentViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
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
    
    def test_list_incidents(self):
        """Test listing incidents"""
        url = '/api/alerts/incidents/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Database Connection Failure')
    
    def test_create_incident(self):
        """Test creating incident"""
        url = '/api/alerts/incidents/'
        data = {
            'title': 'API Response Time Degradation',
            'description': 'API response times are significantly slower',
            'severity': 'medium',
            'impact': 'minor',
            'urgency': 'medium',
            'status': 'open',
            'assigned_to': self.user.id,
            'affected_services': ['api', 'web'],
            'affected_users_count': 500
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Incident.objects.count(), 2)
    
    def test_retrieve_incident(self):
        """Test retrieving single incident"""
        url = f'/api/alerts/incidents/{self.incident.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Database Connection Failure')
    
    def test_update_incident(self):
        """Test updating incident"""
        url = f'/api/alerts/incidents/{self.incident.id}/'
        data = {
            'title': 'Updated Incident Title',
            'severity': 'critical'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.title, 'Updated Incident Title')
        self.assertEqual(self.incident.severity, 'critical')
    
    def test_delete_incident(self):
        """Test deleting incident"""
        url = f'/api/alerts/incidents/{self.incident.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Incident.objects.count(), 0)
    
    def test_acknowledge_incident(self):
        """Test acknowledging incident"""
        url = f'/api/alerts/incidents/{self.incident.id}/acknowledge/'
        data = {
            'acknowledgment_note': 'Investigating the database issue'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'investigating')
        self.assertEqual(self.incident.acknowledged_by, self.user)
    
    def test_identify_incident(self):
        """Test identifying incident"""
        url = f'/api/alerts/incidents/{self.incident.id}/identify/'
        data = {
            'root_cause': 'Database connection pool exhausted',
            'contributing_factors': 'High load, insufficient monitoring'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'identified')
        self.assertEqual(self.incident.root_cause, 'Database connection pool exhausted')
    
    def test_resolve_incident(self):
        """Test resolving incident"""
        url = f'/api/alerts/incidents/{self.incident.id}/resolve/'
        data = {
            'resolution_summary': 'Fixed database connection pool',
            'resolution_actions': 'Increased pool size and restarted connections'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'resolved')
        self.assertEqual(self.incident.resolved_by, self.user)
    
    def test_close_incident(self):
        """Test closing incident"""
        self.incident.status = 'resolved'
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        
        url = f'/api/alerts/incidents/{self.incident.id}/close/'
        data = {
            'closure_note': 'Issue resolved and verified'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'closed')
        self.assertEqual(self.incident.closed_by, self.user)
    
    def test_escalate_incident(self):
        """Test escalating incident"""
        url = f'/api/alerts/incidents/{self.incident.id}/escalate/'
        data = {
            'escalation_reason': 'No response from primary team'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.escalation_level, 1)
        self.assertEqual(self.incident.escalation_reason, 'No response from primary team')
    
    def test_get_incidents_by_severity(self):
        """Test getting incidents by severity"""
        url = '/api/alerts/incidents/by_severity/high/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_incidents_by_status(self):
        """Test getting incidents by status"""
        url = '/api/alerts/incidents/by_status/open/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_incidents(self):
        """Test getting active incidents"""
        url = '/api/alerts/incidents/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_overdue_incidents(self):
        """Test getting overdue incidents"""
        url = '/api/alerts/incidents/overdue/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overdue_incidents', response.data)


class IncidentTimelineViewSetTest(APITestCase):
    """Test cases for IncidentTimelineViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
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
    
    def test_list_incident_timelines(self):
        """Test listing incident timelines"""
        url = '/api/alerts/incidents/timelines/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['event_type'], 'status_change')
    
    def test_create_incident_timeline(self):
        """Test creating incident timeline"""
        url = '/api/alerts/incidents/timelines/'
        data = {
            'incident': self.incident.id,
            'event_type': 'action',
            'title': 'Investigation Started',
            'description': 'Started investigating the incident',
            'participants': [self.user.id]
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IncidentTimeline.objects.count(), 2)
    
    def test_retrieve_incident_timeline(self):
        """Test retrieving single incident timeline"""
        url = f'/api/alerts/incidents/timelines/{self.incident_timeline.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['event_type'], 'status_change')
    
    def test_get_timeline_by_incident(self):
        """Test getting timeline by incident"""
        url = f'/api/alerts/incidents/timelines/by_incident/{self.incident.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_timeline_by_type(self):
        """Test getting timeline by type"""
        url = '/api/alerts/incidents/timelines/by_type/status_change/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_add_timeline_participant(self):
        """Test adding timeline participant"""
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='testpass123'
        )
        
        url = f'/api/alerts/incidents/timelines/{self.incident_timeline.id}/add_participant/'
        data = {
            'user_id': another_user.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_timeline.refresh_from_db()
        self.assertIn(another_user.id, self.incident_timeline.participants)


class IncidentResponderViewSetTest(APITestCase):
    """Test cases for IncidentResponderViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
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
    
    def test_list_incident_responders(self):
        """Test listing incident responders"""
        url = '/api/alerts/incidents/responders/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['role'], 'responder')
    
    def test_create_incident_responder(self):
        """Test creating incident responder"""
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='testpass123'
        )
        
        url = '/api/alerts/incidents/responders/'
        data = {
            'incident': self.incident.id,
            'user': another_user.id,
            'role': 'lead',
            'status': 'assigned',
            'responsibilities': ['Coordination', 'Escalation']
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IncidentResponder.objects.count(), 2)
    
    def test_retrieve_incident_responder(self):
        """Test retrieving single incident responder"""
        url = f'/api/alerts/incidents/responders/{self.incident_responder.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], 'responder')
    
    def test_activate_responder(self):
        """Test activating responder"""
        self.incident_responder.status = 'away'
        self.incident_responder.save()
        
        url = f'/api/alerts/incidents/responders/{self.incident_responder.id}/activate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_responder.refresh_from_db()
        self.assertEqual(self.incident_responder.status, 'active')
    
    def test_deactivate_responder(self):
        """Test deactivating responder"""
        url = f'/api/alerts/incidents/responders/{self.incident_responder.id}/deactivate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_responder.refresh_from_db()
        self.assertEqual(self.incident_responder.status, 'away')
    
    def test_complete_responder(self):
        """Test completing responder"""
        url = f'/api/alerts/incidents/responders/{self.incident_responder.id}/complete/'
        data = {
            'completion_note': 'Tasks completed successfully'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_responder.refresh_from_db()
        self.assertEqual(self.incident_responder.status, 'completed')
    
    def test_get_responders_by_incident(self):
        """Test getting responders by incident"""
        url = f'/api/alerts/incidents/responders/by_incident/{self.incident.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_responders_by_role(self):
        """Test getting responders by role"""
        url = '/api/alerts/incidents/responders/by_role/responder/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class IncidentPostMortemViewSetTest(APITestCase):
    """Test cases for IncidentPostMortemViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
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
    
    def test_list_incident_postmortems(self):
        """Test listing incident post-mortems"""
        url = '/api/alerts/incidents/postmortems/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'draft')
    
    def test_create_incident_postmortem(self):
        """Test creating incident post-mortem"""
        url = '/api/alerts/incidents/postmortems/'
        data = {
            'incident': self.incident.id,
            'title': 'Post-Mortem: API Response Time Issue',
            'description': 'Analysis of API response time degradation',
            'status': 'draft',
            'internal_only': False
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IncidentPostMortem.objects.count(), 2)
    
    def test_retrieve_incident_postmortem(self):
        """Test retrieving single incident post-mortem"""
        url = f'/api/alerts/incidents/postmortems/{self.incident_postmortem.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Post-Mortem: Database Connection Failure')
    
    def test_submit_for_review(self):
        """Test submitting post-mortem for review"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        url = f'/api/alerts/incidents/postmortems/{self.incident_postmortem.id}/submit_for_review/'
        data = {
            'reviewer_id': reviewer.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'submitted_for_review')
    
    def test_approve_postmortem(self):
        """Test approving post-mortem"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        url = f'/api/alerts/incidents/postmortems/{self.incident_postmortem.id}/approve/'
        data = {
            'reviewer_id': reviewer.id,
            'approval_note': 'Approved with minor changes'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'approved')
        self.assertEqual(self.incident_postmortem.approved_by, reviewer)
    
    def test_reject_postmortem(self):
        """Test rejecting post-mortem"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        url = f'/api/alerts/incidents/postmortems/{self.incident_postmortem.id}/reject/'
        data = {
            'reviewer_id': reviewer.id,
            'rejection_note': 'Needs more detail on root cause'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'rejected')
        self.assertEqual(self.incident_postmortem.approved_by, reviewer)
    
    def test_publish_postmortem(self):
        """Test publishing post-mortem"""
        self.incident_postmortem.status = 'approved'
        self.incident_postmortem.save()
        
        url = f'/api/alerts/incidents/postmortems/{self.incident_postmortem.id}/publish/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.incident_postmortem.refresh_from_db()
        self.assertEqual(self.incident_postmortem.status, 'published')
    
    def test_get_postmortems_by_status(self):
        """Test getting post-mortems by status"""
        url = '/api/alerts/incidents/postmortems/by_status/draft/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_postmortems_by_incident(self):
        """Test getting post-mortems by incident"""
        url = f'/api/alerts/incidents/postmortems/by_incident/{self.incident.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class OnCallScheduleViewSetTest(APITestCase):
    """Test cases for OnCallScheduleViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
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
    
    def test_list_oncall_schedules(self):
        """Test listing on-call schedules"""
        url = '/api/alerts/incidents/oncall_schedules/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['schedule_type'], 'rotation')
    
    def test_create_oncall_schedule(self):
        """Test creating on-call schedule"""
        url = '/api/alerts/incidents/oncall_schedules/'
        data = {
            'name': 'Development On-Call',
            'description': 'On-call schedule for development environment',
            'schedule_type': 'fixed',
            'timezone': 'UTC',
            'is_active': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OnCallSchedule.objects.count(), 2)
    
    def test_retrieve_oncall_schedule(self):
        """Test retrieving single on-call schedule"""
        url = f'/api/alerts/incidents/oncall_schedules/{self.oncall_schedule.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Production On-Call')
    
    def test_rotate_oncall_schedule(self):
        """Test rotating on-call schedule"""
        url = f'/api/alerts/incidents/oncall_schedules/{self.oncall_schedule.id}/rotate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rotation_result', response.data)
    
    def test_get_current_oncall(self):
        """Test getting current on-call person"""
        url = f'/api/alerts/incidents/oncall_schedules/{self.oncall_schedule.id}/current_oncall/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('current_oncall', response.data)
    
    def test_get_next_rotation(self):
        """Test getting next rotation time"""
        url = f'/api/alerts/incidents/oncall_schedules/{self.oncall_schedule.id}/next_rotation/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('next_rotation', response.data)
    
    def test_add_user_to_schedule(self):
        """Test adding user to schedule"""
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='testpass123'
        )
        
        url = f'/api/alerts/incidents/oncall_schedules/{self.oncall_schedule.id}/add_user/'
        data = {
            'user_id': another_user.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertIn(another_user, self.oncall_schedule.users.all())
    
    def test_remove_user_from_schedule(self):
        """Test removing user from schedule"""
        url = f'/api/alerts/incidents/oncall_schedules/{self.oncall_schedule.id}/remove_user/'
        data = {
            'user_id': self.user.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertNotIn(self.user, self.oncall_schedule.users.all())
    
    def test_is_user_oncall(self):
        """Test checking if user is on-call"""
        url = f'/api/alerts/incidents/oncall_schedules/{self.oncall_schedule.id}/is_oncall/{self.user.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_oncall', response.data)
    
    def test_get_schedules_by_type(self):
        """Test getting schedules by type"""
        url = '/api/alerts/incidents/oncall_schedules/by_type/rotation/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_schedules(self):
        """Test getting active schedules"""
        url = '/api/alerts/incidents/oncall_schedules/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
